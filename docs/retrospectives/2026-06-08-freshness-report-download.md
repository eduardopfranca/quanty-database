---
session: 2026-06-08
slug: freshness-report-download
---

## Context at start

Second session of 2026-06-08. The first session had completed Phases 3.4–3.6b (catalog, runner, generic run-update, business-day calendar, GET /status with a `fresh` field). The declared next step was Phase 3.6c: define and enforce the freshness gate, add a `force` parameter to bypass it. On-demand ticker-stats report and single-indicator download were also on the radar.

## What was done

**Phase 3.6c — freshness gate + `force` parameter (`status.py`, `api.py`).**

`status.py` gained `freshness_target()` (returns `last_business_day(date.today() - timedelta(days=1))`) and `is_fresh(last_date_iso)`. The `fresh` field was added to the `indicator_status` payload. In `api.py`, `POST /run-update/{name}` now checks freshness before cooldown: if `fresh == True`, it returns 409 with the current `last_date`, the target date, and a hint to pass `force=true`. `force: bool = False` is a query parameter; when set, it bypasses both the freshness and cooldown checks — but never auth, catalog lookup, or the concurrency lock.

Source-lag handling: CDI's `last_date` sat behind the freshness target with no newer data at the source. The gate correctly blocks a re-fetch (409 fresh), and `force=true` re-fetches but the `last_date` does not advance — the data is simply not there yet. The gate must not loop on such indicators.

**On-demand per-indicator report (`src/reports.py`, `GET /report/{name}`).**

`indicator_report(name)` reads the parquet once and returns: date span (`first_date`, `last_date`, `n_days`), ticker stats (`tickers_total`, `tickers_mean_per_day`, `tickers_median_per_day`, `tickers_last_day`), and value stats (`value_min/max/mean/median/nulls`) on the auto-detected value column. Value column detection: the single numeric non-`date`/`ticker` column. `quotes` has multiple numeric columns (OHLCV + adjusted) → `value_column: null`, value stats skipped. The endpoint is open (no auth): it exposes statistics, not raw data.

The report immediately surfaced real signals: `eps`'s `tickers_last_day` (303) was much lower than its mean per day (~544), confirming the latest day is sparsely populated — expected for source data still being updated. Value outliers were also visible. A richer report earns its keep by surfacing data-quality signals on the first run.

**Single-indicator download (`GET /download/{name}`).**

`FileResponse` from FastAPI, with `Content-Disposition: attachment`. Auth required via `X-Worker-Secret` header — proprietary data, unlike the open metadata endpoints. Auth is never via query-string token (secrets in URLs leak into access logs). Returns 404 for unknown or not-yet-produced indicators. Batch download (Phase 3.7b) deliberately deferred: `quotes` alone is hundreds of MB; bandwidth implications over the ngrok free tier need to be weighed before building.

**End-to-end remote demo.**

All new endpoints were exercised from another machine via the ngrok tunnel: `GET /status` → `GET /report/eps` → `POST /run-update/cdi?force=true` → `GET /download/eps`. Full pipeline validated remotely.

## Decisions made or reversed

* **Decision 29** (added): Single-indicator download via an authenticated endpoint; auth via header only (never query-string). Batch download deferred to Phase 3.7b. See `docs/decisions.md#29`.

## Gambiarras & warnings found

* **CDI source lag confirmed**: `last_date` for CDI is behind the freshness target. Re-fetching (even with `force=true`) does not advance it. The freshness gate blocks further fetches correctly; this is expected behavior, not a bug.
* **Latest day is sparsely populated**: `tickers_last_day` can be significantly below the mean (e.g. `eps`: 303 vs ~544). The source is still updating that day's data. The freshness gate checks `last_date`, not completeness — this is a known limitation.
* **`bova11` 0-row bug unchanged**: still blocked. Not investigated this session.
* **`momentum_6m.py` FutureWarning**: `pct_change(fill_method='ffill')` deprecation still pending fix.

## Next step

Phase 3.7b — batch/bundle download. A zip of all present parquets + a `manifest.json` carrying their status. Before building: evaluate ngrok free-tier bandwidth for large bundles (`quotes` parquet is hundreds of MB).

After 3.7b: the frontend (`apps/web`, Next.js 14 on Vercel, calling the worker via the tunnel with `X-Worker-Secret` proxied server-side). Windows-service autostart (Phase 3.10) can be done independently.

## Links

- Commits: TBD (provided by Eduardo after review)
