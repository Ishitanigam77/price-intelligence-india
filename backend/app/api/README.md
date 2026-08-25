# app/api/

FastAPI routers and request/response DTOs. Handles HTTP concerns only: routing, input
validation, auth enforcement, and translating between HTTP and the domain/service layer.

**Status**: empty scaffold. Introduced in **Phase 1** (basic health check) and expanded through
later phases as endpoints are needed. Must not contain business logic — that belongs in
`app/domain/`, `app/pricing/`, `app/matching/`, etc.
