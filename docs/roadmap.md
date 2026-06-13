# Roadmap

Forward-looking plan for Quanty Database after the frontend (F1–F5) shipped on 2026-06-11. This is a **map, not a spec** — each phase gets its own working session and detailed design when picked up. `docs/decisions.md` remains the source of truth for decisions already made; this file sequences what is *not yet* built.

**How to use in a new session:** read `docs/handoff.md` and `docs/decisions.md` first, then pick a phase below. Respect the dependency order — building later phases before their prerequisites forces rework.

---

## Current baseline (done)

- **Worker (Varos)**: 11 indicators + 3 macro refs, provider-namespaced storage, status/report/update/download endpoints. Synchronous (decision 3).
- **Frontend**: Next.js 14 on Vercel, server-side proxies for status / update / report / download. Public, **ungated**.
- Data is **raw-only per provider** (`WORKER_DATA_DIR/varos/`). No fill/merge stages, no strategy-ready outputs yet.

---

## Dependency order

```
A. yfinance provider
        │
        ▼
B. Fill methods (ffill / cross / …)   ← also fixes a correctness bug, not just a feature
        │
        ▼
D. Cross-provider merge (symbology / units / FX)   ← needs A + B
        │
        ▼
E. Personalized pipeline → factor_db / witz_db
        ▲
        │
C. Async job model   ← prerequisite for E *if* the pipeline is remote-triggered
```

Cross-cutting/operational items (gating, autostart, backup, validation) slot in alongside, not after.

---

## Phase A — yfinance provider (objective 2)

**Goal.** Add yfinance as a second data provider.

**Includes.** A `yfinance` node in `CATALOG[provider][kind][name]`; `connections/yfinance.py`; normalizers in `data/normalize.py` (prefixed `yfinance_*`); storage under `WORKER_DATA_DIR/yfinance/`. Frontend extension is minor once new indicators exist (the catalog already drives the table).

**Why first.** It is self-contained and unblocks D and E. The architecture (provider-namespaced catalog + storage, decision 24) was built for exactly this.

**Risks / decisions.** What yfinance indicators are in scope (likely quotes first, for the cross-fill in D). yfinance B3 tickers carry a `.SA` suffix — keep the raw form here; the mapping problem belongs to D.

---

## Phase B — Fill methods (ffill, cross, …)

**Goal.** Build the first transformation stage: forward-fill and related fills over raw data.

**Includes.** ffill for raw accounting series (eps, roic, ebit_ev, bvps, market_cap — sparse, reported quarterly); a cross/merge fill for prices; the folder taxonomy decision that decision 25 deferred *until exactly this point*.

**Why this is a correctness fix, not a feature.** The known `close_adjusted` ffill issue means momentum / volatility / var_252d_95 are only reliable from ~2010 even though raw history goes back to ~1998. The derived indicators are currently subtly wrong for the older period. Fill is what makes them production-grade. Treat as a **blocker for production**, not polish.

**Risks / decisions.** This is where the real stage/fill folder taxonomy gets designed (decision 25): raw per-provider → fill/merge stages → ready outputs. Derived/filled placement is non-trivial; design it against this concrete transformation. Validate fill output against the legacy `MakeIndicator` notebook to catch regressions.

---

## Phase C — Async job model

**Goal.** Replace (or supplement) the synchronous request/response (decision 3) with a fire-and-poll job model: a trigger returns immediately with a job id; the UI polls `/status` (or a `/jobs/{id}`) until done.

**Why.** A full pipeline run (Phase E) is a job of minutes. The Vercel Hobby function timeout (~60s) already breaks a remote `quotes` update; it cannot survive a pipeline. **C is a prerequisite for E *if* the pipeline is triggered from the frontend.**

**Key fork to decide before building C:** is the pipeline (E) **remote-triggered from the UI** (→ C is required) or a **local batch / notebook** whose output the UI only *downloads* (→ C is optional, the existing download endpoints suffice)? Decide this first — it determines whether C happens at all.

**Risks / decisions.** Async reintroduces job state, which decision 3 deliberately avoided. Keep it minimal (in-memory job registry + the existing concurrency lock) rather than a queue/DB unless scale demands it.

---

## Phase D — Cross-provider merge (symbology / units / FX)

**Goal.** Fill/repair Varos prices using yfinance (and vice-versa), producing a single clean price series per ticker.

**The hard part is not the fill — it is reconciliation:**
- **Symbology**: B3 tickers vs yfinance `.SA` suffix; a ticker-mapping table.
- **Adjustments**: split/dividend adjustment consistency between sources.
- **Units / FX**: the "safe conversion" — ensure both sources are in the same currency/units before merging.
- **Overlap rule**: which source wins where both have data, and how gaps are filled across sources.

**Why.** "Fill quotes using yfinance" in the pipeline vision lives here. Needs A (yfinance present) and B (fill machinery + taxonomy).

---

## Phase E — Personalized pipeline → factor_db / witz_db

**Goal.** A curated, strategy-ready dataset produced end-to-end: fetch from Varos → ffill raw accounting → cross-fill prices via yfinance + safe conversion → recompute derived indicators on the *complete* data → write to a dedicated folder (e.g. `factor_db` / `witz_db`) → expose a dedicated download button (or buttons) for that output.

**Includes.** The pipeline orchestration; the output folder in the taxonomy from B; a download endpoint/group for the curated output (extends decisions 29/30); a **run manifest** recording provenance (which source versions + which fill logic produced this factor_db).

**Why last.** It composes A + B + D, and (if remote-triggered) C.

**Risks / decisions.**
- **Versioning / backup**: today each update overwrites the previous parquet. Once strategies depend on factor_db, a bad fetch corrupts production. Add snapshots/versioning before factor_db is load-bearing.
- **Reproducibility**: the run manifest is what lets you debug a strategy back to the exact data that fed it.

---

## Cross-cutting / operational track (slot in alongside)

- **Site gating / auth** — the Vercel site is public and the proxy holds the secret, so anyone with the URL can update/download. Gate (Vercel Auth / shared password / middleware) **before** Felipe/Greg use it for real.
- **Windows Service autostart (Phase 3.10)** — worker + ngrok on boot, self-healing, so the PC-as-server is reliable once others depend on it.
- **Backup / versioning of parquet** — see Phase E; relevant the moment any output is depended upon.
- **Validation harness vs legacy `MakeIndicator`** — catch silent regressions as fill changes inputs (Phase B onward).

## Smaller known items (clear when convenient)

- **`bova11` bug**: Varos returns 0 rows → `KeyError` in `varos_bova` → 500. It is a v1 macro ref; cheap to fix.
- **`varos_bova` date column** not converted to datetime — fix alongside `bova11`.
- **`momentum_6m` FutureWarning** — one-line `fill_method=None`.
- **`volatility_252d` / `var_252d_95`** not yet produced (depend only on `quotes`).
- **B3 holidays** in `business_days.py` (Mon–Fri only today).
- **Migration of the remaining 25+ `MakeIndicator` indicators** — incremental, one at a time.
