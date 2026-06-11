# Architectural Decisions

A log of the main decisions made during the design of Quanty Database.
Each entry follows the pattern: **Context** → **Options considered** → **Decision** → **Trade-offs accepted**.

The goal is to make the reasoning available to future contributors (including future LLM sessions) so that decisions are not silently reversed.

---

## Architecture

### 1. Worker runs locally, exposed via tunnel

**Context.** The worker downloads data from the Varos API and computes derived indicators. It must be reachable by the frontend hosted on Vercel.

**Options.**

- Worker on Render Free (cloud, 512 MB RAM, cold start).
- Worker on a VPS (~US$5/month).
- Worker running locally on Eduardo's PC, exposed via a tunnel.

**Decision.** Local worker + tunnel (ngrok — see decision 19).

**Trade-offs.** Zero recurring cost and full hardware resources, at the price of requiring Eduardo's machine to be online. Acceptable for internal use with three users.

---

### 2. Parquet files stored locally, not in Supabase Storage

**Context.** Generated parquet files (quotes, indicators) can reach hundreds of MB.

**Options.**

- Supabase Storage with bucket sync.
- Worker writes directly to a local folder.

**Decision.** Local folder (`WORKER_DATA_DIR`).

**Trade-offs.** No egress cost (which would have been the dominant cost). The same folder feeds the existing notebooks, so there is no migration. Users other than Eduardo receive files via browser download triggered by the worker response.

---

### 3. Synchronous response from worker

**Context.** Update jobs take seconds to a few minutes.

**Options.**

- Async job queue with status polling.
- Synchronous HTTP response with the result.

**Decision.** Synchronous.

**Trade-offs.** Simpler implementation, no job state to persist. The user waits for the response; acceptable given the low frequency of updates and the small user base.

---

### 4. Supabase used only for metadata *(superseded by decision 21)*

**Context.** Need a place for the indicator catalog and update statistics.

**Decision.** Supabase Postgres holds two tables: `indicators` (catalog) and `indicator_stats` (per-indicator stats). All raw and derived data lives as local parquet.

**Trade-offs.** No central source of truth for the data itself; each user receives their own copy on demand.

*Superseded 2026-05-28: Supabase removed from the project. See decision 21.*

---

### 23. Worker data folder is a dedicated exclusive folder outside the repo

**Context.** Worker output used to land in `C:/Users/eduar/code/quanty_environment/database_fintz/data/factor_db`, a folder shared with the legacy notebook workflow. Two problems: (1) when another process can write to the same files, the parquet mtime is not a reliable "last updated" signal; (2) the data location is coupled to the legacy notebook, creating unintended dependencies.

**Options considered.**

- Keep the shared `database_fintz/factor_db` folder.
- Store inside the repo (gitignored).
- Dedicated folder outside the repo, exclusive to the worker.

**Decision.** Dedicated exclusive folder outside the repo: `WORKER_DATA_DIR = C:/Users/eduar/code/quanty-data`, driven by `.env`. Inside-repo rejected: a `git clean -fdx` would wipe gitignored data and couples the data location to the code checkout.

**Trade-offs accepted.**

- The path must be explicitly set in `.env` — there is no default. Acceptable for a single-machine setup.
- Key benefit: because the folder is exclusive to the worker, the parquet file mtime becomes a reliable "last updated" signal and no separate state store is needed for that (see decision 26).

---

### 24. Parquet storage namespaced by provider

**Context.** The catalog carries a `provider` per indicator (currently only `varos`). A multi-provider future is anticipated. Flat storage (`WORKER_DATA_DIR/{name}.parquet`) would collide if two providers produced an indicator with the same name.

**Options considered.**

- Flat: `WORKER_DATA_DIR/{name}.parquet`.
- Namespaced by provider: `WORKER_DATA_DIR/{provider}/{name}.parquet`.
- Namespaced by provider and kind (e.g. a `derived/` subfolder within each provider).

**Decision.** `WORKER_DATA_DIR/{provider}/{name}.parquet`. `storage.py` accepts a `provider` argument and remains pure I/O; `runner` and `api` pass the provider from the catalog entry. Within a provider folder, storage stays flat — no kind subfolders. Derived indicators live under their source provider (e.g. `varos/`) because they are computed from that provider's data.

**Trade-offs accepted.**

- Callers must pass `provider` to every `storage.*` call. The catalog entry always carries it, so no extra lookup is needed.
- A per-kind subfolder split (e.g. `varos/derived/`) was deliberately not done: it would open a fuller folder taxonomy question that is better answered when fill/merge stages are built. See decision 25.

