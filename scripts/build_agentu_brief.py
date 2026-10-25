#!/usr/bin/env python3
"""Rebuild /brief/<date>/ from a source brief and refresh /brief/index.html.

/brief/ is always the newest dated edition: the MailerLite signup form,
then the full brief. Dated pages stay at /brief/<date>/. The public pages
use AgentU chrome. The series title is AgentU AI Briefing. Direct PDF
links, the old series name, and JerryWLambert.com branding are removed.
The PDF, when present beside the source HTML, is copied to
services/brief-request/pdfs/<date>.pdf for the mailer and is not placed
under /brief/. The pages do not link to that mailer.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SERIES = "AgentU AI Briefing"
SITE = "https://agentu.ai"
OLD_SERIES = "JerryWLambert.com AI Briefing"
OLD_TITLE = "Daily Model Brief"

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>@@TITLE@@</title>
<meta name="description" content="@@DESCRIPTION@@">
<link rel="canonical" href="@@CANONICAL@@">
<meta property="og:type" content="article">
<meta property="og:site_name" content="AgentU AI Briefing">
<meta property="og:title" content="@@TITLE@@">
<meta property="og:description" content="@@DESCRIPTION@@">
<meta property="og:url" content="@@CANONICAL@@">
<meta property="og:image" content="@@OG_IMAGE@@">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="@@TITLE@@">
<meta name="twitter:description" content="@@DESCRIPTION@@">
<meta name="twitter:url" content="@@CANONICAL@@">
<meta name="twitter:image" content="@@OG_IMAGE@@">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Cormorant+Garamond:wght@600;700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
@@HEAD_EXTRA@@
<style>
:root{
  --navy:#12193F; --navy2:#1B2350; --gold:#C6A241; --gold-d:#A9852B; --gold-ink:#8A6410; --gold-soft:#F4EBCF;
  --paper:#F7F3E8; --ink:#1C2135; --slate:#5C6480; --faint:#8A91AC; --line:#E7E0CF;
  --indigo:#243469; --indigo-d:#1A2650;
  --ui:'Inter',system-ui,-apple-system,sans-serif; --disp:'Newsreader',Georgia,serif; --mono:'IBM Plex Mono',ui-monospace,monospace;
  --sh:0 1px 2px rgba(23,29,63,.05),0 4px 14px rgba(23,29,63,.06);
  --sh-lg:0 8px 32px rgba(23,29,63,.14);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--ui);color:var(--ink);background:var(--paper);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--indigo);text-decoration:none}
a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--indigo);outline-offset:2px;border-radius:4px}
.kicker{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--gold-ink)}
.kicker::before{content:"";display:inline-block;width:16px;height:1.5px;background:var(--gold);vertical-align:middle;margin-right:8px;margin-bottom:2px}
.btn{display:inline-flex;align-items:center;gap:7px;border:1px solid transparent;border-radius:8px;padding:9px 16px;font-size:13.5px;font-weight:600;background:var(--indigo);color:#fff;font-family:var(--ui);cursor:pointer}
.btn:hover{background:var(--indigo-d);text-decoration:none}
.btn.gold{background:var(--gold);color:var(--navy);border-color:var(--gold-d)}
.btn.gold:hover{background:var(--gold-d);color:var(--navy)}
.btn.sm{padding:5px 11px;font-size:12.5px;border-radius:7px}
.btn.big{padding:13px 24px;font-size:15px}
.btn:disabled{opacity:.55;cursor:not-allowed}
.mk{background:#fff}
.mnav{position:sticky;top:0;z-index:50;background:rgba(18,25,63,.94);backdrop-filter:blur(8px);color:#fff;display:flex;align-items:center;gap:22px;padding:0 max(24px,5vw);height:60px;border-bottom:1px solid rgba(198,162,65,.5)}
.mnav .brand{display:flex;align-items:center;gap:10px;font-family:var(--disp);font-weight:600;font-size:18px;color:#fff}
.mnav .brand:hover{text-decoration:none}
.mnav .brand .crestmk{width:26px;height:31px;display:block;flex:none}
.mnav a.ml{color:#C9C0A6;font-size:13.5px;font-weight:500}
.mnav a.ml:hover,.mnav a.ml[aria-current="page"]{color:var(--gold);text-decoration:none}
.crestmk .fill-navy{fill:#12193F}.crestmk .st-gold{stroke:#C6A241}.crestmk .fill-gold{fill:#C6A241}
.mnav .sp{flex:1}
.hero{background:var(--navy);color:#fff;padding:56px max(24px,5vw) 48px}
.hero .kicker{color:var(--gold)}
.hero h1{font-family:var(--disp);font-size:clamp(34px,5vw,56px);font-weight:600;line-height:1.08;margin-top:12px}
.hero .deck{color:#B9C1E4;font-size:17px;line-height:1.6;max-width:68ch;margin-top:16px}
.hero .meta{color:#8F99C6;font-size:13px;margin-top:12px}
.sect{padding:36px max(24px,5vw) 72px}
.subscribe{background:#fff;border-bottom:1px solid var(--line);padding:28px max(24px,5vw) 32px}
.subscribe-inner{max-width:640px}
.subscribe h2{font-family:var(--disp);font-size:clamp(28px,3.2vw,40px);font-weight:600;line-height:1.15;color:var(--navy);margin:0 0 16px}
.signup{max-width:640px}
.brief-body{max-width:960px}
.brief-body h2{font-family:var(--disp);font-size:clamp(24px,3vw,32px);font-weight:600;line-height:1.2;margin:34px 0 12px;color:var(--navy)}
.brief-body p,.brief-body li{font-size:15.5px;line-height:1.65}
.brief-body p{margin:0 0 12px}
.brief-body ul{margin:0 0 16px 1.15em}
.brief-body li{margin:8px 0}
.brief-body .unit{color:var(--faint);font-size:13px;margin-bottom:8px}
.brief-body code{font-family:var(--mono);font-size:.92em;background:var(--paper);padding:1px 5px;border-radius:4px}
.brief-body .cap,.brief-body .note{color:var(--slate);font-size:13.5px;line-height:1.6}
.brief-body .notes{color:var(--slate);font-size:13.5px;margin:8px 0 8px 1.15em}
.brief-body .notes li{margin:6px 0}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);margin:8px 0 16px}
table.data{width:100%;border-collapse:collapse;font-size:13px;min-width:720px}
table.data th{font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);text-align:left;padding:12px 14px;border-bottom:1px solid var(--line);background:var(--paper);white-space:nowrap}
table.data td{padding:11px 14px;border-bottom:1px solid #EEF1F8;vertical-align:top}
table.data tr:last-child td{border-bottom:none}
table.data .num,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
table.data .num{text-align:right;white-space:nowrap}
img.chart{display:block;width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:14px;margin:8px 0 12px}
.foot{background:#10152F;color:#8F99C6;padding:36px max(24px,5vw);font-size:12.8px;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
.foot a{color:#AEB7DE}
@media(max-width:960px){
  .hero{padding:40px 20px 36px}
  .mnav{gap:12px;padding:0 14px;height:auto;min-height:60px;flex-wrap:wrap;padding-top:10px;padding-bottom:10px}
  .mnav a.ml{display:none}
  .mnav a.ml.billing,.mnav a.ml.briefnav{display:inline}
  .sect{padding:28px 16px 56px}
  .foot{padding:28px 16px}
}
</style>
</head>
<body>
<div class="mk">
<nav class="mnav">
  <a class="brand" href="/"><span class="crestmk"><svg viewBox="0 0 30 31" aria-hidden="true"><path class="fill-navy st-gold" stroke-width="1.5" d="M2 2 H28 V15 Q28 25 15 30 Q2 25 2 15 Z"/><text x="15" y="21" text-anchor="middle" font-family="'Cormorant Garamond',serif" font-weight="700" font-size="16" letter-spacing="-1" class="fill-gold">AU</text></svg></span> Agent U</a>
  <a class="ml" href="/#why">Why</a>
  <a class="ml" href="/#analytics">Analytics</a>
  <a class="ml" href="/#product">Product</a>
  <a class="ml" href="/#pricing">Pricing</a>
  <a class="ml" href="/#faq">FAQ</a>
  <a class="ml billing" href="/billing-accuracy/">Billing</a>
  <a class="ml briefnav" href="/brief/" aria-current="page">Brief</a>
  <span class="sp"></span>
  <a class="ml" href="/#/login">Sign in</a>
  <a class="btn gold sm" href="/#/signup">Sign up</a>
</nav>
@@SUBSCRIBE@@
<header class="hero">
  <span class="kicker">AgentU AI Briefing</span>
  <h1>@@H1@@</h1>
  @@DECK@@
  @@META@@
</header>
<main class="sect">
  <article class="brief-body">
@@ARTICLE@@
  </article>
</main>
<footer class="foot">
  <div><strong style="color:var(--gold)">Agent U</strong> · SmarterDev.ai · Denton, TX<br>© 2026 · All rights reserved</div>
  <div><a href="/">Home</a> · <a href="/billing-accuracy/">Billing</a> · <a href="mailto:brief@agentu.ai">Contact</a></div>
</footer>
</div>
</body>
</html>
"""

