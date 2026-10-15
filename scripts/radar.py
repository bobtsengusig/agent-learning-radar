"""Dependency-free official-source collector, validator and weekly digest builder."""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
TAIPEI = timezone(timedelta(hours=8))
MAX_BODY = 12 * 1024 * 1024


def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else copy.deepcopy(default)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def stamp(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value):
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%d %B %Y", "%Y/%m/%d"):
                try:
                    result = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
    return result.replace(tzinfo=result.tzinfo or UTC).astimezone(UTC)


def safe_url(value):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid source URL")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS URLs are allowed")
    return value


class Node:
    def __init__(self, tag="root", attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def text(self):
        if self.tag in {"script", "style", "nav", "header", "footer"}:
            return ""
        return " ".join(x.text() if isinstance(x, Node) else x for x in self.children)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def plain(value):
    text = Document(value or "").root.text()
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def excerpt(value):
    # Brief original-language excerpt; preserve a link to the full official source.
    text = plain(value)
    words = text.split()
    if len(words) > 24:
        text = " ".join(words[:24]) + "…"
    return text[:180] + ("…" if len(text) > 180 else "")


def classify(title, body, default="announcement"):
    text = (title + " " + body[:300]).lower()
    if re.search(r"deprecat|sunset|end.of.life|removal|retir", text):
        return "deprecation"
    if re.search(r"\brelease[ds]?\b|introduc|launch|\bnew\b|\badded\b", text):
        return "feature" if default == "announcement" else default
    return "update" if default == "announcement" else default


def make_item(source, identity, title, url, published, body="", version=None, release_type=None):
    title = plain(title)[:300]
    if not title:
        raise ValueError("Empty release title")
    url = safe_url(url)
    published = stamp(parse_date(published)) if parse_date(published) else None
    release_type = release_type or classify(title, body)
    normalized = {"title": title, "url": url, "published_at": published,
                  "source_body_hash": hashlib.sha256(plain(body).encode()).hexdigest(),
                  "excerpt": excerpt(body), "version": version, "release_type": release_type}
    return {"id": source["id"] + ":" + str(identity), "source_id": source["id"],
            "product": source["product"], "category": source["category"], **normalized,
            "content_hash": hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        safe_url(new_url)
        next_request = super().redirect_request(request, response, code, message, headers, new_url)
        if next_request and urllib.parse.urlsplit(new_url).hostname != urllib.parse.urlsplit(request.full_url).hostname:
            next_request.remove_header("Authorization")
        return next_request


def http_get(url, token=None, attempts=3, opener=None, sleep=time.sleep):
    safe_url(url)
    opener = opener or urllib.request.build_opener(SafeRedirect()).open
    headers = {"User-Agent": "agent-learning-radar/1.0 (+https://github.com/bobtsengusig/agent-learning-radar)",
               "Accept": "application/json, application/atom+xml, application/rss+xml, text/html;q=0.9"}
    # Never forward the Actions token to vendors or feed hosts.
    if token and urllib.parse.urlsplit(url).hostname == "api.github.com":
        headers["Authorization"] = "Bearer " + token
    for attempt in range(attempts):
        try:
            with opener(urllib.request.Request(url, headers=headers), timeout=25) as response:
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    raise ValueError("Source response exceeds 12 MiB")
                return body.decode("utf-8", errors="replace"), dict(response.headers)
        except urllib.error.HTTPError as error:
            if error.code not in {403, 429, 500, 502, 503, 504} or attempt == attempts - 1:
                raise
            retry = error.headers.get("Retry-After", "")
            try:
                delay = float(retry)
            except ValueError:
                date = parse_date(retry)
                delay = max(0, (date - datetime.now(UTC)).total_seconds()) if date else 2 ** attempt
            if delay > 30:
                raise RuntimeError("Source rate limited; retry deferred to next run") from error
            sleep(max(delay, 2 ** attempt))
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise
            sleep(2 ** attempt)
    raise RuntimeError("Source fetch failed")


def parse_releases(source, body):
    records = json.loads(body)
    if not isinstance(records, list):
        raise ValueError("GitHub Releases response is not a list")
    return [make_item(source, r["id"], r.get("name") or r["tag_name"], r["html_url"],
                      r.get("published_at"), r.get("body", ""), r.get("tag_name"),
                      "prerelease" if r.get("prerelease") else "release") for r in records if not r.get("draft")]


def parse_feed(source, body):
    if "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
        raise ValueError("Feed entity declarations are not allowed")
    root = ET.fromstring(body)
    atom = {"a": "http://www.w3.org/2005/Atom"}
    records = []
    for entry in root.findall(".//item") + root.findall("a:entry", atom):
        def value(name):
            found = entry.find(name)
            if found is None:
                found = entry.find("a:" + name, atom)
            return "" if found is None else "".join(found.itertext())
        link = value("link")
        if not link:
            links = entry.findall("a:link", atom)
            link = next((x.get("href") for x in links if x.get("rel", "alternate") == "alternate"), "")
        link = urllib.parse.urljoin(source["url"], link)
        identity = value("guid") or value("id") or link
        records.append(make_item(source, identity, value("title"), link,
                                 value("pubDate") or value("published") or value("updated"),
                                 value("description") or value("summary") or value("content")))
    if not records:
        raise ValueError("No feed entries found; source format may have changed")
    return records


def dated_heading(text):
    text = re.sub(r"[\u200b#]", "", text).strip()
    text = re.sub(r"^(?:Updated\s+)?", "", text, flags=re.I)
    match = re.search(r"\b(?:[A-Z][a-z]+ \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})\b", text)
    return parse_date(match.group()) if match else None


def parse_markdown_changelog(source, body):
    records, chunks, date, year = [], [], None, None
    def flush():
        if date and chunks:
            text = plain(" ".join(chunks))
            records.append(make_item(source, date.strftime("%Y-%m-%d"), text[:130], source["url"], stamp(date), text))
    for line in body.splitlines():
        text = re.sub(r"^#+\s*", "", line).strip()
        month = re.fullmatch(r"[A-Z][a-z]+,? (20\d{2})", text)
        if month:
            flush()
            year, date, chunks = int(month.group(1)), None, []
            continue
        new_date = dated_heading(text)
        if not new_date and year and re.fullmatch(r"[A-Z][a-z]{2,8} \d{1,2}", text):
            new_date = parse_date(f"{text}, {year}")
        if new_date:
            flush()
            date, chunks = new_date, []
        elif date and text and text != "---":
            chunks.append(text)
    flush()
    if not records:
        raise ValueError("No dated Markdown entries found; source format requires review")
    merged = {}
    for record in records:
        if record["id"] not in merged:
            merged[record["id"]] = record
    return list(merged.values())


def parse_changelog(source, body):
    if source.get("parser") == "openai" and body.lstrip().startswith("#"):
        return parse_markdown_changelog(source, body)
    doc = Document(body)
    containers = [n for n in doc.root.walk() if n.tag in {"main", "article"}]
    container = max(containers, key=lambda n: len(n.text()), default=doc.root)
    nodes = list(container.walk())
    records, current, chunks, heading_id = [], None, [], None
    year = None

    def flush():
        if current and chunks:
            text = plain(" ".join(chunks))
            # A single day may contain several announcements; keep one dated digest.
            identity = current.strftime("%Y-%m-%d")
            url = source["url"] + ("#" + heading_id if heading_id else "")
            records.append(make_item(source, identity, text[:130], url, stamp(current), text))

    for node in nodes:
        if re.fullmatch(r"h[1-6]", node.tag):
            text = re.sub(r"\s+", " ", node.text()).strip()
            if source.get("parser") == "openai":
                year_match = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December),? (20\d{2})", text)
                if year_match:
                    flush()
                    current, chunks = None, []
                    year = int(year_match.group(1))
                short = re.fullmatch(r"([A-Z][a-z]{2,8}) (\d{1,2})", text)
                date = parse_date(f"{text}, {year}") if short and year else None
            else:
                date = dated_heading(text)
            if date:
                flush()
                current, chunks, heading_id = date, [], node.attrs.get("id")
            elif current and text:
                chunks.append(text)
        elif current and node.tag in {"p", "li"}:
            # Descendant paragraphs inside list items are handled only at the paragraph level.
            if node.tag == "li" and any(c.tag in {"p", "li"} for c in node.walk() if c is not node):
                continue
            text = re.sub(r"\s+", " ", node.text()).strip()
            if text:
                chunks.append(text)
    flush()
    if not records:
        raise ValueError("No dated changelog entries found; parser requires review")
    # Multiple headings can share a date; merge without unstable positional identifiers.
    merged = {}
    for record in records:
        if record["id"] not in merged:
            merged[record["id"]] = record
    return list(merged.values())


def fetch_source(source, now, fetch=http_get, token=None):
    cutoff = now - timedelta(days=90)
    if source["kind"] == "github":
        items, pages, exhausted = [], 0, False
        for page in range(1, 7):
            body, headers = fetch(f'https://api.github.com/repos/{source["repo"]}/releases?per_page=100&page={page}', token=token)
            part = parse_releases(source, body)
            items.extend(part)
            pages += 1
            dates = [parse_date(x["published_at"]) for x in part if x["published_at"]]
            if len(json.loads(body)) < 100 or (dates and min(dates) < cutoff):
                exhausted = True
                break
        coverage = f"GitHub Releases，最近 90 日；讀取 {pages} 頁" + ("（達頁數上限，可能不完整）" if not exhausted else "")
    else:
        body, _ = fetch(source.get("fetch_url", source["url"]), token=token)
        items = parse_feed(source, body) if source["kind"] == "atom" else parse_changelog(source, body)
        coverage = "官方來源目前可回溯範圍，最近 90 日內；不保證完整歷史"
    items = [x for x in items if not x["published_at"] or cutoff <= parse_date(x["published_at"]) <= now]
    return items, coverage


def merge_items(old, incoming, now):
    merged = {x["id"]: copy.deepcopy(x) for x in old}
    for fresh in incoming:
        prior = merged.get(fresh["id"])
        if prior:
            if prior["content_hash"] == fresh["content_hash"]:
                continue
            item = {**fresh, "first_seen_at": prior["first_seen_at"], "updated_at": stamp(now),
                    "revision_count": prior.get("revision_count", 0) + 1}
        else:
            item = {**fresh, "first_seen_at": stamp(now), "updated_at": stamp(now), "revision_count": 0}
        merged[item["id"]] = item
    return sorted(merged.values(), key=lambda x: (x["published_at"] or x["first_seen_at"], x["id"]), reverse=True)


def weekly_digest(items, now):
    local = now.astimezone(TAIPEI)
    end = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=7)
    iso = start.isocalendar()
    chosen = [x for x in items if start <= (parse_date(x["published_at"]) or parse_date(x["first_seen_at"])) < end]
    return {"id": f"{iso.year}-W{iso.week:02d}", "start": start.date().isoformat(), "end_exclusive": end.date().isoformat(),
            "generated_at": stamp(now), "item_ids": [x["id"] for x in chosen],
            "undated_ids": [x["id"] for x in chosen if not x["published_at"]]}


