"""
Indicator status derivation.

Reads cheap, instant metadata for each catalog indicator straight from its
parquet — no separate state store:

- present:    does the parquet exist?
- updated_at: file mtime (reliable, since WORKER_DATA_DIR is exclusive to the worker)
- rows:       parquet footer (no data read)
- last_date:  latest value of the 'date' column
- fresh:      does last_date reach the freshness target (the previous business day)?

Heavier per-day ticker statistics (mean/median per day, last-day count,
distinct total) are NOT computed here — they require a full scan and will
live in a separate on-demand report.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src import business_days, catalog
from src.data import storage


def freshness_target() -> date:
    """Date an indicator's data is expected to cover: the previous business day.

    The fund needs data up to the last business day before today, so 'fresh'
    means the data reaches at least this date. Today's own data is never
    required (it is produced overnight).
    """
    return business_days.last_business_day(date.today() - timedelta(days=1))


def is_fresh(last_date_iso: str | None) -> bool:
    """True if last_date covers at least the freshness target (previous business day)."""
    if last_date_iso is None:
        return False
    return date.fromisoformat(last_date_iso) >= freshness_target()


def _last_date(path: Path) -> str | None:
    """Latest value in the 'date' column as an ISO date string (or None if empty).

    Reads only the 'date' column; parquet is columnar, so this stays cheap.
    """
    s = pd.read_parquet(path, columns=["date"])["date"]
    if s.empty:
        return None
    return pd.to_datetime(s).max().date().isoformat()


def indicator_status(name: str) -> dict:
    """Cheap status for a single indicator. Raises KeyError if not in the catalog."""
    entry = catalog.get(name)
    info = {"name": name, "provider": entry["provider"], "kind": entry["kind"]}

    path = storage.get_indicator_path(name, entry["provider"])
    if not path.is_file():
        info["present"] = False
        return info

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    last_date = _last_date(path)
    info.update({
        "present": True,
        "updated_at": mtime.isoformat(),
        "rows": pq.read_metadata(path).num_rows,
        "last_date": last_date,
        "fresh": is_fresh(last_date),
        "fills": [],
    })
    return info


def all_status() -> list[dict]:
    """Cheap status for every indicator in the catalog (present or not)."""
    return [indicator_status(name) for name in catalog.all_names()]


if __name__ == "__main__":
    import json

    print(f"Freshness target (last_date >= this is fresh): {freshness_target()}\n")
    print(json.dumps(all_status(), indent=2))