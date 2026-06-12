# Retrospective — 2026-06-11 — Frontend F1–F5 (build, deploy, remote validation)

*(Single consolidated retrospective for the session. Adjust headers if `_template.md` differs.)*

## Summary

Built the entire Quanty Database frontend from nothing to production in one session: scaffolded a Next.js 14 app, deployed it to Vercel, and shipped five blocks — status dashboard, remote update trigger, per-indicator reports, and remote downloads — each wired to the worker through server-side proxy routes. The full loop (status → update → report → download) was validated  **remotely from a second machine** , including the large downloads. Objective 1 of the day (a functional frontend that can update and download data remotely) was met.

The worker was untouched; everything this session lives under `apps/web/` plus one decision (31) in `docs/decisions.md`.

## What was done

* **F1 — Scaffold + deploy.** `create-next-app@14` into `apps/web/` (JavaScript, App Router, Tailwind, `src/` dir). Committed, pushed, imported into Vercel with  **Root Directory = `apps/web`** , deployed. Public URL `quanty-database.vercel.app` validated from another device. Deploying early de-risked the pipeline before there was real code.
* **F2 — Status dashboard.** `/api/status` Route Handler proxies the open `/status` endpoint; `page.js` renders a table (freshness badges, `last_date`, `rows`, `updated_at`) with a Refresh button. Added `apps/web/.env.local` (dev) + `.env.example`, repurposed the boilerplate `README.md`, and recorded  **decision 31** .
* **F3 — Remote update.** `/api/run-update/[name]` (POST) injects `X-Worker-Secret` server-side and forwards `?force`. Per-row **Update** button + global **Force** toggle, with inline success/error feedback and auto status-refresh.
* **F4 — Reports.** `/api/report/[name]` proxies the open `/report` endpoint; per-row **Report** button toggles an inline panel (date span, ticker stats, value stats) built from the real fields in `reports.py`, with the `value_column: null` (quotes) case handled.
* **F5 — Downloads.** `/api/download/[name]` and `/api/download-group/[group]` stream the worker's files through with the secret; three buttons (Indicators / Prices / Macro) as plain anchor links. Also fixed the F3 muted-button UX (per-cell muting so absent rows' Update button stays clickable).

All five were committed as separate conventional commits and pushed; Vercel auto-deployed each.

## Decisions made

* **Decision 31** — the frontend has its own env files (`apps/web/.env.local` + `.env.example`), separate from the worker's root `.env`. Driven by the hard fact that Next.js only reads env from its own project root, plus separation of concerns and Vercel's dashboard-based prod env.
* **Route A for downloads** — proxy/stream through the Vercel Route Handler (secret stays off-client, no CORS), rather than a direct-from-ngrok token scheme. Validated: even the large files streamed fine.
* **Gating deferred** — the public site stays ungated for now, by explicit choice; flagged as a pending decision before rollout.
* **Demo with fast indicators** — remote update demoed with `cdi`/`ibov` to stay inside the Vercel function timeout.

## What went well

* **Hybrid pace.** Strict micro-steps for the unfamiliar scaffold/deploy plumbing, then switching to single Claude Code batches once the pattern was clear (F2–F5). Each batch ended at a live, testable milestone.
* **Deploy-early.** Getting the public URL working in F1 meant every later block was testable remotely, not just at the end.
* **The architecture paid off.** Provider-namespaced catalog/storage and the existing endpoint set meant the frontend was pure glue — no worker changes needed.
* **Large downloads just worked.** The main risk going in.

## Surprises / gotchas

* **ngrok free-tier interstitial.** Server-side fetches need `ngrok-skip-browser-warning: true` or ngrok returns a warning HTML page instead of the data. Baked into every proxy route.
* **Next env scope.** Next reads env only from its own root, and only at startup — the dev server must be restarted after `.env.local` changes. This is also why `WORKER_SECRET` is duplicated in three places.
* **Vercel function timeout vs synchronous updates.** A remote `quotes` update (~100s) would exceed the Hobby ~60s function limit; the worker still finishes, but the proxy response times out. Fast indicators are fine. Logged as a pending decision (fire-and-poll pattern later).
* **Large downloads did NOT hit a limit.** Contrary to the pre-build concern, `quotes` (hundreds of MB) and the `indicators` bundle (~94 MB) both downloaded remotely through the streaming proxy. (Still watch ngrok's free monthly transfer cap.)
* **Muted-button confusion.** F2's 40%-opacity on absent rows made the F3 Update button look disabled even though it worked; fixed by muting per-cell instead of per-`<tr>`.

## Open follow-ups

* yfinance provider integration (objective 2) — the planned next session.
* Site gating/auth before rollout to Felipe/Greg.
* Async pattern for large synchronous updates (Vercel timeout).
* Pre-existing worker items unchanged: `bova11` 0-row bug, `momentum_6m` FutureWarning, `varos_bova` date column, B3 holidays, `volatility_252d`/`var_252d_95` not yet produced.
