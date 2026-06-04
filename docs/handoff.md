
# Handoff

This document is updated at the end of every working session so that the next session (human or LLM) can resume exactly where the previous one stopped.

**How to use this document at the start of a new Claude session:**

> "I'm continuing the Quanty Database project. Repo: https://github.com/eduardopfranca/quanty-database. Read `docs/decisions.md` and `docs/handoff.md` in full before doing anything. Then confirm with me what the next step is — do not start writing code."

---

## Last updated

**2026-06-04** — recovered the uncommitted 2026-05-28 working set and committed it as 7 logical commits (Supabase removal, endpoint hardening, doc updates), repaired a botched README, and made `decisions.md` internally consistent. All pushed to `origin/main`.

---

## Project state

### Done and validated

* **Repo and structure** : monorepo at `github.com/eduardopfranca/quanty-database`, branch `main`. Working tree clean and in sync with `origin/main` as of 2026-06-04.
* **Worker environment** : `apps/worker/.venv` with Python 3.11.2 + dependencies from `requirements.txt` (no `supabase-py`).
* **Worker source files** (all tested individually):
  * `src/config.py` — `pydantic-settings` `BaseSettings`. 6 fields: `varos_api_key`, `worker_secret`, `worker_data_dir`, `update_cooldown_hours` (default 6), `log_level`, `log_dir`. No Supabase fields.
  * `src/logger.py` — `get_logger(name)` factory with rotating file + console.
  * `src/data/storage.py` — save/load/list/exists + `get_indicator_path()` for parquet files in `WORKER_DATA_DIR`.
  * `src/data/normalize.py` — 5 normalizer functions (`varos_quotes`, `varos_indicator`, `varos_cdi`, `varos_ibov`, `varos_bova`).
  * `src/connections/varos.py` — `VarosClient` with `fetch_quotes`, `fetch_accounting_file`, `fetch_cdi`, `fetch_ibov`, `fetch_bova`. Returns raw DataFrames, no persistence.
  * `src/compute/graham.py`, `momentum_6m.py`, `volatility_252d.py`, `var_252d_95.py`, `median_volume.py` — 5 derived indicator functions.
  * `src/api.py` — hardened FastAPI app (see endpoints table below).
  * `src/main.py` — Uvicorn entrypoint, binds `0.0.0.0:8000`.
* **Tunnel** : ngrok with static domain `https://chowder-marathon-slapping.ngrok-free.dev`. Validated end-to-end from mobile 5G (2026-05-23): ~4.5M rows in ~1m 43s.

### Git hygiene (2026-06-04)

The entire 2026-05-28 working set had been sitting **uncommitted** for ~10 days; `origin/main` was still the pre-Supabase-removal state. It is now committed and pushed as 7 logical commits:

1. `chore: gitignore worker output, fix stale data-files comment`
2. `feat: harden /run-update/quotes (POST, auth, cooldown, lock)`
3. `refactor: drop Supabase config and dependency`
4. `docs: reflect Supabase removal and ngrok tunnel`
5. `docs: add session retrospectives`
6. `docs: update README to current state (drop Supabase, refresh tree)`
7. `docs: fix decision 6 Supabase ref and clarify v1 indicator count`

### API endpoints

| Method   | Path                   | Auth                      | Description                                                                                                                                                 |
| -------- | ---------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/health`            | none                      | Liveness check. Returns `{"status": "ok"}`.                                                                                                               |
| `POST` | `/run-update/quotes` | `X-Worker-Secret`header | Fetches quotes from Varos, normalizes, saves to parquet. Returns `{"indicator", "rows", "path"}`. Guards: 401 (bad/missing auth), 409 (cooldown or lock). |

### Guards on `POST /run-update/quotes` (in order)

1. **Auth** (`verify_worker_secret` dependency): checks `X-Worker-Secret` header against `settings.worker_secret`. Returns 401 if absent or wrong.
2. **Cooldown** (`_check_cooldown`): reads mtime of `quotes.parquet` via `storage.get_indicator_path()`. Returns 409 if `now - mtime < UPDATE_COOLDOWN_HOURS`. If the file doesn't exist, proceeds (no cooldown on first run).
3. **Concurrency lock** (`_get_lock`): module-level `asyncio.Lock` per indicator. Returns 409 `"Update already running for indicator 'quotes'"` if the lock is already held.

### In progress

Nothing in progress.

### Next step

**Phase 3.4 — local indicator catalog.**

The `indicators` catalog (14 rows) is still nominally in Supabase but is **not used by any code** (and Supabase is no longer a dependency of the worker). Migrate it to a local form so the worker can look up indicator metadata without a database.

**The form is an open decision** (see Pending decisions): candidates are a SQLite file, a JSON file, or a Python dict/module. There is  **no SQLite — or any local metadata store — in the repo yet** ; do not assume one exists. Whatever form is chosen must be recorded as a new decision in `decisions.md` (do not silently introduce it).

After the catalog, **Phase 3.5** will generalize `/run-update/quotes` to `/run-update/{indicator_name}` using the catalog.

---

## How to resume

From the repo root:

```powershell
cd C:\Users\eduar\code\quanty-database\apps\worker
.\.venv\Scripts\Activate.ps1
```

Verify the environment:

```powershell
python -m src.config       # prints 6 settings (no Supabase fields)
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
# Health check
curl.exe http://localhost:8000/health

