"""
On-demand per-indicator reports.

Unlike `status.py` (cheap, metadata-only), a report scans the parquet to
compute richer statistics. It is meant to be requested per indicator, on
demand — not for every indicator on every status call.

The "value column" is detected automatically as the single numeric column
that is neither `date` nor `ticker`:
- macro `cdi` -> `return`, `ibov` -> `close`
- panel indicators (eps, graham, ...) -> `value`
- `quotes` has several numeric columns (OHLCV + adjusted) -> value stats are
  skipped (its values are a separate, quotes-specific concern).
"""
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

from src import catalog
from src.data import storage


def _is_numeric(pa_type) -> bool:
    return pa.types.is_integer(pa_type) or pa.types.is_floating(pa_type)


def indicator_report(name: str) -> dict:
    """Full report for one indicator. Raises KeyError if not in the catalog.

    Scans `date`, `ticker` (if present), and the single value column (if
    unambiguous). All aggregates come from that one read.
    """
    entry = catalog.get(name)
    out = {"name": name, "provider": entry["provider"], "kind": entry["kind"]}

    path: Path = storage.get_indicator_path(name, entry["provider"])
    if not path.is_file():
        out["present"] = False
        return out
    out["present"] = True

    schema = pq.read_schema(path)
    names = schema.names
    has_ticker = "ticker" in names
    value_cols = [
        n for n in names
        if n not in ("date", "ticker") and _is_numeric(schema.field(n).type)
    ]
    value_col = value_cols[0] if len(value_cols) == 1 else None

    cols = ["date"] + (["ticker"] if has_ticker else []) + ([value_col] if value_col else [])
    df = pd.read_parquet(path, columns=cols)
    out["rows"] = len(df)
    if df.empty:
        return out

    df["date"] = pd.to_datetime(df["date"])
    out["first_date"] = df["date"].min().date().isoformat()
    out["last_date"] = df["date"].max().date().isoformat()
    out["n_days"] = int(df["date"].nunique())

    out["has_tickers"] = has_ticker
    if has_ticker:
        per_day = df.groupby("date")["ticker"].nunique()
        last_day = df["date"].max()
        out["tickers_total"] = int(df["ticker"].nunique())
        out["tickers_mean_per_day"] = round(float(per_day.mean()), 1)
        out["tickers_median_per_day"] = int(per_day.median())
        out["tickers_last_day"] = int(df.loc[df["date"] == last_day, "ticker"].nunique())

    out["value_column"] = value_col
    if value_col:
        v = df[value_col]
        out["value_min"] = float(v.min())
        out["value_max"] = float(v.max())
        out["value_mean"] = round(float(v.mean()), 4)
        out["value_median"] = float(v.median())
        out["value_nulls"] = int(v.isna().sum())

    return out


if __name__ == "__main__":
    import sys
    import json

    # Representative shapes: eps (ticker + value), cdi (value, no ticker),
    # quotes (ticker, multiple value columns -> value stats skipped).
    names = sys.argv[1:] or ["eps", "cdi", "quotes"]
    for n in names:
        print(json.dumps(indicator_report(n), indent=2, default=str))
        print()