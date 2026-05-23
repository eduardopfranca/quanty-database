"""
Median trading volume over a rolling window.

Ported from MakeIndicator.median_volume (legacy database_fintz project).
"""
import pandas as pd

from src.data import storage
from src.logger import get_logger


_logger = get_logger("worker.compute.median_volume")

# v1 configuration: median volume over 21 trading days (~1 month).
WINDOW = 21


def compute(quotes: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the median trading volume per ticker over a rolling window of WINDOW days.

    Parameters
    ----------
    quotes : pd.DataFrame
        Normalized quotes DataFrame with columns [date, ticker, volume, ...].

    Returns
    -------
    pd.DataFrame
        DataFrame with columns [date, ticker, value], where `value` is the
        rolling median of `volume` over the past WINDOW days for that ticker.
    """
    df = quotes[["date", "ticker", "volume"]].copy()

    # Fill missing volumes with 0 within each ticker (legacy behavior).
    df["volume"] = df["volume"].fillna(0)

    # Rolling median per ticker.
    df["value"] = (
        df.groupby("ticker")["volume"]
        .rolling(WINDOW)
        .median()
        .reset_index(0, drop=True)
    )

    df = df.dropna(subset=["value"])

    return df[["date", "ticker", "value"]].reset_index(drop=True)


if __name__ == "__main__":
    quotes = storage.load_indicator("quotes")
    result = compute(quotes)
    print(result)
    print(f"\nRows: {len(result)}")
    print(f"Date range: {result['date'].min()} -> {result['date'].max()}")
    print(f"Unique tickers: {result['ticker'].nunique()}")