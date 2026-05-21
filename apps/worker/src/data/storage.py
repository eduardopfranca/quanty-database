"""
Local parquet storage for indicators.

Reads from and writes to settings.worker_data_dir. Each indicator is
stored as a single parquet file named {indicator_name}.parquet.
"""
from pathlib import Path

import pandas as pd

from src.config import settings
from src.logger import get_logger


_logger = get_logger("worker.storage")


def get_indicator_path(name: str) -> Path:
    """Return the absolute path where an indicator would be stored."""
    return settings.worker_data_dir / f"{name}.parquet"


def indicator_exists(name: str) -> bool:
    """Check whether an indicator parquet file exists on disk."""
    return get_indicator_path(name).is_file()


def save_indicator(name: str, df: pd.DataFrame) -> Path:
    """
    Save an indicator DataFrame as a parquet file.

    Overwrites any existing file with the same name.
    Returns the absolute path to the written file.
    """
    path = get_indicator_path(name)
    df.to_parquet(path, index=False, engine="pyarrow")
    _logger.info(f"Saved indicator '{name}' to {path} ({len(df)} rows)")
    return path


def load_indicator(name: str) -> pd.DataFrame:
    """
    Load an indicator DataFrame from disk.

    Raises FileNotFoundError if the indicator does not exist.
    """
    path = get_indicator_path(name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Indicator '{name}' not found at {path}. "
            f"Run an update job to generate it."
        )
    df = pd.read_parquet(path, engine="pyarrow")
    _logger.info(f"Loaded indicator '{name}' from {path} ({len(df)} rows)")
    return df


def list_indicators() -> list[str]:
    """Return the names of all indicators currently stored on disk."""
    return sorted(p.stem for p in settings.worker_data_dir.glob("*.parquet"))


if __name__ == "__main__":
    import pandas as pd

    print(f"Storage directory: {settings.worker_data_dir}\n")

    # Save dummy indicator
    dummy = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-02"]).date,
        "ticker": ["PETR4", "PETR4"],
        "value": [1.23, 4.56],
    })
    saved_path = save_indicator("__test_dummy__", dummy)
    print(f"Saved to: {saved_path}")

    # Check existence
    print(f"\nExists: {indicator_exists('__test_dummy__')}")
    print(f"Does fake indicator exist: {indicator_exists('__nonexistent__')}")

    # Load back
    loaded = load_indicator("__test_dummy__")
    print(f"\nLoaded:\n{loaded}")

    # List all indicators
    print(f"\nAll indicators on disk: {list_indicators()}")

    # Cleanup
    get_indicator_path("__test_dummy__").unlink()
    print("\nDummy file cleaned up.")