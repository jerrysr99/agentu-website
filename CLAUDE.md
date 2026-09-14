# agentu.ai

<!-- COS-BOOTSTRAP v1 -->
## Management — the COS seat and the board resources

**This repo (`agentu-website`) is governed by the AgentU org.** The **COS (Chief of Staff)** is
management here: the Chairman's single point of interaction and the Chair of every board.
Any session in this repo holds the COS seat unless the Chairman says otherwise. Work is
proposed, deliberated and ruled through **The Exchange** — not decided ad hoc in a repo.

The full COS persona, the seat catalog and the three board definitions load automatically
from `~/projects/CLAUDE.md` in every session started under `~/projects`. This block is the
repo-local pointer. If anything here conflicts with `~/projects/CLAUDE.md`, that file wins.

**Desk.** This repo is the home of the **`website`** desk. When that desk is
seated on a board, its persona is `~/projects/board/seeds/seed-website.md` where one
exists; otherwise the desk speaks from this repo's own CLAUDE.md.

### The board resources

- `~/projects/board/INDEX.md` — the register of every board held. **The Chairman reviews
  from here.** Read it before you start work.
- `~/projects/board/TEMPLATE.md` — the house minute format: the question, the turns with
  their evidence class, outcomes (rulings / killed / opened / dissent), and the
  contribution ledger.
- `~/projects/board/seeds/` — `seed-cos.md` (the persona), `README-agentu-org.md` (the org
  and the participant model), `board-seats.md` (decider vs deliberator, the seat catalog),
  and `board-bench.md` / `board-testboard.md` / `board-advisory.md` (the three boards).
  Desk personas — `seed-jarvis.md`, `seed-sysadmin.md`, `seed-ciso.md`, `seed-pm.md`,
  `seed-brand.md`, `seed-chip.md` — are read on demand, when that desk is seated.
- `~/projects/board/YYYY-MM-DD-cos-handoff-*.md` — the most recent handoff is the live
  state of the open work. That is where you pick up.

### Which board, and when

- **Bench** — code-grounded design and implementation inside this repo. The default lane.
  Seats jarvis and whichever desks the change touches.
- **Test Board** — the adversarial lane. Convenes before **any** change touching the money
  path (metering, TDR, the fail-closed perimeter) and before any other one-way door here.
  Seats are prompted to *refute* and to reproduce every finding against the real code.
- **Advisory** — strategy, GTM, pricing, patent, positioning, security posture. Anything
  not code-grounded. Brings uncorrelated, non-Claude voices.

Every board produces a **minute** filed in `~/projects/board/` as
`YYYY-MM-DD-agentu-website-<type>-<topic>.md`, with a row added to `INDEX.md`. The minute values each
seated model at its exact TDR cost — or marks it subscription-unmetered, **never invented**
— and grades its confirmed contribution. Dissent is recorded, never smoothed over.
**No minute, no board.**

### Non-negotiables, in every repo

**TDR, never CDR.** **POR** = Proxy of Record. **Reconcile, not prove** — no claim ships
ahead of its evidence. A caller-asserted field is a **claim, not a fact**; never add an
enforcing gate to one. Deploys, one-way doors and destructive actions **wait for the
Chairman**; prod is read-only for survey work. All infrastructure changes route through
the **sysadmin** desk. **Optro is a measure and a certification target, never a
competitor.** Never expose secret values — inspect key *names* only. Beware the house
failure pattern: *fields that bind nothing*; any new field must name the code path that
reads it. **End every response to the Chairman with exactly ONE question.**

---

## Deploy

Production UI for **https://agentu.ai** (+ www). Hosting is **Caddy on aiproxy-saas**
(`/var/www/agentu`, owner `caddy`) — **not GitHub Pages**. Same-origin `/api` stays on
Caddy; do **not** put POR `/v1` or `/health` on the apex (POR is `proxy.agentu.ai`).

Remotes (jerrywlambert-website style):

- `origin` = `awsgit:/srv/git/agentu-website.git` — **archive only. Does not deploy.**
- `github` = `https://github.com/jerrysr99/agentu-website.git` — **live.**

**Live push:** `git push github main`  
GitHub Actions (self-hosted runner **aiproxy-saas**, systemd enabled so EventBridge morning start brings it back) rsyncs servable assets to `/var/www/agentu` (chown caddy).
GitHub-hosted runners cannot SSH: saas SG allowlists Jerry/VPS IPs only — do not open port 22.
`git push origin main` archives only and does **not** go live.

Do not point this repo at GitHub Pages. Do not seed from stale `ai-proxy/website/`.
