
# Handoff

This document is updated at the end of every working session so that the next session (human or LLM) can resume exactly where the previous one stopped.

**How to use this document at the start of a new Claude session:**

> "I'm continuing the Quanty Database project. Repo: https://github.com/eduardopfranca/quanty-database. Read `docs/decisions.md` and `docs/handoff.md` in full before doing anything. Then confirm with me what the next step is — do not start writing code."

---

## Last updated

**2026-06-08** (second session) — Phase 3.6 complete (freshness gate + `force`); on-demand per-indicator report (`GET /report`); single-indicator download (`GET /download`). End-to-end remote demo from another machine via ngrok: status → report → forced run-update → download.

---

## Project state

### Done and validated

* **Repo and structure**: monorepo at `github.com/eduardopfranca/quanty-database`, branch `main`.
* **Worker environment**: `apps/worker/.venv` with Python 3.11.2 + dependencies from `requirements.txt`.
* **Worker source files** (all in `apps/worker/src/`):
  * `config.py` — `pydantic-settings` `BaseSettings`. 6 fields: `varos_api_key`, `worker_secret`, `worker_data_dir`, `update_cooldown_hours` (default 6), `log_level`, `log_dir`.
  * `logger.py` — `get_logger(name)` factory with rotating file + console.
  * `business_days.py` — `last_business_day(reference)`: most recent Mon–Fri day on or before `reference` (default: today). No B3 holidays yet.
  * `catalog.py` — `CATALOG[provider][kind][name]` dict. Kinds: `macro`, `raw_bulk`, `raw_fundamental`, `derived`. Public API: `get(name)`, `all_names()`, `by_kind(kind)`. Raises on duplicate names at import time.
  * `runner.py` — `run_indicator(name)`: resolves catalog entry → fetch+normalize or load-deps+compute → `storage.save_indicator`. Returns `{indicator, kind, rows, path}`. No auto-fetch of dependencies.
  * `status.py` — `freshness_target()`: returns `last_business_day(date.today() - timedelta(days=1))`. `is_fresh(last_date_iso)`: checks `last_date >= freshness_target()`. `indicator_status(name)` / `all_status()`: cheap metadata from mtime + parquet footer + single-column date read; payload includes `fresh` field.
  * `reports.py` — `indicator_report(name)`: scans the parquet once; returns date span (`first_date`, `last_date`, `n_days`), ticker stats (`tickers_total`, `tickers_mean_per_day`, `tickers_median_per_day`, `tickers_last_day`), and value stats (`value_min/max/mean/median/nulls`) on the auto-detected single value column. Value column = the one numeric non-`date`/`ticker` column; `quotes` has several → `value_column: null`, value stats skipped.
  * `api.py` — FastAPI app. See endpoints table below.
  * `main.py` — Uvicorn entrypoint, binds `0.0.0.0:8000`.
  * `data/storage.py` — save/load/list/exists/get_indicator_path. Provider-namespaced: `WORKER_DATA_DIR/{provider}/{name}.parquet`.
  * `data/normalize.py` — 5 normalizer functions: `varos_quotes`, `varos_indicator`, `varos_cdi`, `varos_ibov`, `varos_bova`.
  * `connections/varos.py` — `VarosClient`: `fetch_quotes`, `fetch_accounting_file`, `fetch_cdi`, `fetch_ibov`, `fetch_bova`. Returns raw DataFrames, no persistence.
  * `compute/` — `graham.py`, `momentum_6m.py`, `volatility_252d.py`, `var_252d_95.py`, `median_volume.py`. Each exposes `compute(*deps)`.
* **Tunnel**: ngrok with static domain `https://chowder-marathon-slapping.ngrok-free.dev`. End-to-end validated (2026-05-23 and again this session).
* **Data folder**: `C:/Users/eduar/code/quanty-data/varos/` — dedicated exclusive folder. Files present (11 of 14): `cdi`, `ibov`, `roic`, `quotes`, `eps`, `bvps`, `market_cap`, `ebit_ev`, `median_volume`, `momentum_6m`, `graham`. Missing: `bova11` (bug — see below), `volatility_252d` and `var_252d_95` (not run yet; both depend only on `quotes`).

### API endpoints

