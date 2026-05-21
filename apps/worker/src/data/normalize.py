"""
Normalizers for raw DataFrames returned by external providers.

Each function takes a raw DataFrame (with provider-specific column
names and types) and returns a standardized DataFrame ready for
storage and computation.

Convention: function names are prefixed with the provider name
(e.g. varos_quotes, varos_indicator).
"""
import pandas as pd

from src.logger import get_logger


_logger = get_logger("worker.normalize")


# ---------- Varos ----------

def varos_quotes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the bulk quotes parquet returned by Varos.

    Renames the 14 raw columns to standardized English names, applies
    the split adjustment factor to open/high/low/average prices,
    forward-fills close_adjusted within each ticker, and sorts by date.
    """
    df = df.copy()

    df.columns = [
        "date", "open", "close", "high", "average", "low",
        "trades_quantity", "trades_volume", "ticker", "volume",
        "adjustment_factor", "close_adjusted",
        "split_adjustment_factor", "close_adjusted_splits",
    ]

    for col in ("open", "high", "average", "low"):
        df[f"{col}_adjusted"] = df[col] * df["adjustment_factor"]

    df["close_adjusted"] = df.groupby("ticker")["close_adjusted"].transform("ffill")
    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    return df


def varos_indicator(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize a single Varos fundamental indicator (e.g. ROIC, EBIT_EV).

    Renames 'data' to 'date' and 'valor' to 'value', drops the redundant
    'indicador' column (it always equals the indicator name), and sorts
    by date. Output columns: [date, ticker, value].
    """
    df = df.copy()

    rename_map = {"data": "date", "valor": "value"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "indicador" in df.columns:
        df = df.drop(columns=["indicador"])

    df = df[["date", "ticker", "value"]]
    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    return df


def varos_cdi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the historical CDI rate.

    Drops auxiliary columns, renames 'data' to 'date' and 'valor' to
    'return', divides 'return' by 100 (Varos returns it as a percentage).
    """
    df = df.copy()

    drop_cols = [c for c in ("dataFim", "nome", "codigo") if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    df = df.rename(columns={"data": "date", "valor": "return"})
    df["return"] = df["return"] / 100
    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    return df


def varos_ibov(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the historical IBOV index series.

    Renames 'data' to 'date' and 'valor' to 'close', drops the
    'indice' column.
    """
    df = df.copy()

    df = df.rename(columns={"data": "date", "valor": "close"})

    if "indice" in df.columns:
        df = df.drop(columns=["indice"])

    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    return df


def varos_bova(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the historical BOVA11 ETF series.

    Selects and renames the price/volume columns.
    """
    df = df.copy()

    df = df[[
        "ticker", "data", "precoFechamento", "precoAbertura",
        "precoMinimo", "precoMaximo", "precoMedio", "volumeNegociado",
    ]]
    df.columns = [
        "ticker", "date", "close", "open",
        "low", "high", "average", "volume",
    ]

    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    return df


if __name__ == "__main__":
    from src.connections.varos import VarosClient

    client = VarosClient()

    print("Testing normalizers against live Varos API...\n")

    print(">>> varos_cdi")
    df = client.fetch_cdi()
    normalized = varos_cdi(df)
    print(f"Columns: {list(normalized.columns)}")
    print(f"Tail:\n{normalized.tail(2)}\n")

    print(">>> varos_ibov")
    df = client.fetch_ibov()
    normalized = varos_ibov(df)
    print(f"Columns: {list(normalized.columns)}")
    print(f"Tail:\n{normalized.tail(2)}\n")

    print(">>> varos_indicator (ROIC)")
    df = client.fetch_accounting_file("ROIC", data_type="indicator")
    normalized = varos_indicator(df)
    print(f"Columns: {list(normalized.columns)}")
    print(f"Tail:\n{normalized.tail(2)}\n")