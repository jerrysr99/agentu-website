"""The brief builder republishes a source page in AgentU chrome."""

from __future__ import annotations

import importlib.util
import shutil
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
        self.assertEqual(latest, dated)
        self.assertNotIn("jerrywlambert", latest.lower())
        self.assertNotIn("Daily Model Brief", latest)
        self.assertNotIn("YWDlJZ", latest)
        self.assertNotIn(".pdf", latest.lower().split("<article", 1)[0])
        self.assertNotIn("sponsored by", latest.lower())
        self.assertNotIn("do not publish", latest.lower())
        self.assertIn("AgentU AI Briefing", latest)
        self.assertIn('rel="canonical" href="https://agentu.ai/brief/2026-10-23/"', latest)
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
        self.assertIn("Download today's brief", latest)
        self.assertIn("Enroll me in the daily AgentU AI Briefing", latest)
        self.assertIn('id="brief-enroll" name="enroll" type="checkbox" checked', latest)
        self.assertIn('id="brief-company"', latest)
        self.assertIn('"/api/brief-request"', latest)
        self.assertIn('brief_date: DATE', latest)
        self.assertIn("Check your inbox", latest)
        self.assertNotIn("\u2014", latest.split("<article", 1)[0])
        self.assertEqual(result["pdf"].read_bytes(), b"%PDF-1.4")
        self.assertEqual(result["pdf"].name, "2026-10-23.pdf")
        self.assertFalse((repo / "brief" / "2026-10-23.pdf").exists())
        self.assertFalse(list((repo / "brief").rglob("*.pdf")))


if __name__ == "__main__":
    unittest.main()
