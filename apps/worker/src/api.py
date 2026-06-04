"""FastAPI application for the Quanty Database worker.

Exposes the HTTP endpoints called by the frontend (or any HTTP client)
through the tunnel.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from src.config import settings
from src.connections.varos import VarosClient
from src.data import normalize, storage
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


def _check_cooldown(indicator_name: str) -> None:
    """Raise 409 if the indicator parquet was written within the cooldown window.

    Uses the local parquet mtime as the last-updated timestamp. If the file
    does not exist yet, there is no cooldown (first run is always allowed).
    """
    if not storage.indicator_exists(indicator_name):
        return

    path = storage.get_indicator_path(indicator_name)
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


@app.post("/run-update/quotes")
async def run_update_quotes(
    _: Annotated[None, Depends(verify_worker_secret)],
) -> dict:
    """Fetch quotes from Varos, normalize, save to parquet, return summary.

    Guards (in order): POST-only, X-Worker-Secret auth (401), cooldown via
    parquet mtime (409), per-indicator asyncio lock (409 if busy).
    """
    _check_cooldown("quotes")

    lock = _get_lock("quotes")
    if lock.locked():
        raise HTTPException(status_code=409, detail="Update already running for indicator 'quotes'")

    await lock.acquire()
    try:
        logger.info("Starting quotes update")
        client = VarosClient()
        raw = client.fetch_quotes()
        df = normalize.varos_quotes(raw)
        path = storage.save_indicator("quotes", df)
        logger.info(f"Quotes update complete: {len(df)} rows saved to {path}")
        return {
            "indicator": "quotes",
            "rows": len(df),
            "path": str(path),
        }
    except Exception as e:
        logger.exception("Quotes update failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        lock.release()
