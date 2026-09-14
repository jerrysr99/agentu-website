# agentu-website

Production marketing / hybrid console UI for **[agentu.ai](https://agentu.ai)**.

Static assets + same-origin `/api` are served by **Caddy on aiproxy-saas**
(`/var/www/agentu`) — **not** GitHub Pages.

## Hosts

| Role | URL |
|---|---|
| Prod UI | https://agentu.ai |
| Prod POR | https://proxy.agentu.ai |
| DEV | https://agentu.jerrywlambert.com (kept) |

Full cutover record (why not Pages, DNS, Caddy, nightly stop, remotes,
abandoned work): **[docs/CUTOVER.md](docs/CUTOVER.md)**.

## Deploy

```bash
git push github main
```

Self-hosted Actions on aiproxy-saas rsyncs HTML/CSS/JS/assets to the Caddy web
root. `git push origin main` archives only and does **not** go live.

See `CLAUDE.md` (Deploy section) for remotes and runner notes.
