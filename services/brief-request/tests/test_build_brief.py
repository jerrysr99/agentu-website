"""The brief builder republishes a source page in AgentU chrome."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def load_builder():
    path = REPO / "scripts" / "build_agentu_brief.py"
    spec = importlib.util.spec_from_file_location("build_agentu_brief", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = """<!DOCTYPE html>
<html><head><title>Daily Model Brief, October 23, 2026 · JerryWLambert.com AI Briefing</title></head>
<body>
<main>
<a class="back" href="/briefings/">All briefings</a>
<h1>Daily Model Brief, October 23, 2026</h1>
<p class="deck">No vendor changed a token price on any model I track today.</p>
<p class="meta">Friday, October 23, 2026 · Prices as of 8:45 AM CT</p>
<a class="pdf" href="./daily-model-brief-2026-10-23.pdf">Download PDF</a>
<a class="pdf" href="/newsletter/">Subscribe</a>
<!-- internal: do not publish the sponsor note -->
<div class="sponsor"><p>Sponsored by Example Co.</p></div>
<h2>Executive Summary</h2>
<p>Prices held. Cached cells use a dash.</p>
<h2>What This Means for Customers</h2>
<ul class="bul"><li>Move off gpt-4.1-nano.</li></ul>
<h2>New Models and Price Changes</h2>
<table class="data"><tr><td class="mono">qwen3.8-27b</td><td class="num">—</td></tr></table>
<h2>Deprecations</h2>
<p><code>gpt-4.1-nano</code></p>
<h2>Agent Platforms</h2>
<p><b>Grok Bot</b></p>
<h2>Model Size vs. Price</h2>
<img class="chart" src="./model-size-vs-price.png" alt="Model Size vs. Price (JerryWLambert.com AI Briefing)">
<h2>Price vs. Performance</h2>
<img class="chart" src="./price-vs-performance.png" alt="Price vs. Performance (JerryWLambert.com AI Briefing)">
<p class="note">All times Central.</p>
<footer><a href="/newsletter/">Get the Brief by email</a></footer>
</main>
</body></html>
"""


class BuildBriefTests(unittest.TestCase):
    def test_source_names_block_the_write(self):
        builder = load_builder()
        for leak in ("Scores from Artificial Analysis.", "Google's pricing page now warns.",
                     "posted on docs.typesafe.ai/models.md", "ranked on LMArena"):
            with self.subTest(leak=leak), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(SystemExit):
                    builder._write_checked(Path(tmp) / "index.html", f"<p>{leak}</p>")
        with tempfile.TemporaryDirectory() as tmp:
            builder._write_checked(Path(tmp) / "index.html", "<p>Google now warns. Scores as of Oct 16.</p>")

    def test_pages_are_public_clean_and_repeatable(self):
        builder = load_builder()
        root = Path(self.id().replace(".", "_"))
        base = Path("/tmp/brief-build") / root.name
        if base.exists():
            shutil.rmtree(base)
        src = base / "in" / "2026-10-23"
        repo = base / "repo"
        src.mkdir(parents=True)
        (src / "index.html").write_text(SOURCE, encoding="utf-8")
        (src / "model-size-vs-price.png").write_bytes(PNG)
        (src / "price-vs-performance.png").write_bytes(PNG)
        (src / "daily-model-brief-2026-10-23.pdf").write_bytes(b"%PDF-1.4")
        result = builder.build(src / "index.html", repo, site="https://agentu.ai")
        latest = result["latest"].read_text(encoding="utf-8")
        dated = result["dated"].read_text(encoding="utf-8")

        def article_of(page: str) -> str:
            return page.split('<article class="brief-body">', 1)[1].split("</article>", 1)[0].strip()

        self.assertNotEqual(latest, dated)
        self.assertEqual(article_of(latest), article_of(dated))
        self.assertNotIn("jerrywlambert", latest.lower())
        self.assertNotIn("Daily Model Brief", latest)
        self.assertNotIn("YWDlJZ", latest)
        self.assertNotIn(".pdf", latest.lower().split("<article", 1)[0])
        self.assertNotIn("sponsored by", latest.lower())
        self.assertNotIn("do not publish", latest.lower())
        self.assertIn("AgentU AI Briefing", latest)
        self.assertIn('rel="canonical" href="https://agentu.ai/brief/"', latest)
        self.assertIn('rel="canonical" href="https://agentu.ai/brief/2026-10-23/"', dated)
        self.assertIn('property="og:url" content="https://agentu.ai/brief/"', latest)
        self.assertIn('data-form="sf6Cjq"', latest)
        self.assertIn("https://assets.mailerlite.com/js/universal.js", latest)
        self.assertIn("ml('account','2731039')", latest)
        self.assertIn("Get the daily brief free", latest)
        self.assertNotIn('data-form="sf6Cjq"', dated)
        self.assertNotIn("Download today's brief", latest)
        self.assertNotIn("Download today's brief", dated)
        self.assertNotIn("open-brief", latest)
        self.assertNotIn("brief-modal", latest)
        self.assertNotIn("/api/brief-request", latest)
        self.assertNotIn("/api/brief-request", dated)
        self.assertIn('property="og:title"', latest)
        self.assertIn('name="twitter:card" content="summary_large_image"', latest)
        for heading in (
            "Executive Summary",
            "What This Means for Customers",
            "New Models and Price Changes",
            "Deprecations",
            "Agent Platforms",
            "Model Size vs. Price",
            "Price vs. Performance",
        ):
            self.assertIn(heading, latest)
        self.assertIn("qwen3.8-27b", latest)
        self.assertIn("gpt-4.1-nano", latest)
        self.assertIn("Grok Bot", latest)
        self.assertIn("—", latest)
        self.assertIn('src="model-size-vs-price.png"', latest)
        self.assertIn('src="price-vs-performance.png"', latest)
        self.assertTrue((repo / "brief" / "model-size-vs-price.png").is_file())
        self.assertTrue((repo / "brief" / "2026-10-23" / "price-vs-performance.png").is_file())
        self.assertNotIn("\u2014", latest.split("<article", 1)[0])
        self.assertNotIn("\u2014", dated.split("<article", 1)[0])
        self.assertEqual(result["pdf"].read_bytes(), b"%PDF-1.4")
        self.assertEqual(result["pdf"].name, "2026-10-23.pdf")
        self.assertFalse((repo / "brief" / "2026-10-23.pdf").exists())
        self.assertFalse(list((repo / "brief").rglob("*.pdf")))

    def test_older_build_does_not_replace_newer_latest(self):
        builder = load_builder()
        base = Path("/tmp/brief-build") / "older_keeps_newer"
        if base.exists():
            shutil.rmtree(base)
        repo = base / "repo"

        def plant(date: str, deck: str) -> Path:
            src = base / "in" / date
            src.mkdir(parents=True)
            text = SOURCE.replace(
                "No vendor changed a token price on any model I track today.",
                deck,
            )
            (src / "index.html").write_text(text, encoding="utf-8")
            (src / "model-size-vs-price.png").write_bytes(PNG)
            (src / "price-vs-performance.png").write_bytes(PNG)
            return src

        newer = plant("2026-10-24", "Newer edition deck sentence.")
        older = plant("2026-10-23", "Older edition deck sentence.")
        builder.build(newer / "index.html", repo, site="https://agentu.ai")
        before = (repo / "brief" / "index.html").read_text(encoding="utf-8")
        builder.build(older / "index.html", repo, site="https://agentu.ai")
        latest = (repo / "brief" / "index.html").read_text(encoding="utf-8")
        dated_old = (repo / "brief" / "2026-10-23" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(before, latest)
        self.assertIn("<h1>October 24, 2026</h1>", latest)
        self.assertIn("Newer edition deck sentence.", latest)
        self.assertNotIn("Older edition deck sentence.", latest)
        self.assertIn('data-form="sf6Cjq"', latest)
        self.assertIn("<h1>October 23, 2026</h1>", dated_old)
        self.assertIn("Older edition deck sentence.", dated_old)
        self.assertNotIn('data-form="sf6Cjq"', dated_old)
        self.assertNotIn("Download today's brief", latest)
        self.assertNotIn("Download today's brief", dated_old)

    def test_refresh_strips_download_and_keeps_latest_form(self):
        builder = load_builder()
        base = Path("/tmp/brief-build") / "refresh_latest"
        if base.exists():
            shutil.rmtree(base)
        src = base / "in" / "2026-10-23"
        repo = base / "repo"
        src.mkdir(parents=True)
        (src / "index.html").write_text(SOURCE, encoding="utf-8")
        (src / "model-size-vs-price.png").write_bytes(PNG)
        (src / "price-vs-performance.png").write_bytes(PNG)
        result = builder.build(src / "index.html", repo, site="https://agentu.ai")
        dated_path = result["dated"]
        html = dated_path.read_text(encoding="utf-8")
        dated_path.write_text(
            html.replace(
                "</header>",
                '<div class="actions"><button type="button" id="open-brief">Download today\'s brief</button></div></header>',
                1,
            ),
            encoding="utf-8",
        )
        builder.rewrite_dated_pages(repo, "https://agentu.ai")
        once = dated_path.read_text(encoding="utf-8")
        self.assertNotIn("Download today's brief", once)
        self.assertNotIn("open-brief", once)
        builder.rewrite_dated_pages(repo, "https://agentu.ai")
        self.assertEqual(once, dated_path.read_text(encoding="utf-8"))
        latest_path = builder.publish_latest(repo, "https://agentu.ai")
        latest = latest_path.read_text(encoding="utf-8")
        self.assertIn('data-form="sf6Cjq"', latest)
        self.assertIn("Get the daily brief free", latest)
        self.assertIn("<h1>October 23, 2026</h1>", latest)
        self.assertNotIn("Download today's brief", latest)
        self.assertNotIn("/api/brief-request", latest)
        again = builder.publish_latest(repo, "https://agentu.ai")
        self.assertEqual(latest, again.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
