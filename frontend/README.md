# frontend/

Next.js + TypeScript + Tailwind CSS application for **PriceRadar India**.

This increment implements the public frontend plus Phase 12 Clerk authentication and
user-owned watchlist, alerts, and profile pages. It talks only to the existing FastAPI
backend through a typed API client.

**Out of scope here:** notification dispatch and real retailer integrations. Sale-price
prediction and BUY/WAIT recommendation are shown on product details when the backend
returns them; missing artifacts render as insufficient data, never as invented prices.

Projected sale dates and prices are evidence-based estimates and are not guaranteed
retailer announcements.

## Stack

- Next.js (App Router) + React + TypeScript
- Tailwind CSS
- Vitest + Testing Library

## Configuration

Copy `frontend/.env.example` to `frontend/.env.local` (never commit `.env.local`):

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
```

The API origin is read only from that environment variable. Backend URLs are not hardcoded.
The browser receives only `NEXT_PUBLIC_*` values. `CLERK_SECRET_KEY` is server-only for Clerk
middleware. See `../AUTHENTICATION.md`.

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

Production image (standalone Next.js server):

```bash
docker build -t priceradar/frontend:local --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 .
```

Do not pass `CLERK_SECRET_KEY` as a build-arg. Compose: `infrastructure/docker/docker-compose.yml`.

## Pages and APIs

| Page            | Backend contract                                                                                |
| --------------- | ----------------------------------------------------------------------------------------------- |
| Home            | Search form → `/search?q=`                                                                      |
| Search results  | `GET /api/v1/products/search`; verified price enrichment via `GET /api/v1/products/{id}/prices` |
| Product details | `GET /api/v1/products/{id}`, `/variants`, `/prices`, `/history`, `/sale-intelligence`, `/recommendation`, `/sale-price-prediction` |
| Price history   | `GET /api/v1/products/{id}/history`                                                             |
| Deals           | `GET /api/v1/deals` (currently always empty — coming-soon state, no fabricated deals)           |
| Retailers       | `GET /api/v1/retailers` (empty registry is shown honestly)                                      |
| About           | Static explanation of observed vs calculated vs predicted data                                  |
| Sign in / up    | Clerk components at `/sign-in` and `/sign-up`                                                   |
| Watchlist       | Protected. `GET /api/v1/watchlists`                                                             |
| Alerts          | Protected. `GET /api/v1/alerts`                                                                 |
| Profile         | Protected. `GET`/`PATCH /api/v1/me`                                                             |

The backend product model has **no image field**. Product cards use a labelled placeholder
instead of inventing photos. Predicted values are never displayed as observed prices: Phase 7
history responses set `predicted` to `null` unless a labeled Phase 10 prediction is returned.

Search cards show the lowest verified price, **distinct retailer count**, cheapest retailer,
and offer count. They do not list every offer. Product details render the **complete**
`offers[]` list (`offers.map`) with no 3-offer cap. A retailer identity and a seller/listing
are counted separately. Monthly statistics remain visible when `best_buying_month` is null.

## Data integrity

- Observed, calculated, and predicted values are labelled separately.
- Mock/fixture adapter data from the backend is shown as returned; this UI does not invent
  retailer names, prices, or availability.
- Network calls use an explicit timeout and bounded retries with backoff.
