---
session: 2026-06-11
slug: grouped-batch-download
---

## Context at start

Phase 3.7a (single-indicator download, `GET /download/{name}`) was complete. The declared next step was Phase 3.7b: a batch/bundle download endpoint. Open question: how to group, and what to do about `quotes` (hundreds of MB, already compressed).

## What was done

**`src/downloads.py` + `GET /download-group/{group}` in `api.py`.**

Groups are derived from catalog kinds: `indicators` = `raw_fundamental` + `derived`; `macro` = `macro`. `quotes` (kind `raw_bulk`) is intentionally excluded from all groups — it is large and already internally compressed, so bundling it into a zip would not meaningfully reduce the transfer size. It continues to be served via `GET /download/quotes`.

`build_group_zip(group)` builds a temporary zip (`ZIP_STORED` — no re-deflation of already-compressed parquets) containing each present group member plus a `manifest.json` that records each member's full status (including absent ones, so the caller knows what was missing). The temporary file is cleaned up after the response is sent via FastAPI `BackgroundTasks`.

The endpoint is at `/download-group/{group}` (distinct prefix from `/download/{name}` to avoid routing collisions) and requires `X-Worker-Secret`. 404 for an unknown group name.

The `indicators` bundle in practice came out at ~94 MB — a real transfer over the ngrok free tier but accepted for the routine analyst workflow.

A custom/personalized batch (user picks indicators by hand) was considered and explicitly deferred. It is tracked in Open items.

## Decisions made or reversed

* **Decision 30** (added): Grouped batch download by indicator kind. `indicators` and `macro` groups; `quotes` excluded; `ZIP_STORED`; `BackgroundTasks` cleanup; custom batch deferred. See `docs/decisions.md#30`.

## Gambiarras & warnings found

* **Indicators bundle is ~94 MB**: acceptable for the routine, but worth noting for the frontend UX — the download may take a few seconds over the ngrok free tier.
* No new bugs discovered this session.

## Next step

Frontend (`apps/web`, Phase 4) — Next.js 14 on Vercel. Status dashboard, per-indicator report, trigger-update controls, and three download buttons (Indicators / Prices / Macro). `X-Worker-Secret` must be proxied server-side.

## Links

- Commits: TBD (provided by Eduardo after review)
