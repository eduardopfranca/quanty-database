"""
Indicator runner.

Resolves an indicator from the catalog and produces its parquet:

- fetched kinds (macro, raw_bulk, raw_fundamental): fetch from the provider,
  normalize, save.
- derived: load its dependencies from disk, compute, save.

Dependency policy (decision A1, rigid): a derived indicator is computed from
whatever its dependencies have on disk. If a dependency is missing,
`storage.load_indicator` raises FileNotFoundError and the run fails — we do
NOT auto-fetch dependencies. In v1 the dependency graph is one level deep
(derived depend only on raw), so no recursion or ordering is needed.

The catalog holds only data (src/catalog.py); turning an entry into actual
fetch/normalize/compute calls is this module's job. Storage is namespaced by
provider, so the provider (from the catalog entry) is passed to storage.
"""
import importlib

from src import catalog
from src.connections.varos import VarosClient
from src.data import normalize, storage
from src.logger import get_logger


_logger = get_logger("worker.runner")


def run_indicator(name: str) -> dict:
    """Produce indicator `name` and save it to disk.

    Returns a summary dict: {indicator, kind, rows, path}.

    Raises
    ------
    KeyError
        If `name` is not in the catalog (from catalog.get).
    FileNotFoundError
        If `name` is derived and one of its dependencies is not on disk
        (rigid policy: dependencies are not auto-fetched).
    """
    entry = catalog.get(name)
    kind = entry["kind"]
    _logger.info(f"Running indicator '{name}' (kind={kind})")

    if kind == "derived":
        # Each dependency is loaded from its own provider's folder.
        deps = [
            storage.load_indicator(dep, catalog.get(dep)["provider"])
            for dep in entry["depends_on"]
        ]
        compute = importlib.import_module(f"src.compute.{name}").compute
        df = compute(*deps)
    else:
        # Fetched kinds. Raw fundamentals share one path (resolved by kind);
        # macro and the bulk quotes are bespoke (fetch method + normalizer
        # named in the entry).
        client = VarosClient()
        if kind == "raw_fundamental":
            raw = client.fetch_accounting_file(entry["varos_name"], entry["data_type"])
            df = normalize.varos_indicator(raw)
        else:  # macro, raw_bulk
            raw = getattr(client, entry["fetch"])()
            df = getattr(normalize, entry["normalizer"])(raw)

    path = storage.save_indicator(name, df, entry["provider"])
    _logger.info(f"Indicator '{name}' done: {len(df)} rows -> {path}")
    return {"indicator": name, "kind": kind, "rows": len(df), "path": str(path)}


if __name__ == "__main__":
    # Smoke test: run one indicator end-to-end.
    #   python -m src.runner            -> runs 'cdi' (small, fast, fetched)
    #   python -m src.runner roic       -> exercises the raw_fundamental path
    #   python -m src.runner graham     -> derived; FileNotFoundError if eps/bvps/quotes
    #                                      are not on disk (demonstrates the A1 policy)
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "cdi"
    print(f"Running indicator '{name}'...\n")
    summary = run_indicator(name)
    print(summary)