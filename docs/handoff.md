
# Handoff

This document is updated at the end of every working session so that the next session (human or LLM) can resume exactly where the previous one stopped.

**How to use this document at the start of a new Claude session:**

> "I'm continuing the Quanty Database project. Repo: https://github.com/eduardopfranca/quanty-database. Read `docs/decisions.md` and `docs/handoff.md` in full before doing anything. Then confirm with me what the next step is — do not start writing code."

---

## Last updated

**2026-06-08** — Phase 3.4 (catalog), Phase 3.5 (runner + generic `POST /run-update/{indicator_name}`), Phase 3.6a (business-day calendar), Phase 3.6b (`GET /status`) complete. Storage moved to a dedicated exclusive folder (`C:/Users/eduar/code/quanty-data/`) and namespaced by provider. 11 of 14 indicators populated via a remote end-to-end re-fetch.

---

## Project state

### Done and validated

* **Repo and structure**: monorepo at `github.com/eduardopfranca/quanty-database`, branch `main`.
* **Worker environment**: `apps/worker/.venv` with Python 3.11.2 + dependencies from `requirements.txt`.
* **Worker source files** (all in `apps/worker/src/`):
  * `config.py` — `pydantic-settings` `BaseSettings`. 6 fields: `varos_api_key`, `worker_secret`, `worker_data_dir`, `update_cooldown_hours` (default 6), `log_level`, `log_dir`.
  * `logger.py` — `get_logger(name)` factory with rotating file + console.
  * `business_days.py` — `last_business_day(reference)`: most recent Mon–Fri day on or before `reference` (default: today). No B3 holidays yet. *(Phase 3.6a)*
  * `catalog.py` — `CATALOG[provider][kind][name]` dict. Kinds: `macro`, `raw_bulk`, `raw_fundamental`, `derived`. Public API: `get(name)`, `all_names()`, `by_kind(kind)`. Raises on duplicate names at import time. *(Phase 3.4)*
  * `runner.py` — `run_indicator(name)`: resolves catalog entry → fetch+normalize or load-deps+compute → `storage.save_indicator`. Returns `{indicator, kind, rows, path}`. Derived indicators raise `FileNotFoundError` if a dependency is missing on disk — no auto-fetch. *(Phase 3.5)*
  * `status.py` — `all_status()` / `indicator_status(name)`: cheap per-indicator metadata — mtime, row count from parquet footer, `last_date` from a single-column read. No full data scan. *(Phase 3.6b)*
  * `api.py` — FastAPI app. See endpoints table below.
  * `main.py` — Uvicorn entrypoint, binds `0.0.0.0:8000`.
  * `data/storage.py` — save/load/list/exists/get_indicator_path. Now takes a `provider` argument. Path layout: `WORKER_DATA_DIR/{provider}/{name}.parquet`.
  * `data/normalize.py` — 5 normalizer functions: `varos_quotes`, `varos_indicator`, `varos_cdi`, `varos_ibov`, `varos_bova`.
  * `connections/varos.py` — `VarosClient` with `fetch_quotes`, `fetch_accounting_file`, `fetch_cdi`, `fetch_ibov`, `fetch_bova`. Returns raw DataFrames, no persistence.
  * `compute/` — `graham.py`, `momentum_6m.py`, `volatility_252d.py`, `var_252d_95.py`, `median_volume.py`. Each exposes a `compute(*deps)` function.
* **Tunnel**: ngrok with static domain `https://chowder-marathon-slapping.ngrok-free.dev`. Validated end-to-end from mobile 5G (2026-05-23) and remotely during this session's full re-fetch.
* **Data folder**: `C:/Users/eduar/code/quanty-data/varos/` — dedicated exclusive folder (see decision 23). Files present (11 of 14): `cdi`, `ibov`, `roic`, `quotes`, `eps`, `bvps`, `market_cap`, `ebit_ev`, `median_volume`, `momentum_6m`, `graham`. Missing: `bova11` (bug — see below), `volatility_252d` and `var_252d_95` (not run yet; both depend only on `quotes`, which is present).

### API endpoints

