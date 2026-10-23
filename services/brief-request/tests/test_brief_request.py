"""Unit tests for the brief request service. Mail is fake; SMTP cannot connect."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import brief_request  # noqa: E402
from brief_request import (  # noqa: E402
    BriefApp,
    BriefError,
    Config,
    SMTPMailer,
    ip_hash,
    newest_pdf,
    sign_token,
)
from server import serve  # noqa: E402


def setUpModule():
    global _smtp_patches
    _smtp_patches = [
        patch("smtplib.SMTP", side_effect=AssertionError("real smtp blocked")),
        patch("smtplib.SMTP_SSL", side_effect=AssertionError("real smtp blocked")),
    ]
    for item in _smtp_patches:
        item.start()


def tearDownModule():
    for item in _smtp_patches:
        item.stop()


class FakeMailer:
    def __init__(self):
        self.messages = []
        self.fail = False

    def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise RuntimeError("smtp down")
        self.messages.append(message)


class Clock:
    def __init__(self, stamp=1_800_000_000.0):
        self.t = stamp

    def __call__(self):
        return self.t


def plain_body(message: EmailMessage) -> str:
    return message.get_body(preferencelist=("plain",)).get_content()


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.id().replace(".", "_"))
        base = Path(os.environ.get("TMPDIR", "/tmp")) / "brief-request-tests" / self.tmp.name
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)
        self.base = base
        self.pdf_dir = base / "pdf"
        self.pdf_dir.mkdir()
        self.subscribers = base / "agentu-subscribers.json"
        self.log_path = base / "brief-requests.jsonl"
        self.other = base / "daily-model-brief.json"
        self.other.write_text('{"do":"not touch"}\n', encoding="utf-8")
        self.cfg = Config(
            subscribers_path=self.subscribers,
            request_log=self.log_path,
            pdf_dir=self.pdf_dir,
            smtp_host="email-smtp.example.com",
            smtp_port=587,
            smtp_user="replace-me",
            smtp_pass="replace-me",
            mail_from="brief@agentu.ai",
            confirm_secret="test-secret",
            public_base_url="https://agentu.ai",
        )
        self.mailer = FakeMailer()
        self.clock = Clock()
        self.app = BriefApp(self.cfg, self.mailer, now=self.clock)
        self.write_pdf("2026-10-22", b"%PDF-22")
        self.write_pdf("2026-10-23", b"%PDF-23")

    def write_pdf(self, date, content):
        (self.pdf_dir / f"{date}.pdf").write_bytes(content)

    def payload(self, **overrides):
        body = {
            "email": "reader@example.com",
            "enroll": True,
            "brief_date": "2026-10-23",
            "page": "/brief/",
            "company": "",
        }
        body.update(overrides)
        return body

    def lists(self):
        return json.loads(self.subscribers.read_text(encoding="utf-8"))

    def log_rows(self):
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line]

    def test_enroll_goes_to_pending_and_sends_newest_pdf(self):
        result = self.app.request_brief(self.payload(), "203.0.113.10")
        self.assertEqual(result, {"ok": True})
        data = self.lists()
        self.assertEqual(data["pending"], ["reader@example.com"])
        self.assertEqual(data["bcc"], [])
        self.assertEqual(data["unsubscribed"], [])
        self.assertEqual(len(self.mailer.messages), 1)
        message = self.mailer.messages[0]
        self.assertEqual(message["To"], "reader@example.com")
        self.assertEqual(message["Subject"], "AgentU AI Briefing, October 23, 2026")
        self.assertIn("brief@agentu.ai", message["From"])
        body = plain_body(message)
        self.assertIn("/api/brief-confirm?token=", body)
        self.assertIn("/api/brief-unsubscribe?token=", body)
        attachment = message.get_payload()[-1]
        self.assertEqual(attachment.get_filename(), "2026-10-23.pdf")
        self.assertEqual(attachment.get_payload(decode=True), b"%PDF-23")
        row = self.log_rows()[0]
        self.assertEqual(set(row), {"ts", "email", "enroll", "ip_hash", "brief_date"})
        self.assertEqual(row["email"], "reader@example.com")
        self.assertTrue(row["enroll"])
        self.assertEqual(row["brief_date"], "2026-10-23")
        self.assertNotIn("203.0.113.10", self.log_path.read_text(encoding="utf-8"))
        self.assertEqual(row["ip_hash"], ip_hash("test-secret", "203.0.113.10"))
        self.assertEqual(self.other.read_text(encoding="utf-8"), '{"do":"not touch"}\n')

    def test_confirm_moves_pending_to_bcc(self):
        self.app.request_brief(self.payload(), "203.0.113.10")
        token = plain_body(self.mailer.messages[0]).split("/api/brief-confirm?token=", 1)[1].split()[0]
        status, page = self.app.confirm(token)
        self.assertEqual(status, 200)
        self.assertIn("You're enrolled.", page)
        self.assertIn("#12193F", page)
        data = self.lists()
        self.assertEqual(data["bcc"], ["reader@example.com"])
        self.assertEqual(data["pending"], [])

    def test_unsubscribe_then_confirm_does_not_readd(self):
        self.app.request_brief(self.payload(), "203.0.113.11")
        body = plain_body(self.mailer.messages[0])
        confirm = body.split("/api/brief-confirm?token=", 1)[1].split()[0]
        unsub = body.split("/api/brief-unsubscribe?token=", 1)[1].split()[0]
        status, page = self.app.unsubscribe(unsub)
        self.assertEqual(status, 200)
        self.assertIn("You're unsubscribed.", page)
        status, page = self.app.confirm(confirm)
        self.assertEqual(status, 200)
        self.assertIn("not added back", page)
        data = self.lists()
        self.assertEqual(data["unsubscribed"], ["reader@example.com"])
        self.assertEqual(data["bcc"], [])
        self.assertEqual(data["pending"], [])

    def test_unsubscribed_address_is_not_pended_but_pdf_still_sends(self):
        self.subscribers.write_text(
            json.dumps({"bcc": [], "unsubscribed": ["reader@example.com"], "pending": []}),
            encoding="utf-8",
        )
        self.app.request_brief(self.payload(enroll=True), "203.0.113.12")
        data = self.lists()
        self.assertEqual(data["pending"], [])
        self.assertEqual(data["bcc"], [])
        self.assertEqual(data["unsubscribed"], ["reader@example.com"])
        body = plain_body(self.mailer.messages[0])
        self.assertNotIn("/api/brief-confirm?token=", body)
        self.assertIn("not added", body)
        self.assertIn("/api/brief-unsubscribe?token=", body)

    def test_already_enrolled_is_not_duplicated(self):
        self.subscribers.write_text(
            json.dumps({"bcc": ["reader@example.com"], "unsubscribed": [], "pending": []}),
            encoding="utf-8",
        )
        self.app.request_brief(self.payload(email="Reader@Example.com"), "203.0.113.13")
        self.app.request_brief(self.payload(email="reader@example.com"), "203.0.113.14")
        data = self.lists()
        self.assertEqual(data["bcc"], ["reader@example.com"])
        self.assertEqual(data["pending"], [])
        self.assertIn("already enrolled", plain_body(self.mailer.messages[0]))

    def test_enroll_false_sends_pdf_without_pending(self):
        self.app.request_brief(self.payload(enroll=False), "203.0.113.15")
        self.assertFalse(self.subscribers.exists())
        body = plain_body(self.mailer.messages[0])
        self.assertNotIn("/api/brief-confirm?token=", body)
        self.assertIn("/api/brief-unsubscribe?token=", body)
        self.assertFalse(self.log_rows()[0]["enroll"])

    def test_pending_is_deduped(self):
        self.app.request_brief(self.payload(), "203.0.113.16")
        self.clock.t += 10
        self.app.request_brief(self.payload(email="reader@example.com"), "203.0.113.17")
        self.assertEqual(self.lists()["pending"], ["reader@example.com"])

    def test_honeypot_rejects_without_mail_or_log(self):
        with self.assertRaises(BriefError) as caught:
            self.app.request_brief(self.payload(company="https://spam.example"), "203.0.113.18")
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.mailer.messages, [])
        self.assertEqual(self.log_rows(), [])
        self.assertFalse(self.subscribers.exists())

    def test_invalid_email_and_header_injection(self):
        for bad in ("", "nope", "a@b", "a@b.c", "bad y@example.com", "a@example.com\nBcc: x@y.z"):
            with self.assertRaises(BriefError):
                self.app.request_brief(self.payload(email=bad), "203.0.113.19")
        self.assertEqual(self.mailer.messages, [])

    def test_rate_limit_per_ip_and_per_email(self):
        for index in range(5):
            self.app.request_brief(self.payload(email=f"u{index}@example.com"), "203.0.113.20")
        with self.assertRaises(BriefError) as caught:
            self.app.request_brief(self.payload(email="u6@example.com"), "203.0.113.20")
        self.assertEqual(caught.exception.status, 429)
        self.clock.t += 3601
        self.app.request_brief(self.payload(email="later@example.com"), "203.0.113.20")

        for _ in range(3):
            self.clock.t += 1
            self.app.request_brief(self.payload(email="daily@example.com"), f"198.51.100.{self.clock.t % 50}")
        with self.assertRaises(BriefError) as caught:
            self.app.request_brief(self.payload(email="daily@example.com"), "198.51.100.99")
        self.assertEqual(caught.exception.status, 429)
        self.clock.t += 86401
        self.app.request_brief(self.payload(email="daily@example.com"), "198.51.100.99")

    def test_missing_and_legacy_pdf_names(self):
        for path in self.pdf_dir.iterdir():
            path.unlink()
        (self.pdf_dir / "daily-model-brief-2026-10-23.pdf").write_bytes(b"%PDF-old")
        with self.assertRaises(BriefError) as caught:
            self.app.request_brief(self.payload(), "203.0.113.30")
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.mailer.messages, [])
        self.write_pdf("2026-10-01", b"%PDF-old-date")
        self.write_pdf("2026-10-23", b"%PDF-new")
        self.app.request_brief(self.payload(brief_date="2026-10-01"), "203.0.113.31")
        self.assertEqual(self.mailer.messages[0].get_payload()[-1].get_filename(), "2026-10-23.pdf")
        self.assertEqual(self.log_rows()[0]["brief_date"], "2026-10-01")

    def test_mail_failure_does_not_log(self):
        self.mailer.fail = True
        with self.assertRaises(BriefError) as caught:
            self.app.request_brief(self.payload(), "203.0.113.32")
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(self.log_rows(), [])
        self.assertEqual(self.lists()["pending"], ["reader@example.com"])

    def test_bad_and_expired_and_mismatched_tokens(self):
        status, page = self.app.confirm("not-a-token")
        self.assertEqual(status, 400)
        self.assertIn("not valid", page)
        issued = int(self.clock.t)
        confirm = sign_token(self.cfg.confirm_secret, "confirm", "reader@example.com", issued)
        unsub = sign_token(self.cfg.confirm_secret, "unsub", "reader@example.com", issued)
        status, _page = self.app.confirm(unsub)
        self.assertEqual(status, 400)
        self.clock.t += 15 * 24 * 3600
        status, page = self.app.confirm(confirm)
        self.assertEqual(status, 400)
        self.assertIn("not valid", page)
        self.assertFalse(self.subscribers.exists())
        status, page = self.app.unsubscribe(unsub)
        self.assertEqual(status, 200)
        self.assertIn("You're unsubscribed.", page)

    def test_source_does_not_name_the_box_list(self):
        text = Path(brief_request.__file__).read_text(encoding="utf-8")
        self.assertNotIn("daily-model-brief.json", text)
        self.assertIsNone(newest_pdf(self.base / "missing"))

    def test_config_defaults_and_required_secret(self):
        env = {
            "SMTP_HOST": "email-smtp.us-east-1.amazonaws.com",
            "SMTP_USER": "replace-me",
            "SMTP_PASS": "replace-me",
            "CONFIRM_SECRET": "replace-with-a-long-random-string",
        }
        cfg = Config.from_env(env)
        self.assertEqual(cfg.subscribers_path, Path("/srv/briefs/agentu-subscribers.json"))
        self.assertEqual(cfg.request_log, Path("/srv/briefs/brief-requests.jsonl"))
        self.assertEqual(cfg.pdf_dir, Path("/srv/briefs/pdf"))
        self.assertEqual(cfg.mail_from, "brief@agentu.ai")
        self.assertEqual(cfg.smtp_port, 587)
        self.assertEqual(cfg.public_base_url, "https://agentu.ai")
        with self.assertRaises(BriefError):
            Config.from_env({"SMTP_HOST": "h", "SMTP_USER": "u", "SMTP_PASS": "p"})


class SMTPMailerTests(unittest.TestCase):
    def test_starttls_on_587_and_ssl_on_465(self):
        cfg = Config(
            subscribers_path=Path("/tmp/unused.json"),
            request_log=Path("/tmp/unused.jsonl"),
            pdf_dir=Path("/tmp"),
            smtp_host="email-smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_pass="pass",
            mail_from="brief@agentu.ai",
            confirm_secret="s",
        )
        message = EmailMessage()
        message["From"] = "brief@agentu.ai"
        message["To"] = "a@b.co"
        message["Subject"] = "t"
        message.set_content("hi")
        smtp = MagicMock()
        with patch("brief_request.smtplib.SMTP", return_value=smtp) as ctor:
            SMTPMailer(cfg).send(message)
        ctor.assert_called_once_with("email-smtp.example.com", 587, timeout=30)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("user", "pass")
        smtp.send_message.assert_called_once_with(message)
        smtp.quit.assert_called_once()

        cfg.smtp_port = 465
        ssl = MagicMock()
        with patch("brief_request.smtplib.SMTP_SSL", return_value=ssl) as ctor:
            SMTPMailer(cfg).send(message)
        ctor.assert_called_once_with("email-smtp.example.com", 465, timeout=30)
        ssl.starttls.assert_not_called()
        ssl.login.assert_called_once_with("user", "pass")


class HttpTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("TMPDIR", "/tmp")) / "brief-request-http" / self.id()
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)
        pdf_dir = base / "pdf"
        pdf_dir.mkdir(exist_ok=True)
        (pdf_dir / "2026-10-23.pdf").write_bytes(b"%PDF-http")
        cfg = Config(
            subscribers_path=base / "subscribers.json",
            request_log=base / "requests.jsonl",
            pdf_dir=pdf_dir,
            smtp_host="email-smtp.example.com",
            smtp_port=587,
            smtp_user="replace-me",
            smtp_pass="replace-me",
            mail_from="brief@agentu.ai",
            confirm_secret="http-secret",
            public_base_url="https://agentu.ai",
        )
        self.mailer = FakeMailer()
        self.app = BriefApp(cfg, self.mailer, now=Clock())
        self.httpd = serve(self.app, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def post(self, payload, ip="203.0.113.40"):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/brief-request",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Forwarded-For": ip},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_post_confirm_and_unsubscribe_over_http(self):
        status, body = self.post(
            {
                "email": "http@example.com",
                "enroll": True,
                "brief_date": "2026-10-23",
                "page": "/brief/2026-10-23/",
                "company": "",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        text = plain_body(self.mailer.messages[0])
        confirm = text.split("/api/brief-confirm?token=", 1)[1].split()[0]
        unsub = text.split("/api/brief-unsubscribe?token=", 1)[1].split()[0]
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/brief-confirm?token={confirm}") as res:
            page = res.read().decode()
            self.assertEqual(res.status, 200)
            self.assertIn("You're enrolled.", page)
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/brief-unsubscribe?token={unsub}") as res:
            page = res.read().decode()
        self.assertIn("You're unsubscribed.", page)
        logged = (self.app.cfg.request_log.read_text(encoding="utf-8"))
        self.assertNotIn("203.0.113.40", logged)
        self.assertIn(ip_hash("http-secret", "203.0.113.40"), logged)

    def test_honeypot_over_http(self):
        status, body = self.post(
            {
                "email": "http@example.com",
                "enroll": True,
                "brief_date": "2026-10-23",
                "page": "/brief/",
                "company": "bot",
            }
        )
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertEqual(self.mailer.messages, [])


class OpsFileTests(unittest.TestCase):
    def test_unit_env_and_caddy_match_the_hosting_plan(self):
        unit = (ROOT / "brief-request.service").read_text(encoding="utf-8")
        self.assertIn("User=www-data", unit)
        self.assertIn("Group=www-data", unit)
        self.assertIn("EnvironmentFile=/etc/brief-request.env", unit)
        env = (ROOT / "brief-request.env.example").read_text(encoding="utf-8")
        for key in (
            "SUBSCRIBERS_PATH=/srv/briefs/agentu-subscribers.json",
            "REQUEST_LOG=/srv/briefs/brief-requests.jsonl",
            "PDF_DIR=/srv/briefs/pdf",
            "SMTP_HOST=",
            "SMTP_PORT=587",
            "SMTP_USER=replace-me",
            "SMTP_PASS=replace-me",
            "MAIL_FROM=brief@agentu.ai",
            "CONFIRM_SECRET=replace-with-a-long-random-string",
            "PUBLIC_BASE_URL=https://agentu.ai",
        ):
            self.assertIn(key, env)
        self.assertNotIn("daily-model-brief.json", env)
        caddy = (ROOT / "Caddyfile.snippet").read_text(encoding="utf-8")
        self.assertIn("handle /api/brief-*", caddy)
        self.assertIn("reverse_proxy 127.0.0.1:8720", caddy)
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn('HOST = "127.0.0.1"', server)
        self.assertIn("PORT = 8720", server)


if __name__ == "__main__":
    unittest.main()
