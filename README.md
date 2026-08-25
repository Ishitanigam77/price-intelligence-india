# PriceRadar India

An India-focused price intelligence platform that discovers product listings across a growing
network of Indian online retailers, identifies identical products/variants across them, tracks
price history, detects genuine price drops and sale events, and recommends whether to
**BUY_NOW**, **WAIT**, or **WATCH**.

> **Status: Phase 1 — Core Domain Model & Database Foundation**, plus a **FastAPI backend
> application foundation** (application factory, `/api/v1/` versioned routing, Redis
> infrastructure, centralized exception handling, structured logging, CORS, and local Docker
> Compose support — see `backend/README.md`) and the **retailer adapter framework** with
> fixture-backed mock adapters (see `backend/app/retailer_adapters/` and
> `RETAILER_ARCHITECTURE.md`). Real retailer integrations, matching, price intelligence, ML
> models, authentication, notifications, and the frontend do **not** exist yet — see
> `ROADMAP.md`.

## Why This Exists

Most price-comparison tools hardcode "Retailer A vs Retailer B." PriceRadar India is designed
from the start to scale to 100+ retailers across many categories (electronics, mobiles,
laptops, appliances, fashion, beauty, grocery, home, sports, automotive, and more) without
rewriting its core comparison, matching, or pricing logic. Every retailer integration is
isolated behind a common adapter interface — see `RETAILER_ARCHITECTURE.md`.

Data acquisition only ever uses legitimate sources (official APIs, affiliate/partner feeds,
product feeds, other permitted integrations). The system never bypasses CAPTCHA,
authentication, anti-bot systems, rate limits, `robots.txt`, or retailer terms of service, and
never fabricates retailer data.

## Documentation

| Document | Purpose |
|---|---|
| [`PROJECT_ARCHITECTURE.md`](./PROJECT_ARCHITECTURE.md) | Target system architecture, layers, and the product/price data model |
| [`TECH_STACK.md`](./TECH_STACK.md) | Chosen technologies per layer and why |
| [`DEVELOPMENT_RULES.md`](./DEVELOPMENT_RULES.md) | Engineering rules, including the phase-by-phase process |
| [`ROADMAP.md`](./ROADMAP.md) | Phase-by-phase delivery plan |
| [`RETAILER_ARCHITECTURE.md`](./RETAILER_ARCHITECTURE.md) | The retailer adapter contract and legitimate-data-acquisition policy |
| [`DATA_FLOW.md`](./DATA_FLOW.md) | End-to-end data flow from acquisition to UI |

## Repository Structure (Scaffolding)

```
.
├── frontend/                  # Next.js + TypeScript + Tailwind CSS app (Phase 5+)
├── backend/
│   ├── Dockerfile, docker-entrypoint.sh   # Production-oriented backend image
│   ├── app/
│   │   ├── api/                 # FastAPI routers, DTOs, deps, centralized error handling
│   │   │   └── v1/                # Versioned API: health, products, retailers, prices, deals
│   │   ├── schemas/              # Pydantic API request/response DTOs (separate from ORM models)
│   │   ├── services/             # Thin service-layer boundaries (only where genuinely needed)
│   │   ├── auth/                # Clerk token verification (Phase 5+)
│   │   ├── core/                # Settings, logging, Redis client management
│   │   ├── domain/               # Product / Variant / Listing / Seller / Observation entities (Phase 1)
│   │   ├── repositories/         # Data access layer (Phase 1+)
│   │   ├── db/                   # SQLAlchemy session/base setup (Phase 1+)
│   │   ├── retailer_adapters/    # Common adapter interface + per-retailer adapters (Phase 2+)
│   │   ├── collectors/           # Orchestrates data acquisition via adapters (Phase 2+)
│   │   ├── normalization/        # Raw listing → common normalized shape (Phase 3)
│   │   ├── matching/             # Product/variant matching engine (Phase 3)
│   │   ├── pricing/              # Price intelligence: effective price, history, drops (Phase 4)
│   │   ├── sales/                # Sale-event intelligence (Phase 7)
│   │   ├── recommendation/       # BUY_NOW / WAIT / WATCH engine (Phase 9)
│   │   ├── notifications/        # Watchlist & price alert dispatch (Phase 6)
│   │   ├── workers/              # Celery app, tasks, schedules (Phase 2+)
│   │   └── observability/        # Structured logging, health checks, metrics
│   ├── alembic/                  # Database migrations (Phase 1+)
│   └── tests/
│       ├── unit/
│       └── integration/
├── ml/
│   ├── training/                # XGBoost sale-price model training (Phase 8)
│   ├── inference/                # Prediction serving (Phase 8)
│   ├── features/                 # Feature engineering (Phase 8)
│   └── notebooks/                # Exploratory analysis
├── infrastructure/
│   ├── terraform/                 # Azure infrastructure as code (Phase 11)
│   ├── docker/                    # docker-compose.yml: local dev stack (backend+Postgres+Redis)
│   └── pipelines/                 # Azure DevOps pipeline definitions (Phase 11)
├── .cursor/rules/                 # Cursor project rules enforcing the phase-by-phase process
├── .env.example                   # Documented environment variables (no real secrets)
└── .gitignore
```

Directories not yet populated with implementation code (`retailer_adapters/`, `collectors/`,
`normalization/`, `matching/`, `pricing/`, `sales/`, `recommendation/`, `notifications/`,
`workers/`, `frontend/`, `ml/`, `infrastructure/terraform/`, `infrastructure/pipelines/`, ...)
currently contain only a `README.md` describing their intended purpose.
`infrastructure/docker/` now contains the local development Docker Compose file described
above.

## Development Process

This project is built strictly **phase by phase**. See `ROADMAP.md` for the phase plan and
`DEVELOPMENT_RULES.md` for the rules that govern implementation, testing, secrets handling,
and reporting. These rules are also encoded as Cursor project rules under `.cursor/rules/` so
that AI-assisted contributions follow the same process.

## Getting Started

The backend now has a working database schema and a production-quality FastAPI application
foundation (versioned API, Redis, Docker). See [`backend/README.md`](./backend/README.md) for
local setup, running migrations, running the API (locally or via Docker Compose), and running
tests. There is no frontend yet (Phase 5+).

## License

Not yet decided.
