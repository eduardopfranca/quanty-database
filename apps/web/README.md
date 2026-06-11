# Quanty Database — frontend

Next.js 14 (App Router) frontend for the Quanty Database internal tool. Proxies the local Python worker and provides a browser UI for status, reports, updates, and downloads.

## Running locally

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The worker must also be running (`python -m src.main` in `apps/worker/`) for the dashboard to load data.

## Environment variables

| Variable     | Required | Description                                   |
| ------------ | -------- | --------------------------------------------- |
| `WORKER_URL` | Yes      | Base URL of the worker. `http://localhost:8000` for local dev. |

Copy `.env.example` to `.env.local` and fill in the values:

```bash
cp .env.example .env.local
```

`.env.local` is gitignored. Never commit real values.

## Production (Vercel)

Environment variables are set in the Vercel dashboard — there is no `.env` file in production. Set `WORKER_URL` to the ngrok static domain (e.g. `https://chowder-marathon-slapping.ngrok-free.dev`).

Why the frontend has its own env files separate from the worker's root `.env`: see `docs/decisions.md` decision 31.