# Same embed already used on the billing page. Latest /brief/ only.
MAILERLITE = (
    "<!-- MailerLite Universal -->"
    "<script>"
    "(function(w,d,e,u,f,l,n){w[f]=w[f]||function(){(w[f].q=w[f].q||[]).push(arguments);},l=d.createElement(e),l.async=1,l.src=u,n=d.getElementsByTagName(e)[0],n.parentNode.insertBefore(l,n);})"
    "(window,document,'script','https://assets.mailerlite.com/js/universal.js','ml');"
    "ml('account','2731039');"
    "</script>"
    "<!-- End MailerLite Universal -->"
)
SUBSCRIBE = """<section class="subscribe" id="subscribe" aria-labelledby="subscribe-title">
  <div class="subscribe-inner">
    <h2 id="subscribe-title">Get the daily brief free</h2>
    <div class="ml-embedded signup" data-form="sf6Cjq"></div>
  </div>
</section>"""

DATE_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def pretty_date(iso_date: str) -> str:
    stamp = datetime.strptime(iso_date, "%Y-%m-%d")
    return f"{stamp.strftime('%B')} {stamp.day}, {stamp.year}"


def infer_date(source: Path, explicit: str | None) -> str:
    if explicit:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", explicit):
            raise SystemExit(f"date must be YYYY-MM-DD, got {explicit}")
        return explicit
    for part in source.parts:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", part):
            return part
    raise SystemExit("pass --date YYYY-MM-DD or place index.html in a dated directory")


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _strip_class_blocks(text: str, needle: str) -> str:
    pattern = re.compile(
        rf"<(div|section|aside|p|ul|li)[^>]*class=['\"][^'\"]*{needle}[^'\"]*['\"][^>]*>.*?</\1>",
        re.I | re.S,
    )
    previous = None
    while previous != text:
        previous = text
        text = pattern.sub("", text)
    return text


