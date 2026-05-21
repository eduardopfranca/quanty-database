# Handoff

This document is updated at the end of every working session so that the next session (human or LLM) can resume exactly where the previous one stopped.

**How to use this document at the start of a new Claude session:**

> "I'm continuing the Quanty Database project. Repo: https://github.com/eduardopfranca/quanty-database. Read `docs/decisions.md` and `docs/handoff.md` in full before doing anything. Then confirm with me what the next step is — do not start writing code."

---

## Last updated

**2026-05-21** — end of session covering Phase 3.2 (config, logger, storage, varos client, normalize).

---

## Project state

### Done and validated

- **Repo and structure**: monorepo at `github.com/eduardopfranca/quanty-database`, branch `main`.
- **Worker environment**: `apps/worker/.venv` with Python 3.11.2 + dependencies from `requirements.txt`.
- **Supabase project**: `quanty-database` (region SP). Two tables:
  - `indicators` — seeded with 14 rows (11 v1 indicators + cdi/ibov/bova11).
  - `indicator_stats` — empty, ready to be populated by the worker.
- **Worker source files** (all tested individually):
  - `src/config.py` — `load_dotenv` + Settings class, validates required vars, creates dirs.
  - `src/logger.py` — `get_logger(name)` factory with rotating file + console.
  - `src/data/storage.py` — save/load/list/exists for parquet files in `WORKER_DATA_DIR`.
  - `src/data/normalize.py` — 5 normalizer functions (`varos_quotes`, `varos_indicator`, `varos_cdi`, `varos_ibov`, `varos_bova`).
  - `src/connections/varos.py` — `VarosClient` with `fetch_quotes`, `fetch_accounting_file`, `fetch_cdi`, `fetch_ibov`, `fetch_bova`. Returns raw DataFrames, no persistence.

### In progress

Nothing in progress.

### Next step

**Phase 3.3 — Create `src/compute/` with the 5 derived indicator functions.**

Order:

1. `compute/graham.py` — port from `MakeIndicator.graham_valuation`.
2. `compute/momentum.py` — port from `MakeIndicator.momentum_indicator`.
3. `compute/volatility.py` — port from `MakeIndicator.annualized_volatility`.
4. `compute/var_historical.py` — port from `MakeIndicator.historical_simulation_var`.
5. `compute/median_volume.py` — port from `MakeIndicator.median_volume`.

Each function should:

- Take normalized DataFrames as input (not file paths).
- Return a DataFrame with columns `[date, ticker, value]`.
- Be a pure function — no I/O.
- Have a `__main__` block that loads inputs from local parquet (using `storage.load_indicator`) and prints the result, for standalone testing.

After `compute/`, the next phases are:

- **3.4** — `catalog.py` (declarative registry of indicators and their dependencies).
- **3.5** — `orchestrator.py` (resolve dependencies, fetch raw, compute derived, return report).
- **3.6** — `stats.py` (compute per-indicator stats, upsert to `indicator_stats`).
- **3.7** — `api.py` (FastAPI: `/run-update`, `/health`, `/indicators`).
- **3.8** — `main.py` (uvicorn entrypoint).
- **3.9** — Cloudflare Tunnel setup.
- **3.10** — Windows Service for autostart.

---

## How to resume

From the repo root:

```powershell
cd C:\Users\eduar\code\quanty-database\apps\worker
.\.venv\Scripts\Activate.ps1
python -m src.config       # should print 7 masked settings
python -m src.logger       # should write INFO/WARNING/ERROR to console and file
python -m src.data.storage # should save/load/list a dummy DataFrame
python -m src.data.normalize  # hits Varos API, normalizes CDI/IBOV/ROIC
```

If all four pass, the environment is healthy and you can proceed to Phase 3.3.

---

## Pending decisions

None at the moment. All open questions from previous sessions were resolved.

---

## Known gambiarras and warnings

- **`worker_data_dir` points to `.../database_fintz/data/factor_db`**, which already contains files from the legacy project with Portuguese names (`cotacoes.parquet`, `momento_6_meses.parquet`, `vol_252.parquet`, `volume_mediano.parquet`, `var_252_95.parquet`, `ValorDeMercado.parquet`, `EBIT_EV.parquet`). When the worker runs, it will create parallel files in English (`quotes.parquet`, `momentum_6m.parquet`, etc.) without overwriting the legacy ones. Eduardo will decide later whether to clean up the legacy files.
- **The `.claude/` folder** exists locally as a leftover from a Claude Code sandbox attempt. It is gitignored. Safe to delete when no process is locking it.
- **No `update_jobs` table.** Execution timestamps live in `indicator_stats.updated_at`. If detailed execution history becomes useful (e.g. for debugging failed runs), add the table back.

---

## Lessons for the next Claude session

These are habits Eduardo expects from the assistant. Do not relearn them by being corrected.

1. **Break work into micro-steps**, one per message. Do not bundle. Wait for confirmation before moving on.
2. **Do not suggest pydantic-settings, ABCs, Pydantic models, or other "best practice" abstractions** without checking that the project size justifies them. Default to plain functions and `load_dotenv`.
3. **Do not create folders containing a single file.** Subfolders need ≥2 (ideally ≥3) related files.
4. **Do not propose features beyond v1 scope.** The v1 has 11 indicators. The other 25+ from `MakeIndicator` migrate later, one at a time.
5. **When Eduardo objects to a design**, take it seriously. His intuitions against over-engineering have been right more often than the assistant's defaults.
6. **Read referenced files before suggesting refactors.** Several mistakes early in the project came from assumptions about code that had not been read.
7. **`python -m src.MODULE` is the correct way to run anything in the worker.** Direct `python src/X.py` breaks imports.
8. **Never invent file paths or commands without verifying them in the repo first.**
9. **English everywhere. Do not ask about language preference.**
10. **The Varos API was previously called Fintz.** Some legacy files still reference `FINTZ` env var. The new project uses `VAROS_API_KEY`.

---

## Open items for future phases

- **Authentication**: currently only `WORKER_SECRET` shared header. Phase 4 may need Supabase Auth for the frontend if external access is needed.
- **Frontend (`apps/web/`)**: not started. Will be Next.js 14 on Vercel, reading the indicator catalog from Supabase and calling the worker via tunnel.
- **Concurrency**: orchestrator should refuse a second update while one is already running (simple lock, no queue).
- **Migration of remaining indicators**: 25+ from `MakeIndicator`. Order will be defined when needed.
- **Backup/versioning of parquet files**: not implemented. Each update overwrites the previous.
