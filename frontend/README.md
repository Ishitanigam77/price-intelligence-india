# frontend/

Next.js + TypeScript + Tailwind CSS application for **PriceRadar India**.

This increment implements the public frontend: product search, product details with retailer
comparison, historical price views, deals, retailers, and about. It talks only to the existing
FastAPI backend through a typed API client.

**Out of scope here:** Clerk/authentication, watchlists/alerts, ML prediction UI, real retailer
integrations, and recommendation (BUY_NOW / WAIT / WATCH).

## Stack

- Next.js (App Router) + React + TypeScript
- Tailwind CSS
- Vitest + Testing Library

## Configuration

Copy `frontend/.env.example` to `frontend/.env.local` (never commit `.env.local`):

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The API origin is read only from that environment variable. Backend URLs are not hardcoded.
This frontend does not embed secrets.

The backend must allow the Next.js origin in `CORS_ALLOWED_ORIGINS` (see repo-root
`.env.example`, default `http://localhost:3000`).

## Running locally

From this directory, with the FastAPI backend already running:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

| Command                | Purpose                                  |
| ---------------------- | ---------------------------------------- |
| `npm run test`         | Frontend unit/component tests            |
| `npm run lint`         | ESLint                                   |
| `npm run format:check` | Prettier check                           |
| `npm run typecheck`    | TypeScript `--noEmit`                    |
| `npm run build`        | Production build                         |
| `GET /health`          | Frontend liveness (`{ "status": "ok" }`) |

## Pages and APIs

| Page            | Backend contract                                                                                |
| --------------- | ----------------------------------------------------------------------------------------------- |
| Home            | Search form → `/search?q=`                                                                      |
| Search results  | `GET /api/v1/products/search`; verified price enrichment via `GET /api/v1/products/{id}/prices` |
| Product details | `GET /api/v1/products/{id}`, `/variants`, `/prices`, `/history`                                 |
| Price history   | `GET /api/v1/products/{id}/history`                                                             |
| Deals           | `GET /api/v1/deals` (currently always empty — coming-soon state, no fabricated deals)           |
| Retailers       | `GET /api/v1/retailers` (empty registry is shown honestly)                                      |
| About           | Static explanation of observed vs calculated vs predicted data                                  |

The backend product model has **no image field**. Product cards use a labelled placeholder
instead of inventing photos. Predicted values are never displayed: Phase 7 history responses
set `predicted` to `null`.

## Data integrity

- Observed, calculated, and predicted values are labelled separately.
- Mock/fixture adapter data from the backend is shown as returned; this UI does not invent
  retailer names, prices, or availability.
- Network calls use an explicit timeout and bounded retries with backoff.
