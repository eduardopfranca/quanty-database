"""
Indicator catalog.

A static registry of the indicators the worker knows how to produce,
organized by provider and kind. This module holds only *data*: how to turn
an entry into actual fetch / normalize / compute calls lives in the
orchestrator (Phase 3.5), not here.

Structure: CATALOG[provider][kind][name] -> entry fields.

Kinds
-----
- "macro"           : standalone reference series. Each has its own
                      VarosClient fetch method and normalizer (bespoke), so
                      its entry carries `fetch` and `normalizer`.
- "raw_bulk"        : the full quotes table. Its own fetch method and
                      normalizer, like a macro.
- "raw_fundamental" : per-ticker fundamentals. All share
                      VarosClient.fetch_accounting_file + normalize.varos_indicator,
                      so an entry only carries the Varos code (`varos_name`)
                      and `data_type`. Adding one is a single row, no code.
- "derived"         : computed from other indicators. The compute function is
                      resolved by convention (src/compute/<name>.py, function
                      `compute`); an entry only carries `depends_on`, ordered
                      to match the compute() signature.

This module imports nothing from the worker's fetch/normalize/compute layers
on purpose: it must stay cheap to import even when there are hundreds of
indicators. Resolution (getattr / importlib) happens in the orchestrator.

When a second provider is added, split this into a `catalog/` package with
one module per provider; the lookup API below stays the same.
"""


CATALOG = {
    "varos": {
        "macro": {
            "cdi":    {"fetch": "fetch_cdi",  "normalizer": "varos_cdi"},
            "ibov":   {"fetch": "fetch_ibov", "normalizer": "varos_ibov"},
            "bova11": {"fetch": "fetch_bova", "normalizer": "varos_bova"},
        },
        "raw_bulk": {
            "quotes": {"fetch": "fetch_quotes", "normalizer": "varos_quotes"},
        },
        "raw_fundamental": {
            # All resolved by kind: fetch_accounting_file(name=varos_name,
            # data_type=data_type) -> normalize.varos_indicator.
            "market_cap": {"varos_name": "ValorDeMercado", "data_type": "indicator"},
            "roic":       {"varos_name": "ROIC",           "data_type": "indicator"},
            "ebit_ev":    {"varos_name": "EBIT_EV",        "data_type": "indicator"},
            "eps":        {"varos_name": "LPA",            "data_type": "indicator"},
            "bvps":       {"varos_name": "VPA",            "data_type": "indicator"},
        },
        "derived": {
            # compute resolved by convention: src/compute/<name>.py -> compute(*deps)
            "graham":          {"depends_on": ["eps", "bvps", "quotes"]},
            "momentum_6m":     {"depends_on": ["quotes"]},
            "volatility_252d": {"depends_on": ["quotes"]},
            "var_252d_95":     {"depends_on": ["quotes"]},
            "median_volume":   {"depends_on": ["quotes"]},
        },
    },
}


def _build_index() -> dict[str, dict]:
    """Flatten CATALOG into name -> {name, provider, kind, **fields}.

    Raises if a name is defined more than once. Today names are unique; when a
    second provider reuses an indicator name, this trips and tells us it is
    time to add provider-qualified lookup (instead of silently shadowing).
    """
    index: dict[str, dict] = {}
    for provider, kinds in CATALOG.items():
        for kind, entries in kinds.items():
            for name, fields in entries.items():
                if name in index:
                    other = index[name]
                    raise ValueError(
                        f"Indicator name '{name}' is defined twice "
                        f"({other['provider']}/{other['kind']} and {provider}/{kind}). "
                        f"Names must be unique until provider-qualified lookup exists."
                    )
                index[name] = {"name": name, "provider": provider, "kind": kind, **fields}
    return index


_INDEX = _build_index()


def get(name: str) -> dict:
    """Return the catalog entry for `name`, enriched with `provider` and `kind`.

    Returns a fresh dict (safe to mutate). Raises KeyError listing the known
    names if `name` is unknown.
    """
    try:
        return dict(_INDEX[name])
    except KeyError:
        raise KeyError(
            f"Unknown indicator '{name}'. Known indicators: {sorted(_INDEX)}"
        ) from None


def all_names() -> list[str]:
    """Return every indicator name, sorted."""
    return sorted(_INDEX)


def by_kind(kind: str) -> list[str]:
    """Return the names of all indicators of a given kind, sorted."""
    return sorted(name for name, entry in _INDEX.items() if entry["kind"] == kind)


if __name__ == "__main__":
    # Self-check: confirm every string/convention in the catalog actually
    # resolves against the code. Imports are local so the module itself stays
    # import-light.
    import importlib

    from src.connections.varos import VarosClient
    from src.data import normalize

    print(f"Catalog: {len(_INDEX)} indicators across {len(CATALOG)} provider(s).\n")
    for kind in ("macro", "raw_bulk", "raw_fundamental", "derived"):
        names = by_kind(kind)
        print(f"  {kind:16} ({len(names)}): {', '.join(names)}")

    print("\nValidating references against the code...")
    problems: list[str] = []

    for name in all_names():
        entry = get(name)
        kind = entry["kind"]

        if kind in ("macro", "raw_bulk"):
            if not hasattr(VarosClient, entry["fetch"]):
                problems.append(f"{name}: VarosClient has no method '{entry['fetch']}'")
            if not hasattr(normalize, entry["normalizer"]):
                problems.append(f"{name}: normalize has no function '{entry['normalizer']}'")

        elif kind == "raw_fundamental":
            if not hasattr(VarosClient, "fetch_accounting_file"):
                problems.append(f"{name}: VarosClient has no method 'fetch_accounting_file'")
            if not hasattr(normalize, "varos_indicator"):
                problems.append(f"{name}: normalize has no function 'varos_indicator'")

        elif kind == "derived":
            try:
                module = importlib.import_module(f"src.compute.{name}")
                if not callable(getattr(module, "compute", None)):
                    problems.append(f"{name}: src/compute/{name}.py has no callable 'compute'")
            except ModuleNotFoundError:
                problems.append(f"{name}: missing module src/compute/{name}.py")
            for dep in entry["depends_on"]:
                if dep not in _INDEX:
                    problems.append(f"{name}: depends_on unknown indicator '{dep}'")

    if problems:
        print("\nPROBLEMS FOUND:")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("All references resolve. Catalog is consistent with the code.")