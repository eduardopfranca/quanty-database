
# Handoff

This document is updated at the end of every working session so that the next session (human or LLM) can resume exactly where the previous one stopped.

**How to use this document at the start of a new Claude session:**

> "I'm continuing the Quanty Database project. Repo: https://github.com/eduardopfranca/quanty-database. Read `docs/decisions.md` and `docs/handoff.md` in full before doing anything. Then confirm with me what the next step is — do not start writing code."

---

## Last updated

**2026-06-11** — Frontend Phase F1–F5 complete and deployed. The Next.js 14 frontend (`apps/web/`) is live on Vercel at `https://quanty-database.vercel.app`, wrapping the worker through server-side proxy routes: status dashboard, remote update trigger, per-indicator reports, and downloads (single + grouped). The full loop (status → update → report → download) was validated  **remotely from another machine** , including the large downloads (`quotes`, `indicators` bundle). New decision 31 (frontend has its own env files). Two open items surfaced: the public site is currently  **ungated** , and large **synchronous** updates (e.g. `quotes`) exceed the Vercel function timeout.

---

## Project state

### Done and validated — Worker (`apps/worker/`)

* **Repo and structure** : monorepo at `github.com/eduardopfranca/quanty-database`, branch `main`.
* **Worker environment** : `apps/worker/.venv` with Python 3.11.2 + dependencies from `requirements.txt`.
* **Worker source files** (all in `apps/worker/src/`):
  * `config.py` — `pydantic-settings` `BaseSettings`. 6 fields: `varos_api_key`, `worker_secret`, `worker_data_dir`, `update_cooldown_hours` (default 6), `log_level`, `log_dir`.
  * `logger.py` — `get_logger(name)` factory with rotating file + console.
  * `business_days.py` — `last_business_day(reference)`. Mon–Fri only; no B3 holidays yet.
  * `catalog.py` — `CATALOG[provider][kind][name]` dict. Kinds: `macro`, `raw_bulk`, `raw_fundamental`, `derived`. Public API: `get(name)`, `all_names()`, `by_kind(kind)`. Raises on duplicate names at import time.
  * `runner.py` — `run_indicator(name)`: catalog entry → fetch+normalize or load-deps+compute → `storage.save_indicator`. No auto-fetch of dependencies.
  * `status.py` — `freshness_target()`, `is_fresh(last_date_iso)`, `indicator_status(name)` / `all_status()`. No data scan.
  * `reports.py` — `indicator_report(name)`: one parquet scan; date span, ticker stats, value stats on the auto-detected single value column (`quotes` → `value_column: null`).
  * `downloads.py` — `GROUPS` dict (`indicators`: raw_fundamental + derived; `macro`: macro). `build_group_zip(group)`: `ZIP_STORED` temp zip of present parquets + `manifest.json`.
  * `api.py` — FastAPI app (worker endpoints below).
  * `main.py` — Uvicorn entrypoint, binds `0.0.0.0:8000`.
  * `data/storage.py` — provider-namespaced I/O: `WORKER_DATA_DIR/{provider}/{name}.parquet`.
  * `data/normalize.py` — `varos_quotes`, `varos_indicator`, `varos_cdi`, `varos_ibov`, `varos_bova`.
  * `connections/varos.py` — `VarosClient`.
  * `compute/` — `graham.py`, `momentum_6m.py`, `volatility_252d.py`, `var_252d_95.py`, `median_volume.py`.
* **Tunnel** : ngrok with static domain `https://chowder-marathon-slapping.ngrok-free.dev`.
* **Data folder** : `C:/Users/eduar/code/quanty-data/varos/` — dedicated exclusive folder. 11 of 14 indicators present. Absent: `bova11` (bug), `volatility_252d`, `var_252d_95` (not yet produced; both depend only on `quotes` and can now be produced via the frontend "Update" button).

### Done and validated — Frontend (`apps/web/`)

Next.js 14, App Router,  **JavaScript** , Tailwind, `src/` dir. Pinned at Next 14 (do not run `npm audit fix --force`).

* **Deployed on Vercel** : root directory `apps/web`, production domain `quanty-database.vercel.app`, auto-deploy on push to `main`.
* **Env strategy** (decision 31): `apps/web/.env.local` (gitignored, local dev) + Vercel dashboard (prod). Vars: `WORKER_URL`, `WORKER_SECRET`.
  * Local dev: `WORKER_URL=http://localhost:8000` (talks to the worker directly; no ngrok needed).
  * Vercel: `WORKER_URL=https://chowder-marathon-slapping.ngrok-free.dev` (no trailing slash), `WORKER_SECRET` (Sensitive).