---

### 25. Data-layout vision: per-provider raw folders now; fill/merge taxonomy deferred

**Context.** The future pipeline will have raw data per provider, fill/merge transformation stages, and strategy-ready outputs (e.g. a `factor_db`). Designing the full folder structure upfront requires knowing what fill/merge looks like — which is not yet built.

**Decision.** Current state: `WORKER_DATA_DIR/{provider}/{name}.parquet` (per-provider raw). Vision (not yet built): provider-raw folders → fill/merge stages → strategy-ready outputs, possibly produced by an API-triggered process or notebook. The real stage/fill folder taxonomy is deliberately deferred to when forward-fill (the first transformation stage) is built, because derived/filled/merged placement is non-trivial and is best designed against a concrete transformation.

**Trade-offs accepted.** Deferring means no folder structure commitment yet. The risk of premature structure is higher than the cost of renaming folders when fill is concrete.

---

### 26. Per-indicator state derived from parquet files; no separate store

**Context.** The frontend needs per-indicator state: when an indicator was last updated, the latest date in its data, and its row count. Options are a separate store (SQLite / JSON) updated after each run, or deriving state on demand from the parquets.

**Options considered.**

- A separate state store (SQLite or JSON sidecar) written on each successful run.
- Derive on demand from the parquets themselves.

**Decision.** Derive on demand — `updated_at` from file mtime, row count from the parquet footer (cheap metadata read, no data scan), `last_date` from the `date` column (single-column read). Exposed via `GET /status` (`src/status.py`). No separate store. Enabled by: (1) the exclusive data folder (decision 23) makes mtime reliable; (2) no forward-fill in the pipeline means a parquet's max date equals the actual last date in the data. Each future fill stage will be its own parquet whose mtime and max date **are** that stage's state, so the model holds as providers and stages are added.

**Trade-offs accepted.**

- The mtime assumption holds only as long as the data folder remains exclusive to the worker. If another process writes to the folder, mtime becomes unreliable.
- Heavier per-day ticker statistics require a full data scan and are not in `GET /status` — see decision 28.

---

### 27. Freshness target: up to the previous business day

**Context.** The fund needs data updated through the last business day before today. "Fresh" must be defined precisely so the Phase 3.6c freshness gate can decide whether a re-fetch is needed.

**Decision.** An indicator is "fresh" when its `last_date >= business_days.last_business_day(date.today() - timedelta(days=1))` — i.e., its data covers at least through the most recent business day strictly before today. The business-day calendar is Mon–Fri for now (`src/business_days.py`); B3 holidays will be added there when needed, and every call site benefits automatically.

