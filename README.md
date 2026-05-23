# Quanty Database

Web platform for updating and managing financial databases from multiple data providers. Internal tool used by Madcap / Quanty to keep B3 fundamental and market data in sync across analysts' machines.

Currently supports:

- **Varos** — B3 stocks, fundamental indicators, quotes, macro references (CDI, IBOV, BOVA11).

## How it works

1. User opens the web UI and selects the indicators to update.
2. The frontend (Vercel) calls the worker (running on Eduardo's machine, exposed via ngrok tunnel).
3. The worker downloads the raw data from Varos, computes derived indicators, and writes parquet files to the local data folder.
4. The user receives a download containing the updated parquets and a completeness report.
5. Per-indicator statistics (last date, ticker count, etc.) are upserted to Supabase, so anyone can see the current state of the database from the UI.

## Architecture

```
┌─────────────────┐     HTTPS      ┌──────────────────────┐
│ Browser (any)   │ ─────────────> │  Vercel (Next.js 14) │
└─────────────────┘                │  - UI                │
                                   │  - calls worker      │
                                   └──────────┬───────────┘
                                              │
                                              │ POST /run-update
                                              ▼
                                   ┌────────────────────────────────┐
                                   │   ngrok tunnel (public)        │
                                   │   chowder-marathon-            │
                                   │   slapping.ngrok-free.dev      │
                                   └────────────────┬───────────────┘
                                                    │
                                                    ▼
                                   ┌────────────────────────────────┐
                                   │  Worker (FastAPI, Python 3.11) │
                                   │  running on Eduardo's PC       │
                                   │  ─────────────────────────     │
                                   │  1. fetch raw from Varos       │
                                   │  2. normalize columns          │
                                   │  3. compute derived indicators │
                                   │  4. write parquet to disk      │
                                   │  5. upsert stats to Supabase   │
                                   └────────────────┬───────────────┘
                                                    │
                          ┌─────────────────────────┼──────────────────────┐
                          ▼                         ▼                      ▼
                 ┌──────────────┐      ┌──────────────────┐    ┌──────────────┐
                 │   Varos API  │      │   Local folder   │    │   Supabase   │
                 │  (B3 data)   │      │ (parquet files)  │    │  (metadata)  │
                 └──────────────┘      └──────────────────┘    └──────────────┘
```

## Stack

- **Frontend**: Next.js 14 (App Router), hosted on Vercel — *not yet built*.
- **Worker**: FastAPI + pandas + pyarrow + statsmodels, Python 3.11.
- **Metadata**: Supabase Postgres (catalog of indicators + per-indicator stats).
- **Tunnel**: ngrok (free tier, static domain `chowder-marathon-slapping.ngrok-free.dev`).
- **Data storage**: local parquet files (no cloud storage, no egress cost).

## Repository structure

```
quanty-database/
├── README.md                   # this file
├── docs/
│   ├── decisions.md            # architectural decisions log
│   └── handoff.md              # session handoff document
├── apps/
│   ├── worker/                 # Python worker (FastAPI)
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── api.py          # FastAPI app and HTTP endpoints
│   │       ├── main.py         # uvicorn entrypoint
│   │       ├── config.py
│   │       ├── logger.py
│   │       ├── connections/    # data provider clients
│   │       │   └── varos.py
│   │       ├── data/           # I/O and normalization
│   │       │   ├── storage.py
│   │       │   └── normalize.py
│   │       └── compute/        # derived indicator calculations
│   │           ├── graham.py
│   │           ├── momentum_6m.py
│   │           ├── volatility_252d.py
│   │           ├── var_252d_95.py
│   │           └── median_volume.py
│   └── web/                    # Next.js frontend (not started)
├── .env.example
└── .gitignore
```

## V1 indicators

Six raw indicators (downloaded directly from Varos): `quotes`, `market_cap`, `roic`, `ebit_ev`, `eps`, `bvps`.

Three macro / market references: `cdi`, `ibov`, `bova11`.

Five derived indicators (computed locally): `graham`, `momentum_6m`, `volatility_252d`, `var_252d_95`, `median_volume`.

## Local setup

### Prerequisites

- Python 3.11 (install via `py -3.11 -m venv` or download from python.org)
- [ngrok](https://ngrok.com/download) with a free account (provides one static domain per account)

### Worker

```powershell
cd apps\worker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.env` at the repo root with:

```
VAROS_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
WORKER_SECRET=...
WORKER_DATA_DIR=C:/path/to/your/local/data/folder
LOG_LEVEL=INFO
LOG_DIR=./logs
```

Validate the environment:

```powershell
python -m src.config       # prints 7 masked settings
python -m src.logger       # writes INFO/WARNING/ERROR to console and file
python -m src.data.storage # saves/loads/lists a dummy DataFrame
python -m src.connections.varos  # hits Varos API, returns raw DataFrames
```

Start the worker:

```powershell
python -m src.main
```

Start the ngrok tunnel (separate terminal):

```powershell
ngrok http --url=chowder-marathon-slapping.ngrok-free.dev 8000
```

### Frontend

Not built yet.

## Status

🚧 In active development.

See `docs/handoff.md` for the latest progress, what is currently being worked on, and the immediate next step.
See `docs/decisions.md` for the reasoning behind the main architectural choices.

## License

Internal project, not open source.
