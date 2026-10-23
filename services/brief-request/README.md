# AgentU brief request service

Small same-host service for the public brief at `https://agentu.ai/brief/`.
A reader enters an email, and the service emails the newest PDF. If they
leave the enroll box checked, the address is held as pending until they
open the confirm link in that email.

Python standard library only. It listens on `127.0.0.1:8720` and is not
reachable except through Caddy.

## Layout on the server

| Env | Default | Role |
|---|---|---|
| `SUBSCRIBERS_PATH` | `/srv/briefs/agentu-subscribers.json` | AgentU list: `{bcc, unsubscribed, pending}` |
| `REQUEST_LOG` | `/srv/briefs/brief-requests.jsonl` | Append-only send log |
| `PDF_DIR` | `/srv/briefs/pdf` | Files named `<date>.pdf`. The newest name is the one sent |

Do not point `SUBSCRIBERS_PATH` at `daily-model-brief.json`. This service
never reads or writes that file.

`PDF_DIR` is outside the website root. The site deploy does not publish
PDFs, and the brief page has no PDF link.

## Install

```bash
sudo mkdir -p /srv/briefs/pdf /opt/agentu-website
sudo cp -a services/brief-request /opt/agentu-website/services/brief-request
sudo cp /path/to/2026-10-23.pdf /srv/briefs/pdf/2026-10-23.pdf
sudo chown -R www-data:www-data /srv/briefs

sudo install -m 640 -o root -g www-data \
  services/brief-request/brief-request.env.example /etc/brief-request.env
# Replace SMTP_USER, SMTP_PASS, and CONFIRM_SECRET. Leave the placeholders
# only in the example file.

sudo cp services/brief-request/brief-request.service /etc/systemd/system/brief-request.service
sudo systemctl daemon-reload
sudo systemctl enable --now brief-request.service
```

`brief-request.service` runs as `www-data` and loads `/etc/brief-request.env`.

Mail is SES SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`) from
`MAIL_FROM=brief@agentu.ai`. Port 587 uses STARTTLS. Port 465 uses TLS.
`brief@agentu.ai` has to be a verified SES identity.

Confirm and unsubscribe links use `PUBLIC_BASE_URL` (default
`https://agentu.ai`). `CONFIRM_SECRET` signs those links with HMAC-SHA256.
Confirm links expire after 14 days. Unsubscribe links do not expire.

## Caddy

In the `agentu.ai` site block, **before** the general `/api/*` proxy to
`127.0.0.1:8507`:

```
handle /api/brief-* {
	reverse_proxy 127.0.0.1:8720
}
```

`handle` is first match. If this block sits below the general API proxy,
brief posts never reach this service.

## HTTP

`POST /api/brief-request` with JSON:

```json
{"email": "reader@example.com", "enroll": true, "brief_date": "2026-10-23", "page": "/brief/", "company": ""}
```

`company` is the honeypot. A non-empty value is rejected and nothing is
sent or stored.

Limits: 5 requests per IP per rolling hour, and 3 per email per rolling
day. The client IP is the first `X-Forwarded-For` hop when the peer is
localhost (Caddy), otherwise the peer address. The log stores a hash of
that address, not the address itself.

Each accepted send appends one JSON line:
`{ts, email, enroll, ip_hash, brief_date}`.

When `enroll` is true and the address is not already in `bcc` or
`unsubscribed`, it is added to `pending` (deduped). The message includes
a confirm link. `GET /api/brief-confirm?token=...` moves that address
from `pending` to `bcc` and shows a short confirmation page.

An address in `unsubscribed` is never added again. The PDF still goes
out on the request that asked for it.

`GET /api/brief-unsubscribe?token=...` removes the address from `bcc` and
`pending` and adds it to `unsubscribed`.

## Each morning

Copy the new file to `/srv/briefs/pdf/<date>.pdf`. The service attaches
whichever dated PDF sorts last. Republish the HTML with
`scripts/build_agentu_brief.py`. That script writes `/brief/` and
`/brief/<date>/` only. It can also drop a local copy under
`services/brief-request/pdfs/`, which is gitignored and is not the
web root.

## Tests

```bash
python3 -m unittest discover -s services/brief-request/tests -v
```

Tests use a fake mailer. `smtplib` is blocked for the suite, and the
SMTP client is covered with a mock.