**Note.** Some sources lag (e.g. CDI's latest date trailed the other indicators). An indicator can sit behind the freshness target with no newer data available at the source; the Phase 3.6c freshness gate must not loop forever asking to update such indicators.

**Trade-offs accepted.** "Strictly before today" means today's data is never declared stale on the day it is produced — the gate waits until the following calendar day. This is the correct behavior for an overnight batch process.

---

### 28. Heavier ticker statistics live in a separate on-demand report

**Context.** `GET /status` must respond instantly without reading parquet data. The desired per-indicator ticker metrics — mean and median tickers per day, tickers on the latest day, total distinct tickers — require a full column scan and cannot be derived from file metadata.

**Options considered.**

- Include ticker stats in `GET /status` (blocks on a full data scan).
- Compute at produce-time and cache in the parquet's own footer metadata.
- Expose in a separate on-demand endpoint or report.

**Decision.** `GET /status` carries only cheap metadata-derived fields (mtime, row count from parquet footer, `last_date` from a single-column read). The four ticker metrics go in a separate on-demand per-indicator report, to be built later. The "always-on-hand" footer-metadata approach is to be revisited when that part is built — it may become the preferred design if the per-indicator report proves too slow.

**Trade-offs accepted.** Callers wanting ticker stats must make a separate, slower request. Acceptable: the only current consumers are the frontend (not yet built) and ad-hoc monitoring.

---

### 29. Single-indicator download via an authenticated endpoint

**Context.** Consumers — analysts and the future frontend — need the parquet files on their own machines after an update run.

**Options considered.**

- Serve files from a shared location (cloud storage, Supabase Storage, etc.).
- A dedicated worker endpoint that streams the parquet directly.

**Decision.** `GET /download/{indicator_name}` streams the indicator's parquet as a file download (`FastAPI.FileResponse`, `Content-Disposition: attachment`). It requires the `X-Worker-Secret` header — unlike `GET /status` and `GET /report` (open metadata endpoints), `/download` serves the actual proprietary data. Auth is via **header only, never a query-string token**: secrets in URLs appear in server access logs, browser history, and referrer headers. Returns 404 for unknown indicators or indicators not yet produced.

**Trade-offs accepted.**

- A plain browser `GET` cannot easily add a custom header, so ad-hoc downloads go through `/docs` (the FastAPI Swagger UI) or the future frontend (which will proxy the request server-side). Acceptable for an internal tool with a small user base.
- Batch download (a zip of all indicators + a status manifest) is the logical next step (Phase 3.7b) and is deliberately deferred: over the ngrok free tier, a full bundle — the `quotes` parquet alone is on the order of hundreds of MB — is a real bandwidth concern that should be weighed when it is built.

---

### 30. Grouped batch download by indicator kind

**Context.** The standard consumer routine is to grab all the factor indicators, then prices, then macro references — not one file at a time. A batch endpoint should match this routine rather than expose an arbitrary list.

**Options considered.**

- One endpoint for all indicators at once (a single large zip).
- User-defined selection: a request body lists which indicators to include.
- Groups derived from catalog kinds, with a fixed mapping.

**Decision.** `GET /download-group/{group}` zips a group's present parquets plus a `manifest.json` (each member's full status) and streams the result. Groups are derived from catalog kinds: `indicators` = `raw_fundamental` + `derived`; `macro` = `macro`. Prices (`quotes`, kind `raw_bulk`) are intentionally **not** bundled — `quotes` is large and already compressed; it is served directly via `GET /download/quotes`. The zip uses `ZIP_STORED` (parquets are already compressed internally, so re-deflating wastes CPU without shrinking the file). The temporary zip is cleaned up after the response via FastAPI `BackgroundTasks`. A separate path prefix (`/download-group/`) avoids routing collisions with `GET /download/{indicator_name}`. Requires `X-Worker-Secret`.

**Trade-offs accepted.**

- The `indicators` bundle is on the order of ~94 MB — a real transfer over the ngrok free tier, but accepted for the routine analyst workflow.
- A custom/personalized batch (user picks indicators by hand) is a natural follow-on and is planned but not yet built. See Open items in the handoff.
- Groups are hardcoded in `downloads.GROUPS`; adding a new kind requires updating that dict. Acceptable given the small, stable set of catalog kinds.

---

## Code organization

### 5. Subfolders by domain inside `src/`

**Decision.** `connections/`, `data/`, `compute/` instead of flat `src/`.

**Rationale.** When a second data provider is added, all provider clients live in `connections/` without restructuring.

---

### 6. One file per derived indicator, raw indicators parameterized

**Context.** Raw indicators (ROIC, EBIT_EV, etc.) share the same Varos endpoint with different parameters. Derived indicators (graham, vol_252d, etc.) each have unique math.

**Decision.**

- Raw tabular indicators: a single download function parameterized by name. Adding a new raw indicator is a single row in the indicator catalog — no code change. (The catalog lived in Supabase; after decision 21 it moves to a local form, TBD in Phase 3.4.)
- Derived indicators: one file per indicator in `compute/`.

**Trade-offs.** Avoids duplicating download code for raw indicators while keeping derived math clearly separated.

---

### 7. No abstract base classes

**Decision.** No `Indicator`, `Provider`, or other ABCs. Use plain functions and small classes only where state is genuinely needed.

**Rationale.** Project size and team size do not justify the indirection.

---

### 8. Normalize functions prefixed by provider

**Decision.** Functions named `varos_quotes`, `varos_indicator`, `varos_cdi`, etc., all in a single `data/normalize.py`. Splits into per-provider modules only when the file becomes hard to navigate.

---

## Stack

### 9. pydantic-settings for config

**Context.** Settings module loads environment variables from `.env`.

**Decision.** `pydantic-settings` `BaseSettings` with typed fields and directory auto-creation via `field_validator`.

**History.** The original plan was `python-dotenv` + a plain `Settings` class (simpler dependency, ~30 lines). The implementation used `pydantic-settings` from the very first commit (`cdb4eb7`) and has been running correctly since. Eduardo decided to keep it: "if it's working, it stays."

