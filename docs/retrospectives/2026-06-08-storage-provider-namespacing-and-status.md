---
session: 2026-06-08
slug: storage-provider-namespacing-and-status
---

## Context at start

At the start of this session, the project had recovered the uncommitted 2026-05-28 working set (see `2026-05-28-remove-supabase-and-fix-cooldown.md` for that batch). The declared next step was Phase 3.4: a local indicator catalog. The data folder still pointed at the legacy shared location (`database_fintz/data/factor_db`). Only one hardcoded endpoint existed: `POST /run-update/quotes`.

## What was done

**Batch recovery note.** ~10 days of uncommitted work from 2026-05-28 were first recovered and committed as 7 logical commits before this session's work began. Lesson: verify the real git state, commit incrementally, and do not let work accumulate in the working tree.

**Phase 3.4 — Local indicator catalog (`src/catalog.py`).**

`CATALOG[provider][kind][name]` dict, organized by four kinds: `macro`, `raw_bulk`, `raw_fundamental`, `derived`. Holds data only; turning an entry into actual calls is the runner's job. A `_build_index()` function flattens the catalog at import time and raises on duplicate names — the tripwire for future multi-provider collision. Public API: `get(name)`, `all_names()`, `by_kind(kind)`. The `__main__` block validates all string references against the actual code.

**Phase 3.5 — Runner + generic `POST /run-update/{indicator_name}` (`src/runner.py`, updated `api.py`).**

`run_indicator(name)` resolves the catalog entry and dispatches: fetched kinds (macro, raw_bulk, raw_fundamental) go through VarosClient + normalize; derived kinds load dependencies from disk and compute. Dependency policy: no auto-fetch — if a dependency is missing on disk, `FileNotFoundError` propagates and the endpoint returns 422. The generic `POST /run-update/{indicator_name}` endpoint replaced the hardcoded `/run-update/quotes`; guards order: 401 (auth) → 404 (catalog) → 409 (cooldown) → 409 (lock) → 422 (missing dep) → 500.

**Provider-namespaced storage + dedicated exclusive data folder.**

`storage.py` updated to take a `provider` argument; path layout becomes `WORKER_DATA_DIR/{provider}/{name}.parquet`. Data moved from `database_fintz/factor_db` to `C:/Users/eduar/code/quanty-data/`, a folder exclusive to the worker. The migration was done by **re-fetching every indicator through the live API from another machine (via the ngrok tunnel)** rather than copying files — which also validated the whole pipeline end-to-end, remotely.

**Date standardization for macro normalizers.**

`varos_cdi` and `varos_ibov` already applied `pd.to_datetime()` to the `date` column; `varos_bova` does not (string date remains). The inconsistency was caught by reading the actual parquet schema. Fix is deferred until the `bova11` bug (0-row response) is resolved.

**Phase 3.6a — Business-day calendar (`src/business_days.py`).**

`last_business_day(reference)`: most recent Mon–Fri day on or before `reference`. No B3 holidays yet; the function is the single place where they will be added. `is_business_day(d)` exposed for callers that need it.

**Phase 3.6b — `GET /status` (`src/status.py`, updated `api.py`).**

`indicator_status(name)` derives state cheaply: `present` from `Path.is_file()`, `updated_at` from mtime, `rows` from pyarrow parquet footer (no data read), `last_date` from a single-column read of the `date` column. `all_status()` maps over the full catalog. The endpoint is open (no auth) — revisit if exposure becomes a concern.

## Decisions made or reversed

* **Decision 23** (added): Worker data folder is a dedicated exclusive folder outside the repo. Exclusive ownership makes mtime a reliable state signal. See `docs/decisions.md#23`.
* **Decision 24** (added): Parquet storage namespaced by provider (`{provider}/{name}.parquet`). See `docs/decisions.md#24`.
* **Decision 25** (added): Data-layout vision — per-provider raw folders now; fill/merge taxonomy deferred until the first transformation stage is built. See `docs/decisions.md#25`.
* **Decision 26** (added): Per-indicator state derived from parquet files; no separate store. See `docs/decisions.md#26`.
* **Decision 27** (added): Freshness target = the previous business day (`last_business_day(date.today() - timedelta(days=1))`). See `docs/decisions.md#27`.
* **Decision 28** (added): Heavier ticker statistics live in a separate on-demand report, not in `GET /status`. See `docs/decisions.md#28`.

## Gambiarras & warnings found

* **`bova11` returns 0 rows**: Varos returns an empty response for `fetch_bova` → `varos_bova` raises `KeyError` → `POST /run-update/bova11` returns HTTP 500. Pre-existing; surfaced by the generic endpoint. Do not run until investigated.
* **`momentum_6m.py` `FutureWarning`**: `pct_change` uses deprecated default `fill_method='ffill'`. One-line fix when convenient.
* **`varos_bova` date column is a string**: unlike `varos_cdi`/`varos_ibov`, `varos_bova` does not convert `date` to datetime. Fix when addressing the `bova11` bug.
* **CDI source lag**: CDI's `last_date` trailed the other indicators. Re-fetching will not advance it until Varos publishes newer data. The Phase 3.6c freshness gate must handle this without looping.
* **`GET /status` is open**: No `X-Worker-Secret` on the status endpoint. Exposes metadata only.

## Next step

Phase 3.6c — freshness rule + optional `force` parameter on `POST /run-update/{indicator_name}`. Use `business_days.last_business_day(date.today() - timedelta(days=1))` as the freshness threshold. Do not auto-loop on source-lagged indicators.

After 3.6c: on-demand per-indicator ticker-stats report. Then Phase 3.7 (download/packaging).

## Links

- Commits: TBD (provided by Eduardo after review)
