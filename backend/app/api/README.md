# app/api/

FastAPI routers and request/response DTOs. Handles HTTP concerns only: routing, input
validation, auth enforcement, and translating between HTTP and the domain/service layer.

**Status**:

- `health.py` — Phase 1: unversioned `GET /health` (liveness) and `GET /health/ready`
  (liveness + database connectivity). Kept for backward compatibility and simple
  container/orchestrator probes.
- `deps.py` — FastAPI dependency providers (DB session, Redis client, one per repository, and
  `PriceService`), added as part of the FastAPI backend application foundation.
- `errors.py` — centralized exception handling (`NotFoundError`, validation errors, domain
  errors, database errors, and unexpected errors), all returning the same
  `app.schemas.common.ErrorResponse` envelope. Never exposes stack traces, SQL, or secrets.
- `v1/` — the versioned `/api/v1/` API: `health`, `products`, `retailers`, `prices`, `deals`.
  Read-only foundation over the Phase 1 domain model — no matching, pricing, or recommendation
  business logic.

Must not contain business logic — that belongs in `app/domain/`, `app/pricing/`,
`app/matching/`, etc.
