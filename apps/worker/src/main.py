"""Uvicorn entrypoint for the worker.

Run with:
    python -m src.main

The host 0.0.0.0 is required so the Cloudflare Tunnel can reach the
server. The port is fixed at 8000.
"""
import uvicorn

from src.api import app
from src.logger import get_logger

logger = get_logger("worker.main")


if __name__ == "__main__":
    logger.info("Starting worker on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)