* **All worker calls are proxied server-side** (browser → Vercel → ngrok → worker). This keeps `X-Worker-Secret` off the client and avoids CORS entirely. Every proxy fetch sends the header `ngrok-skip-browser-warning: true` (otherwise ngrok's free-tier interstitial HTML replaces the JSON/stream).
* **Files** :
* `src/app/page.js` — `'use client'` dashboard. Status table (freshness badges, `last_date`, `rows`, `updated_at`), global **Force** toggle, per-row **Update** + **Report** buttons, and a **Downloads** section (3 buttons). Absent rows render muted per-cell but their **Update** button stays full-opacity/clickable.
* `src/app/api/status/route.js` — GET, proxies `/status` (open).
* `src/app/api/run-update/[name]/route.js` — POST, proxies `/run-update/{name}` with `X-Worker-Secret`; forwards `?force=true`. `maxDuration = 60`.
* `src/app/api/report/[name]/route.js` — GET, proxies `/report/{name}` (open).
* `src/app/api/download/[name]/route.js` — GET, streams `/download/{name}` with `X-Worker-Secret` (forwards `content-type`/`content-disposition`/`content-length`).
* `src/app/api/download-group/[group]/route.js` — GET, streams `/download-group/{group}` with `X-Worker-Secret`.
* `.env.example` — committed template documenting `WORKER_URL` + `WORKER_SECRET`.
* `README.md` — practical frontend readme (how to run dev, env vars, Vercel prod, pointer to decision 31).

### Worker API endpoints

| Method   | Path                        | Auth                | Description                                                                              |
| -------- | --------------------------- | ------------------- | ---------------------------------------------------------------------------------------- |
| `GET`  | `/health`                 | none                | Liveness.                                                                                |
| `GET`  | `/status`                 | none                | Cheap per-indicator state for all indicators. No data scan.                              |
| `GET`  | `/report/{name}`          | none                | On-demand full report (scans parquet). 404 for unknown.                                  |
| `POST` | `/run-update/{name}`      | `X-Worker-Secret` | Produces one indicator.`?force=true`bypasses freshness + cooldown.                     |
| `GET`  | `/download/{name}`        | `X-Worker-Secret` | Streams one indicator's parquet.                                                         |
| `GET`  | `/download-group/{group}` | `X-Worker-Secret` | Streams a zip of a group's parquets +`manifest.json`. Groups:`indicators`,`macro`. |

### Frontend proxy routes (Vercel → worker)

| Frontend route                  | Method | Proxies to                         | Secret? |
| ------------------------------- | ------ | ---------------------------------- | ------- |
| `/api/status`                 | GET    | `/status`                        | no      |
| `/api/report/[name]`          | GET    | `/report/{name}`                 | no      |
| `/api/run-update/[name]`      | POST   | `/run-update/{name}`(`?force`) | yes     |
| `/api/download/[name]`        | GET    | `/download/{name}`               | yes     |
| `/api/download-group/[group]` | GET    | `/download-group/{group}`        | yes     |

### In progress

Nothing in progress.

### Next step

**yfinance provider integration (objective 2).** A new data provider added as a `yfinance` node in `CATALOG[provider][kind][name]`, with `connections/yfinance.py`, normalizers, and storage under `WORKER_DATA_DIR/yfinance/`. The architecture (provider-namespaced catalog + storage) was built for exactly this, so the frontend should need only minor extension once new indicators exist. Substantial — its own session.

Before broad rollout to Felipe/Greg: **gate the public site** (see Pending decisions).

---

## How to resume

 **For the public site to be live** , two local processes must be running on Eduardo's PC: the **worker** and  **ngrok** . The Vercel frontend is always-on (no terminal). `npm run dev` is only for local frontend development.

```powershell
# Terminal 1 — worker
cd C:\Users\eduar\code\quanty-database\apps\worker
.\.venv\Scripts\Activate.ps1
python -m src.main          # Worker listening on http://0.0.0.0:8000

# Terminal 2 — ngrok (no venv needed)
ngrok http --url=chowder-marathon-slapping.ngrok-free.dev 8000

# Terminal 3 — frontend (LOCAL DEV ONLY; not needed for the live Vercel site)
cd C:\Users\eduar\code\quanty-database\apps\web
npm run dev                 # http://localhost:3000  (restart it after editing .env.local)
```

Smoke test:

```powershell
# Worker direct
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/status

# Frontend proxy (local dev, worker up)
# browser: http://localhost:3000  → dashboard; click Update on cdi; Report on eps; Macro download

# Production (worker + ngrok up)
# browser/phone: https://quanty-database.vercel.app
```

---

## Pending decisions

* **Site gating / auth.** The Vercel site is currently public and ungated. Because the proxy injects `X-Worker-Secret` server-side  **on behalf of any caller** , anyone with the URL can trigger updates and download proprietary data. Options: Vercel Authentication, a shared password, or basic-auth middleware. Deferred this session by choice; decide before real rollout.
* **Async pattern for large synchronous updates.** The worker is synchronous (decision 3). A `quotes` update (~1m43s) exceeds the Vercel Hobby function limit (~60s), so a **remote** `quotes` update times out at the proxy (the worker still completes the work). Fast indicators (`cdi`, `ibov`, macros) are fine remotely. A "fire and poll `/status`" pattern would fix this without changing the worker's synchronous design.

Session records live in `docs/retrospectives/`.

---

## Known gambiarras and warnings

* **Next.js reads env only from its own project root** (`apps/web/`). It does **not** read the monorepo-root `.env`. `WORKER_SECRET` is therefore duplicated across three places: the worker's root `.env`, `apps/web/.env.local`, and Vercel. (Decision 31.)
* **Restart `npm run dev` after editing `.env.local`** — Next loads env at startup only.
* **`ngrok-skip-browser-warning: true`** is sent on every proxy fetch; without it ngrok's free-tier interstitial HTML replaces the worker's JSON/stream.
* **Vercel function timeout (~60s Hobby) vs synchronous updates** — remote `quotes` update times out (worker finishes anyway). See Pending decisions.
* **Public Vercel site is an ungated proxy holding the secret** — see Pending decisions.
* **Large downloads worked remotely** via the streaming proxy — `quotes` (hundreds of MB) and the `indicators` bundle (~94 MB) both downloaded fine through Vercel → ngrok. The feared free-tier large-file limit did **not** materialize. Watch ngrok's free monthly transfer cap with repeated large downloads.
* **Downloads use plain `<a>` links** to the proxy routes (browser streams straight to disk; no JS buffering). Do not switch to fetch+blob for large files.
* **`bova11` fetches 0 rows** : Varos returns empty → `varos_bova` raises `KeyError` → `POST /run-update/bova11` returns HTTP 500. Do not run until investigated.
* **`momentum_6m.py` `FutureWarning`** : `pct_change` uses deprecated default `fill_method='ffill'`. One-line fix: pass `fill_method=None`.
* **`varos_bova` date column is a string** : unlike `varos_cdi`/`varos_ibov`, it does not apply `pd.to_datetime()`. Fix alongside the `bova11` bug.
* **CDI lags behind other indicators** : source lag — re-fetching won't advance `last_date` until Varos publishes newer data. The freshness gate blocks correctly.
* **Latest day is often sparsely populated** : `tickers_last_day` (from `/report`) can be much lower than the mean per day. Expected.
* **ngrok authtoken** must never be committed (covered by `.gitignore`).
* **An editor markdown auto-formatter** adds a blank line before lists on save (cosmetic whitespace diffs). Harmless.

---

## Lessons for the next Claude session

These are habits Eduardo expects from the assistant. Do not relearn them by being corrected.

1. **Break work into micro-steps** , one per message; wait for confirmation. (When Eduardo asks to "concentrate steps," shift to delegating a defined batch to Claude Code — surface ambiguities *before* writing the prompt, not after.)
2. **Do not add new abstractions without justification.**
3. **Do not create folders containing a single file** — *except* where a framework mandates it (e.g. Next.js App Router route handlers live in `api/<segment>/route.js`; the folder name *is* the URL path).
4. **Do not propose features beyond the current scope.**
5. **When Eduardo objects to a design, take it seriously.**
6. **Read referenced files before suggesting refactors.**
7. **`python -m src.MODULE`** is the only correct way to run worker modules.
8. **Never invent file paths or commands without verifying them in the repo first.**
9. **English everywhere. Do not ask about language preference.**
10. **The Varos API was previously called Fintz.**
11. **Always give complete commands** : navigate + activate venv + run.
12. **PATH reload on Windows after winget/MSI requires reopening the terminal** (restart VS Code).
13. **Do not invent security trade-offs** when Eduardo is already aware — he calibrates the paranoia.
14. **Never probe external services to discover their schema.**
15. **Commit (and push) at the end of every session.**
16. **Treat `git status` and actual diffs as ground truth** — above what any handoff/retrospective claims.
17. **Read the real parquet schema before coding.**
18. **Next.js loads env only from its own project root** ; the monorepo-root `.env` is invisible to it. Restart the dev server after `.env.local` changes.
19. **Proxy all worker calls server-side** (secret off-client + no CORS); send `ngrok-skip-browser-warning` on every fetch. For downloads, use plain anchor links (stream to disk, no buffering).

---

## Open items for future phases

* **yfinance provider (objective 2)** : next step — see above.
* **Site gating / auth** : see Pending decisions.
* **Async update pattern for large updates** (Vercel timeout): see Pending decisions.
* **Custom/personalized batch download** : let the user select indicators by hand for a zip. Planned, not built.
* **`bova11` bug** : Varos returns 0 rows → `KeyError` in `varos_bova`. Investigate before running.
* **`momentum_6m.py` FutureWarning** : one-line fix.
* **`varos_bova` date column** : not converted to datetime. Fix alongside the `bova11` bug.
* **`volatility_252d` and `var_252d_95`** : not yet produced. Both depend only on `quotes` (present) — producible now via the frontend Update button.
* **B3 holidays in `business_days.py`** : Mon–Fri only for now.
* **Data folder taxonomy** (decision 25): deferred until forward-fill stage is designed.
* **Migration of remaining indicators** : 25+ from `MakeIndicator`. Order TBD.
* **Backup/versioning of parquet files** : not implemented. Each update overwrites the previous.
* **Windows Service for autostart** (Phase 3.10): make worker + ngrok start on boot and self-heal, removing the manual two-terminal step.
