"""
Grouped (batch) downloads.

A group bundles several indicators' parquets into a single zip, with a
manifest.json describing what is inside (each member's status). Groups are
derived from catalog kinds:

- "indicators" -> raw_fundamental + derived (the factor data)
- "macro"      -> macro references (cdi, ibov, bova11)

Prices (quotes, kind raw_bulk) are intentionally NOT bundled: quotes is large
and already compressed, so it is served directly by GET /download/quotes.

A future "custom" batch (user picks indicators by hand) is planned but not
built yet.
"""
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from src import catalog, status
from src.data import storage


GROUPS: dict[str, list[str]] = {
    "indicators": ["raw_fundamental", "derived"],
    "macro": ["macro"],
}


def group_names(group: str) -> list[str]:
    """Indicator names belonging to a group. Raises KeyError if group is unknown."""
    names: list[str] = []
    for kind in GROUPS[group]:
        names.extend(catalog.by_kind(kind))
    return sorted(names)


def build_group_zip(group: str) -> Path:
    """Build a zip of the present parquets in `group` plus a manifest.json.

    Returns the path to a temporary zip file; the caller is responsible for
    deleting it after the response is sent. Raises KeyError if the group is
    unknown.

    The manifest lists every member's status (present or not), so the user
    can see what was bundled and what was missing.
    """
    names = group_names(group)  # KeyError -> unknown group

    manifest = {
        "group": group,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indicators": [status.indicator_status(name) for name in names],
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    # ZIP_STORED: parquet is already compressed, so don't waste CPU re-deflating.
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_STORED) as zf:
        for name in names:
            entry = catalog.get(name)
            path = storage.get_indicator_path(name, entry["provider"])
            if path.is_file():
                zf.write(path, arcname=f"{name}.parquet")
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

    return Path(tmp.name)


if __name__ == "__main__":
    import sys

    group = sys.argv[1] if len(sys.argv) > 1 else "macro"
    print(f"Known groups: {list(GROUPS)}")
    print(f"'{group}' members: {group_names(group)}\n")

    zip_path = build_group_zip(group)
    print(f"Built {group} zip: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            print(f"  {info.filename}  ({info.file_size} bytes)")

    zip_path.unlink()
    print("\n(temp zip removed)")