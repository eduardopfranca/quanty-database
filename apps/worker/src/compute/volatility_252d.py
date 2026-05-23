"""
Annualized volatility of daily returns over a rolling window.

Ported from MakeIndicator.annualized_volatility (legacy database_fintz project).
"""
import numpy as np
import pandas as pd

from src.data import storage
from src.logger import get_logger


_logger = get_logger("worker.compute.volatility_252d")

# v1 configuration: 1-year volatility, 252 trading days per year,
# annualization factor sqrt(252), minimum 80% of the window required.
YEARS = 1
TRADING_DAYS_PER_YEAR = 252
WINDOW = int(TRADING_DAYS_PER_YEAR * YEARS)
MIN_PERIODS = int(WINDOW * 0.8)


def compute(quotes: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the annualized volatility per ticker as the rolling standard
    deviation of daily returns over WINDOW days, scaled by sqrt(252).

    Parameters
    ----------
    quotes : pd.DataFrame
        Normalized quotes DataFrame with columns [date, ticker, close_adjusted, ...].

    Returns
    -------
    pd.DataFrame
        DataFrame with columns [date, ticker, value], where `value` is the
        annualized standard deviation of daily returns over the lookback window.
    """
    df = quotes[["date", "ticker", "close_adjusted"]].copy()
    df["return"] = df.groupby("ticker")["close_adjusted"].pct_change()

    # Legacy behavior: treat zero and infinite returns as missing.
    df.loc[df["return"] == 0, "return"] = pd.NA
    df.loc[df["return"] == np.inf, "return"] = pd.NA
    df = df.dropna(subset=["return"])

    df["value"] = (
        df.groupby("ticker")["return"]
        .rolling(window=WINDOW, min_periods=MIN_PERIODS)
        .std()
        .reset_index(0, drop=True)
    )
    df["value"] = df["value"] * np.sqrt(TRADING_DAYS_PER_YEAR)

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