**Trade-offs.** Adds `pydantic-settings` as a dependency. In return, provides typed field parsing, `.env` file resolution, and `extra="ignore"` safety — features that the plain-`dotenv` approach would have reimplemented manually.

---

### 10. Python 3.11 for the worker

**Decision.** Python 3.11 instead of Eduardo's installed 3.14.

**Rationale.** Mature, stable wheels for pyarrow, pandas, statsmodels on Windows. Matches the version of the legacy notebook.

---

### 11. Stack summary

- Worker: FastAPI + pandas.
- Frontend: Next.js 14 (App Router) hosted on Vercel.
- Metadata: local (parquet mtimes for cooldown; catalog TBD in Phase 3.4 — see decision 21).
- Tunnel: ngrok (free tier, static `.ngrok-free.dev` domain — see decision 19).

---

## Naming

### 12. Everything in English

**Decision.** Variable names, function names, column names, log messages, and the UI are all in English. No alias layers.

---

### 13. Indicator names in English

**Decision.** v1 covers 11 indicators plus 3 macro references (14 named series), all in English:

- Raw indicators (6): `quotes`, `market_cap`, `roic`, `ebit_ev`, `eps`, `bvps`
- Macro references (3): `cdi`, `ibov`, `bova11`
- Derived (5): `graham`, `momentum_6m`, `volatility_252d`, `var_252d_95`, `median_volume`

The Varos API uses Portuguese names internally (e.g. `LPA`, `VPA`, `ValorDeMercado`). The mapping happens in the catalog layer.

---

## Scope

### 14. v1 ships with 11 indicators

**Context.** The legacy `MakeIndicator` class contains 30+ indicators.

**Decision.** Ship v1 with the 5 derived indicators currently used in production strategies (graham, momentum_6m, volatility_252d, var_252d_95, median_volume) plus their raw dependencies. Migrate the remaining indicators incrementally.

---

### 15. Varos client returns raw DataFrames

**Decision.** `VarosClient` methods return raw DataFrames with the original Varos column names. They never persist to disk. Persistence and normalization happen in `data/storage.py` and `data/normalize.py`.

---

## Tunnel provider

### 19. ngrok with static domain over Cloudflare Tunnel

**Context.** The worker runs locally and needs a stable public HTTPS URL so the frontend (Vercel) and other HTTP clients can reach it without knowing Eduardo's home IP.

**Options considered.**

- **Cloudflare Tunnel** (originally chosen): previously offered a stable `.cfargotunnel.com` URL on the free tier. Policy changed — a fixed subdomain now requires a domain registered in the Cloudflare account. Eduardo does not want to buy a domain.
- **ngrok free tier**: offers one static domain per account in the format `*.ngrok-free.dev`, no custom domain required.

**Decision.** ngrok with static domain `chowder-marathon-slapping.ngrok-free.dev`.

**Trade-offs accepted.**

- ngrok is a single point of failure for the tunnel; if ngrok's free tier changes policy, the URL breaks (same risk that affected Cloudflare).
- The domain name contains "ngrok-free" (aesthetic, not functional concern).
- The ngrok authtoken gives access to create tunnels under Eduardo's account. It must never be committed to git (handled by `.gitignore`).

**Validated.** End-to-end test on 2026-05-23: mobile phone on 5G → `GET /run-update/quotes` → 4,521,491 rows downloaded and saved in ~1m 43s.

---

## Dropped ideas

### 16. No `update_jobs` table

Originally planned to track each update execution. Dropped — synchronous response carries the report directly to the caller. The execution timestamp was originally intended for `indicator_stats.updated_at`; after Supabase was removed (decision 21), the cooldown uses the local parquet mtime instead.

---

### 17. No Supabase Storage bucket

Initial plan included a Storage bucket for parquet files. Dropped after egress cost analysis (see decision 2).

---

### 18. No Pyodide or File System Access API

Earlier brainstorm considered running computations in the browser (Pyodide) or reading the user's local folder via the File System Access API. Both dropped in favor of the worker-local-with-tunnel approach.

---

### 20. Cloudflare Zero Trust tunnel (abandoned)

Tried on 2026-05-23. A Cloudflare Zero Trust account was created and a tunnel named `quanty-database-worker` was configured. Abandoned because Cloudflare's free tier no longer provides a stable subdomain without a domain registered in the account (policy changed). The account and the inert tunnel can be deleted at any time without impact to the project.

---

## Supabase removal

### 21. Supabase removed; metadata moves local

