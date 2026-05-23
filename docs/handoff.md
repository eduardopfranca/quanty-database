# Handoff

This document is updated at the end of every working session so that the next session (human or LLM) can resume exactly where the previous one stopped.

**How to use this document at the start of a new Claude session:**

> "I'm continuing the Quanty Database project. Repo: https://github.com/eduardopfranca/quanty-database. Read `docs/decisions.md` and `docs/handoff.md` in full before doing anything. Then confirm with me what the next step is — do not start writing code."

---

## Last updated

**2026-05-23** — end of session covering Phase 3.3 (5 derived indicators in `compute/`), first functional API (`api.py` + `main.py`), and end-to-end tunnel validation with ngrok.

---

## Project state

### Done and validated

- **Repo and structure**: monorepo at `github.com/eduardopfranca/quanty-database`, branch `main`.
- **Worker environment**: `apps/worker/.venv` with Python 3.11.2 + dependencies from `requirements.txt`.
- **Supabase project**: `quanty-database` (region SP). Two tables:
  - `indicators` — seeded with 14 rows (11 v1 indicators + cdi/ibov/bova11).
  - `indicator_stats` — empty, ready for worker output.
- **Worker source files** (all tested individually):
  - `src/config.py` — `pydantic-settings` `BaseSettings`, validates required vars, creates dirs at boot. See decision 9.
  - `src/logger.py` — `get_logger(name)` factory with rotating file + console.
  - `src/data/storage.py` — save/load/list/exists for parquet files in `WORKER_DATA_DIR`.
  - `src/data/normalize.py` — 5 normalizer functions (`varos_quotes`, `varos_indicator`, `varos_cdi`, `varos_ibov`, `varos_bova`). Fix applied 2026-05-23: `close_adjusted <= 0` values coerced to NA before ffill; redundant `sort_values("date")` call removed.
  - `src/connections/varos.py` — `VarosClient` with `fetch_quotes`, `fetch_accounting_file`, `fetch_cdi`, `fetch_ibov`, `fetch_bova`. Returns raw DataFrames, no persistence.
  - `src/compute/graham.py` — Graham valuation number.
  - `src/compute/momentum_6m.py` — 6-month price momentum.
  - `src/compute/volatility_252d.py` — 252-day annualized volatility.
  - `src/compute/var_252d_95.py` — 252-day historical VaR at 95%.
  - `src/compute/median_volume.py` — 252-day median volume.
  - `src/api.py` — FastAPI app (see endpoints table below). *Committed with this doc update.*
  - `src/main.py` — Uvicorn entrypoint, binds `0.0.0.0:8000`. *Committed with this doc update.*
- **Tunnel**: ngrok with static domain `https://chowder-marathon-slapping.ngrok-free.dev`. Validated end-to-end from a phone on mobile 5G: `GET /run-update/quotes` fetched and saved 4,521,491 rows in ~1m 43s.

### API endpoints (current state of `api.py`)

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | stable | Liveness check. Returns `{"status": "ok"}`. |
| `GET` | `/run-update/quotes` | **temporary** | Fetches quotes from Varos, normalizes, saves to parquet. Returns `{"indicator", "rows", "path"}`. No auth. Will become `POST` with `X-Worker-Secret` header. |

### In progress

Nothing in progress.

### Next step

**Harden `/run-update/quotes` — three changes in one session:**

1. Change `GET /run-update/quotes` to `POST /run-update/quotes`.
2. Add a FastAPI dependency that validates the `X-Worker-Secret` header against `settings.worker_secret`. Return 401 if absent or wrong.
3. Add a concurrency lock (`asyncio.Lock` or module-level `threading.Lock`) that returns 409 if an update is already running.

After this triplet is committed, the next phase is to generalize to `POST /run-update/{indicator_name}` via a catalog (Phase 3.4 + 3.5). Do not start that until the hardening is done.

---

## How to resume

From the repo root:

```powershell
cd C:\Users\eduar\code\quanty-database\apps\worker
.\.venv\Scripts\Activate.ps1
```

Verify the environment:

```powershell
python -m src.config       # prints 7 masked settings
python -m src.logger       # writes INFO/WARNING/ERROR to console and file
python -m src.data.storage # saves/loads/lists a dummy DataFrame
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
Invoke-WebRequest http://localhost:8000/health
Invoke-WebRequest http://localhost:8000/run-update/quotes   # takes ~1-2 min
```

