"""Render a portable, pre-rendered static website. No package installation required."""
from __future__ import annotations
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from email.utils import format_datetime

from radar import ROOT, TAIPEI, UTC, parse_date, read_json, safe_url, validate


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, title):
    return f'<a href="{esc(safe_url(url))}" target="_blank" rel="noopener noreferrer">{esc(title)} ↗</a>'


def items_list(items):
    return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


def week_card(week):
    num = week["week"]
    blocks = "".join(f'<div class="lesson-block"><h4>{title}</h4>{items_list(week[key])}</div>' for title, key in
                     [("必要概念", "concepts"), ("實作步驟", "steps"), ("完成條件", "acceptance"), ("常見失敗", "pitfalls")])
    refs = "".join(link(url, title) for title, url in week["refs"])
    return f'''<article class="week-card" id="week-{num}" data-week="{num}">
      <div class="week-top"><span class="eyebrow">WEEK {num:02d} <span>／{esc(week['phase'])}</span></span>
      <label class="complete-label"><input type="checkbox" data-complete="{num}"><span>已完成</span></label></div>
      <h3>{esc(week['title'])}</h3><p class="muted">{esc(week['subtitle'])}</p>
      <p class="week-goal">{esc(week['goal'])}</p>
      <div class="deliverable"><span>本週成果</span>{esc(week['deliverable'])}</div>
      <details><summary>展開學習與實作指南 <span aria-hidden="true">＋</span></summary><div class="lesson-grid">{blocks}</div>
      <div class="reference-links"><h4>官方教材</h4>{refs}</div></details></article>'''


def framework_card(f):
    fields = "".join(f'<div><dt>{label}</dt><dd>{esc(f[key])}</dd></div>' for label, key in
                     [("適用場景", "fit"), ("控制程度", "control"), ("狀態管理", "state"), ("模型支援", "models"), ("學習門檻", "learning")])
    return f'''<article class="framework-card"><div class="card-meta"><span>{esc(f['level'])}</span><span class="pill">{esc(f['priority'])}</span></div>
      <h3>{esc(f['name'])}</h3><dl>{fields}</dl><div class="card-foot">{link(f['url'], '官方文件')}<small>查核 {esc(f['checked'])}</small></div></article>'''


def radar_card(item, settings):
    date = (item["published_at"] or "")[:10] or "日期未提供"
    category = settings["categories"][item["category"]]
    return f'''<article class="news-card"><div class="card-meta"><span>{esc(category)} · {esc(item['product'])}</span><time>{esc(date)}</time></div>
      <h3>{link(item['url'],item['title'])}</h3><p>{esc(item['excerpt'])}</p></article>'''


def write_rss(state, settings, output):
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    for key, value in [("title", "Agent Learning Radar · 每週彙整"), ("link", settings["site_url"]),
                       ("description", "官方 LLM 與 Agent 技術更新；原文短摘錄、規則分類，無 AI 摘要。"), ("language", "zh-TW")]:
        ET.SubElement(channel, key).text = value
    lookup = {x["id"]: x for x in state["items"]}
    for digest in state.get("digests", []):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"{digest['id']} · {len(digest['item_ids'])} 則官方更新"
        ET.SubElement(item, "link").text = settings["site_url"] + "#weekly"
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = settings["site_url"] + "digest/" + digest["id"]
        ET.SubElement(item, "pubDate").text = format_datetime(parse_date(digest["generated_at"]))
        blocks = [f"<p>{esc(digest['start'])} 至 {esc(digest['end_exclusive'])} 前（台北時間）。依來源發布日期分類；無日期項目依首次發現時間。</p>"]
        for category, label in settings["categories"].items():
            chosen = [lookup[i] for i in digest["item_ids"] if lookup[i]["category"] == category]
            if chosen:
                blocks.append(f"<h3>{esc(label)}</h3><ul>" + "".join(f'<li>{link(x["url"],x["product"]+" · "+x["title"])}</li>' for x in chosen) + "</ul>")
        ET.SubElement(item, "description").text = "".join(blocks) if digest["item_ids"] else "本週沒有收集到新消息；請查看來源健康狀態。"
    ET.indent(root)
    ET.ElementTree(root).write(output / "feed.xml", encoding="utf-8", xml_declaration=True)


def build(output=None):
    output = Path(output) if output else ROOT / "dist"
    output.mkdir(parents=True, exist_ok=True)
    settings = read_json(ROOT / "content/settings.json")
    courses = read_json(ROOT / "content/roadmap.json")
    frameworks = read_json(ROOT / "content/frameworks.json")
    sources = read_json(ROOT / "sources.json")
    state = read_json(ROOT / "data/radar.json", {"schema_version":1,"items":[],"sources":{},"digests":[],"last_success_at":None})
    validate(sources, state, settings)
    if [c["week"] for c in courses] != list(range(1, 13)):
        raise ValueError("Roadmap must contain weeks 1 through 12")
    payload = {"settings": settings, "sources": sources, "radar": state}
    # JSON lives in an inert data block; escape '<' to prevent premature </script> termination.
    json_data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")
    template = (ROOT / "site/index.html").read_text(encoding="utf-8")
    values = {"COURSES": "".join(week_card(w) for w in courses), "FRAMEWORKS": "".join(framework_card(f) for f in frameworks),
              "NEWS": "".join(radar_card(x, settings) for x in state["items"][:12]), "PAYLOAD": json_data,
              "BUILD_DATE": datetime.now(TAIPEI).strftime("%Y-%m-%d"), "CANONICAL": esc(settings["site_url"])}
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    (output / "index.html").write_text(template, encoding="utf-8")
    for name in ("app.js", "style.css", "favicon.svg"):
        shutil.copyfile(ROOT / "site" / name, output / name)
    (output / ".nojekyll").touch()
    (output / "data").mkdir(exist_ok=True)
    for source, name in [(ROOT / "data/radar.json", "radar.json"), (ROOT / "sources.json", "sources.json")]:
        if source.exists():
            shutil.copyfile(source, output / "data" / name)
    write_rss(state, settings, output)
    print(f"Built {output}: 12 lessons, {len(frameworks)} comparisons, {len(state['items'])} updates")
    return output


if __name__ == "__main__":
    build()
