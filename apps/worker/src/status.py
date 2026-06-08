"""
Indicator status derivation.

Reads cheap, instant metadata for each catalog indicator straight from its
parquet — no separate state store:

- present:    does the parquet exist?
- updated_at: file mtime (reliable, since WORKER_DATA_DIR is exclusive to the worker)
- rows:       parquet footer (no data read)
- last_date:  latest value of the 'date' column

Heavier per-day ticker statistics (mean/median per day, last-day count,
distinct total) are NOT computed here — they require a full scan and will
live in a separate on-demand report.
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from src import catalog
from src.data import storage


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
    info.update({
        "present": True,
        "updated_at": mtime.isoformat(),
        "rows": pq.read_metadata(path).num_rows,
        "last_date": _last_date(path),
        "fills": [],
    })
    return info


def all_status() -> list[dict]:
    """Cheap status for every indicator in the catalog (present or not)."""
    return [indicator_status(name) for name in catalog.all_names()]


if __name__ == "__main__":
    import json

    print(json.dumps(all_status(), indent=2))