---
session: 2026-05-28
slug: remove-supabase-and-fix-cooldown
---

## Context at start

At the start of this session, `api.py` and `main.py` were uncommitted and broken. The previous session had hardened the `/run-update/quotes` endpoint with POST, `X-Worker-Secret` auth, and an `asyncio.Lock` — but the cooldown check was querying Supabase (`indicator_stats.updated_at`) and crashing with `column indicator_stats.indicator_name does not exist`. The `indicator_stats` table was also empty (nothing had ever written to it), so even if the column name were correct, the cooldown would have always been skipped.

The declared next step was to fix the cooldown and commit the hardening.

## What was done

- Rewrote `_check_cooldown` in `api.py` to use local parquet mtime via `storage.get_indicator_path()` and `storage.indicator_exists()`. No network call, no Supabase.
- Removed `from supabase import create_client` from `api.py`.
- Removed `supabase_url` and `supabase_service_role_key` from `config.py` and their lines from the `__main__` print block.
- Removed `supabase==2.10.0` from `requirements.txt`.
- Removed the Supabase section from `.env.example`; also fixed stale comment "FastAPI no Render" → "FastAPI local"; added missing vars `WORKER_DATA_DIR`, `LOG_LEVEL`, `LOG_DIR`.
- Fixed stale comment in `main.py` docstring ("Cloudflare Tunnel" → "ngrok tunnel") — this was already fixed in a prior session; confirmed correct.
- Updated `docs/decisions.md`: annotated decision 4 as superseded, updated decisions 11 and 16, added decision 21.
- Updated `README.md`: removed Supabase from diagram, stack, How it works, and setup.
- Rewrote `docs/handoff.md` to reflect the post-session state.
- Created `docs/retrospectives/` with README, template, and this file.

Commits: TBD (provided by Eduardo after review)

## Decisions made or reversed

- **Decision 4** (superseded): Supabase used only for metadata — superseded by decision 21.
- **Decision 11** (revised): Stack summary — removed supabase-py; metadata now described as local.
- **Decision 16** (revised): Cooldown timestamp source changed from `indicator_stats.updated_at` to local parquet mtime.
- **Decision 21** (added): Supabase removed; metadata moves local. See `docs/decisions.md#21`.

## Gambiarras & warnings found

- The `indicator_stats` Supabase table was empty — nothing in the worker ever wrote to it. The cooldown that was meant to use it had never worked.
- Probing the actual Supabase schema by writing a request to the live service was rejected. The correct approach: ask Eduardo, or design around the unknown schema. Lesson saved in handoff.md as lesson 14.
- Cooldown is now tied to parquet mtime, not a dedicated "last successful update" record. If the parquet is touched by another process (e.g. a legacy notebook), the cooldown resets. This is acceptable for now and noted in handoff.md gambiarras.
- The `indicators` catalog (14 rows) still lives in Supabase but is unused by current code. It needs to be migrated to a local form in Phase 3.4.

## Next step

Phase 3.4 — local indicator catalog. Migrate the 14-row `indicators` table from Supabase to a local form. Form (JSON file, Python dict, etc.) to be decided at the start of that session.

## Links

- Commits: TBD
