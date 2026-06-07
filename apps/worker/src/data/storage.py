"""
Local parquet storage for indicators.

Reads from and writes to settings.worker_data_dir, namespaced by provider:
each indicator is stored at {worker_data_dir}/{provider}/{name}.parquet.

The provider is passed in by the caller (runner / api), which already holds
the catalog entry. Storage stays pure I/O and does not depend on the catalog.
"""
from pathlib import Path

import pandas as pd

from src.config import settings
from src.logger import get_logger


_logger = get_logger("worker.storage")


def get_indicator_path(name: str, provider: str) -> Path:
    """Return the absolute path where an indicator is stored.

    Files are namespaced by provider:
    {worker_data_dir}/{provider}/{name}.parquet
    """
    return settings.worker_data_dir / provider / f"{name}.parquet"


def indicator_exists(name: str, provider: str) -> bool:
    """Check whether an indicator parquet file exists on disk."""
    return get_indicator_path(name, provider).is_file()


def save_indicator(name: str, df: pd.DataFrame, provider: str) -> Path:
    """
    Save an indicator DataFrame as a parquet file.

    Creates the provider folder if needed. Overwrites any existing file with
    the same name. Returns the absolute path to the written file.
    """
    path = get_indicator_path(name, provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")
    _logger.info(f"Saved indicator '{name}' to {path} ({len(df)} rows)")
    return path


def load_indicator(name: str, provider: str) -> pd.DataFrame:
    """
    Load an indicator DataFrame from disk.

    Raises FileNotFoundError if the indicator does not exist.
    """
    path = get_indicator_path(name, provider)
    if not path.is_file():
        raise FileNotFoundError(
            f"Indicator '{name}' not found at {path}. "
            f"Run an update job to generate it."
        )
    df = pd.read_parquet(path, engine="pyarrow")
    _logger.info(f"Loaded indicator '{name}' from {path} ({len(df)} rows)")
    return df


def list_indicators() -> list[str]:
    """Return the names of all indicators stored on disk, across all providers."""
    return sorted(p.stem for p in settings.worker_data_dir.glob("*/*.parquet"))


if __name__ == "__main__":
    import pandas as pd

    print(f"Storage directory: {settings.worker_data_dir}\n")

    provider = "_selftest_"  # throwaway provider folder, cleaned up below

    # Save dummy indicator
    dummy = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-01-02"]).date,
        "ticker": ["PETR4", "PETR4"],
        "value": [1.23, 4.56],
    })
    saved_path = save_indicator("__test_dummy__", dummy, provider)
    print(f"Saved to: {saved_path}")

    # Check existence
    print(f"\nExists: {indicator_exists('__test_dummy__', provider)}")
    print(f"Does fake indicator exist: {indicator_exists('__nonexistent__', provider)}")

    # Load back
    loaded = load_indicator("__test_dummy__", provider)
    print(f"\nLoaded:\n{loaded}")

    # List all indicators (across provider folders)
    print(f"\nAll indicators on disk: {list_indicators()}")

    # Cleanup: remove the dummy file and its throwaway folder
    saved_path.unlink()
    try:
        saved_path.parent.rmdir()  # only removes the folder if it is now empty
    except OSError:
        pass
    print("\nDummy file cleaned up.")