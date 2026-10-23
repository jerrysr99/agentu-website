#!/usr/bin/env python3
"""Rebuild /brief/ and /brief/<date>/ from a Jerry Lambert brief.

The public pages use AgentU chrome. The series title is AgentU AI Briefing.
Direct PDF links, the old series name, and JerryWLambert.com branding are
removed. The PDF, when present beside the source HTML, is copied to
services/brief-request/pdfs/<date>.pdf for the mailer and is not placed
under /brief/.
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
.hero .actions{margin-top:22px}
.sect{padding:36px max(24px,5vw) 72px}
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
.modal-back{position:fixed;inset:0;z-index:80;background:rgba(18,25,63,.55);display:flex;align-items:flex-start;justify-content:center;padding:24px 16px;overflow:auto}
.modal-back[hidden]{display:none}
.modal{background:#fff;color:var(--ink);border-radius:14px;max-width:440px;width:100%;padding:22px 22px 26px;box-shadow:var(--sh-lg);position:relative;margin-top:8vh}
.modal h2{font-family:var(--disp);font-size:28px;font-weight:600;line-height:1.15;margin:0 36px 8px 0}
.modal-sub{color:var(--slate);font-size:14px;line-height:1.5;margin:0 0 16px}
.modal-x{position:absolute;top:10px;right:12px;border:0;background:transparent;color:var(--faint);font-size:22px;line-height:1;cursor:pointer;padding:4px}
.field{margin-bottom:14px}
.field label{display:block;font-size:12.5px;font-weight:600;margin-bottom:6px}
.input{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:16px;font-family:var(--ui);background:#fff;color:var(--ink)}
.input:focus{outline:none;border-color:var(--indigo);box-shadow:0 0 0 3px rgba(36,52,105,.15)}
.check{display:flex;gap:9px;align-items:flex-start;font-size:14px;line-height:1.45;margin:2px 0 16px}
.check input{margin-top:3px}
.aerr{background:#FBE9E9;border:1px solid #F0C3C3;color:#9B2C2C;font-size:13px;padding:9px 12px;border-radius:8px;margin-bottom:12px}
.success-title{font-family:var(--disp);font-size:32px;font-weight:600;color:var(--navy);margin:0 0 8px}
#brief-success p{color:var(--slate);line-height:1.55}
.hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
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
<header class="hero">
  <span class="kicker">AgentU AI Briefing</span>
  <h1>@@H1@@</h1>
  @@DECK@@
  @@META@@
  <div class="actions"><button type="button" class="btn gold big" id="open-brief">Download today's brief</button></div>
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
<div id="brief-modal" class="modal-back" hidden>
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="brief-dialog-title">
    <button type="button" class="modal-x" data-close aria-label="Close">&times;</button>
    <h2 id="brief-dialog-title">Download today's brief</h2>
    <p class="modal-sub">Enter your email and we will send today's edition.</p>
    <form id="brief-form">
      <div class="hp" aria-hidden="true">
        <label for="brief-company">Company</label>
        <input id="brief-company" name="company" type="text" tabindex="-1" autocomplete="off">
      </div>
      <div class="field">
        <label for="brief-email">Email</label>
        <input id="brief-email" name="email" type="email" class="input" required autocomplete="email" inputmode="email">
      </div>
      <label class="check">
        <input id="brief-enroll" name="enroll" type="checkbox" checked>
        <span>Enroll me in the daily AgentU AI Briefing</span>
      </label>
      <div id="brief-error" class="aerr" hidden role="alert"></div>
      <button class="btn gold big" id="brief-submit" type="submit">Email it to me</button>
    </form>
    <div id="brief-success" hidden>
      <p class="success-title">Check your inbox</p>
      <p>Today's brief is on its way. If you enrolled, open the email and confirm to join the daily list.</p>
    </div>
  </div>
</div>
<script>
(function () {
  var DATE = "@@DATE@@";
  var openBtn = document.getElementById("open-brief");
  var modal = document.getElementById("brief-modal");
  var form = document.getElementById("brief-form");
  var email = document.getElementById("brief-email");
  var enroll = document.getElementById("brief-enroll");
  var hp = document.getElementById("brief-company");
  var err = document.getElementById("brief-error");
  var ok = document.getElementById("brief-success");
  var submit = document.getElementById("brief-submit");
  function show() {
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    email.focus();
  }
  function hide() {
    modal.hidden = true;
    document.body.style.overflow = "";
  }
  openBtn.addEventListener("click", show);
  modal.querySelector("[data-close]").addEventListener("click", hide);
  modal.addEventListener("click", function (e) { if (e.target === modal) hide(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.hidden) hide();
  });
  function valid(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    err.hidden = true;
    var addr = email.value.trim();
    if (!valid(addr)) {
      err.textContent = "Enter a valid email address.";
      err.hidden = false;
      email.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Sending";
    fetch("/api/brief-request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: addr,
        enroll: !!enroll.checked,
        brief_date: DATE,
        page: location.pathname,
        company: hp.value
      })
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok || !data.ok) {
          throw new Error((data && data.error) || "We could not send the brief. Try again.");
        }
        form.hidden = true;
        ok.hidden = false;
      });
    }).catch(function (ex) {
      err.textContent = (ex && ex.message) || "We could not send the brief. Try again.";
      err.hidden = false;
      submit.disabled = false;
      submit.textContent = "Email it to me";
    });
  });
})();
</script>
</body>
</html>
"""


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


def render_page(date: str, article: str, deck: str, meta: str, image_name: str, site: str) -> str:
    canonical = f"{site.rstrip('/')}/brief/{date}/"
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
        "@@DATE@@": date,
        "@@ARTICLE@@": article,
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
    page = render_page(iso, article, deck, meta, image_name, site)
    if "@@" in page:
        raise SystemExit("unfilled template token in brief page")
    latest_dir = repo / "brief"
    dated_dir = repo / "brief" / iso
    for directory in (latest_dir, dated_dir):
        directory.mkdir(parents=True, exist_ok=True)
    copy_assets(source.parent, names, [latest_dir, dated_dir])
    (latest_dir / "index.html").write_text(page, encoding="utf-8")
    (dated_dir / "index.html").write_text(page, encoding="utf-8")
    pdf_target = copy_pdf(source.parent, iso, pdf_out or (repo / "services" / "brief-request" / "pdfs"))
    return {
        "date": iso,
        "latest": latest_dir / "index.html",
        "dated": dated_dir / "index.html",
        "images": names,
        "pdf": pdf_target,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish an AgentU AI Briefing page from a source brief.")
    parser.add_argument("--source", required=True, type=Path, help="Path to the source brief index.html")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="agentu-website repo root")
    parser.add_argument("--date", help="YYYY-MM-DD. Default: a dated directory in the source path")
    parser.add_argument("--site", default=SITE, help="Canonical site origin")
    parser.add_argument("--pdf-out", type=Path, help="Directory or .pdf path for the mailer copy")
    args = parser.parse_args(argv)
    if not args.source.is_file():
        print(f"source not found: {args.source}", file=sys.stderr)
        return 1
    result = build(args.source, args.repo, args.date, args.site, args.pdf_out)
    print(f"wrote {result['latest']}")
    print(f"wrote {result['dated']}")
    if result["pdf"]:
        print(f"pdf {result['pdf']}")
    else:
        print("no source pdf found; pages still written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
