#!/usr/bin/env python3
"""HTTP entrypoint for the AgentU brief request service.

Listens on 127.0.0.1:8720. Caddy on agentu.ai reverse-proxies /api/brief-*
to this process. Configuration is read from the environment
(/etc/brief-request.env when started by systemd).
"""

from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from brief_request import BriefApp, BriefError, Config, SMTPMailer

HOST = "127.0.0.1"
PORT = 8720
MAX_BODY = 8192

ROUTES = {
    "/api/brief-request": "request",
    "/api/brief-confirm": "confirm",
    "/api/brief-unsubscribe": "unsubscribe",
}


def make_handler(app: BriefApp):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            path = urlparse(self.path).path
            sys.stderr.write("%s %s %s\n" % (self.log_date_time_string(), self.command, path))

        def _client_ip(self) -> str:
            peer = self.client_address[0]
            if peer in ("127.0.0.1", "::1"):
                forwarded = self.headers.get("X-Forwarded-For", "")
                if forwarded:
                    hop = forwarded.split(",")[0].strip()
                    if hop:
                        return hop[:64]
            return peer

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def _html(self, status: int, page: str) -> None:
            self._send(status, page.encode("utf-8"), "text/html; charset=utf-8")

        def _read_json(self):
            length_raw = self.headers.get("Content-Length", "")
            try:
                length = int(length_raw)
            except ValueError:
                self._json(400, {"ok": False, "error": "Request rejected."})
                return None
            if length <= 0 or length > MAX_BODY:
                self._json(400, {"ok": False, "error": "Request rejected."})
                return None
            raw = self.rfile.read(length)
            content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._json(400, {"ok": False, "error": "Request rejected."})
                return None
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"ok": False, "error": "Request rejected."})
                return None
            return data

        def do_POST(self):
            path = urlparse(self.path).path
            if path != "/api/brief-request":
                if path in ROUTES:
                    self._json(405, {"ok": False, "error": "Request rejected."})
                else:
                    self._json(404, {"ok": False, "error": "Not found."})
                return
            payload = self._read_json()
            if payload is None:
                return
            try:
                result = app.request_brief(payload, self._client_ip())
            except BriefError as exc:
                self._json(exc.status, {"ok": False, "error": exc.message})
                return
            except Exception:
                traceback.print_exc()
                self._json(500, {"ok": False, "error": "Something went wrong. Try again."})
                return
            self._json(200, result)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/brief-confirm":
                token = parse_qs(parsed.query).get("token", [""])[0]
                status, page = app.confirm(token)
                self._html(status, page)
                return
            if parsed.path == "/api/brief-unsubscribe":
                token = parse_qs(parsed.query).get("token", [""])[0]
                status, page = app.unsubscribe(token)
                self._html(status, page)
                return
            if parsed.path in ROUTES:
                self._json(405, {"ok": False, "error": "Request rejected."})
                return
            self._json(404, {"ok": False, "error": "Not found."})

        def do_PUT(self):
            self._json(405, {"ok": False, "error": "Request rejected."})

        def do_DELETE(self):
            self._json(405, {"ok": False, "error": "Request rejected."})

    return Handler


def serve(app: BriefApp, host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    return httpd


def main() -> None:
    try:
        cfg = Config.from_env()
    except BriefError as exc:
        sys.stderr.write(exc.message + "\n")
        sys.exit(2)
    app = BriefApp(cfg, SMTPMailer(cfg))
    httpd = serve(app, HOST, PORT)
    sys.stderr.write(f"brief-request listening on {HOST}:{PORT}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    main()
