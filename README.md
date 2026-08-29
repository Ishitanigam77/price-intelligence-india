# PriceRadar India

An India-focused price intelligence platform that discovers product listings across a growing
network of Indian online retailers, identifies identical products/variants across them, tracks
price history, detects genuine price drops and sale events, and recommends whether to
**BUY_NOW**, **WAIT**, or **WATCH**.

> **Status:** backend through sale-event intelligence, sale-price prediction, the BUY /
> WAIT recommendation engine, Clerk authentication, Phase 13 collection workers, and
> Phase 14A Amazon.in / Flipkart affiliate adapters is implemented (see
> `backend/README.md` and `ml/README.md`).
> The **Next.js frontend** (`frontend/`) consumes catalogue APIs for search, product details,
> price history, deals, retailers, and about. **Phase 12** adds Clerk authentication and
> user-owned watchlists, saved products, target prices, alerts, and profile (see
> `AUTHENTICATION.md`). **Phase 15** adds production DevOps (GitHub + Azure DevOps CI/CD,
> Docker, ACR, Terraform for Azure). Live retailer E2E is not run without approved credentials —
> see `backend/app/retailer_adapters/INTEGRATIONS.md`.

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
| [`AUTHENTICATION.md`](./AUTHENTICATION.md) | Phase 12 Clerk setup, user mapping, authorization, protected routes |

## Repository Structure (Scaffolding)

```
.
├── frontend/                  # Next.js + TypeScript + Tailwind CSS app (search, compare, history)
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
│   │   ├── recommendation/       # BUY_NOW / WAIT / WATCH engine (Phase 11)
│   │   ├── notifications/        # Watchlist & price alert dispatch (Phase 6)
│   │   ├── workers/              # Celery app, tasks, schedules (Phase 2+)
│   │   └── observability/        # Structured logging, health checks, metrics
│   ├── alembic/                  # Database migrations (Phase 1+)
│   └── tests/
│       ├── unit/
│       └── integration/
├── ml/
│   ├── training/                # XGBoost sale-price model training (Phase 10)
│   ├── inference/                # Prediction serving (Phase 10)
│   ├── features/                 # Feature engineering (Phase 10)
│   ├── preprocessing/            # Train-only encoding (Phase 10)
│   ├── evaluation/               # MAE/RMSE and residual intervals (Phase 10)
│   └── models/                   # Artifact versioning (Phase 10)
│   └── notebooks/                # Exploratory analysis
├── infrastructure/
│   ├── terraform/                 # Azure IaC: modules + dev/staging/prod (Phase 15)
│   ├── docker/                    # docker-compose.yml: local stack (API, worker, frontend, ML, Postgres, Redis)
│   └── pipelines/                 # Azure DevOps YAML (app CI/CD + Terraform; Phase 15)
├── .cursor/rules/                 # Cursor project rules enforcing the phase-by-phase process
├── .env.example                   # Documented environment variables (no real secrets)
└── .gitignore
```

Directories not yet populated with implementation code are called out in their own README files.
`infrastructure/` contains Phase 15 Terraform, Azure DevOps pipelines, and local Docker Compose.

## Development Process

This project is built strictly **phase by phase**. See `ROADMAP.md` for the phase plan and
`DEVELOPMENT_RULES.md` for the rules that govern implementation, testing, secrets handling,
and reporting. These rules are also encoded as Cursor project rules under `.cursor/rules/` so
that AI-assisted contributions follow the same process.

## Getting Started

See [`backend/README.md`](./backend/README.md) for API setup, migrations, and backend tests.
See [`frontend/README.md`](./frontend/README.md) for the Next.js app (`NEXT_PUBLIC_API_BASE_URL`,
dev server, lint, typecheck, and frontend tests).
See [`infrastructure/CICD.md`](./infrastructure/CICD.md) for CI/CD, Terraform, ACR, and
how to deploy safely (Phase 15).

## License

Not yet decided.
