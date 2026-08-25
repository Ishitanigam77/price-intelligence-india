# PROJECT_ARCHITECTURE.md — PriceRadar India

> Status: **Phase 1 — Core Domain Model & Database Foundation implemented**, plus a **FastAPI
> backend application foundation** (application factory, `/api/v1/` versioned routing, Redis
> infrastructure, centralized exception handling, Docker support — see `backend/README.md`)
> and the **retailer adapter framework** with fixture-backed mock adapters (see
> `backend/app/retailer_adapters/` and `RETAILER_ARCHITECTURE.md`). Real retailer
> integrations, matching, pricing, ML, and other later-phase business logic described below
> are still targets, not yet built. This document describes the target architecture the
> codebase will grow into, phase by phase.

## 1. Vision

PriceRadar India is an India-focused price intelligence platform. It continuously discovers
product listings across a growing network of Indian online retailers, identifies identical
products and variants across those retailers, tracks their prices over time, and helps users
decide **when** and **where** to buy.

This is explicitly **not** a two-retailer comparison tool. The architecture must scale to
100+ retailers across many categories without rewriting the core comparison, matching, or
pricing engines. Every retailer integration is isolated behind a common adapter interface so
that adding retailer #50 or #100 is a matter of writing a new adapter, not modifying core logic.

## 2. Architectural Principles

1. **Retailer isolation.** All retailer-specific logic (parsing, auth, rate limits, feed
   formats) lives inside a retailer adapter. The core engine only ever talks to the common
   adapter interface, never to a specific retailer's API/HTML shape.
2. **Layered, unidirectional dependencies.** Presentation → API → Domain/Services →
   Repositories → Database. Domain logic never imports from the API layer or from a specific
   retailer adapter.
3. **Separation of observed, calculated, and predicted data.** A price that was *observed* on
   a retailer page, a price that was *calculated* (e.g. effective price after coupons), and a
   price that was *predicted* by a model are distinct, clearly labeled data types. They are
   never merged into a single ambiguous "price" field.
4. **Legitimate data acquisition only.** Data collection uses official APIs, affiliate/partner
   feeds, and other permitted structured sources. The system never bypasses CAPTCHA,
   authentication, anti-bot protections, rate limits, or `robots.txt` restrictions, and never
   violates retailer terms of service. See `RETAILER_ARCHITECTURE.md`.
5. **Incremental, phase-gated delivery.** Each phase produces a working, tested increment.
   Future phases are never implemented ahead of schedule. See `ROADMAP.md` and
   `DEVELOPMENT_RULES.md`.
6. **Everything is observable.** Health checks, structured logs, and metrics are first-class,
   not an afterthought bolted on at the end.

## 3. System Context (Target State)

```
                         ┌─────────────────────┐
                         │   Next.js Frontend   │
                         │  (search, compare,   │
                         │  watchlists, charts)  │
                         └──────────┬───────────┘
                                    │ HTTPS / REST
                                    ▼
                         ┌─────────────────────┐
                         │   FastAPI Backend    │
                         │  (API layer)          │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────────┐
        │ Domain / Services│ │ Recommendation │ │ Notifications        │
        │ (matching,       │ │ Engine         │ │ (alerts, watchlists) │
        │  pricing, sales) │ └───────┬────────┘ └──────────┬──────────┘
        └────────┬─────────┘         │                     │
                 ▼                   ▼                     ▼
        ┌────────────────────────────────────────────────────────┐
        │                  Repositories (data access)             │
        └───────────────────────────┬──────────────────────────────┘
                                     ▼
                         ┌─────────────────────┐
                         │     PostgreSQL        │
                         └─────────────────────┘

        ┌─────────────────────────────────────────────────────────┐
        │                  Background Workers (Celery)              │
        │  Collectors → Retailer Adapters → Normalization →         │
        │  Matching → Price Intelligence → Sale-Event Intelligence  │
        └───────────────────────────┬─────────────────────────────┘
                                     │
                         ┌─────────────────────┐
                         │  Retailer Adapters    │
                         │  (one per retailer,   │
                         │   common interface)   │
                         └─────────────────────┘

        ┌─────────────────────────────────────────────────────────┐
        │            ML Training / Inference (offline + async)      │
        │  Feature store → XGBoost sale-price model → Inference API │
        └─────────────────────────────────────────────────────────┘

        Redis: cache + Celery broker/result backend
        Clerk: authentication (frontend + backend token verification)
        Azure: hosting, Key Vault, Container Registry, Monitor
```

## 4. Layers and Responsibilities

