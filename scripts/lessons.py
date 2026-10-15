"""Render authored tutorials and their runnable, offline Python exercises."""
from __future__ import annotations
import html
from pathlib import Path
import shutil

from radar import ROOT, read_json, safe_url


def esc(value):
    return html.escape(str(value), quote=True)


def paragraphs(values):
    return "".join(f"<p>{esc(value)}</p>" for value in values)


def listing(values, ordered=False):
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{esc(value)}</li>" for value in values) + f"</{tag}>"


def code_block(code, identifier, label):
    return (f'<div class="code-block"><div class="code-toolbar"><span>{esc(label)}</span>'
            f'<button type="button" data-copy="{identifier}" hidden>複製程式碼</button></div>'
            f'<pre tabindex="0" aria-label="{esc(label)}"><code id="{identifier}">{esc(code)}</code></pre></div>')


def render_lessons(output, courses, settings):
    template = (ROOT / "site/lesson.html").read_text(encoding="utf-8")
    for course in courses:
        num = course["week"]
        slug = f"week-{num:02d}"
        lesson = read_json(ROOT / f"content/lessons/{slug}.json")
        if lesson["week"] != num or len(lesson["sections"]) < 3 or len(lesson["exercises"]) < 2:
            raise ValueError(f"Incomplete tutorial: {slug}")
        lab_path = ROOT / f"labs/{slug}.py"
        lab = lab_path.read_text(encoding="utf-8")
        concepts = "".join(f'<section class="concept"><span class="concept-number">{i:02d}</span>'
                           f'<h3>{esc(s["title"])}</h3>{paragraphs(s["body"])}'
                           f'{listing(s["bullets"]) if s.get("bullets") else ""}</section>'
                           for i, s in enumerate(lesson["sections"], 1))
        exercises = "".join(f'<article class="exercise"><span class="eyebrow">EXERCISE {i:02d}</span>'
                            f'<h3>{esc(e["title"])}</h3><p>{esc(e["task"])}</p>'
                            f'<details><summary>提示 ＋</summary><p>{esc(e["hint"])}</p></details>'
                            f'<details><summary>參考解法 ＋</summary><p>{esc(e["answer"])}</p></details></article>'
                            for i, e in enumerate(lesson["exercises"], 1))
        quiz = "".join(f'<details class="quiz"><summary>{esc(q["question"])} ＋</summary>'
                       f'<p>{esc(q["answer"])}</p></details>' for q in lesson["quiz"])
        integration = lesson["integration"]
        refs = list(course["refs"])
        refs.extend(integration.get("refs", []))
        seen = set()
        references = []
        for title, url in refs:
            url = safe_url(url)
            if url not in seen:
                references.append(f'<li><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(title)} ↗</a></li>')
                seen.add(url)
        directory = "".join(f'<a href="../week-{c["week"]:02d}/"'
                            f'{" aria-current=\"page\"" if c["week"] == num else ""}>'
                            f'<span>{c["week"]:02d}</span>{esc(c["title"])}</a>' for c in courses)
        navigation = []
        if num > 1:
            navigation.append(f'<a href="../week-{num-1:02d}/"><small>← 上一週</small>{esc(courses[num-2]["title"])}</a>')
        else:
            navigation.append('<a href="../../#roadmap"><small>← 學習路線</small>回到 12 週總覽</a>')
        if num < 12:
            navigation.append(f'<a href="../week-{num+1:02d}/"><small>下一週 →</small>{esc(courses[num]["title"])}</a>')
        else:
            navigation.append('<a href="../../#radar"><small>繼續追蹤 →</small>探索最新技術雷達</a>')
        values = {
            "WEEK": str(num), "WEEK_PAD": f"{num:02d}", "TITLE": esc(course["title"]),
            "SUBTITLE": esc(course["subtitle"]), "INTRO": esc(lesson["intro"]), "PHASE": esc(course["phase"]),
            "GOAL": esc(course["goal"]), "DELIVERABLE": esc(course["deliverable"]),
            "CANONICAL": esc(settings["site_url"].rstrip("/") + f"/lessons/{slug}/"),
            "PREREQUISITES": listing(lesson["prerequisites"]), "CONCEPTS": concepts,
            "WALKTHROUGH": listing(lesson["walkthrough"], True), "EXPECTED": listing(lesson["expected"]),
            "LAB_CODE": code_block(lab, "lab-code", f"{slug}.py · 離線練習"),
            "LAB_FILE": f"{slug}.py", "COMMAND": f"python {slug}.py",
            "INTEGRATION_TITLE": esc(integration["title"]), "INTEGRATION_BODY": paragraphs(integration["body"]),
            "INTEGRATION_CODE": code_block(integration["code"], "integration-code", "Python · 選做串接範例") if integration.get("code") else "",
            "EXERCISES": exercises, "QUIZ": quiz, "TRANSFER": esc(lesson["transfer"]),
            "PROJECT_STEPS": listing(course["steps"], True), "ACCEPTANCE": listing(course["acceptance"]),
            "PITFALLS": listing(course["pitfalls"]), "REFERENCES": "".join(references),
            "DIRECTORY": directory, "NAVIGATION": "".join(navigation),
        }
        page = template
        for key, value in values.items():
            page = page.replace("{{" + key + "}}", value)
        folder = Path(output) / "lessons" / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(page, encoding="utf-8")
        shutil.copyfile(lab_path, folder / lab_path.name)
    for name in ("lesson.js", "lesson.css"):
        shutil.copyfile(ROOT / "site" / name, Path(output) / name)
