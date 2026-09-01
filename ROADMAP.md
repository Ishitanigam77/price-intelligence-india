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
  implement). **Implemented** (`backend/app/retailer_adapters/base/`).
- Validate the interface with fixture-backed mock adapters (no live network calls, no real
  retailer). **Implemented** (`mock_retailer_a/b/c`). A reference adapter against a
  legitimate permitted data source is deferred until a real retailer is onboarded.
- Collector orchestration skeleton (how collectors invoke adapters and hand off raw data).
  **Not in this increment** — the framework's `RetailerFleet` / registry are the call
  surface collectors will use; Celery scheduling belongs with workers.

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

> **Delivery note:** in the implemented sequence this work is **Phase 10** (after Phase 7
> historical intelligence, Phase 8 frontend, and Phase 9 sale-event intelligence). See
> Phase 10 below.

## Phase 9 — Recommendation Engine

- BUY_NOW / WAIT / WATCH recommendation logic combining price intelligence, sale-event
  intelligence, and ML predictions.
- Human-readable explanations for why a recommendation or offer was chosen.

> **Delivery note:** in the implemented sequence this work is **Phase 11** (after Phase 10
> sale-price prediction). See Phase 11 below.

## Phase 10 — ML: Sale-Price Prediction

Implemented after Phase 9 sale-event intelligence. Scope matches the ML work originally
listed under Phase 8 above:

- Feature engineering from stored observations and sale events, with mandatory leakage
  prevention (no future observations, no target-as-feature, inferred events not treated as
  known upcoming sales).
- Chronological train / validation / test splits (not random).
- XGBoost training, MAE/RMSE evaluation, residual-based prediction intervals, model
  versioning/metadata, and inference that always labels outputs as predictions.
- `INSUFFICIENT_DATA` when legitimate history cannot support training or a reliable
  evaluation split. Training data is never fabricated.

Retailer-ecosystem expansion (onboarding at scale, collection-health alerting) remains a
later increment and is **not** part of this phase.

## Phase 11 — BUY / WAIT Recommendation Engine (this increment)

Implemented after Phase 10 sale-price prediction. Scope matches the recommendation work
originally listed under Phase 9 above:

- Deterministic BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA decisions from current effective
  price, historical percentile/low/averages/trend, optional Phase 10 predicted sale price and
  prediction confidence, upcoming sale events, expected savings, and data freshness.
- Explicit, explainable rules. No LLM or additional ML model is a decision maker.
- Phase 10 artifacts are consumed as labeled PREDICTED inputs only; they are not modified
  or retrained. Missing or low-confidence predictions fall back to historical/current-price
  signals and are never invented.
- Human-readable reasons citing the rules and values that actually fired.

Infrastructure & production readiness (Terraform, Azure DevOps pipelines, Azure Monitor
export) remains a later increment and is **not** part of this phase.

## Phase 12 — User Authentication and Personalization

- Clerk as the identity provider (sign up, sign in, sign out, session).
- Internal PostgreSQL user mapping (`clerk_user_id` → `users.id`), no application passwords.
- Protected backend APIs and frontend routes (`/watchlist`, `/alerts`, `/profile`).
- User-owned watchlists, saved products, target prices, alerts, preferences, and profile.
- Ownership enforced at the service/repository layer; client-supplied user ids cannot override
  identity. See `AUTHENTICATION.md`.

## Phase 13 — Scalable Data Collection

Implemented after Phase 12 authentication. Background collection only:

- Celery workers with Redis as broker and result backend (environment-configured).
- Five jobs: retailer product search, product refresh, price refresh, availability refresh,
  sale-event refresh.
- Per-retailer isolation, retries with bounded exponential backoff, timeouts, per-retailer
  rate limiting, and idempotent job records (`CollectionJob` / `CollectionError`).
- Uses `RetailerRegistry` and mock/approved adapters only. No real-retailer scraping,
  notification delivery, billing, or collection UI.

## Phase 14A — First real retailer integration batch (this increment)

Implemented after Phase 13 collection. **Only** this batch:

- Inspect the existing `RetailerAdapter` / `RetailerRegistry` contract (unchanged).
- Add a small first batch of real Indian retailer adapters that have a legitimate, documented
  data-acquisition path (official API or official affiliate API/feed).
- **Implemented:** Amazon.in (Associates Creators API) and Flipkart (Affiliate API 1.0).
- Other major Indian retailers were evaluated and skipped when no clearly permitted, documented
  catalog API/feed was available (see `backend/app/retailer_adapters/INTEGRATIONS.md`).
- Fixture/mocked tests only unless approved credentials are already configured. No scraping,
  Playwright, CAPTCHA bypass, or hardcoded secrets.
- Phase 13 collection architecture and the comparison engine are not modified.
- **Explicitly excluded:** Phase 14B and later retailer-expansion work.

## Phase 15 — Production DevOps (this increment)

Implemented after Phase 14A. Production-grade CI/CD and Azure infrastructure **as code** only:

