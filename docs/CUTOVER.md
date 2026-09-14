# agentu.ai domain move / cutover

**Status:** **SHIPPED / CLOSED**  
**Brand QA:** **YES** (2026-09-13 / 2026-09-14 America/Chicago)  
**Canonical sysadmin memo:** `~/projects/sysadmin/requests/2026-09-13-agentu-ai-pages-api-cutover-plan.md`

This file is the website-repo factual record of the move from
`agentu.jerrywlambert.com` (hybrid DEV) to production on **agentu.ai**.
Do not paste secrets or `cpk_` values here.

## Why not GitHub Pages

The console is a hybrid SPA: static UI **plus** same-origin `/api` with
**httpOnly** session cookies. GitHub Pages cannot terminate that `/api`
surface on the apex. Pages was ruled out; Caddy on aiproxy-saas keeps UI and
`/api` on the same origin.

## Hostnames

| Role | Hostname | Notes |
|---|---|---|
| **Prod UI** | `https://agentu.ai` (+ `www`) | Static + same-origin `/api` |
| **Prod POR** | `https://proxy.agentu.ai` | API-only (`/v1/*`, `/health`) |
| **DEV / test** | `https://agentu.jerrywlambert.com` | **Kept** — lasting staging (UI + `/api` + POR) |

Do **not** point coding clients (`ANTHROPIC_BASE_URL`, etc.) at `agentu.ai`
(that is the console UI only). Prod Messages / POR base is `proxy.agentu.ai`.

## DNS (GoDaddy)

| Host | Type | Value |
|---|---|---|
| `@` | A | `52.21.140.15` |
| `www` | CNAME / A | → `agentu.ai` / same IP |
| `proxy` | A | `52.21.140.15` |

- Apex moved off WebsiteBuilder Site.
- **Builder Free:** deleted.
- **Premium:** cancel pending (**May 22, 2027**).

## Caddy (aiproxy-saas)

- **`agentu.ai` / `www.agentu.ai`:** static from `/var/www/agentu` + `/api/*` →
  `127.0.0.1:8507`. **No POR** (`/v1` / `/health`) on apex.
- **`proxy.agentu.ai`:** `/v1/*` + `/health` → `127.0.0.1:8700` only; other
  paths redirect to `https://agentu.ai`.

## Live path / box

- **Web root:** `/var/www/agentu` on **aiproxy-saas** (owner `caddy`)
- **saas EIP:** `52.21.140.15`
- **Nightly stop/start:** historically framed as EventBridge **11pm–7am CT**;
  **last prove (2026-09-13 CHANGELOG):** narrowed to
  `cron(0 0 * * ? *)` stop and `cron(0 6 * * ? *)` start,
  `ScheduleExpressionTimezone: America/Chicago` (midnight–6am CT).
  Schedules: `aiproxy-saas-stop-nightly` / `aiproxy-saas-start-morning`.

## Website repo standup

- **Remotes:**
  - `github` = `https://github.com/jerrysr99/agentu-website.git` — **live**
  - `origin` = `awsgit:/srv/git/agentu-website.git` — archive only (does not deploy)
- **Live push:** `git push github main`
- **Deploy:** GitHub Actions self-hosted runner on **aiproxy-saas** rsyncs
  servable assets to `/var/www/agentu` (see `scripts/deploy-saas.sh`,
  `.github/workflows/deploy.yml`). Runner systemd comes back with morning start.
- **GitHub Pages:** off — do not re-enable for this SPA.
- **Seed:** live `/var/www/agentu` / `_staging` (byte-identical to DEV UI at ship).
  **Not** the stale tree under `ai-proxy/website/`.

## Docs dual-list (ai-proxy)

Prod vs DEV bases dual-listed in ai-proxy docs (commit **`43f54c6`** on
`main`):

- `~/projects/ai-proxy/docs/GATEWAY_ONBOARDING.md`
- `~/projects/ai-proxy/docs/CLAUDE_CODE_POR_THIN_PROVE.md`

## Abandoned

- GitHub Pages seed for the hybrid console
- `api.agentu.ai` hostname (POR is **`proxy.agentu.ai`**)

## Optional follow-ups

- `keys.html` may still mention `jerrywlambert.com` hosts (MCP / base URL
  copy). Update when convenient; not a cutover blocker.
- Residual GoDaddy Website Builder disconnect UI may still be belt-and-suspenders
  after apex DNS move.

## Quick verify (no secrets)

- UI: `https://agentu.ai/` and `https://agentu.ai/version.json`
- Same-origin API path exists under `/api` on apex (auth required for real calls)
- POR health: `https://proxy.agentu.ai/health`
- DEV still up: `https://agentu.jerrywlambert.com/`