---

## Pending decisions

None. All open questions from previous sessions were resolved.

---

## Known gambiarras and warnings

- **`worker_data_dir` points to `.../database_fintz/data/factor_db`**, which already contains legacy files with Portuguese names (`cotacoes.parquet`, `momento_6_meses.parquet`, etc.). The worker creates parallel English-named files (`quotes.parquet`, `momentum_6m.parquet`, etc.) without overwriting the legacy ones. Eduardo will decide later whether to remove the legacy files.
- **The `.claude/` folder** exists locally as a leftover from a Claude Code sandbox attempt. It is gitignored. Safe to delete when no process is locking it.
- **No `update_jobs` table.** Execution timestamps live in `indicator_stats.updated_at`.
- **Race condition on `GET /run-update/quotes`.** Two simultaneous calls run fetch in parallel and write to the same parquet (last-write-wins). Observed today: two GETs 22s apart, likely Chrome browser prefetch. Fixed in the next step (lock → 409).
- **cloudflared is installed on the system** (via winget, today's session, never removed). It is inactive. Can be uninstalled at any time. A Cloudflare Zero Trust account and a tunnel named `quanty-database-worker` were created today but are inert — can be deleted.
- **ngrok authtoken** gives access to create tunnels on Eduardo's ngrok account. Must never be committed to git (covered by `.gitignore`).
- **Stale comment in `src/main.py`**: module docstring says "so the Cloudflare Tunnel can reach the server". Should say ngrok. Fix when that file is next touched (likely during the POST + auth session).

---

## Lessons for the next Claude session

These are habits Eduardo expects from the assistant. Do not relearn them by being corrected.

1. **Break work into micro-steps**, one per message. Do not bundle. Wait for confirmation before moving on.
2. **Do not add new abstractions without justification.** `pydantic-settings` is already in `config.py` — that is fine as-is. The lesson is not to add more layers unprompted.
3. **Do not create folders containing a single file.** Subfolders need ≥2 (ideally ≥3) related files.
4. **Do not propose features beyond v1 scope.** The v1 has 11 indicators. The other 25+ from `MakeIndicator` migrate later, one at a time.
5. **When Eduardo objects to a design**, take it seriously. His intuitions against over-engineering have been right more often than the assistant's defaults.
6. **Read referenced files before suggesting refactors.** Several mistakes early in the project came from assumptions about code that had not been read.
7. **`python -m src.MODULE` is the correct way to run anything in the worker.** Direct `python src/X.py` breaks imports.
8. **Never invent file paths or commands without verifying them in the repo first.**
9. **English everywhere. Do not ask about language preference.**
10. **The Varos API was previously called Fintz.** Some legacy files still reference `FINTZ` env var. The new project uses `VAROS_API_KEY`.
11. **When running commands during a session, always provide complete steps**: navigate to the folder + activate venv + final command. Do not assume the terminal state is preserved from a previous step.
12. **PATH reload on Windows after installing via winget/MSI requires closing and reopening the terminal.** In VS Code, this means restarting VS Code itself.
13. **Do not invent security trade-offs or hypothetical scenarios** when Eduardo is already aware of the risks. He decides the appropriate level of paranoia.

---

## Open items for future phases

- **Authentication**: `GET /run-update/quotes` has no auth. Next step adds `X-Worker-Secret` header (POST). Phase 4 may add Supabase Auth if external users need access.
- **Frontend (`apps/web/`)**: not started. Will be Next.js 14 on Vercel, reading the indicator catalog from Supabase and calling the worker via the ngrok tunnel.
- **Catalog and orchestrator** (Phase 3.4–3.5): after the endpoint is hardened, generalize `/run-update/{indicator_name}` to resolve dependencies via a catalog.
- **Stats upsert** (Phase 3.6): compute per-indicator stats and upsert to `indicator_stats`.
- **Migration of remaining indicators**: 25+ from `MakeIndicator`. Order will be defined when needed.
- **Backup/versioning of parquet files**: not implemented. Each update overwrites the previous.
- **Windows Service for autostart** (Phase 3.10): not started.
