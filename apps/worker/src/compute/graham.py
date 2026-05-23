"""
Graham's adapted fair-value indicator.

Computes (graham_value / price), where graham_value = sqrt(EPS * BVPS * 22.5).

The result is a ratio: value > 1 means the stock trades below Graham's fair
value (potentially undervalued); value < 1 means it trades above.

Special cases (all set to 0, so they sort to the bottom in a "higher is
better" ranking but stay present in the dataset):

  - EPS < 0 or BVPS < 0:
      Graham's formula is undefined for negative earnings or book value.
      The company is treated as non-investible by this metric.

  - value > 10:
      Almost certainly a data error (wrong EPS, BVPS, or price). The
      ticker stays in the dataset with value=0 to avoid losing the
      observation for ranking purposes; investigate manually if needed.

The two "0" cases are indistinguishable downstream — if you need to know
*why* a ticker was zeroed, recompute with the filters removed.

Ported from MakeIndicator.graham_valuation (legacy database_fintz project).
"""
import pandas as pd

from src.data import storage
from src.logger import get_logger


_logger = get_logger("worker.compute.graham")

# Benjamin Graham's multiplier for the fair-value formula:
# fair_value = sqrt(EPS * BVPS * 22.5).
GRAHAM_MULTIPLIER = 22.5

# Maximum plausible value of the ratio (graham_value / price). Anything
# above this is assumed to be a data error and zeroed.
MAX_PLAUSIBLE_RATIO = 10


def compute(
    eps: pd.DataFrame,
    bvps: pd.DataFrame,
    quotes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute Graham's adapted fair-value ratio per ticker per date.

    Parameters
    ----------
    eps : pd.DataFrame
        Normalized EPS DataFrame with columns [date, ticker, value].
    bvps : pd.DataFrame
        Normalized BVPS DataFrame with columns [date, ticker, value].
    quotes : pd.DataFrame
        Normalized quotes DataFrame with columns [date, ticker, close_adjusted, ...].

    Returns
    -------
    pd.DataFrame
        DataFrame with columns [date, ticker, value], where `value` is the
        ratio graham_value / price, clipped to [0, 10] (see module docstring
        for the meaning of 0).
    """
    eps_df = eps[["date", "ticker", "value"]].rename(columns={"value": "eps"})
    bvps_df = bvps[["date", "ticker", "value"]].rename(columns={"value": "bvps"})
    price_df = quotes[["date", "ticker", "close_adjusted"]].rename(
        columns={"close_adjusted": "price"}
    )

    # Merge on (date, ticker). All three inputs must have a value for the
    # row to survive.
    df = eps_df.merge(bvps_df, on=["date", "ticker"], how="inner")
    df = df.merge(price_df, on=["date", "ticker"], how="inner")

    # Graham fair value (only defined when both EPS and BVPS are positive).
    graham_value = (df["eps"] * df["bvps"] * GRAHAM_MULTIPLIER) ** 0.5
    df["value"] = graham_value / df["price"]

    # Force value=0 for non-investible companies (negative earnings or
    # negative book value).
    df.loc[(df["eps"] < 0) | (df["bvps"] < 0), "value"] = 0

    # Force value=0 for implausibly large ratios (likely data errors).
    df.loc[df["value"] > MAX_PLAUSIBLE_RATIO, "value"] = 0

    # Any remaining NaN (shouldn't happen given the filters above, but
    # belt-and-suspenders for safety).
    df = df.dropna(subset=["value"])

    return df[["date", "ticker", "value"]].reset_index(drop=True)


if __name__ == "__main__":
    eps = storage.load_indicator("eps")
    bvps = storage.load_indicator("bvps")
    quotes = storage.load_indicator("quotes")
    result = compute(eps, bvps, quotes)
    print(result)
    print(f"\nRows: {len(result)}")
    print(f"Date range: {result['date'].min()} -> {result['date'].max()}")
    print(f"Unique tickers: {result['ticker'].nunique()}")
    print(f"\nValue stats:")
    print(result["value"].describe())
    print(f"\nNon-zero count: {(result['value'] > 0).sum()}")
    print(f"Zero count: {(result['value'] == 0).sum()}")