def _take(pattern: str, text: str) -> tuple[str, str]:
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return "", text
    return match.group(1).strip(), text[: match.start()] + text[match.end() :]


def prepare_article(main_html: str) -> tuple[str, str, str]:
    text = _strip_comments(main_html)
    text = _strip_class_blocks(text, "sponsor")
    text = _strip_class_blocks(text, "internal")
    text = _strip_class_blocks(text, "stage-direction")
    text = re.sub(r"<p[^>]*>\s*sponsored by\b.*?</p>", "", text, flags=re.I | re.S)
    text = re.sub(r"<a[^>]*class=['\"][^'\"]*\b(?:pdf|back)\b[^'\"]*['\"][^>]*>.*?</a>", "", text, flags=re.I | re.S)
    text = re.sub(
        r"<a[^>]*href=['\"][^'\"]*(?:/newsletter/|daily-model-brief-[^'\"]+\.pdf|\.pdf)[^'\"]*['\"][^>]*>.*?</a>",
        "",
        text,
        flags=re.I | re.S,
    )
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.I | re.S)
    _h1, text = _take(r"<h1[^>]*>(.*?)</h1>", text)
    deck, text = _take(r"<p[^>]*class=['\"]deck['\"][^>]*>(.*?)</p>", text)
    meta, text = _take(r"<p[^>]*class=['\"]meta['\"][^>]*>(.*?)</p>", text)
    text = text.replace(OLD_SERIES, SERIES)
    text = re.sub(r"JerryWLambert\.com", "AgentU", text, flags=re.I)
    text = re.sub(r"https?://(?:www\.)?jerrywlambert\.com", SITE, text, flags=re.I)
    text = text.replace(OLD_TITLE, SERIES)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, deck, meta