| Layer | Directory (target) | Responsibility | Depends on |
|---|---|---|---|
| Frontend | `frontend/` | Search UI, comparison UI, watchlists, alerts, charts, retailer health display | Backend API only (via HTTP) |
| API | `backend/app/api/` | HTTP request/response, auth enforcement, input validation, DTOs | Domain, Repositories |
| Auth | `backend/app/auth/` | Clerk session/token verification, request identity | Core |
| Domain | `backend/app/domain/` | Business entities and rules (Product, Variant, Listing, Seller, Observation) | Nothing below it |
| Normalization | `backend/app/normalization/` | Cleans and standardizes raw retailer product data into a common shape | Domain |
| Matching | `backend/app/matching/` | Decides whether listings refer to the same product/variant | Domain, Normalization |
| Pricing (Price Intelligence) | `backend/app/pricing/` | MRP/effective price computation, historical tracking, drop detection | Domain, Repositories |
| Sales (Sale-Event Intelligence) | `backend/app/sales/` | Detects and tracks sale events (e.g. Big Billion Days, Republic Day Sale) | Domain, Pricing |
| Recommendation | `backend/app/recommendation/` | BUY_NOW / WAIT / WATCH decisions with explanations | Pricing, Sales, ML inference |
| Retailer Adapters | `backend/app/retailer_adapters/` | One adapter per retailer implementing the common interface | Nothing above it |
| Collectors | `backend/app/collectors/` | Orchestrate scheduled/triggered data acquisition via adapters | Retailer Adapters |
| Workers | `backend/app/workers/` | Celery app, task definitions, schedules | Collectors, Normalization, Matching, Pricing, Sales |
| Repositories | `backend/app/repositories/` | Data access abstractions over the database | Database models |
| Database | `backend/app/db/`, `backend/alembic/` | SQLAlchemy models, sessions, Alembic migrations | PostgreSQL |
| Notifications | `backend/app/notifications/` | Price alert delivery, watchlist notifications | Repositories, Pricing |
| Observability | `backend/app/observability/` | Structured logging, health checks, metrics | Cross-cutting |
| ML Training | `ml/training/` | Offline model training pipelines (XGBoost sale-price model) | Historical price data (read-only) |
| ML Inference | `ml/inference/` | Serves predictions to the Recommendation Engine | Trained model artifacts |
| Infrastructure | `infrastructure/` | Terraform, Docker, CI/CD pipeline definitions | N/A |

## 5. Product Model (Conceptual)

```
Product
  └── Product Variant        (e.g. 128GB / Black)
        └── Retailer Listing  (e.g. this variant, as listed by Retailer A)
              └── Seller       (the actual seller on a marketplace listing)
                    └── Price Observation  (one timestamped observation of price/availability)
```

Rules:

- A **Product** is a distinct real-world product (e.g. "Apple iPhone 16").
- A **Product Variant** is a specific configuration (storage, color, size, etc.). Variants are
  never merged with each other even if superficially similar.
- A **Retailer Listing** is a specific variant as offered by a specific retailer/marketplace.
- A **Seller** is the entity fulfilling a listing (relevant on marketplaces with multiple
  sellers per listing, e.g. Amazon.in, Flipkart).
- A **Price Observation** is an immutable, timestamped record of what was observed at a point
  in time. Observations are never edited after the fact — corrections are new observations.

See `DATA_FLOW.md` for how data moves through these entities, and `RETAILER_ARCHITECTURE.md`
for how retailer adapters populate them.

> **Phase 1 naming note**: the implemented SQLAlchemy models use `RetailerProduct` for
> "Retailer Listing" (a `ProductVariant` as offered by a specific `Retailer`) and `PriceSnapshot`
> for "Price Observation". `Seller` is implemented as its own entity (scoped to a `Retailer`)
> and referenced directly from `PriceSnapshot`, since a given `RetailerProduct` can have
> multiple sellers' offers recorded over time. Phase 1 also adds `Category`, `Brand`, and
> `ProductIdentifier` (GTIN/EAN/UPC/MPN/...), which this conceptual model didn't originally
> enumerate but which are needed for product lookup and future cross-retailer matching. See
> `backend/app/db/models/` for the authoritative schema.

## 6. Price Data Model (Conceptual)

Each Price Observation distinguishes:

- **MRP** — manufacturer's stated maximum retail price (where available).
- **Displayed price** — the price shown on the retailer page/feed.
- **Coupon discount**, **payment discount**, **cashback** — separate, itemized adjustments,
  never pre-merged into a single number unless the retailer itself only ever exposes a single
  final number.
- **Delivery fee**, **platform fee** — additive costs.
- **Effective price** — a *calculated* value, only produced when the inputs required to
  calculate it are verified/available. Never guessed.
- **Observed historical price** — a fact about the past, from stored Price Observations.
- **Predicted price** — an *ML output*, always labeled as a prediction, with a confidence
  indicator, and never displayed as if it were an observed fact.

## 7. Cross-Cutting Concerns

- **Authentication**: Clerk on the frontend; backend verifies Clerk-issued tokens. No custom
  password/session handling.
- **Caching & messaging**: Redis for caching hot reads (product pages, price history) and as
  the Celery broker/result backend.
- **Background processing**: Celery workers run collectors, normalization, matching, pricing
  recalculation, sale-event detection, and notification dispatch.
- **Observability**: structured (JSON) logs, `/health` and `/ready` endpoints per service,
  metrics exported to Azure Monitor / Application Insights.
- **Infrastructure**: Docker images built per service, pushed to Azure Container Registry,
  provisioned via Terraform, deployed through Azure DevOps Pipelines.

## 8. Non-Goals (explicitly out of scope for the architecture)

- Scraping behind authentication walls, CAPTCHAs, or anti-bot systems.
- Circumventing retailer rate limits or `robots.txt`.
- Fabricating, estimating, or "filling in" retailer prices that were not actually observed or
  provided by a legitimate source.
- Treating this as a two-retailer (Amazon vs Flipkart) comparison tool — the design must hold
  for 100+ retailers.

## 9. Related Documents

- `TECH_STACK.md` — concrete technology choices per layer.
- `DEVELOPMENT_RULES.md` — phase-by-phase engineering rules.
- `ROADMAP.md` — phase plan.
- `RETAILER_ARCHITECTURE.md` — retailer adapter contract and data acquisition policy.
- `DATA_FLOW.md` — end-to-end data flow from acquisition to UI.
