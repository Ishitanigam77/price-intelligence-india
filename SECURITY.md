# SECURITY.md — Phase 17 application security

This document describes the security model for PriceRadar India, the localized
hardening applied in Phase 17, classified findings, and items that require live
Azure or Azure DevOps verification.

**Live Azure RBAC, Key Vault networking, and Azure DevOps Environment approvals
were not verified against a real subscription in this change.** Do not treat this
file as proof that production identities or approvals are correctly configured in
Azure. Those checks are **PENDING LIVE AZURE VERIFICATION**.

Phase 15 CI/CD (tests, scans, immutable tags, Environment approval, no
`terraform destroy`) and Phase 16 observability (structured JSON logs, secret
redaction, health probes, Application Insights export) are preserved. This phase
does not deploy to production Azure and does not start Phase 18.

---

## 1. Authentication model

Clerk is the identity provider. The application never stores passwords.

1. The user signs in through Clerk. The frontend obtains a session JWT via
   `useAuth().getToken()` and sends `Authorization: Bearer <token>` on
   personalization API calls.
2. The backend verifies the JWT against the Clerk JWKS (`ClerkTokenVerifier`).
   Verification fails closed when the JWKS URL is missing (HTTP 401).
3. The verified `sub` claim is mapped idempotently to an internal `users` row.
   Client-supplied `user_id` / `clerk_user_id` / `owner_id` cannot override
   identity (`extra="forbid"` on mutation bodies).
4. Sign-out is Clerk session end. The backend does not store sessions.

Frontend middleware calls `auth.protect()` on `/watchlist`, `/alerts`, and
`/profile` when both the publishable key and `CLERK_SECRET_KEY` are present.
If keys are absent, those routes redirect to `/sign-in`. Frontend UI gates are
defense in depth only; the API is authoritative.

In production (`ENVIRONMENT=prod` or `production`), if Clerk JWKS is configured,
`CLERK_ISSUER` and `CLERK_AUDIENCE` are required at API startup.

Catalogue, health, deals, sale-event, prediction, and recommendation routes
remain public by product design. They are rate-limited in deployed environments.

---

## 2. Authorization model

- User-owned resources (watchlists, saved products, target prices, alerts,
  profile) are scoped by the authenticated internal `user.id` in repositories.
  Cross-user access returns **404** (IDOR control).
- There is no admin role and no HTTP API to trigger Celery collection jobs or
  ML training. Collection runs via workers; ML inference is in-process.
- Authorization is enforced server-side. Clerk `SignedIn` / `SignedOut`
  components are UI only.

---

## 3. Secret management

| Secret | Source | Never |
|---|---|---|
| Database / Redis / Celery URLs | Environment / Key Vault | Logged, committed, baked into images |
| Clerk secret key | Environment / Key Vault | Prefixed `NEXT_PUBLIC_`, logged |
| Retailer credentials | Environment / Key Vault per adapter | Stored on adapter config objects |
| Application Insights connection string | Environment / Key Vault | Logged, sent to the browser |

`.env` is gitignored. `.env.example` contains placeholders only (`changeme` for
local Compose). Production startup rejects a database URL containing `changeme`.

---

## 4. Azure security

Intended least privilege is documented in `infrastructure/IDENTITY.md`:

- Runtime: user-assigned managed identity with AcrPull, Key Vault Secrets User,
  Storage Blob Data Contributor (ML artifacts).
- CI/CD: OIDC service connections (`azure-sc-dev/staging/prod`). GitHub Actions
  has `contents: read` and does not deploy.
- Key Vault: RBAC, purge protection in staging/prod.
- PostgreSQL: private network, TLS. Redis: TLS 1.2, non-SSL port disabled.
- ACR: admin user disabled, anonymous pull disabled.
- ML Container App ingress is internal. Workers have no ingress.

**Live RBAC assignments, Key Vault firewalls, tfstate ACLs, and service
connection federation are PENDING LIVE AZURE VERIFICATION.**

Known configuration-level limitations (accepted unless operators harden them):

- One shared runtime identity is attached to frontend, backend, worker, and ML.
- Key Vault and tfstate storage default to public network access with Azure AD
  as the control (Checkov exceptions documented).
- Redis is public in Terraform defaults for dev/staging; prod disables public access.
- Private-endpoint subnet is provisioned but unused.

---

## 5. Data protection

- TLS is expected at Azure Container Apps ingress. Containers speak HTTP
  internally.
- User data is scoped by `user_id`. Catalogue data is public read.
- Predicted values are labeled as predictions and are not merged with observed
  prices.
- Request bodies, Authorization headers, cookies, and query strings are not
  written to structured request logs (Phase 16).