def rewrite_images(article: str) -> tuple[str, list[str]]:
    names: list[str] = []

    def repl(match: re.Match) -> str:
        quote, src = match.group(1), match.group(2)
        if re.match(r"(?:https?:|data:)", src):
            return match.group(0)
        name = Path(src.split("?", 1)[0]).name
        if name not in names:
            names.append(name)
        return f"src={quote}{name}{quote}"

    return re.sub(r"src=(['\"])([^'\"]+)\1", repl, article), names


def plain_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def render_page(
    date: str,
    article: str,
    deck: str,
    meta: str,
    image_name: str,
    site: str,
    latest: bool = False,
) -> str:
    root = site.rstrip("/")
    canonical = f"{root}/brief/" if latest else f"{root}/brief/{date}/"
    title = f"{pretty_date(date)} · {SERIES}"
    description = plain_text(deck) or f"{SERIES} for {pretty_date(date)}."
    if len(description) > 300:
        description = description[:297].rstrip() + "..."
    deck_html = f'<p class="deck">{deck}</p>' if deck else ""
    meta_html = f'<p class="meta">{meta}</p>' if meta else ""
    og_image = f"{canonical}{image_name}" if image_name else canonical
    page = PAGE
    replacements = {
        "@@TITLE@@": html.escape(title, quote=True),
        "@@DESCRIPTION@@": html.escape(description, quote=True),
        "@@CANONICAL@@": html.escape(canonical, quote=True),
        "@@OG_IMAGE@@": html.escape(og_image, quote=True),
        "@@H1@@": html.escape(pretty_date(date)),
        "@@DECK@@": deck_html,
        "@@META@@": meta_html,
        "@@ARTICLE@@": article,
        "@@HEAD_EXTRA@@": MAILERLITE if latest else "",
        "@@SUBSCRIBE@@": SUBSCRIBE if latest else "",
    }
    for token, value in replacements.items():
        page = page.replace(token, value)
    return page


def copy_assets(src_dir: Path, names: list[str], destinations: list[Path]) -> None:
    for name in names:
        source = src_dir / name
        if not source.is_file():
            raise SystemExit(f"missing asset {source}")
        for dest_dir in destinations:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest_dir / name)


def list_dated(repo: Path) -> list[str]:
    root = repo / "brief"
    if not root.is_dir():
        return []
    found = [
        child.name
        for child in root.iterdir()
        if child.is_dir() and DATE_DIR.fullmatch(child.name) and (child / "index.html").is_file()
    ]
    return sorted(found)


def copy_edition_images(src_dir: Path, dest_dir: Path) -> None:
    if not src_dir.is_dir():
        return
    dest_dir.mkdir(parents=True, exist_ok=True)
    for path in src_dir.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            target = dest_dir / path.name
            if target.resolve() != path.resolve():
                shutil.copy2(path, target)


