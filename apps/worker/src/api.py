"""FastAPI application for the Quanty Database worker.

Exposes the HTTP endpoints called by the frontend (or any HTTP client)
through the tunnel.
"""
from fastapi import FastAPI, HTTPException

from src.connections.varos import VarosClient
from src.data import normalize, storage
from src.logger import get_logger

logger = get_logger("worker.api")

app = FastAPI(title="Quanty Database Worker", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness check. Returns a constant payload."""
    logger.info("Health check called")
    return {"status": "ok"}


@app.get("/run-update/quotes")
def run_update_quotes() -> dict:
    """Fetch quotes from Varos, normalize, save to parquet, return summary.

    Temporary GET endpoint for end-to-end validation. Will be moved to POST
    with WORKER_SECRET auth in a future session.
    """
    logger.info("Starting quotes update")
    try:
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