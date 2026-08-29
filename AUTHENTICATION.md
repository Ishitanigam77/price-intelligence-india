# AUTHENTICATION.md — Phase 12 user authentication and personalization

Clerk is the identity provider for PriceRadar India. This application never stores passwords
and never treats a client-supplied user id as the authenticated identity.

## Clerk setup

1. Create a Clerk application (development instance is enough locally).
2. Copy the **publishable key** and **secret key** from the Clerk dashboard.
3. Copy the JWKS URL for the instance (typically
   `https://<instance>.clerk.accounts.dev/.well-known/jwks.json`) and the issuer
   (`https://<instance>.clerk.accounts.dev`).
4. Put values only in uncommitted env files (repo-root `.env`, `frontend/.env.local`). Never
   commit real credentials. `.env.example` files contain placeholders only.

Frontend (browser-safe):

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
```

Frontend server-only (Next.js middleware; never prefix with `NEXT_PUBLIC_`):

```
CLERK_SECRET_KEY=
```

Backend (token verification; secret key is never returned to clients):

```
CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
CLERK_JWKS_URL=
CLERK_ISSUER=
CLERK_AUDIENCE=
```

If Clerk is not configured, protected backend routes fail closed with HTTP 401. The frontend
sign-in page explains that Clerk is missing. Neither layer invents a successful session.

## Authentication flow

1. The user signs up or signs in through Clerk (`/sign-in`, `/sign-up`).
2. Clerk issues a session JWT. The Next.js client reads it via `useAuth().getToken()`.
3. The frontend sends `Authorization: Bearer <token>` on personalization API calls.
4. The backend verifies the JWT against the Clerk JWKS (`app.auth.tokens.ClerkTokenVerifier`).
5. `sub` on the verified token is the Clerk user id. It is mapped idempotently onto an internal
   PostgreSQL `users` row (`clerk_user_id` is unique). Preferences are created if missing.
6. Protected service methods receive that internal `User` and scope every query by `user.id`.

Sign-out is Clerk's session end (`UserButton` / Clerk sign-out). The backend does not store
sessions or passwords.

## Database user mapping

| Table | Role |
|---|---|
| `users` | Internal UUID + unique `clerk_user_id`. Optional email/display name synced from verified claims. **No password column.** |
| `user_preferences` | 1:1 with `users` (`email_alerts_enabled`, `default_currency`). |
| `watchlists` | Unique `(user_id, product_id)` watchlist/product association. |
| `saved_products` | Unique `(user_id, product_id)` saved-product association. |
| `target_prices` | Unique `(user_id, product_id)` user-stated target amount. |
| `price_alerts` | Unique `(user_id, product_id)` alert rule (threshold, enabled). Notification dispatch is not in this phase. |

Product catalogue tables are not duplicated; user-owned rows foreign-key to `products.id`.

## Backend authorization flow

- Catalogue routes (`/api/v1/products`, `/retailers`, `/prices`, `/deals`, `/sale-events`,
  health) remain public.
- Personalization routes depend on `get_current_user`. Missing/invalid tokens return **401**
  (`unauthenticated`).
- Request bodies use `extra="forbid"`. `user_id` / `owner_id` / `clerk_user_id` in a create or
  patch body is **422**, not an ownership override.
- Repositories for user-owned entities always filter by the authenticated `user_id`. A lookup
  of another user's id returns **404** (the row is not in the caller's set). This is the IDOR
  control: changing an id in the URL cannot read or mutate another user's data.
- Duplicate `(user, product)` creates return **409**.

## Protected frontend routes

| Path | Behaviour |
|---|---|
| `/watchlist` | Requires Clerk session. Lists `GET /api/v1/watchlists`. |
| `/alerts` | Requires Clerk session. Lists `GET /api/v1/alerts`. |
| `/profile` | Requires Clerk session. `GET`/`PATCH /api/v1/me`. |
| `/sign-in`, `/sign-up` | Clerk hosted components (or a configuration message if keys are absent). |

`src/middleware.ts` calls `auth.protect()` on those routes when Clerk keys are present. If
keys are absent, those routes redirect to `/sign-in` and do not show another user's data.

## Ownership rules

An authenticated user may access **only** their own watchlists, alerts, saved products, target
prices, preferences, and profile. Ownership is taken from the verified Clerk identity mapped to
the internal user, never from the request body or a `user_id` query parameter.

## API endpoints (Phase 12)

| Method | Path | Auth |
|---|---|---|
| GET, PATCH | `/api/v1/me` | required |
| POST, GET | `/api/v1/watchlists` | required |
| GET, DELETE | `/api/v1/watchlists/{id}` | required |
| POST, GET | `/api/v1/saved-products` | required |
| GET, DELETE | `/api/v1/saved-products/{id}` | required |
| POST, GET | `/api/v1/target-prices` | required |
| GET, PATCH, DELETE | `/api/v1/target-prices/{id}` | required |
| POST, GET | `/api/v1/alerts` | required |
| GET, PATCH, DELETE | `/api/v1/alerts/{id}` | required |

## Running authentication tests

Backend (from `backend/`, with `TEST_DATABASE_URL` and Redis as for the rest of the suite):

```bash
pytest tests/unit/auth tests/unit/services tests/unit/test_config.py
pytest tests/integration/test_api_authorization.py tests/integration/test_exception_handling.py
pytest
```

Authorization tests use `StaticTokenVerifier` so they do not require live Clerk credentials.
JWT unit tests sign tokens with locally generated RSA keys. They do not contact Clerk.

Frontend:

```bash
cd frontend
npm test
```

Clerk UI is mocked in Vitest. Live Clerk sign-in is not exercised unless real keys are
configured in a local browser session.

## What this phase does not include

- Notification email/push dispatch
- Password storage or password-reset APIs
- Changing Phase 10 XGBoost or Phase 11 recommendation engines (those modules are unchanged)
- Any Phase 13+ work