def extract_edition(page_html: str, date: str) -> dict:
    article_match = re.search(r'<article class="brief-body">\s*(.*?)\s*</article>', page_html, flags=re.S)
    if not article_match:
        raise SystemExit(f"brief {date} has no article")
    article = article_match.group(1).strip()
    deck_match = re.search(r'<p class="deck">(.*?)</p>', page_html, flags=re.S)
    meta_match = re.search(r'<p class="meta">(.*?)</p>', page_html, flags=re.S)
    image_match = re.search(r'<meta property="og:image" content="([^"]*)">', page_html)
    image_name = Path(html.unescape(image_match.group(1))).name if image_match else ""
    if not image_name:
        names = re.findall(r"""<img[^>]*src=['"]([^'"]+)['"]""", article)
        if "price-vs-performance.png" in names:
            image_name = "price-vs-performance.png"
        elif names:
            image_name = Path(names[0]).name
    return {
        "date": date,
        "article": article,
        "deck": deck_match.group(1).strip() if deck_match else "",
        "meta": meta_match.group(1).strip() if meta_match else "",
        "image_name": image_name,
    }


# Public pages never name data sources, collection method, or vendor docs/pricing URLs.
SOURCE_TERMS = re.compile(
    r"artificial ?analysis|\bLMSYS\b|LMArena|chatbot arena|OpenRouter|\bEpoch (?:AI|notable)\b"
    r"|pricing pages?|price pages?|leaderboard read|read cleanly|returned 403|did not render"
    r"|trending on Hugging Face|\bAA's\b|AA-estimated",
    re.I,
)
SOURCE_URLS = re.compile(
    r"\b(?:docs|platform|dev|developers?|help|api-docs|console|cloud)\.[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:ai|com|io|cn|dev|co)\b"
    r"|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:ai|com|io|cn|dev|co)/(?:docs|pricing|help)\b"
    r"|\b(?:artificialanalysis\.ai|lmarena\.ai|lmsys\.org|openrouter\.ai|huggingface\.co|epoch\.ai)\b",
    re.I,
)


def source_leaks(page: str) -> list[str]:
    hits = [m.group(0) for m in SOURCE_TERMS.finditer(page)]
    return hits + [m.group(0) for m in SOURCE_URLS.finditer(page)]


