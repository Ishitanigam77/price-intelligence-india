# app/api/

FastAPI routers and request/response DTOs. Handles HTTP concerns only: routing, input
validation, auth enforcement, and translating between HTTP and the domain/service layer.

**Status**:

- `health.py` — Phase 1: unversioned `GET /health` (liveness) and `GET /health/ready`
  (liveness + database connectivity). Kept for backward compatibility and simple
  container/orchestrator probes.
- `deps.py` — FastAPI dependency providers (DB session, Redis client, one per repository,
  `PriceService`, the process `RetailerRegistry`, and `ProductDiscoveryService`).
- `errors.py` — centralized exception handling (`NotFoundError`, validation errors, domain
  errors, database errors, and unexpected errors), all returning the same
  `app.schemas.common.ErrorResponse` envelope. Never exposes stack traces, SQL, or secrets.
- `v1/` — the versioned `/api/v1/` API: `health`, `products` (including
  `GET /products/search` product discovery), `retailers`, `prices`, `deals`. Catalogue routes
  remain a read-only foundation over the Phase 1 domain model. Discovery is the Phase 4
  write path and still contains no matching, pricing-intelligence, or recommendation logic.

Must not contain business logic — that belongs in `app/domain/`, `app/pricing/`,
`app/matching/`, etc.