| Method   | Path                            | Auth              | Description                                                                                                                                         |
| -------- | ------------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`    | `/health`                       | none              | Liveness check. Returns `{"status": "ok"}`.                                                                                                        |
| `GET`    | `/status`                       | none              | Per-indicator status for all catalog indicators. Returns list of `{name, provider, kind, present, updated_at, rows, last_date}`. Instant, no data scan. |
| `POST`   | `/run-update/{indicator_name}`  | `X-Worker-Secret` | Produces one indicator and saves its parquet. Returns `{indicator, kind, rows, path}`. Guards: 401/404/409/422/500 (see below).                     |

### Guards on `POST /run-update/{indicator_name}` (in order)

1. **Auth** (`verify_worker_secret` dependency): checks `X-Worker-Secret` header against `settings.worker_secret`. Returns 401 if absent or wrong.
2. **Catalog membership**: `catalog.get(indicator_name)`. Returns 404 if unknown.
3. **Cooldown** (`_check_cooldown`): reads mtime of `{provider}/{name}.parquet`. Returns 409 if `now - mtime < UPDATE_COOLDOWN_HOURS`. No cooldown on first run (file absent → allowed).
4. **Concurrency lock** (`_get_lock`): module-level `asyncio.Lock` per indicator. Returns 409 `"Update already running for indicator '…'"` if the lock is already held.
5. **Missing dependency** (derived only): `storage.load_indicator` raises `FileNotFoundError` if a dependency is not on disk. Returns 422. Dependencies are never auto-fetched.
6. Any other exception returns 500.

### In progress

Nothing in progress.

### Next step

**Phase 3.6c — freshness rule + `force` parameter on `/run-update/{indicator_name}`.**

Define "fresh" as `last_date >= business_days.last_business_day(date.today() - timedelta(days=1))`. Add an optional `force` query parameter to bypass the cooldown when the caller knows the data is stale but within the cooldown window. The freshness gate must not loop forever on indicators that are behind the target because the source itself lags (e.g. CDI).

After 3.6c: the on-demand per-indicator ticker-stats report (mean/median tickers per day, tickers on latest day, distinct total). Then Phase 3.7 (download/packaging).

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
python -m src.data.storage   # saves/loads/lists a dummy DataFrame (uses _selftest_ provider folder)
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

# Auth test (expect 401)
curl.exe -X POST http://localhost:8000/run-update/cdi

# Full update (expect 200 or 409 cooldown)
$secret = (Get-Content C:\Users\eduar\code\quanty-database\.env | Select-String "^WORKER_SECRET=") -replace "^WORKER_SECRET=",""
curl.exe -X POST http://localhost:8000/run-update/cdi -H "X-Worker-Secret: $secret"
```

---

## Pending decisions

None — all open decisions from the previous handoff are resolved.

Session records live in `docs/retrospectives/`.

---

## Known gambiarras and warnings

* **`bova11` fetches 0 rows**: Varos returns an empty response → `varos_bova` raises `KeyError` → `POST /run-update/bova11` returns HTTP 500. Pre-existing bug, surfaced by the generic endpoint. Do not run `bova11` until investigated.
* **`momentum_6m.py` `FutureWarning`**: `pct_change` uses deprecated default `fill_method='ffill'`. One-line fix when convenient: pass `fill_method=None`.
* **`varos_bova` date column is a string**: `varos_bova` does not apply `pd.to_datetime()` to the `date` column, unlike `varos_cdi` and `varos_ibov`. Fix alongside the `bova11` bug.
* **CDI lags behind other indicators**: Varos has not published newer CDI data than what is already saved. Re-fetching will not advance it until Varos publishes. The Phase 3.6c freshness gate must not loop forever on such indicators.
* **`GET /status` has no auth**: The endpoint is currently open (no `X-Worker-Secret`). It exposes only metadata, not raw data. Revisit if the public ngrok URL exposure becomes a concern.
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
15. **Commit (and push) at the end of every session.** The 2026-05-28 batch sat uncommitted for ~10 days. Do not leave a session with a dirty working tree.
16. **Treat `git status` and the actual diffs as ground truth** — above anything a handoff or retrospective claims was done. Verify each file's diff before committing it.
17. **Read the real parquet schema before coding.** During the 2026-06-08 session, checking actual column types revealed the string-vs-timestamp `date` inconsistency across normalizers.

---

## Open items for future phases

* **Frontend (`apps/web/`)**: not started. Will be Next.js 14 on Vercel. It will call the worker via the ngrok tunnel using the `X-Worker-Secret` header. No Supabase Auth planned.
* **Phase 3.6c**: freshness rule + `force` parameter on `/run-update/{indicator_name}`. See Next step above.
* **On-demand ticker-stats report** (after 3.6c): mean/median tickers per day, tickers on latest day, distinct total. Separate from `GET /status` (decision 28).
* **Phase 3.7**: download/packaging of parquet files for analysts.
* **`bova11` bug**: Varos returns 0 rows → `KeyError` in `varos_bova`. Investigate before running.
* **`momentum_6m.py` FutureWarning**: `pct_change(fill_method=...)` is deprecated. One-line fix.
* **`varos_bova` date column**: not converted to datetime. Fix alongside the `bova11` bug.
* **`volatility_252d` and `var_252d_95`**: not yet run. Both depend only on `quotes` (present). Run after cooldown clears.
* **B3 holidays in `business_days.py`**: Mon–Fri only for now. Add when Phase 3.6c freshness gate is built.
* **Data folder taxonomy** (decision 25): deferred until forward-fill stage is designed.
* **Migration of remaining indicators**: 25+ from `MakeIndicator`. Order will be defined when needed.
* **Backup/versioning of parquet files**: not implemented. Each update overwrites the previous.
* **Windows Service for autostart** (Phase 3.10): not started.