---

## 6. API security

| Control | Behaviour |
|---|---|
| CORS | Explicit origin list. `*` is rejected when credentials are enabled. Methods and headers are allowlisted (not `*`). |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store`. HSTS in production. |
| OpenAPI | `/docs`, `/redoc`, `/openapi.json` disabled in deployed environments (`dev` / `staging` / `prod`). |
| Rate limiting | In-process sliding window. Default 120 req/min; search, sale-price prediction, and recommendation 20 req/min. Health probes excluded. Auto-on when `ENVIRONMENT` is not `development` or `test`. |
| Validation | Pydantic/FastAPI types; mutation `extra="forbid"`; slug and `model_version` length/pattern limits. 422 responses omit submitted `input`. |
| Errors | 500/database errors return generic messages. Stack traces stay in server logs. |
| Frontend | CSP + baseline headers; `/api/telemetry` origin check, 4 KB body cap, in-memory rate limit; external `href` limited to http(s). |

---

## 7. Container security

| Image | Runtime user | Notes |
|---|---|---|
| frontend | `nextjs` | Multi-stage; `CLERK_SECRET_KEY` is runtime-only |
| backend / workers | `appuser` | Multi-stage; no secrets in layers |
| ml | `appuser` | Health process only on 8080 |

Local Compose binds published ports to `127.0.0.1`. Compose is not a production
manifest. Trivy filesystem and image scans run in GitHub Actions and Azure
DevOps (HIGH/CRITICAL).

---

## 8. CI/CD and deployment security

- GitHub Actions: validate, lint, test, pip-audit, npm audit, Checkov, Trivy.
  No deploy, no ACR push.
- Azure DevOps: same gates, then ACR push of `sha-<commit>` on `main` only.
  Development → smoke → staging → **production Environment approval** →
  production ACR push → production deploy.
- Production Terraform apply uses a saved plan and the `production` Environment.
  Pipelines never run `terraform destroy`.
- `addSpnToEnvironment: false` on AzureCLI tasks.

---

## 9. Security monitoring

Phase 16 structured logs and metrics remain the monitoring surface:

- Secret-like keys and `Bearer` fragments are redacted.
- API, worker, database, retailer, and ML custom metrics feed Azure Monitor
  workbooks and alerts when operators apply Terraform and set `alert_email`.
- Frontend errors/navigations post to `/api/telemetry` (sanitized; no stacks).

Live alert firing is PENDING (same limitation as Phase 16).

---

## 10. Known limitations / pending live verification

1. Live Azure RBAC, Key Vault network rules, ACR firewall, Redis (dev/staging)
   public access, tfstate storage ACLs, and Container Apps identities.
2. Azure DevOps Environment approvers, fork-PR policy, and whether service
   connections use OIDC vs long-lived secrets.
3. Shared runtime managed identity and full Key Vault secret mount on backend
   and worker (least-privilege split is a future infra change, not done here).
4. In-process rate limiting is per replica, not a shared Redis limiter.
5. Clerk JWT template / audience alignment must be set by operators in Clerk
   and `CLERK_AUDIENCE`.
6. CSP allows `'unsafe-inline'` / `'unsafe-eval'` because Next.js and Clerk
   require them today.

---

## Security findings

Status values: **FIXED**, **ACCEPTED / EXISTING**, **PENDING LIVE AZURE VERIFICATION**.

### CRITICAL

None identified in this review.

### HIGH

| ID | Component | Issue | Impact | Remediation | Status |
|---|---|---|---|---|---|
| H1 | API | Unauthenticated expensive endpoints (product search with adapter fan-out and writes; ML prediction; recommendation) had no HTTP rate limit | Cost, retailer quota exhaustion, CPU/DB abuse | In-process rate limiting (stricter bucket for those paths). Catalogue remains public by design | FIXED |
| H2 | Frontend | No security headers (CSP, frame protection, nosniff) | XSS / clickjacking / MIME sniffing residual risk | Headers in `next.config.ts` | FIXED |
| H3 | Frontend `/api/telemetry` | Unauthenticated ingest with no body cap or abuse control | Log flooding | Origin check, 4 KB cap, in-memory rate limit, status allowlist | FIXED |
| H4 | Azure DevOps | Production ACR push ran before Environment approval | Unapproved image in prod ACR | Push moved into the `production` deployment job | FIXED |
| H5 | Terraform | Shared identity + broad Key Vault secret mount (backend/worker get retailer and Clerk secrets; frontend/ML get a subset already) | Larger blast radius if one app is compromised | Split identities / secret subsets — requires a reviewed Terraform change and live apply | ACCEPTED / EXISTING |
| H6 | Terraform | Key Vault and tfstate storage default to public network `Allow` | Relies entirely on Azure AD RBAC | Operator: Deny + IP/VNet/private endpoint. Documented Checkov exceptions | ACCEPTED / EXISTING |
| H7 | Azure DevOps | Terraform `plan` on PRs uses environment service connections | Untrusted PR risk if fork builds can reach secrets | ADO fork policy + restrict plan to `main` — operator setting | PENDING LIVE AZURE VERIFICATION |

### MEDIUM

| ID | Component | Issue | Impact | Remediation | Status |
|---|---|---|---|---|---|
| M1 | API | Missing security headers | Browser/proxy residual risk | Headers middleware | FIXED |
| M2 | API | OpenAPI enabled in deployed environments | Surface extra API detail | Docs disabled when not local/test | FIXED |
| M3 | API | CORS `allow_methods` / `allow_headers` were `*` | Over-broad preflight | Explicit lists; reject `*` with credentials | FIXED |
| M4 | API / ML | `model_version` could contain path segments | Artifact path escape | Pattern + `version_dir` confinement | FIXED |
| M5 | API | 422 responses echoed Pydantic `input` | Client-supplied secrets reflected | Strip `input` / `ctx` | FIXED |
| M6 | Config | `ENVIRONMENT=prod` was not treated as production; placeholder DB URL accepted | Production hardening would not apply on Azure | `prod` counts as production; reject `changeme` DB URL; require Clerk issuer/audience when Clerk is configured | FIXED |
| M7 | Terraform | Redis public in dev/staging; ACR/storage public endpoints; unused private-endpoint subnet | Larger network exposure | Operator network hardening | ACCEPTED / EXISTING |
| M8 | Frontend | Signed-out account views showed a loading skeleton if middleware was bypassed | Confusing UX, not a data leak (API still 401s) | Sign-in required empty state | FIXED |
| M9 | Frontend | External listing/retailer URLs used directly in `href` | `javascript:` / `data:` if API ever returned them | http(s)-only helper | FIXED |

### LOW

| ID | Component | Issue | Impact | Remediation | Status |
|---|---|---|---|---|---|
| L1 | Compose | Ports published on all interfaces | Local LAN exposure | Bind to `127.0.0.1` | FIXED |
| L2 | Frontend | Search queries unbounded | Oversized query strings | 500-character cap (matches API) | FIXED |
| L3 | Frontend | Raw 500 API messages shown | Occasional internal wording | Generic copy for status ≥ 500 | FIXED |
| L4 | API | Slug / category query unbounded | Odd inputs hit the DB (parameterized) | max_length on path/query | FIXED |
| L5 | CI | Trivy installed via `curl \| sh` | Supply-chain residual | Pin installer in a later ops change | ACCEPTED / EXISTING |
| L6 | Auth | Partial Clerk config (publishable without secret) | UI may load Clerk while middleware fails closed | Operators must set both keys; middleware already fails closed | ACCEPTED / EXISTING |
| L7 | API | In-memory pagination for some list filters; history used by ML is unbounded | Resource use on large catalogues | Existing behaviour; not changed | ACCEPTED / EXISTING |
| L8 | Infra | Deploy by mutable tag (`sha-<git>`) not digest | Tag rewrite risk | Operators can pin digest later | ACCEPTED / EXISTING |

---

## Security testing

Executed in the Phase 17 environment (not a substitute for GitHub Actions CI):

| Check | Result |
|---|---|
| `ruff check app tests` | Passed |
| Backend unit tests (`tests/unit` excluding workers) | 473 passed |
| ML artifact / versioning / inference unit tests | 8 passed |
| Integration: exception handling + app factory | Passed (no Postgres required) |
| Integration: `test_api_authorization.py` | **Not run here** — PostgreSQL was not available on this VM |
| Frontend Vitest | 45 passed |
| Frontend ESLint / `tsc --noEmit` | Passed |
| `pip-audit` on backend runtime + ML extras | No known vulnerabilities |
| `npm audit` (frontend) | 0 vulnerabilities |
| Checkov (`infrastructure/terraform`) | 68 passed, 0 failed, 0 skipped |
| Trivy filesystem (HIGH/CRITICAL, vuln+secret+misconfig) | Clean (0 findings in scanned targets) |
| Trivy **image** scans | **Not run here** — Docker was not available |
| Live Azure RBAC / ADO approvals | **PENDING** — no Azure credentials |

GitHub Actions CI on this branch re-runs lint, unit, integration (with Postgres),
pip-audit, npm audit, Checkov, Trivy fs, and Docker image builds/scans.
