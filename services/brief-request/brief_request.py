"""AgentU AI Briefing request service.

Stdlib only. Binds in server.py to 127.0.0.1:8720. Every filesystem path
comes from the environment. Mail is sent by an injected mailer so tests
never open a network connection.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import html
import json
import os
import re
import smtplib
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

SERIES = "AgentU AI Briefing"
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._%+\-]{0,63}"
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}$"
)
DATE_PDF = re.compile(r"^(\d{4}-\d{2}-\d{2})\.pdf$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LIST_KEYS = ("bcc", "unsubscribed", "pending")
IP_LIMIT = 5
IP_WINDOW = 3600
EMAIL_LIMIT = 3
EMAIL_WINDOW = 86400
CONFIRM_TTL = 14 * 24 * 3600
HONEYPOT_FIELD = "company"


class BriefError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class ConfigError(BriefError):
    def __init__(self, message: str):
        super().__init__(500, message)


@dataclass
class Config:
    subscribers_path: Path
    request_log: Path
    pdf_dir: Path
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    mail_from: str
    confirm_secret: str
    public_base_url: str = "https://agentu.ai"

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "Config":
        src = os.environ if env is None else env

        def need(name: str) -> str:
            value = (src.get(name) or "").strip()
            if not value:
                raise ConfigError(f"{name} is required")
            return value

        try:
            port = int((src.get("SMTP_PORT") or "587").strip())
        except ValueError as exc:
            raise ConfigError("SMTP_PORT must be an integer") from exc
        base = (src.get("PUBLIC_BASE_URL") or "https://agentu.ai").strip().rstrip("/")
        return cls(
            subscribers_path=Path(src.get("SUBSCRIBERS_PATH") or "/srv/briefs/agentu-subscribers.json"),
            request_log=Path(src.get("REQUEST_LOG") or "/srv/briefs/brief-requests.jsonl"),
            pdf_dir=Path(src.get("PDF_DIR") or "/srv/briefs/pdf"),
            smtp_host=need("SMTP_HOST"),
            smtp_port=port,
            smtp_user=need("SMTP_USER"),
            smtp_pass=need("SMTP_PASS"),
            mail_from=(src.get("MAIL_FROM") or "brief@agentu.ai").strip(),
            confirm_secret=need("CONFIRM_SECRET"),
            public_base_url=base or "https://agentu.ai",
        )


def valid_email(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if not email or len(email) > 254:
        return None
    if any(ch in email for ch in "\r\n\t "):
        return None
    if ".." in email:
        return None
    if not EMAIL_RE.match(email):
        return None
    local, _, _domain = email.partition("@")
    if len(local) > 64:
        return None
    return email


def ip_hash(secret: str, ip: str) -> str:
    return hashlib.sha256(f"{secret}\n{ip}".encode("utf-8")).hexdigest()[:32]


def _b64e(raw: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    import base64
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign_token(secret: str, action: str, email: str, issued_at: int) -> str:
    payload = json.dumps(
        {"a": action, "e": email, "t": int(issued_at)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    body = _b64e(payload)
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def read_token(secret: str, token: str, expected_action: str, now: float) -> str:
    if not isinstance(token, str) or token.count(".") != 1:
        raise BriefError(400, "This link is not valid.")
    body, sig = token.split(".", 1)
    try:
        expected = _b64e(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    except Exception as exc:
        raise BriefError(400, "This link is not valid.") from exc
    if not hmac.compare_digest(expected, sig):
        raise BriefError(400, "This link is not valid.")
    try:
        data = json.loads(_b64d(body))
    except Exception as exc:
        raise BriefError(400, "This link is not valid.") from exc
    if not isinstance(data, dict) or data.get("a") != expected_action:
        raise BriefError(400, "This link is not valid.")
    email = valid_email(data.get("e"))
    issued = data.get("t")
    if email is None or not isinstance(issued, int):
        raise BriefError(400, "This link is not valid.")
    if issued > int(now) + 300:
        raise BriefError(400, "This link is not valid.")
    if expected_action == "confirm" and int(now) - issued > CONFIRM_TTL:
        raise BriefError(400, "This link is not valid.")
    return email


def newest_pdf(pdf_dir: Path) -> Optional[Path]:
    if not pdf_dir.is_dir():
        return None
    found = []
    for path in pdf_dir.iterdir():
        if path.is_file() and DATE_PDF.match(path.name):
            found.append(path)
    if not found:
        return None
    return max(found, key=lambda item: item.name)


def _empty_list() -> dict:
    return {"bcc": [], "unsubscribed": [], "pending": []}


def _normalize_list(data) -> dict:
    if not isinstance(data, dict):
        raise BriefError(500, "Subscriber list is unreadable.")
    for key in LIST_KEYS:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise BriefError(500, "Subscriber list is unreadable.")
        data[key] = value
    return data


def _mutate_list(path: Path, mutator: Callable[[dict], None]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            raw = handle.read()
            try:
                data = json.loads(raw) if raw.strip() else _empty_list()
            except json.JSONDecodeError as exc:
                raise BriefError(500, "Subscriber list is unreadable.") from exc
            data = _normalize_list(data)
            mutator(data)
            text = json.dumps(data, indent=2, sort_keys=True) + "\n"
            handle.seek(0)
            handle.truncate()
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            return data
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _append_log(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _contains(rows: list, email: str) -> bool:
    return email in rows


def _drop(rows: list, email: str) -> list:
    return [item for item in rows if item != email]


class RateLimiter:
    def __init__(self, now: Callable[[], float]):
        self.now = now
        self._ip = {}
        self._email = {}
        self._lock = threading.Lock()

    def _prune(self, bucket: dict, key: str, now: float, window: int) -> list:
        hits = [stamp for stamp in bucket.get(key, []) if now - stamp < window]
        bucket[key] = hits
        return hits

    def check(self, ip: str, email: str) -> Optional[str]:
        now = float(self.now())
        with self._lock:
            ip_hits = self._prune(self._ip, ip, now, IP_WINDOW)
            if len(ip_hits) >= IP_LIMIT:
                return "ip"
            email_hits = self._prune(self._email, email, now, EMAIL_WINDOW)
            if len(email_hits) >= EMAIL_LIMIT:
                return "email"
            self._ip.setdefault(ip, []).append(now)
            self._email.setdefault(email, []).append(now)
            return None


class SMTPMailer:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def send(self, message: EmailMessage) -> None:
        host = self.cfg.smtp_host
        port = self.cfg.smtp_port
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            smtp = smtplib.SMTP(host, port, timeout=30)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        try:
            if self.cfg.smtp_user:
                smtp.login(self.cfg.smtp_user, self.cfg.smtp_pass)
            smtp.send_message(message)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()


def _pretty_date(iso_date: str) -> str:
    stamp = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return f"{stamp.strftime('%B')} {stamp.day}, {stamp.year}"


def _from_header(mail_from: str) -> str:
    if "<" in mail_from:
        return mail_from
    return f"{SERIES} <{mail_from}>"


def build_message(cfg: Config, email: str, pdf_path: Path, enroll_state: str, now: float) -> EmailMessage:
    iso_date = DATE_PDF.match(pdf_path.name).group(1)
    pretty = _pretty_date(iso_date)
    issued = int(now)
    confirm_token = sign_token(cfg.confirm_secret, "confirm", email, issued)
    unsub_token = sign_token(cfg.confirm_secret, "unsub", email, issued)
    confirm_url = f"{cfg.public_base_url}/api/brief-confirm?token={quote(confirm_token)}"
    unsub_url = f"{cfg.public_base_url}/api/brief-unsubscribe?token={quote(unsub_token)}"
    lines = [f"Your {SERIES} for {pretty} is attached.", ""]
    html_bits = [f"<p>Your {html.escape(SERIES)} for {html.escape(pretty)} is attached.</p>"]
    if enroll_state == "pending":
        lines += [
            "Confirm your place on the daily list:",
            confirm_url,
            "",
        ]
        html_bits.append(
            "<p>Confirm your place on the daily list:<br>"
            f'<a href="{html.escape(confirm_url)}">{html.escape(confirm_url)}</a></p>'
        )
    elif enroll_state == "enrolled":
        lines += ["This address is already enrolled in the daily list.", ""]
        html_bits.append("<p>This address is already enrolled in the daily list.</p>")
    elif enroll_state == "blocked":
        lines += ["This address is unsubscribed, so it was not added to the daily list.", ""]
        html_bits.append("<p>This address is unsubscribed, so it was not added to the daily list.</p>")
    lines += ["Unsubscribe:", unsub_url, "", "Agent U", f"{cfg.public_base_url}/brief/"]
    html_bits.append(
        "<p>Unsubscribe:<br>"
        f'<a href="{html.escape(unsub_url)}">{html.escape(unsub_url)}</a></p>'
        f'<p>Agent U<br><a href="{html.escape(cfg.public_base_url)}/brief/">{html.escape(cfg.public_base_url)}/brief/</a></p>'
    )
    message = EmailMessage()
    message["From"] = _from_header(cfg.mail_from)
    message["To"] = email
    message["Subject"] = f"{SERIES}, {pretty}"
    message["List-Unsubscribe"] = f"<{unsub_url}>"
    message.set_content("\n".join(lines) + "\n")
    message.add_alternative("".join(html_bits), subtype="html")
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    return message


def _apply_enroll(data: dict, email: str, enroll: bool) -> str:
    if not enroll:
        return "skip"
    if _contains(data["unsubscribed"], email):
        return "blocked"
    if _contains(data["bcc"], email):
        return "enrolled"
    if not _contains(data["pending"], email):
        data["pending"].append(email)
    return "pending"


def _apply_confirm(data: dict, email: str) -> str:
    if _contains(data["unsubscribed"], email):
        return "blocked"
    data["pending"] = _drop(data["pending"], email)
    if not _contains(data["bcc"], email):
        data["bcc"].append(email)
    return "ok"


def _apply_unsub(data: dict, email: str) -> None:
    data["pending"] = _drop(data["pending"], email)
    data["bcc"] = _drop(data["bcc"], email)
    if not _contains(data["unsubscribed"], email):
        data["unsubscribed"].append(email)


class BriefApp:
    def __init__(self, cfg: Config, mailer, now: Optional[Callable[[], float]] = None):
        self.cfg = cfg
        self.mailer = mailer
        self.now = now or time.time
        self.limiter = RateLimiter(self.now)

    def request_brief(self, payload, ip: str) -> dict:
        if not isinstance(payload, dict):
            raise BriefError(400, "Request rejected.")
        company = payload.get(HONEYPOT_FIELD, "")
        if isinstance(company, str):
            company = company.strip()
        if company:
            raise BriefError(400, "Request rejected.")
        email = valid_email(payload.get("email"))
        if email is None:
            raise BriefError(400, "Enter a valid email address.")
        if not isinstance(payload.get("enroll"), bool):
            raise BriefError(400, "Enrollment choice is missing.")
        brief_date = payload.get("brief_date")
        if not isinstance(brief_date, str) or not DATE_RE.match(brief_date):
            raise BriefError(400, "Brief date is missing.")
        page = payload.get("page")
        if page is not None and not isinstance(page, str):
            raise BriefError(400, "Request rejected.")
        pdf_path = newest_pdf(self.cfg.pdf_dir)
        if pdf_path is None:
            raise BriefError(503, "Today's brief is not available right now.")
        if self.limiter.check(ip or "unknown", email):
            raise BriefError(429, "Too many requests. Try again later.")
        state = {"value": "skip"}
        if payload["enroll"]:

            def mutate(data: dict) -> None:
                state["value"] = _apply_enroll(data, email, True)

            _mutate_list(self.cfg.subscribers_path, mutate)
        message = build_message(self.cfg, email, pdf_path, state["value"], self.now())
        try:
            self.mailer.send(message)
        except BriefError:
            raise
        except Exception as exc:
            raise BriefError(502, "We could not send the brief. Try again.") from exc
        _append_log(
            self.cfg.request_log,
            {
                "brief_date": brief_date,
                "email": email,
                "enroll": payload["enroll"],
                "ip_hash": ip_hash(self.cfg.confirm_secret, ip or "unknown"),
                "ts": datetime.fromtimestamp(self.now(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        return {"ok": True}

    def confirm(self, token: str) -> tuple[int, str]:
        try:
            email = read_token(self.cfg.confirm_secret, token or "", "confirm", self.now())
        except BriefError as exc:
            return exc.status, _page("Link not valid", "This link is not valid.", "Request the brief again and use the confirm link in that email.")
        outcome = {"value": "ok"}

        def mutate(data: dict) -> None:
            outcome["value"] = _apply_confirm(data, email)

        _mutate_list(self.cfg.subscribers_path, mutate)
        if outcome["value"] == "blocked":
            return 200, _page(
                "Unsubscribed",
                "This address is unsubscribed.",
                "It was not added back to the daily AgentU AI Briefing.",
            )
        return 200, _page(
            "Enrolled",
            "You're enrolled.",
            "This address will receive the daily AgentU AI Briefing.",
        )

    def unsubscribe(self, token: str) -> tuple[int, str]:
        try:
            email = read_token(self.cfg.confirm_secret, token or "", "unsub", self.now())
        except BriefError as exc:
            return exc.status, _page("Link not valid", "This link is not valid.", "Use the unsubscribe link from a brief email.")

        def mutate(data: dict) -> None:
            _apply_unsub(data, email)

        _mutate_list(self.cfg.subscribers_path, mutate)
        return 200, _page(
            "Unsubscribed",
            "You're unsubscribed.",
            "This address will no longer receive the daily AgentU AI Briefing.",
        )


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="referrer" content="no-referrer">
<title>@@TITLE@@ · AgentU AI Briefing</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{--navy:#12193F;--gold:#C6A241;--paper:#F7F3E8;--ink:#1C2135;--slate:#5C6480;--line:#E7E0CF}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 Inter,system-ui,sans-serif}
header{background:var(--navy);color:#fff;padding:22px 24px;border-bottom:1px solid rgba(198,162,65,.5)}
header a{color:#fff;text-decoration:none;font-family:Newsreader,Georgia,serif;font-size:20px;font-weight:600}
main{max-width:560px;margin:0 auto;padding:48px 20px}
h1{font-family:Newsreader,Georgia,serif;font-weight:600;font-size:36px;line-height:1.15;margin:0 0 12px;color:var(--navy)}
p{color:var(--slate);margin:0 0 18px}
a.back{color:var(--navy);font-weight:600}
</style>
</head>
<body>
<header><a href="@@HOME@@">Agent U</a></header>
<main>
<h1>@@HEADING@@</h1>
<p>@@BODY@@</p>
<a class="back" href="@@HOME@@">Back to the briefing</a>
</main>
</body>
</html>
"""


def _page(title: str, heading: str, body: str) -> str:
    page = _PAGE
    page = page.replace("@@TITLE@@", html.escape(title, quote=False))
    page = page.replace("@@HEADING@@", html.escape(heading, quote=False))
    page = page.replace("@@BODY@@", html.escape(body, quote=False))
    page = page.replace("@@HOME@@", "/brief/")
    return page
