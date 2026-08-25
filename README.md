# PriceRadar India

An India-focused price intelligence platform that discovers product listings across a growing
network of Indian online retailers, identifies identical products/variants across them, tracks
price history, detects genuine price drops and sale events, and recommends whether to
**BUY_NOW**, **WAIT**, or **WATCH**.

> **Status: Phase 0 — Project Scaffolding.** No business logic, database models, retailer
> integrations, ML models, or authentication exist yet. This repository currently contains
> only documentation, directory structure, and Cursor project rules that govern how the
> project will be built, phase by phase.

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
│   ├── app/
│   │   ├── api/                 # FastAPI routers (Phase 1+)
│   │   ├── auth/                # Clerk token verification (Phase 5+)
│   │   ├── core/                # Settings, shared config, cross-cutting utilities
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
│   ├── docker/                    # Dockerfiles / compose (introduced per-service, per-phase)
│   └── pipelines/                 # Azure DevOps pipeline definitions (Phase 11)
├── .cursor/rules/                 # Cursor project rules enforcing the phase-by-phase process
├── .env.example                   # Documented environment variables (no real secrets)
└── .gitignore
```

Each directory currently contains only a `README.md` describing its intended purpose — no
implementation code exists yet.

## Development Process

This project is built strictly **phase by phase**. See `ROADMAP.md` for the phase plan and
`DEVELOPMENT_RULES.md` for the rules that govern implementation, testing, secrets handling,
and reporting. These rules are also encoded as Cursor project rules under `.cursor/rules/` so
that AI-assisted contributions follow the same process.

## Getting Started

There is no runnable application yet — Phase 0 is documentation and scaffolding only. Once
Phase 1 introduces the backend skeleton and database, this section will be updated with setup
instructions.

## License

Not yet decided.
