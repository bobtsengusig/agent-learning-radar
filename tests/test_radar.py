import copy
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from radar import (UTC, ROOT, collect, excerpt, fetch_source, http_get, make_item, merge_items,
                   parse_changelog, parse_date, parse_feed, parse_releases, read_json, safe_url, stamp,
                   validate, weekly_digest, refresh_digests, SafeRedirect)
from build import build

NOW = datetime(2026, 10, 15, 2, tzinfo=UTC)
SOURCE = {"id":"test", "product":"Test", "category":"framework", "kind":"github", "repo":"example/project"}


def item(title="Release", identity=1, published="2026-10-10T00:00:00Z"):
    return make_item(SOURCE, identity, title, "https://example.org/release/1", published, "Official release notes", "v1", "release")


def state(items=None):
    return {"schema_version":1, "items":items or [], "sources":{}, "digests":[], "last_success_at":None}


class CollectorTests(unittest.TestCase):
    def test_identical_recollection_is_idempotent(self):
        first = merge_items([], [item()], NOW)
        self.assertEqual(first, merge_items(first, [item()], NOW + timedelta(days=1)))

    def test_revision_retains_identity_and_first_seen(self):
        first = merge_items([], [item()], NOW)
        revised = merge_items(first, [item("Corrected release")], NOW + timedelta(days=1))
        self.assertEqual(len(revised), 1)
        self.assertEqual(revised[0]["first_seen_at"], first[0]["first_seen_at"])
        self.assertEqual(revised[0]["revision_count"], 1)
        self.assertNotEqual(revised[0]["content_hash"], first[0]["content_hash"])

    def test_edit_beyond_excerpt_is_detected(self):
        body = "same " * 50
        a = make_item(SOURCE, 1, "Release", "https://example.org/1", None, body + "original ending")
        b = make_item(SOURCE, 1, "Release", "https://example.org/1", None, body + "corrected ending")
        self.assertEqual(a["excerpt"], b["excerpt"])
        self.assertNotEqual(a["content_hash"], b["content_hash"])

    def test_missing_publication_date_is_explicit(self):
        self.assertIsNone(item(published=None)["published_at"])

    def test_safe_urls_reject_executable_and_credential_urls(self):
        for url in ["javascript:alert(1)", "data:text/html,hello", "http://example.org", "https://user:pass@example.org", "https://example.org/\nhello"]:
            with self.assertRaises(ValueError): safe_url(url)

    def test_external_markup_is_text_only(self):
        record = item('<script>alert(1)</script><b>Release</b>')
        self.assertEqual(record["title"], "Release")
        self.assertNotIn("alert", excerpt("<script>alert(1)</script>safe"))

    def test_github_drafts_and_prereleases(self):
        records = [{"id":1,"tag_name":"v1","html_url":"https://example.org/1","prerelease":True},
                   {"id":2,"tag_name":"v2","html_url":"https://example.org/2","draft":True}]
        actual = parse_releases(SOURCE, json.dumps(records))
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["release_type"], "prerelease")

    def test_date_parsing(self):
        self.assertEqual(parse_date("October 15, 2026"), datetime(2026,10,15,tzinfo=UTC))
        self.assertEqual(parse_date("2026-10-15T08:00:00+08:00").hour, 0)
        self.assertIsNone(parse_date("not a date"))

    def test_feed_handles_atom_and_undated_rss(self):
        source = {**SOURCE,"kind":"atom","url":"https://example.org/feed"}
        atom = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x1</id><title>New tool</title><link href="https://example.org/x1"/><published>2026-10-10T00:00:00Z</published></entry></feed>'
        self.assertEqual(parse_feed(source, atom)[0]["id"], "test:x1")
        rss = '<rss><channel><item><guid>x2</guid><title>Update</title><link>https://example.org/x2</link></item></channel></rss>'
        self.assertIsNone(parse_feed(source, rss)[0]["published_at"])

    def test_feed_entity_declaration_is_rejected(self):
        with self.assertRaises(ValueError): parse_feed({**SOURCE,"url":"https://example.org"}, '<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>')

    def test_html_changelog_stable_date_identity(self):
        source = {**SOURCE,"kind":"changelog","parser":"dated_headings","url":"https://example.org/changelog"}
        html = '<nav><h2>October 14, 2026</h2><p>Wrong menu item</p></nav><main><h2 id="oct-15">October 15, 2026</h2><p>New model available.</p><h2>October 14, 2026</h2><p>Bug fix.</p></main>'
        actual = parse_changelog(source, html)
        self.assertEqual([x["id"] for x in actual], ["test:2026-10-15", "test:2026-10-14"])
        self.assertEqual(actual[0]["url"], "https://example.org/changelog#oct-15")

    def test_changed_html_format_fails_instead_of_empty_success(self):
        with self.assertRaises(ValueError): parse_changelog({**SOURCE,"url":"https://example.org"}, '<main><h1>Login required</h1></main>')

    def test_openai_markdown_changelog(self):
        source = {**SOURCE,"parser":"openai","url":"https://developers.openai.com/api/docs/changelog"}
        body = '# Changelog\n### October, 2026\nOct 8\nFeature\nAdded a new feature.\nOct 7\nUpdate\nUpdated the SDK.\n### September, 2026\nSep 29\nReleased a model.'
        parsed = parse_changelog(source, body)
        self.assertEqual([x["published_at"][:10] for x in parsed], ["2026-10-08","2026-10-07","2026-09-29"])

    def test_same_day_announcements_are_all_retained_for_search_and_hashing(self):
        source = {**SOURCE,"parser":"openai","url":"https://developers.openai.com/api/docs/changelog"}
        body = '# Changelog\n### October, 2026\nOct 8\nFeature\nAdded a tool.\nOct 8\nFeature\nReleased gpt-6.1-sol.'
        parsed = parse_changelog(source, body)
        self.assertEqual(len(parsed), 1)
        self.assertIn("gpt-6.1-sol", parsed[0]["keywords"])
        changed = parse_changelog(source, body.replace("gpt-6.1-sol", "gpt-6-astra"))
        self.assertNotEqual(parsed[0]["content_hash"], changed[0]["content_hash"])

    def test_redirect_strips_token_on_host_change(self):
        import urllib.request
        request = urllib.request.Request("https://api.github.com/repos/x/y", headers={"Authorization":"Bearer test-token"})
        redirected = SafeRedirect().redirect_request(request, None, 302, "Moved", {}, "https://example.org/new")
        self.assertIsNone(redirected.get_header("Authorization"))
        with self.assertRaises(ValueError): SafeRedirect().redirect_request(request, None, 302, "Moved", {}, "http://example.org/new")

    def test_future_and_old_releases_are_filtered(self):
        releases = [{"id":n,"tag_name":f"v{n}","html_url":f"https://example.org/{n}","published_at":d} for n,d in enumerate(["2026-10-10T00:00:00Z","2026-11-01T00:00:00Z","2026-01-01T00:00:00Z"])]
        def fetch(url, **kwargs): return json.dumps(releases), {}
        actual, _ = fetch_source(SOURCE, NOW, fetch=fetch)
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["published_at"], "2026-10-10T00:00:00Z")

    def test_partial_failure_preserves_data_and_previous_source_success(self):
        old = state(merge_items([], [item()], NOW))
        old["sources"]["test"] = {"last_success_at":"2026-10-14T00:00:00Z"}
        other = {**SOURCE, "id":"other"}
        def fetcher(source, now):
            if source["id"] == "test": raise TimeoutError("source timeout")
            return [], "No new releases"
        result, successes = collect([SOURCE, other], old, NOW, fetcher)
        self.assertEqual(successes, 1)
        self.assertEqual(result["items"], old["items"])
        self.assertEqual(result["sources"]["test"]["last_success_at"], "2026-10-14T00:00:00Z")
        self.assertEqual(result["sources"]["test"]["status"], "error")

    def test_total_failure_does_not_claim_success(self):
        def fail(source, now): raise RuntimeError("offline")
        result, successes = collect([SOURCE], state(), NOW, fail)
        self.assertEqual(successes, 0)
        self.assertIsNone(result["last_success_at"])

    def test_http_retry_and_host_scoped_authorization(self):
        requests, delays = [], []
        def opener(request, **kwargs):
            requests.append(request)
            if len(requests) == 1: raise urllib.error.HTTPError(request.full_url, 429, "Rate limited", {"Retry-After":"2"}, None)
            response = io.BytesIO(b"[]"); response.headers = {}; return response
        self.assertEqual(http_get("https://api.github.com/repos/x/y/releases", token="test-token", opener=opener, sleep=delays.append)[0], "[]")
        self.assertEqual(delays, [2.0])
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer test-token")
        requests.clear()
        def vendor(request, **kwargs):
            requests.append(request); response = io.BytesIO(b"ok"); response.headers = {}; return response
        http_get("https://example.org", token="test-token", opener=vendor)
        self.assertIsNone(requests[0].get_header("Authorization"))

    def test_timeout_retries_are_bounded(self):
        calls, delays = [], []
        def fail(request, **kwargs): calls.append(1); raise TimeoutError("timed out")
        with self.assertRaises(TimeoutError): http_get("https://example.org", opener=fail, sleep=delays.append)
        self.assertEqual(len(calls), 3)

    def test_long_retry_after_is_deferred(self):
        def fail(request, **kwargs): raise urllib.error.HTTPError(request.full_url, 429, "Rate limited", {"Retry-After":"3600"}, None)
        with self.assertRaises(RuntimeError): http_get("https://example.org", opener=fail, sleep=lambda x: self.fail("Should not wait an hour"))

    def test_weekly_digest_uses_taipei_boundaries(self):
        records = merge_items([], [item(identity=1,published="2026-10-04T15:59:59Z"), item(identity=2,published="2026-10-04T16:00:00Z"), item(identity=3,published="2026-10-11T15:59:59Z"), item(identity=4,published="2026-10-11T16:00:00Z")], NOW)
        digest = weekly_digest(records, NOW)
        self.assertEqual(digest["start"], "2026-10-05")
        self.assertEqual(digest["end_exclusive"], "2026-10-12")
        self.assertEqual(set(digest["item_ids"]), {"test:2","test:3"})

    def test_unknown_source_and_duplicate_items_are_rejected(self):
        records = merge_items([], [item()], NOW)
        with self.assertRaises(ValueError): validate([SOURCE], state(records + records))
        records[0]["source_id"] = "unknown"
        with self.assertRaises(ValueError): validate([SOURCE], state(records))

    def test_missing_weeks_are_backfilled_and_late_arrivals_update(self):
        records = merge_items([], [item(identity=1,published="2026-09-21T00:00:00Z"), item(identity=2,published="2026-10-10T00:00:00Z")], NOW)
        digests = refresh_digests(records, [], NOW)
        self.assertEqual([d["start"] for d in digests], ["2026-10-05","2026-09-28","2026-09-21"])
        self.assertEqual(refresh_digests(records, digests, NOW+timedelta(hours=1)), digests)
        late = merge_items(records, [item(identity=3,published="2026-09-29T00:00:00Z")], NOW+timedelta(hours=1))
        updated = refresh_digests(late, digests, NOW+timedelta(hours=1))
        self.assertIn("test:3", updated[1]["item_ids"])

    def test_full_build_rss_and_script_injection_safety(self):
        sources = [SOURCE]
        settings = {"categories":{"framework":"框架"}, "release_types":{"release":"正式版本"}, "site_url":"https://example.org/"}
        malicious = item()
        malicious["title"] = '</script><img src=x onerror="alert(1)">'
        data = state(merge_items([], [malicious], NOW))
        data["digests"] = [weekly_digest(data["items"], NOW)]
        original = read_json
        def fake_read(path, default=None):
            if str(path).endswith("sources.json"): return sources
            if str(path).endswith("settings.json"): return settings
            if str(path).endswith("radar.json"): return data
            return original(path, default)
        test_root = ROOT / ".cache/tests"
        test_root.mkdir(parents=True, exist_ok=True)
        folder = test_root / "rendered"
        with patch("build.read_json", side_effect=fake_read):
            output = build(folder)
            page = (output/"index.html").read_text(encoding="utf-8")
            self.assertIn("\\u003c/script>", page)
            self.assertNotIn('<img src=x onerror="alert(1)">', page)
            self.assertEqual(len(ET.parse(output/"feed.xml").findall("./channel/item")), 1)
            for name in ["app.js","style.css","favicon.svg",".nojekyll"]: self.assertTrue((output/name).exists())


if __name__ == "__main__": unittest.main()
