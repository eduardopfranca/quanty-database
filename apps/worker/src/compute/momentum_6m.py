"""
Momentum: percent change of adjusted close over N months.

Ported from MakeIndicator.momentum_indicator (legacy database_fintz project).
"""
import numpy as np
import pandas as pd

from src.data import storage
from src.logger import get_logger


_logger = get_logger("worker.compute.momentum_6m")

# v1 configuration: 6-month momentum, using 21 trading days per month.
MONTHS = 6
TRADING_DAYS_PER_MONTH = 21


def compute(quotes: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the N-month momentum per ticker as the percent change of
    adjusted close over MONTHS * TRADING_DAYS_PER_MONTH days.

    Parameters
    ----------
    quotes : pd.DataFrame
        Normalized quotes DataFrame with columns [date, ticker, close_adjusted, ...].

    Returns
    -------
    pd.DataFrame
        DataFrame with columns [date, ticker, value], where `value` is the
        percent change of close_adjusted over the lookback window.
    """
    df = quotes[["date", "ticker", "close_adjusted"]].copy()

    periods = MONTHS * TRADING_DAYS_PER_MONTH
    df["value"] = df.groupby("ticker")["close_adjusted"].pct_change(periods=periods)

    # Legacy behavior: treat zero and infinite returns as missing.
    df.loc[df["value"] == 0, "value"] = pd.NA
    df.loc[df["value"] == np.inf, "value"] = pd.NA
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