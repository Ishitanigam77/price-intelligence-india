# app/api/

FastAPI routers and request/response DTOs. Handles HTTP concerns only: routing, input
validation, auth enforcement, and translating between HTTP and the domain/service layer.

**Status**: `health.py` implemented in **Phase 1** — `GET /health` (liveness) and
`GET /health/ready` (liveness + database connectivity). Expanded through later phases as real
endpoints are needed. Must not contain business logic — that belongs in `app/domain/`,
`app/pricing/`, `app/matching/`, etc.
