
# Quanty Database

Web platform for updating and managing financial databases from multiple data providers.

Currently supported:

- **Varos** (B3 stocks, fundamental indicators, quotes)

## Architecture

- **Frontend** (`apps/web`) — Next.js 14, hosted on Vercel
- **Worker** (`apps/worker`) — FastAPI in Python, hosted on Render
- **Metadata and config** — Supabase Postgres
- **Parquet file storage** — Supabase Storage

## Flow

1. User selects desired factors in the web interface
2. Frontend dispatches a job to the worker
3. Worker downloads raw components from Varos, computes derived factors (graham, ebit_ev, roic, etc.)
4. Worker saves parquets to Supabase Storage and writes the completeness report to Postgres
5. Frontend displays the completeness report to the user

## Repository structure

\`\`\`
quanty-database/
├── apps/
│   ├── web/          # Next.js (Vercel)
│   └── worker/       # FastAPI (Render)
│       └── src/
│           ├── providers/    # Data provider abstraction
│           ├── indicators/   # Derived factor computation
│           ├── jobs/         # Update pipeline
│           └── storage/      # Supabase Storage integration
├── .env.example
├── .gitignore
└── README.md
\`\`\`

## Local setup

(detailed documentation will be added as we progress)

## Status

🚧 In development — v1