def refresh_digests(items, existing, now):
    """Backfill complete weeks and incorporate late arrivals without changing unchanged dates."""
    previous = {x["id"]: x for x in existing}
    last = weekly_digest(items, now)
    moments = [(parse_date(x["published_at"]) or parse_date(x["first_seen_at"])) for x in items]
    if not moments:
        return [previous.get(last["id"], last)]
    first = min(moments).astimezone(TAIPEI)
    start = (first - timedelta(days=first.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = datetime.fromisoformat(last["end_exclusive"]).replace(tzinfo=TAIPEI)
    while start < end:
        digest = weekly_digest(items, start + timedelta(days=7, hours=8))
        digest["generated_at"] = stamp(now)
        old = previous.get(digest["id"])
        if old and old["item_ids"] == digest["item_ids"] and old.get("undated_ids", []) == digest["undated_ids"]:
            digest["generated_at"] = old["generated_at"]
        previous[digest["id"]] = digest
        start += timedelta(days=7)
    return sorted(previous.values(), key=lambda x: x["start"], reverse=True)


def validate(sources, state, settings=None):
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("Unsupported data schema")
    ids = [x["id"] for x in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs")
    for source in sources:
        safe_url(source.get("url") or "https://github.com/" + source["repo"])
        if source["kind"] not in {"github", "atom", "changelog"}:
            raise ValueError("Unsupported source kind")
    seen = set()
    for item in state["items"]:
        if item["id"] in seen or item["source_id"] not in ids or not item["id"].startswith(item["source_id"] + ":"):
            raise ValueError("Duplicate item or unknown source")
        seen.add(item["id"])
        safe_url(item["url"])
        if not item["title"].strip() or len(item["title"]) > 300:
            raise ValueError("Invalid item title")
        for key in ("first_seen_at", "updated_at"):
            if not parse_date(item[key]):
                raise ValueError("Invalid item timestamp")
        if item["published_at"] and not parse_date(item["published_at"]):
            raise ValueError("Invalid publication date")
        if not re.fullmatch(r"[a-f0-9]{64}", item["content_hash"]):
            raise ValueError("Invalid content hash")
        if settings and (item["category"] not in settings["categories"] or item["release_type"] not in settings["release_types"]):
            raise ValueError("Unknown category or release type")
    for digest in state.get("digests", []):
        if any(x not in seen for x in digest["item_ids"]):
            raise ValueError("Digest refers to missing item")
    return True


def collect(sources, state, now, fetcher=fetch_source):
    state = copy.deepcopy(state)
    results, incoming = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(fetcher, source, now): source for source in sources}
        for task in concurrent.futures.as_completed(tasks):
            source = tasks[task]
            prior = state.get("sources", {}).get(source["id"], {})
            try:
                items, coverage = task.result()
                incoming.extend(items)
                results[source["id"]] = {"status": "ok", "last_attempt_at": stamp(now), "last_success_at": stamp(now),
                                          "error": None, "items_in_window": len(items), "coverage": coverage}
            except Exception as error:
                results[source["id"]] = {**prior, "status": "error", "last_attempt_at": stamp(now),
                                          "last_success_at": prior.get("last_success_at"),
                                          "error": f"{type(error).__name__}: {str(error)[:160]}"}
    state["sources"] = {s["id"]: results[s["id"]] for s in sources}
    state["last_attempt_at"] = stamp(now)
    succeeded = sum(s["status"] == "ok" for s in results.values())
    if succeeded:
        state["last_success_at"] = stamp(now)
    state["items"] = merge_items(state.get("items", []), incoming, now)
    return state, succeeded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["collect", "validate"])
    parser.add_argument("--now", help="ISO timestamp; useful for reproducible runs")
    parser.add_argument("--weekly", action="store_true", help="Generate previous complete week's digest")
    args = parser.parse_args()
    now = parse_date(args.now) if args.now else datetime.now(UTC)
    if now is None:
        parser.error("Invalid --now timestamp")
    sources = read_json(ROOT / "sources.json")
    state_path = ROOT / "data/radar.json"
    state = read_json(state_path, {"schema_version": 1, "items": [], "sources": {}, "digests": [], "last_success_at": None})
    settings = read_json(ROOT / "content/settings.json")
    if args.command == "validate":
        validate(sources, state, settings)
        print(f"Validated {len(state['items'])} items and {len(sources)} sources")
        return
    token = os.environ.get("GITHUB_TOKEN")
    next_state, succeeded = collect(sources, state, now, lambda s, n: fetch_source(s, n, token=token))
    # Always retain diagnostics, even when no new site should be deployed.
    write_json(ROOT / ".cache/collection-status.json", {"at": stamp(now), "succeeded": succeeded, "sources": next_state["sources"]})
    if not succeeded:
        raise SystemExit("All sources failed. Retaining the last usable data and deployment; see collection-status artifact.")
    # A missing Monday is caught up on the next successful run; late publications are incorporated.
    next_state["digests"] = refresh_digests(next_state["items"], next_state.get("digests", []), now)
    validate(sources, next_state, settings)
    write_json(state_path, next_state)
    print(f"Collected {succeeded}/{len(sources)} sources; {len(next_state['items'])} retained items")
    for sid, status in next_state["sources"].items():
        if status["status"] == "error":
            print(f"WARNING {sid}: {status['error']}")


if __name__ == "__main__":
    main()
