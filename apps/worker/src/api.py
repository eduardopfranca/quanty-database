"""FastAPI application for the Quanty Database worker.

Exposes the HTTP endpoints called by the frontend (or any HTTP client)
through the tunnel.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from src import catalog, reports, runner, status
from src.config import settings
from src.data import storage
from src.logger import get_logger

logger = get_logger("worker.api")

app = FastAPI(title="Quanty Database Worker", version="0.1.0")

# Per-indicator asyncio locks — lazily populated, prevents concurrent updates.
_indicator_locks: dict[str, asyncio.Lock] = {}


def _get_lock(indicator: str) -> asyncio.Lock:
    if indicator not in _indicator_locks:
        _indicator_locks[indicator] = asyncio.Lock()
    return _indicator_locks[indicator]


def verify_worker_secret(
    x_worker_secret: Annotated[str | None, Header()] = None,
) -> None:
    """FastAPI dependency: validates the X-Worker-Secret header. Returns 401 if absent or wrong."""
    if x_worker_secret != settings.worker_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Worker-Secret header")


def _check_cooldown(indicator_name: str, provider: str) -> None:
    """Raise 409 if the indicator parquet was written within the cooldown window.

    Uses the local parquet mtime as the last-updated timestamp. If the file
    does not exist yet, there is no cooldown (first run is always allowed).
    """
    if not storage.indicator_exists(indicator_name, provider):
        return

    path = storage.get_indicator_path(indicator_name, provider)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    elapsed = now - mtime
    cooldown = timedelta(hours=settings.update_cooldown_hours)

    if elapsed < cooldown:
        elapsed_hours = elapsed.total_seconds() / 3600
        retry_after = mtime + cooldown
        raise HTTPException(
            status_code=409,
            detail=(
                f"Indicator '{indicator_name}' was updated {elapsed_hours:.1f}h ago, "
                f"cooldown is {settings.update_cooldown_hours}h. "
                f"Try again after {retry_after.isoformat()}"
            ),
        )


@app.get("/health")
def health() -> dict:
    """Liveness check. Returns a constant payload."""
    logger.info("Health check called")
    return {"status": "ok"}


@app.get("/status")
def get_status() -> list[dict]:
    """Cheap, instant status for every catalog indicator (no data scan)."""
    logger.info("Status requested")
    return status.all_status()


@app.get("/report/{indicator_name}")
def get_report(indicator_name: str) -> dict:
    """On-demand full report for one indicator (scans its parquet)."""
    try:
        return reports.indicator_report(indicator_name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown indicator '{indicator_name}'. Known: {catalog.all_names()}",
        )


@app.get("/download/{indicator_name}")
def download_indicator(
    indicator_name: str,
    _: Annotated[None, Depends(verify_worker_secret)],
) -> FileResponse:
    """Stream one indicator's parquet as a file download (requires X-Worker-Secret)."""
    try:
        entry = catalog.get(indicator_name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown indicator '{indicator_name}'. Known: {catalog.all_names()}",
        )
    path = storage.get_indicator_path(indicator_name, entry["provider"])
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Indicator '{indicator_name}' has not been produced yet. Run an update first.",
        )
    logger.info(f"Download requested: '{indicator_name}'")
    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=f"{indicator_name}.parquet",
    )


@app.post("/run-update/{indicator_name}")
async def run_update(
    indicator_name: str,
    _: Annotated[None, Depends(verify_worker_secret)],
    force: bool = False,
) -> dict:
    """Produce one indicator and save its parquet, returning a summary.

    `indicator_name` must exist in the catalog. The runner resolves the
    catalog entry: fetched kinds (macro, raw_bulk, raw_fundamental) fetch +
    normalize; derived kinds load their dependencies from disk and compute.

    Guards (in order): X-Worker-Secret auth (401), catalog membership (404),
    freshness (409 if already fresh), cooldown via parquet mtime (409),
    per-indicator asyncio lock (409 if busy). A derived indicator with a
    missing dependency on disk returns 422 (rigid policy: dependencies are
    not auto-fetched). Any other failure returns 500.

    `force=true` bypasses the freshness and cooldown checks (but never auth
    or the concurrency lock) — use it to re-produce an indicator on demand.
    """
    try:
        entry = catalog.get(indicator_name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown indicator '{indicator_name}'. Known: {catalog.all_names()}",
        )

    if not force:
        current = status.indicator_status(indicator_name)
        if current.get("fresh"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Indicator '{indicator_name}' is already fresh "
                    f"(last_date {current['last_date']} reaches the target {status.freshness_target()}). "
                    f"Pass force=true to update anyway."
                ),
            )
        _check_cooldown(indicator_name, entry["provider"])

    lock = _get_lock(indicator_name)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail=f"Update already running for indicator '{indicator_name}'",
        )

    await lock.acquire()
    try:
        logger.info(f"Starting update for '{indicator_name}'{' (forced)' if force else ''}")
        summary = runner.run_indicator(indicator_name)
        logger.info(f"Update complete for '{indicator_name}': {summary['rows']} rows saved")
        return summary
    except FileNotFoundError as e:
        logger.warning(f"Update for '{indicator_name}' failed: missing dependency")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"Update for '{indicator_name}' failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        lock.release()