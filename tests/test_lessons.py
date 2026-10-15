"""Tutorials are executable and remain portable under a Pages project path."""
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import unittest
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build import build
from lessons import code_block


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.links = [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if "id" in data:
            self.ids.append(data["id"])
        for key in ("href", "src"):
            if data.get(key):
                self.links.append(data[key])


class LessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = build(ROOT / ".cache/tests/lessons")

    def test_every_week_has_substantial_authored_content(self):
        for week in range(1, 13):
            with self.subTest(week=week):
                data = json.loads((ROOT / f"content/lessons/week-{week:02d}.json").read_text(encoding="utf-8"))
                self.assertEqual(data["week"], week)
                self.assertGreaterEqual(len(data["sections"]), 3)
                self.assertTrue(all(len(s["body"]) >= 2 for s in data["sections"]))
                self.assertGreaterEqual(len(data["walkthrough"]), 4)
                self.assertGreaterEqual(len(data["exercises"]), 2)
                self.assertTrue(all(e["task"] and e["hint"] and e["answer"] for e in data["exercises"]))
                self.assertGreaterEqual(len(data["quiz"]), 2)
                self.assertTrue(data["integration"]["refs"])
                if data["integration"].get("code"):
                    ast.parse(data["integration"]["code"])

    def test_all_offline_exercises_execute_without_dependencies(self):
        for week in range(1, 13):
            with self.subTest(week=week):
                result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / f"labs/week-{week:02d}.py")],
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
                self.assertIsInstance(json.loads(result.stdout.decode("utf-8")), dict)

    def test_generated_pages_assets_downloads_and_local_anchors(self):
        home = Page((self.output / "index.html").read_text(encoding="utf-8"))
        for week in range(1, 13):
            self.assertIn(f"./lessons/week-{week:02d}/", home.links)
        for source in [self.output / "index.html", *self.output.glob("lessons/*/index.html")]:
            with self.subTest(page=source):
                text = source.read_text(encoding="utf-8")
                self.assertNotIn("{{", text)
                page = Page(text)
                self.assertEqual(len(page.ids), len(set(page.ids)))
                if source.parent != self.output:
                    self.assertIn("lab-code", page.ids)
                    self.assertIn("lesson-complete", page.ids)
                    lab = source.parent / f"{source.parent.name}.py"
                    self.assertEqual(lab.read_bytes(), (ROOT / "labs" / lab.name).read_bytes())
                for url in page.links:
                    parts = urlparse(url)
                    if parts.scheme or parts.netloc:
                        continue
                    target = (source.parent / unquote(parts.path)).resolve() if parts.path else source
                    self.assertTrue(target.is_relative_to(self.output.resolve()), url)
                    if target.is_dir():
                        target = target / "index.html"
                    self.assertTrue(target.is_file(), f"{source}: {url}")
                    if parts.fragment and target.suffix == ".html":
                        target_page = Page(target.read_text(encoding="utf-8"))
                        self.assertIn(unquote(parts.fragment), target_page.ids, url)

    def test_code_is_text_not_executable_markup(self):
        rendered = code_block('</code><script>alert("x")</script>', "sample", "example")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn('tabindex="0"', rendered)


if __name__ == "__main__":
    unittest.main()
