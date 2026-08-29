# app/auth/

Clerk integration: verifies Clerk-issued session tokens on protected backend routes and maps
the verified Clerk user id onto an internal PostgreSQL `User`. No custom password or session
store.

**Status**: implemented in **Phase 12 — User Authentication and Personalization**.

- `tokens.py` — JWKS-backed JWT verification (`ClerkTokenVerifier`). Fails closed when Clerk
  is not configured. `StaticTokenVerifier` exists only for tests.
- `identity.py` — `ClerkIdentity` (`clerk_user_id` = Clerk `sub`).
- `dependencies.py` — FastAPI `get_current_user`: bearer token → verified identity →
  idempotent internal user upsert. Never trusts a client-supplied user id.
- `errors.py` — `AuthenticationError` (401) and `AuthorizationError` (403).

See `../../AUTHENTICATION.md` at the repository root for setup, environment variables, and
ownership rules.