- GitHub Actions CI (validate, lint, unit/integration tests including Phase 13/14 tests, security scanning, Docker builds). No GitHub deploy.
- Azure DevOps YAML pipelines for the full CD path: Docker → ACR (immutable tags) → development → smoke tests → staging → **Azure DevOps Environment approval** → production. No `terraform destroy`. Production is not automatic.
- Multi-stage Docker images for frontend, backend, workers, and ML; local Compose updated to those services.
- Terraform for networking, ACR, PostgreSQL, Redis, Key Vault, Container Apps, monitoring, and storage across **dev**, **staging**, and **prod**. Existing Azure resources must be imported, not recreated.

**Explicitly excluded:** Phase 16 and later. No additional retailers, no application redesign, no automatic production deploy from this repository change.

## Phase 16 — Observability (this increment)

Implemented after Phase 15. Application and Azure Monitor observability **only**:

- Structured JSON logs (timestamp, service, environment, correlation ID, operation, status,
  duration, error type) with secret redaction.
- Custom metrics for API, retailer adapters/collection, workers, database, and ML.
- Liveness, readiness, and dependency health checks (no secrets in probe bodies).
- Application Insights export via environment-configured connection string (Key Vault /
  managed identity from Phase 15). Missing telemetry config does not block startup.
- Terraform workbooks, diagnostic settings, and alerts for API, collection, workers,
  database, and ML. No `terraform apply` or `terraform destroy` in this change.
- Frontend health plus error/navigation telemetry posted to a server route (connection
  string stays server-side).

**Explicitly excluded:** Phase 17 and later. Phase 15 CI/CD, Docker, ACR, and deploy
pipelines are preserved. No production deploy from this increment.

## Phase 17 — Application Security Review and Hardening (this increment)

Implemented after Phase 16 observability. Repository-wide security review and
**localized** hardening only:

- Authentication/authorization review (Clerk JWT, ownership scoping). No Clerk redesign.
- Input validation, CORS tightening, security headers, in-process API rate limiting.
- Secret scanning, dependency/container/Terraform scanner execution where tooling exists.
- Safe error responses and log redaction preserved from Phase 16.
- Production ACR push moved behind the existing Azure DevOps `production` Environment approval.
- `SECURITY.md` documents the model, findings, and pending live Azure verification.

**Explicitly excluded:** Phase 18 and later. No application redesign, no Azure service
replacement, no `terraform destroy`, no production deploy from this increment.

## Phase 18 — Full Production Readiness Review (this increment)

Implemented after Phase 17 security hardening. **Repository review only** — no new
product phase, no architecture rewrite, and no unapproved production deploy:

- Review architecture, code quality, database, APIs, frontend, adapters, matching,
  pricing, history, sale events, ML, BUY/WAIT, Clerk, watchlists, alerts, workers,
  Docker, Terraform, Azure/ADO configuration, monitoring, security, testing, and docs.
- Run the complete available test suite. Live Azure verification is classified
  **PENDING — LIVE AZURE VERIFICATION** when the subscription is not activated.
- Fix only clearly safe, localized, backward-compatible issues.
- Preserve Phase 15 CI/CD, Phase 16 observability, and Phase 17 security controls.
- Record findings and readiness in `PRODUCTION_READINESS.md`.

**Explicitly excluded:** Any Phase 20+. No `terraform destroy`, no unapproved
production deployment, no technology replacements, no CI/CD or observability redesign.

## Phase 19 — Sale Timing + Price Intelligence (this increment)

Implemented after Phase 18. Extends existing comparison, history, sale-event, Phase 10
XGBoost, and Phase 11 recommendation systems. Does **not** create duplicate engines.

- Monthly price intelligence from stored `PriceSnapshot` observations (does not replace
  7/30/90/180-day history).
- MAJOR / ORDINARY / UNKNOWN classification and reusable sale families.
- Previous-year → current-year mapping: fixed-calendar, festival-relative, recurring,
  retailer-specific. CONFIRMED only when a persisted permitted/curated future event exists.
- Expected sale windows, expected sale prices (reusing Phase 10 when usable), expected
  savings, current vs expected best retailer, ordinary vs major comparison.
- Optional urgency overlay on Phase 11 (`BUY_IN_ORDINARY_SALE` / `WAIT_FOR_MAJOR_SALE`).
  Absent urgency preserves BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA.

**Projected sale dates and prices are evidence-based estimates and are not guaranteed
retailer announcements.**

**Explicitly excluded:** Phase 20+. No scraping, no Terraform apply/destroy, no production
deploy, no second ML or recommendation engine.

## Phase Ordering Notes

- Phases are sequential by default but a later phase may be pulled forward only on explicit
  instruction. Skipping ahead without instruction is a violation of `DEVELOPMENT_RULES.md`.
- This roadmap will be revised as the project evolves; revisions happen deliberately, not as a
  side effect of unrelated work.