| Method   | Path                            | Auth              | Description                                                                                                                                                                                                   |
| -------- | ------------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`    | `/health`                       | none              | Liveness check. Returns `{"status": "ok"}`.                                                                                                                                                                  |
| `GET`    | `/status`                       | none              | Cheap per-indicator state for all catalog indicators. Returns list of `{name, provider, kind, present, updated_at, rows, last_date, fresh}`. No data scan.                                                    |
| `GET`    | `/report/{name}`                | none              | On-demand full report (scans parquet). Returns date span, ticker stats, value stats on the auto-detected value column. `value_column: null` for `quotes` (multiple numeric columns). 404 for unknown names.   |
| `POST`   | `/run-update/{name}`            | `X-Worker-Secret` | Produces one indicator and saves its parquet. `?force=true` bypasses freshness + cooldown (not auth or lock). Returns `{indicator, kind, rows, path}`. See guards below.                                      |
| `GET`    | `/download/{name}`              | `X-Worker-Secret` | Streams the indicator's parquet as a file download. 404 for unknown or not-yet-produced indicators. Auth via header only — never a query-string token (secrets in URLs leak into logs).                        |

### Guards on `POST /run-update/{name}` (in order)

1. **Auth** (`verify_worker_secret` dependency): checks `X-Worker-Secret` header. Returns 401 if absent or wrong. Always checked, even with `force=true`.
2. **Catalog membership**: `catalog.get(indicator_name)`. Returns 404 if unknown.
3. **Freshness** *(skipped if `force=true`)*: `status.indicator_status()` checks `fresh`. Returns 409 if already fresh (`last_date >= freshness_target()`). Message includes `last_date`, target, and hint to pass `force=true`.
4. **Cooldown** *(skipped if `force=true`)*: reads mtime of `{provider}/{name}.parquet`. Returns 409 if `now - mtime < UPDATE_COOLDOWN_HOURS`.
5. **Concurrency lock** (`_get_lock`): returns 409 if the lock is already held. Never bypassed.
6. **Missing dependency** (derived only): `FileNotFoundError` from `runner.run_indicator` → returns 422. No auto-fetch.
7. Any other exception returns 500.

### In progress

Nothing in progress.

### Next step

**Phase 3.7b — batch / bundle download.**

A single endpoint (e.g. `GET /download-all`) that zips all present parquets and includes a `manifest.json` with their status. Before building, weigh the ngrok free-tier bandwidth: the `quotes` parquet alone is on the order of hundreds of MB, and a full bundle would be much larger. Options include streaming individual downloads via the existing `/download` endpoint, or a proper batch endpoint with a zip. Decide at the start of that session.

After 3.7b: the frontend (`apps/web`, Next.js 14 on Vercel, calling the worker via the tunnel with `X-Worker-Secret` proxied server-side). Windows-service autostart (Phase 3.10) can be done at any time.

---

## How to resume

From the repo root:

```powershell
cd C:\Users\eduar\code\quanty-database\apps\worker
.\.venv\Scripts\Activate.ps1
```

Verify the environment:

```powershell
python -m src.config         # prints 6 settings
python -m src.catalog        # prints indicator count by kind; validates code references
python -m src.logger         # writes INFO/WARNING/ERROR to console and file
python -m src.data.storage   # saves/loads/lists a dummy DataFrame
```

Start the worker:

```powershell
python -m src.main
# Worker listening on http://0.0.0.0:8000
```

Start the ngrok tunnel (separate terminal, venv not required):

```powershell
ngrok http --url=chowder-marathon-slapping.ngrok-free.dev 8000
```

Quick smoke test (worker must be running):

```powershell
# Health check
curl.exe http://localhost:8000/health

# Status — no auth needed
curl.exe http://localhost:8000/status

# Report — no auth needed
curl.exe http://localhost:8000/report/eps

# Auth test for run-update (expect 401)
curl.exe -X POST http://localhost:8000/run-update/cdi

# Forced run-update (bypasses freshness + cooldown)
$secret = (Get-Content C:\Users\eduar\code\quanty-database\.env | Select-String "^WORKER_SECRET=") -replace "^WORKER_SECRET=",""
curl.exe -X POST "http://localhost:8000/run-update/cdi?force=true" -H "X-Worker-Secret: $secret"

