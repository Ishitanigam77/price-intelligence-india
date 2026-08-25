# ROADMAP.md — PriceRadar India

> This roadmap defines the phase boundaries referenced by `DEVELOPMENT_RULES.md` and enforced
> by `.cursor/rules/`. Phases are implemented strictly in order, and only when explicitly
> requested. Scope descriptions here are intentionally high-level; each phase will be scoped
> precisely at the time it is requested.

## Phase 0 — Project Scaffolding (this phase)

- Architecture, tech stack, development rules, and roadmap documentation.
- Initial directory structure for frontend, backend, ML, and infrastructure — no code logic.
- `.env.example` and `.gitignore`.
- Cursor project rules enforcing the phase-by-phase process.
- **Explicitly excluded**: database models, real APIs, real retailer integrations, ML models,
  authentication, production deployment.

## Phase 1 — Core Domain Model & Database Foundation

- Define the Product / Product Variant / Retailer Listing / Seller / Price Observation domain
  entities.
- SQLAlchemy models and initial Alembic migration.
- Repository interfaces and implementations for the core entities.
- Basic FastAPI app skeleton with health check endpoint.
- Unit tests for domain logic and repositories.

## Phase 2 — Retailer Adapter Framework

- Define the common retailer adapter interface (contract every retailer integration must
  implement).
- Implement one reference adapter against a legitimate, permitted data source (official API or
  affiliate feed) to validate the interface — not a scraped integration.
- Collector orchestration skeleton (how collectors invoke adapters and hand off raw data).
- Adapter-level tests using recorded/fixture data (no live network calls in CI).

## Phase 3 — Product Normalization & Matching

- Normalization pipeline: turning raw adapter output into a common product shape.
- Matching engine v1: deterministic matching (GTIN/EAN/UPC, brand + model number + variant
  attributes).
- Groundwork for future semantic matching (Sentence Transformers) without requiring it yet.

## Phase 4 — Price Intelligence

- Price Observation storage and historical tracking.
- Effective price calculation (MRP, discounts, cashback, fees) with strict separation between
  observed and calculated values.
- Genuine price-drop detection logic.

## Phase 5 — Search, Compare & Frontend MVP

- FastAPI search/compare endpoints.
- Next.js frontend: product search, product detail with retailer comparison table, historical
  price chart.
- Clerk authentication wired into frontend and backend.

## Phase 6 — Watchlists, Alerts & Notifications

- User watchlists.
- Price alert rules and notification dispatch (email and/or other channels).
- Retailer health / data freshness indicators surfaced in the UI.

## Phase 7 — Sale-Event Intelligence

- Sale event detection and tracking (e.g. recurring seasonal sales).
- Historical sale price analysis per product/category.

## Phase 8 — ML: Sale-Price Prediction

- Feature engineering pipeline (current price, 7/30/90-day averages, historical min/max,
  volatility, previous sale prices, retailer, seller, category, brand, sale event, days until
  sale).
- XGBoost training pipeline with `INSUFFICIENT_DATA` fallback when history is inadequate.
- Inference service consumed by the Recommendation Engine.

## Phase 9 — Recommendation Engine

- BUY_NOW / WAIT / WATCH recommendation logic combining price intelligence, sale-event
  intelligence, and ML predictions.
- Human-readable explanations for why a recommendation or offer was chosen.

## Phase 10 — Retailer Ecosystem Expansion

- Onboarding process/checklist for adding new retailer adapters at scale (targeting 100+
  retailers over time), without modifying core engine code.
- Retailer health monitoring and alerting on data collection issues.

## Phase 11 — Infrastructure & Production Readiness

- Terraform modules for Azure resources (App hosting, PostgreSQL, Redis, Key Vault, ACR,
  Monitor/Application Insights).
- Azure DevOps pipelines: CI (build, lint, test, security scan) → build image → push to ACR →
  deploy dev → integration tests → manual approval → deploy production.
- Full observability: structured logging, health checks, metrics, alerting.

## Phase Ordering Notes

- Phases are sequential by default but a later phase may be pulled forward only on explicit
  instruction. Skipping ahead without instruction is a violation of `DEVELOPMENT_RULES.md`.
- This roadmap will be revised as the project evolves; revisions happen deliberately, not as a
  side effect of unrelated work.