def _write_checked(path: Path, page: str) -> None:
    if "@@" in page:
        raise SystemExit(f"unfilled template token in {path}")
    leaks = source_leaks(page)
    if leaks:
        raise SystemExit(f"public page names a data source in {path}: {sorted(set(leaks))}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def rewrite_dated_pages(repo: Path, site: str = SITE) -> list[str]:
    """Re-render each dated page from its own article so the download UI stays off."""
    dates = list_dated(repo)
    if not dates:
        raise SystemExit("no dated briefs under brief/")
    for date in dates:
        path = repo / "brief" / date / "index.html"
        parts = extract_edition(path.read_text(encoding="utf-8"), date)
        page = render_page(
            parts["date"],
            parts["article"],
            parts["deck"],
            parts["meta"],
            parts["image_name"],
            site,
            latest=False,
        )
        _write_checked(path, page)
    return dates


def publish_latest(repo: Path, site: str = SITE, current: dict | None = None) -> Path:
    """Write /brief/index.html from the newest dated edition."""
    dates = list_dated(repo)
    if current and current["date"] not in dates:
        dates = sorted([*dates, current["date"]])
    if not dates:
        raise SystemExit("no dated brief to publish at /brief/")
    newest = dates[-1]
    latest_dir = repo / "brief"
    latest_dir.mkdir(parents=True, exist_ok=True)
    if current and current["date"] == newest:
        copy_assets(current["assets_from"], current["asset_names"], [latest_dir])
        page = render_page(
            current["date"],
            current["article"],
            current["deck"],
            current["meta"],
            current["image_name"],
            site,
            latest=True,
        )
    else:
        source_dir = repo / "brief" / newest
        copy_edition_images(source_dir, latest_dir)
        parts = extract_edition((source_dir / "index.html").read_text(encoding="utf-8"), newest)
        page = render_page(
            parts["date"],
            parts["article"],
            parts["deck"],
            parts["meta"],
            parts["image_name"],
            site,
            latest=True,
        )
    path = latest_dir / "index.html"
    _write_checked(path, page)
    return path


def copy_pdf(src_dir: Path, date: str, pdf_out: Path) -> Path | None:
    candidates = [src_dir / f"{date}.pdf", src_dir / f"daily-model-brief-{date}.pdf"]
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        return None
    target = pdf_out if pdf_out.suffix == ".pdf" else pdf_out / f"{date}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() != source.resolve():
        shutil.copy2(source, target)
    return target


def build(source: Path, repo: Path, date: str | None = None, site: str = SITE, pdf_out: Path | None = None) -> dict:
    source = source.resolve()
    repo = repo.resolve()
    iso = infer_date(source, date)
    raw = source.read_text(encoding="utf-8")
    main = re.search(r"<main[^>]*>(.*)</main>", raw, flags=re.I | re.S)
    if not main:
        raise SystemExit(f"{source} has no <main>")
    article, deck, meta = prepare_article(main.group(1))
    article, names = rewrite_images(article)
    if re.search(r"\b(?:pdf|back)\b", article) and ".pdf" in article:
        raise SystemExit("a PDF link survived the rewrite")
    image_name = "price-vs-performance.png" if "price-vs-performance.png" in names else (names[0] if names else "")
    page = render_page(iso, article, deck, meta, image_name, site, latest=False)
    dated_dir = repo / "brief" / iso
    dated_dir.mkdir(parents=True, exist_ok=True)
    copy_assets(source.parent, names, [dated_dir])
    dated_path = dated_dir / "index.html"
    _write_checked(dated_path, page)
    latest_path = publish_latest(
        repo,
        site,
        current={
            "date": iso,
            "article": article,
            "deck": deck,
            "meta": meta,
            "image_name": image_name,
            "assets_from": source.parent,
            "asset_names": names,
        },
    )
    pdf_target = copy_pdf(source.parent, iso, pdf_out or (repo / "services" / "brief-request" / "pdfs"))
    return {
        "date": iso,
        "latest": latest_path,
        "dated": dated_path,
        "images": names,
        "pdf": pdf_target,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish an AgentU AI Briefing page from a source brief.")
    parser.add_argument("--source", type=Path, help="Path to the source brief index.html")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="agentu-website repo root")
    parser.add_argument("--date", help="YYYY-MM-DD. Default: a dated directory in the source path")
    parser.add_argument("--site", default=SITE, help="Canonical site origin")
    parser.add_argument("--pdf-out", type=Path, help="Directory or .pdf path for the mailer copy")
    parser.add_argument(
        "--refresh-latest",
        action="store_true",
        help="Rewrite /brief/index.html from the newest dated brief. With no --source, also re-render dated pages.",
    )
    args = parser.parse_args(argv)
    if args.source is None:
        if not args.refresh_latest:
            parser.error("pass --source, or --refresh-latest to rebuild /brief/ from dated pages")
        dates = rewrite_dated_pages(args.repo, args.site)
        path = publish_latest(args.repo, args.site)
        print(f"wrote {path} from {dates[-1]}")
        for date in dates:
            print(f"wrote {args.repo / 'brief' / date / 'index.html'}")
        return 0
    if not args.source.is_file():
        print(f"source not found: {args.source}", file=sys.stderr)
        return 1
    result = build(args.source, args.repo, args.date, args.site, args.pdf_out)
    if args.refresh_latest:
        rewrite_dated_pages(args.repo, args.site)
    print(f"wrote {result['latest']}")
    print(f"wrote {result['dated']}")
    if result["pdf"]:
        print(f"pdf {result['pdf']}")
    else:
        print("no source pdf found; pages still written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
