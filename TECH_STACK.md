# TECH_STACK.md — PriceRadar India

> Status: Phases 1–14A application work plus **Phase 15 production DevOps** (GitHub Actions CI,
> Azure DevOps CD, Docker images, Terraform for Azure). PostgreSQL, SQLAlchemy, Alembic, a
> production-quality FastAPI application, Redis, Celery workers, the retailer adapter framework
> (mock + Amazon.in / Flipkart affiliate adapters), and the Next.js frontend are wired up.
> **Phase 16** adds observability; **Phase 17** adds localized security hardening
> (`SECURITY.md`). Azure resources are defined in Terraform but live apply/verification
> is **PENDING — LIVE AZURE VERIFICATION** — see `PRODUCTION_READINESS.md` and
> `infrastructure/CICD.md`.

## Frontend

| Technology | Purpose |
|---|---|
| Next.js | React framework, SSR/ISR for product & comparison pages, API routes for BFF concerns |
| TypeScript | Type safety across the frontend codebase |
| Tailwind CSS | Utility-first styling, consistent design system |

## Backend

| Technology | Purpose |
|---|---|
| Python | Primary backend language |
| FastAPI | HTTP API framework, request validation via Pydantic, OpenAPI docs |

## Database

| Technology | Purpose |
|---|---|
| PostgreSQL | Primary relational data store (products, variants, listings, sellers, observations, users, watchlists, alerts) |
| SQLAlchemy | ORM / data access layer used by repositories |
| Alembic | Schema migrations |

## Caching & Messaging

| Technology | Purpose |
|---|---|
| Redis | Read-through cache (hot product/price data), Celery broker and result backend |

## Background Jobs

| Technology | Purpose |
|---|---|
| Celery | Scheduled and triggered background jobs: collection, normalization, matching, price recalculation, sale-event detection, notification dispatch |

## Authentication

| Technology | Purpose |
|---|---|
| Clerk | User identity, sign-in/sign-up, session/token issuance (frontend); backend verifies Clerk tokens on protected routes |

## Data Collection

| Technology | Purpose |
|---|---|
| Python | Collector and adapter implementation language (shared with backend) |
| httpx / Requests | HTTP clients for official APIs, affiliate/partner feeds, and other permitted structured sources |
| Playwright | Used **only** where a legitimate, permitted integration requires browser automation (e.g. an authorized partner portal with no API) — never to bypass anti-bot protections, CAPTCHAs, or terms of service |

## Machine Learning

| Technology | Purpose |
|---|---|
| pandas | Data wrangling for feature engineering and training pipelines |
| scikit-learn | Preprocessing, baseline models, evaluation utilities |
| XGBoost | Primary sale-price prediction model |
| Sentence Transformers | Semantic embeddings for product matching (title/description similarity) |

## Infrastructure

| Technology | Purpose |
|---|---|
| Docker | Containerization of frontend, backend, workers, and ML services |
| Terraform | Infrastructure as code for all Azure resources |
| Azure | Cloud hosting platform |
| Azure Container Registry (ACR) | Container image registry |
| Azure Key Vault | Secret storage, referenced via managed identity — never committed to source |
| Azure Monitor / Application Insights | Metrics, logs, traces, alerting |

## CI/CD

| Technology | Purpose |
|---|---|
| Azure DevOps Pipelines | CI (build, lint, test, security scan) and CD (build image → push to ACR → deploy dev → integration tests → manual approval → deploy production) |

## Version Control & Collaboration

| Technology | Purpose |
|---|---|
| GitHub | Source control, pull requests, branch protection; mirrors into Azure DevOps for pipeline execution |

## Notes on Technology Introduction Order

Technologies are introduced into the repository only when the phase that needs them begins
(see `ROADMAP.md`). For example:

- Database (PostgreSQL/SQLAlchemy/Alembic) is introduced when the domain model is implemented,
  not in Phase 0.
- Playwright is only introduced for a specific, named, permitted retailer integration — never
  added speculatively.
- ML libraries (XGBoost, NumPy) are introduced with Phase 10 sale-price prediction. They
  train only on stored observations and sale events; missing history yields `INSUFFICIENT_DATA`.