# Auth test (expect 401)
curl.exe -X POST http://localhost:8000/run-update/quotes

# Full update (expect 200 or 409 cooldown; ~2 min if 200)
$secret = (Get-Content C:\Users\eduar\code\quanty-database\.env | Select-String "^WORKER_SECRET=") -replace "^WORKER_SECRET=",""
curl.exe -X POST http://localhost:8000/run-update/quotes -H "X-Worker-Secret: $secret"
```

---

## Pending decisions

* **Phase 3.4 catalog form** — SQLite file vs JSON file vs Python dict/module. To be decided at the start of Phase 3.4 and recorded as a new decision in `decisions.md`.

Session records live in `docs/retrospectives/`.

---

## Known gambiarras and warnings

* **`worker_data_dir` points to `.../database_fintz/data/factor_db`** , which contains legacy Portuguese-named files (`cotacoes.parquet`, etc.). The worker creates parallel English-named files (`quotes.parquet`, etc.) without overwriting the legacy ones. Eduardo will decide later whether to remove the legacy files.
* **`worker_stdout.txt` / `worker_stderr.txt`** are runtime output from the worker process. Gitignored as of 2026-06-04.
* **The `.claude/` folder** exists locally as a leftover from a Claude Code sandbox attempt. It is gitignored. Safe to delete when no process is locking it.
* **cloudflared is installed on the system** (winget, 2026-05-23). Inactive. Can be uninstalled. A Cloudflare Zero Trust account and tunnel `quanty-database-worker` are inert — can be deleted.
* **ngrok authtoken** must never be committed to git (covered by `.gitignore`).
* **Cooldown is tied to parquet mtime** , not a real "last successful update" record. If the parquet is written by another process (e.g. a legacy notebook), the cooldown clock resets. Acceptable for now; revisit in Phase 3.4 if it causes confusion.
* **An editor markdown auto-formatter** adds a blank line before lists on save, so editing `.md` files can produce small cosmetic whitespace diffs. Harmless.

---

## Lessons for the next Claude session

These are habits Eduardo expects from the assistant. Do not relearn them by being corrected.

1. **Break work into micro-steps** , one per message. Do not bundle. Wait for confirmation before moving on.
2. **Do not add new abstractions without justification.** `pydantic-settings` is already in `config.py` — that is fine as-is. The lesson is not to add more layers unprompted.
3. **Do not create folders containing a single file.** Subfolders need ≥2 (ideally ≥3) related files.
4. **Do not propose features beyond v1 scope.** v1 ships 11 indicators + 3 macro references. The other 25+ from `MakeIndicator` migrate later, one at a time.
5. **When Eduardo objects to a design** , take it seriously. His intuitions against over-engineering have been right more often than the assistant's defaults.
6. **Read referenced files before suggesting refactors.** Several mistakes early in the project came from assumptions about code that had not been read.
7. **`python -m src.MODULE` is the correct way to run anything in the worker.** Direct `python src/X.py` breaks imports.
8. **Never invent file paths or commands without verifying them in the repo first.**
9. **English everywhere. Do not ask about language preference.**
10. **The Varos API was previously called Fintz.** Some legacy files still reference `FINTZ` env var. The new project uses `VAROS_API_KEY`.
11. **When running commands during a session, always provide complete steps** : navigate to the folder + activate venv + final command. Do not assume the terminal state is preserved from a previous step.
12. **PATH reload on Windows after installing via winget/MSI requires closing and reopening the terminal.** In VS Code, this means restarting VS Code itself.
13. **Do not invent security trade-offs or hypothetical scenarios** when Eduardo is already aware of the risks. He decides the appropriate level of paranoia.
14. **Never probe external services to discover their schema.** If schema is unknown, ask Eduardo — do not write requests to a live service to trigger error messages.
15. **Commit (and push) at the end of every session.** The 2026-05-28 batch sat uncommitted for ~10 days, which is how the docs drifted from reality. Do not leave a session with a dirty working tree.
16. **Treat `git status` and the actual diffs as ground truth — above anything a handoff or retrospective claims was done.** This session, the 2026-05-28 retrospective said the endpoint hardening and a Supabase import removal had been committed to `api.py`; `git` showed they had not. Verify each file's diff before committing it.

---

## Open items for future phases

* **Frontend (`apps/web/`)** : not started. Will be Next.js 14 on Vercel. It will call the worker via the ngrok tunnel using the `X-Worker-Secret` header. No Supabase Auth planned.
* **Catalog** (Phase 3.4): migrate the 14-row `indicators` catalog from Supabase to a local form. Form TBD (see Pending decisions).
* **Orchestrator** (Phase 3.5): generalize `/run-update/{indicator_name}` to resolve dependencies via the local catalog.
* **Stats / completeness report** (Phase 3.6): per-indicator stats (row count, last date, ticker count). Now that Supabase is gone, the output form is TBD — could be a local JSON sidecar, logged to the response, or deferred further.
* **Migration of remaining indicators** : 25+ from `MakeIndicator`. Order will be defined when needed.
* **Backup/versioning of parquet files** : not implemented. Each update overwrites the previous.
* **Windows Service for autostart** (Phase 3.10): not started.