# Download
curl.exe -OJ http://localhost:8000/download/eps -H "X-Worker-Secret: $secret"
```

---

## Pending decisions

None.

Session records live in `docs/retrospectives/`.

---

## Known gambiarras and warnings

* **`bova11` fetches 0 rows**: Varos returns an empty response → `varos_bova` raises `KeyError` → `POST /run-update/bova11` returns HTTP 500. Do not run until investigated.
* **`momentum_6m.py` `FutureWarning`**: `pct_change` uses deprecated default `fill_method='ffill'`. One-line fix when convenient: pass `fill_method=None`.
* **`varos_bova` date column is a string**: unlike `varos_cdi`/`varos_ibov`, `varos_bova` does not apply `pd.to_datetime()` to `date`. Fix alongside the `bova11` bug.
* **CDI lags behind other indicators**: Varos has not published newer CDI data. Re-fetching will not advance it. The freshness gate surfaces this as "not fresh" — do not loop. `force=true` will re-fetch but the `last_date` will not advance.
* **Latest day is often sparsely populated**: `tickers_last_day` (from `/report`) can be significantly lower than the mean-per-day (e.g. `eps` showed 303 vs ~544). Expected — the source data for the most recent day is still being updated. The freshness gate checks `last_date`, not completeness.
* **`GET /status` and `GET /report` are open**: no `X-Worker-Secret` required. They expose metadata and statistics, not the raw data. `GET /download` requires the secret. Revisit if ngrok URL exposure becomes a concern.
* **`worker_stdout.txt` / `worker_stderr.txt`**: runtime output files from the worker process. Gitignored.
* **`cloudflared` installed on the system** (winget, 2026-05-23). Inactive. Can be uninstalled. A Cloudflare Zero Trust account and tunnel `quanty-database-worker` are inert — can be deleted.
* **ngrok authtoken** must never be committed to git (covered by `.gitignore`).
* **An editor markdown auto-formatter** adds a blank line before lists on save, producing small cosmetic whitespace diffs. Harmless.

---

## Lessons for the next Claude session

These are habits Eduardo expects from the assistant. Do not relearn them by being corrected.

1. **Break work into micro-steps**, one per message. Do not bundle. Wait for confirmation before moving on.
2. **Do not add new abstractions without justification.** `pydantic-settings` is already in `config.py` — that is fine as-is. The lesson is not to add more layers unprompted.
3. **Do not create folders containing a single file.** Subfolders need ≥2 (ideally ≥3) related files.
4. **Do not propose features beyond v1 scope.** v1 ships 11 indicators + 3 macro references. The other 25+ from `MakeIndicator` migrate later, one at a time.
5. **When Eduardo objects to a design**, take it seriously. His intuitions against over-engineering have been right more often than the assistant's defaults.
6. **Read referenced files before suggesting refactors.** Several mistakes early in the project came from assumptions about code that had not been read.
7. **`python -m src.MODULE` is the correct way to run anything in the worker.** Direct `python src/X.py` breaks imports.
8. **Never invent file paths or commands without verifying them in the repo first.**
9. **English everywhere. Do not ask about language preference.**
10. **The Varos API was previously called Fintz.** Some legacy files still reference `FINTZ` env var. The new project uses `VAROS_API_KEY`.
11. **When running commands during a session, always provide complete steps**: navigate to the folder + activate venv + final command. Do not assume the terminal state is preserved from a previous step.
12. **PATH reload on Windows after installing via winget/MSI requires closing and reopening the terminal.** In VS Code, this means restarting VS Code itself.
13. **Do not invent security trade-offs or hypothetical scenarios** when Eduardo is already aware of the risks. He decides the appropriate level of paranoia.
14. **Never probe external services to discover their schema.** If schema is unknown, ask Eduardo — do not write requests to a live service to trigger error messages.
15. **Commit (and push) at the end of every session.** Do not leave a session with a dirty working tree.
16. **Treat `git status` and the actual diffs as ground truth** — above anything a handoff or retrospective claims was done. Verify each file's diff before committing it.
17. **Read the real parquet schema before coding.** Checking actual column types revealed the string-vs-timestamp `date` inconsistency across normalizers.

---

## Open items for future phases

* **Frontend (`apps/web/`)**: not started. Will be Next.js 14 on Vercel. It will call the worker via the ngrok tunnel with `X-Worker-Secret` proxied server-side. No Supabase Auth planned.
* **Phase 3.7b**: batch/bundle download — zip of all present parquets + `manifest.json`. Weigh ngrok free-tier bandwidth before building; `quotes` alone is hundreds of MB.
* **`bova11` bug**: Varos returns 0 rows → `KeyError` in `varos_bova`. Investigate before running.
* **`momentum_6m.py` FutureWarning**: `pct_change(fill_method=...)` is deprecated. One-line fix.
* **`varos_bova` date column**: not converted to datetime. Fix alongside the `bova11` bug.
* **`volatility_252d` and `var_252d_95`**: not yet run. Both depend only on `quotes` (present). Run after cooldown clears.
* **B3 holidays in `business_days.py`**: Mon–Fri only for now. Add when needed.
* **Data folder taxonomy** (decision 25): deferred until forward-fill stage is designed.
* **Migration of remaining indicators**: 25+ from `MakeIndicator`. Order will be defined when needed.
* **Backup/versioning of parquet files**: not implemented. Each update overwrites the previous.
* **Windows Service for autostart** (Phase 3.10): not started.