**Context.** During the 2026-05-28 session, the cooldown check attempted to query `indicator_stats.updated_at` from Supabase. The table was empty (nothing had ever populated it), and the column name used in the query was wrong. Investigating the real schema would have required writing a probe request to an external service. Eduardo rejected that approach.

**Decision.** Supabase removed from the project. Specifically:

- `supabase-py` removed from `requirements.txt`.
- `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` removed from `config.py` and `.env.example`.
- Cooldown now reads the local parquet mtime (`Path.stat().st_mtime`) via `storage.get_indicator_path()` and `storage.indicator_exists()`. No network call required.
- The `indicators` catalog (14 rows) remains in Supabase but is not used by any current code. It will be migrated to a local form (file format TBD) in Phase 3.4.

**Trade-offs.**

- No shared metadata: the worker's state (when an indicator was last updated) is visible only on Eduardo's machine. Acceptable for the current 3-user, PC-as-server setup.
- Catalog migration to local is deferred. Until Phase 3.4 ships, there is no catalog lookup in the worker code — the `quotes` endpoint is still hardcoded.
- The actual Supabase project (`quanty-database`, region SP) remains intact and can be reconnected if requirements change.


---
## Catalog

### 22. Local indicator catalog as a provider→kind dict

**Context.** Phase 3.4 needed a local form for the indicator catalog (the registry mapping each indicator name to how it is fetched or computed). Decision 21 removed Supabase and left the form open. The catalog must scale toward many indicators and, eventually, multiple providers — without per-indicator code or becoming a flat mess.

**Options considered.**

- SQLite table — queryable, but a database for read-only static config, and it reverses the simplification of decision 21.
- JSON file — data/code split and frontend-editable, but forces a string→function dispatch and separates the data from the resolver code.
- Python dict module (`src/catalog.py`).

**Decision.** A Python dict in `src/catalog.py`, organized as `CATALOG[provider][kind][name]`. The catalog holds **data only**; turning an entry into fetch/normalize/compute calls is the orchestrator's job (Phase 3.5). Key points:

- Per-indicator **data** is separated from per-(provider, kind) **logic**. Raw fundamentals share one fetch path + normalizer, so each is a single data row (Varos code + `data_type`, no code). Derived `compute` is resolved by convention (`src/compute/<name>.py`). Macro and the bulk quotes are bespoke (own fetch method + normalizer).
- `provider` and `kind` come from position in the nesting, not repeated per entry.
- Names must be unique (a build-time index raises on collision) — the tripwire for adding provider-qualified lookup when a second provider arrives.

**Trade-offs accepted.**

- The catalog stores strings (method/normalizer names), resolved later via `getattr`/`importlib`, instead of direct function references. Deliberate: it keeps the module import-light and lets the bulk of indicators (raw fundamentals) be pure data rows, which is what scales.
- Static config lives in code, so a non-dev cannot add an indicator. Acceptable: adding a derived needs code anyway, and the frontend gets the catalog via a worker endpoint, not by reading the file.
- Multi-provider machinery (per-provider adapters, splitting into a `catalog/` package) is intentionally not built yet; the structure accommodates it without rework.

---

## Frontend

### 31. Frontend has its own env files, separate from the worker's root .env

**Context.** The worker reads `.env` at the repo root (`VAROS_API_KEY`, `WORKER_SECRET`, `WORKER_DATA_DIR`, etc.). The Next.js frontend in `apps/web/` also needs configuration (`WORKER_URL` now; `WORKER_SECRET` later for authenticated endpoints). The question was whether the frontend should reuse the root `.env` or have its own.

**Options considered.**

- Reuse the root `.env` for both worker and frontend.
- Give the frontend its own env files under `apps/web/`.

**Decision.** The frontend has its own env files under `apps/web/`: `.env.local` (gitignored, local dev) and `.env.example` (committed template). Reasons: (1) Next.js only loads env files from its own project root (`apps/web/`) — it does not read the monorepo-root `.env` without extra machinery; (2) separation of concerns — the frontend has no business holding `VAROS_API_KEY` or `WORKER_DATA_DIR`; (3) production env vars on Vercel are set in the Vercel dashboard, read from no file at all. The frontend's source of truth is `apps/web/.env.local` (dev) + the Vercel dashboard (prod).

**Trade-offs accepted.** `WORKER_SECRET` is duplicated across the worker's root `.env`, the frontend's env, and Vercel — consumed by different processes in different places. There is no single secrets source across a Python worker, a Next.js app, and Vercel without a secrets manager, which is overkill for a 3-user internal tool.
