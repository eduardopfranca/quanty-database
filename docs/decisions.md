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

### 4. Supabase used only for metadata

**Context.** Need a place for the indicator catalog and update statistics.

**Decision.** Supabase Postgres holds two tables: `indicators` (catalog) and `indicator_stats` (per-indicator stats). All raw and derived data lives as local parquet.

**Trade-offs.** No central source of truth for the data itself; each user receives their own copy on demand.

---

## Code organization

### 5. Subfolders by domain inside `src/`

**Decision.** `connections/`, `data/`, `compute/` instead of flat `src/`.

**Rationale.** When a second data provider is added, all provider clients live in `connections/` without restructuring.

---

### 6. One file per derived indicator, raw indicators parameterized

**Context.** Raw indicators (ROIC, EBIT_EV, etc.) share the same Varos endpoint with different parameters. Derived indicators (graham, vol_252d, etc.) each have unique math.

**Decision.**

- Raw tabular indicators: a single download function parameterized by name. Adding a new raw indicator is a single row in the Supabase `indicators` table — no code change.
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

- Worker: FastAPI + pandas + supabase-py.
- Frontend: Next.js 14 (App Router) hosted on Vercel.
- Metadata: Supabase Postgres.
- Tunnel: ngrok (free tier, static `.ngrok-free.dev` domain — see decision 19).

---

## Naming

### 12. Everything in English

**Decision.** Variable names, function names, column names, log messages, and the UI are all in English. No alias layers.

---

### 13. Indicator names in English

**Decision.** The 11 v1 indicators are named:

- Raw: `quotes`, `market_cap`, `roic`, `ebit_ev`, `eps`, `bvps`, `cdi`, `ibov`, `bova11`
- Derived: `graham`, `momentum_6m`, `volatility_252d`, `var_252d_95`, `median_volume`

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

Originally planned to track each update execution. Dropped — synchronous response carries the report directly to the caller. The execution timestamp is captured in `indicator_stats.updated_at`.

---

### 17. No Supabase Storage bucket

Initial plan included a Storage bucket for parquet files. Dropped after egress cost analysis (see decision 2).

---

### 18. No Pyodide or File System Access API

Earlier brainstorm considered running computations in the browser (Pyodide) or reading the user's local folder via the File System Access API. Both dropped in favor of the worker-local-with-tunnel approach.

---

### 20. Cloudflare Zero Trust tunnel (abandoned)

Tried on 2026-05-23. A Cloudflare Zero Trust account was created and a tunnel named `quanty-database-worker` was configured. Abandoned because Cloudflare's free tier no longer provides a stable subdomain without a domain registered in the account (policy changed). The account and the inert tunnel can be deleted at any time without impact to the project.
