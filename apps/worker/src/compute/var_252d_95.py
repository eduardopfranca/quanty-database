"""
Historical-simulation Value at Risk (VaR) at 95% confidence over a rolling
1-year window.

Returns the magnitude of loss at the 5th percentile of daily returns as a
positive number (industry convention: higher value = higher risk).

Note: this differs from the legacy MakeIndicator.historical_simulation_var,
which divided the quantile by the average price of the window. That
normalization had no clear financial interpretation and was dropped.
"""
import numpy as np
import pandas as pd

from src.data import storage
from src.logger import get_logger


_logger = get_logger("worker.compute.var_252d_95")

# v1 configuration: 1-year window, 95% confidence (5th percentile of returns).
YEARS = 1
TRADING_DAYS_PER_YEAR = 252
WINDOW = int(TRADING_DAYS_PER_YEAR * YEARS)
MIN_PERIODS = int(WINDOW * 0.8)
CONFIDENCE = 0.95
PERCENTILE = 1 - CONFIDENCE  # 0.05 (left tail of returns)


def compute(quotes: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the historical-simulation VaR per ticker as the absolute value
    of the 5th-percentile daily return over a rolling WINDOW-day window.

    Parameters
    ----------
    quotes : pd.DataFrame
        Normalized quotes DataFrame with columns [date, ticker, close_adjusted, ...].

    Returns
    -------
    pd.DataFrame
        DataFrame with columns [date, ticker, value], where `value` is the
        magnitude of the worst 5% daily return over the lookback window
        (positive number; higher = higher risk).
    """
    df = quotes[["date", "ticker", "close_adjusted"]].copy()
    df["return"] = df.groupby("ticker")["close_adjusted"].pct_change()

    # Legacy behavior: treat zero and infinite returns as missing.
    df.loc[df["return"] == 0, "return"] = pd.NA
    df.loc[df["return"] == np.inf, "return"] = pd.NA
    df = df.dropna(subset=["return"])

    # Rolling 5th-percentile of returns per ticker.
    df["value"] = (
        df.groupby("ticker")["return"]
        .rolling(window=WINDOW, min_periods=MIN_PERIODS)
        .quantile(PERCENTILE)
        .reset_index(0, drop=True)
    )

    # Convert to positive magnitude of loss (industry convention).
    df["value"] = -df["value"]

    df = df.dropna(subset=["value"])

    return df[["date", "ticker", "value"]].reset_index(drop=True)


if __name__ == "__main__":
    quotes = storage.load_indicator("quotes")
    result = compute(quotes)
    print(result)
    print(f"\nRows: {len(result)}")
    print(f"Date range: {result['date'].min()} -> {result['date'].max()}")
    print(f"Unique tickers: {result['ticker'].nunique()}")
    print(f"\nValue stats:")
    print(result["value"].describe())