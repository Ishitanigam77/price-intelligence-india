# PRODUCTION_READINESS.md — Phase 18

Final production-readiness review of the PriceRadar India repository.

This review does **not** start a new product phase after Phase 18. It does not rewrite
architecture, replace Clerk/Azure/CI/CD/observability, run `terraform destroy`, or perform
an unapproved production deployment. Phase 15 CI/CD, Phase 16 observability, and Phase 17
security hardening are preserved.

**Live Azure verdict:** the Azure subscription / live environment has not been fully
activated or applied from this review. Azure, Terraform, Azure DevOps, monitoring, RBAC,
networking, Key Vault, identities, and deployment were reviewed from **repository and
configuration only**.

**PENDING — LIVE AZURE VERIFICATION** applies to every live infrastructure, telemetry,
RBAC, alert, and deployment claim below. This repository is **not** fully
production-verified from in-repo tests alone.

---

## Overall assessment

**READY WITH PENDING OPERATIONAL VERIFICATION**

The application through Phase 17 is implemented, layered, and covered by a large automated
suite. Catalogue, matching, pricing, history, sale events, ML inference, BUY/WAIT,
Clerk-protected personalization, Celery collection, Docker images, Terraform, GitHub CI,
and Azure DevOps CD exist in the repository.

The system is **not READY** as a fully production-verified live service: Azure apply,
Environment approvals, Key Vault secret replacement, alert action groups, RBAC, network
posture, and end-to-end traffic have not been verified against a live subscription.

Do not treat green repository tests as proof that production Azure is healthy.

---

## Review of requested areas

| # | Area | Repository assessment | Live Azure |
|---|---|---|---|
| 1 | Architecture | Layers and retailer isolation hold. Services import API exceptions (accepted layering leak). | N/A |
| 2 | Code quality | Strong typing, structured logs, Pydantic boundaries. Localized pagination/N+1 fixes applied in this review. | N/A |
| 3 | Database | SQLAlchemy models, Alembic, FKs, uniqueness, indexes. Observations immutable. | PENDING — LIVE AZURE VERIFICATION |
| 4 | Backend APIs | Versioned FastAPI, centralized errors, Phase 17 headers/rate limits/OpenAPI-off when deployed. | PENDING — LIVE AZURE VERIFICATION |
| 5 | Frontend | Next.js catalogue + Clerk personalization, CSP/headers, typed client, health routes. | PENDING — LIVE AZURE VERIFICATION |
| 6 | Retailer adapters | Common interface; mock + Amazon.in / Flipkart official APIs only. No scraping. | PENDING — LIVE AZURE VERIFICATION (credentials) |
| 7 | Product matching | Deterministic engine; no retailer-identity branching in core. | N/A |
| 8 | Price comparison | Effective vs displayed vs predicted kept distinct. | N/A |
| 9 | Historical prices | Immutable snapshots; history APIs labeled. | N/A |
| 10 | Sale events | Detection from stored observations; no invented campaign names. | N/A |
| 11 | ML | Leakage-safe features, chronological splits, `INSUFFICIENT_DATA`, labeled predictions. | PENDING — artifact mount / train job |
| 12 | Buy/Wait engine | Deterministic rules; Phase 10 outputs consumed as PREDICTED only. | N/A |
| 13 | Clerk authentication | JWKS fail-closed; ownership scoped in repos; frontend `auth.protect()`. | PENDING — LIVE AZURE VERIFICATION |
| 14 | Watchlists | Authenticated CRUD; IDOR → 404. | N/A |
| 15 | Price alerts | Rules persist; **notification dispatch is an empty scaffold**. | N/A |
| 16 | Celery workers | Isolated collection jobs, retries, timeouts, rate limits, optional health HTTP. | PENDING — LIVE AZURE VERIFICATION |
| 17 | Docker | Multi-stage, non-root, HEALTHCHECK. Compose binds localhost. | Docker image scans in this VM: see test results |
| 18 | Terraform | fmt/validate/Checkov clean. Network hardening incomplete by design (pre–private-endpoint). | PENDING — LIVE AZURE VERIFICATION |
| 19 | Azure | IaC for networking, ACR, PostgreSQL, Redis, Key Vault, Container Apps, storage, identity. | PENDING — LIVE AZURE VERIFICATION |
| 20 | Azure DevOps | YAML CD: tests → scan → ACR → dev → smoke → staging → production Environment. | PENDING — LIVE AZURE VERIFICATION |
| 21 | Monitoring | Structured logs, metrics, probes, workbooks, alerts (email-gated). Frontend telemetry is log-only. | PENDING — LIVE AZURE VERIFICATION |
| 22 | Security | Phase 17 controls intact. Remaining items are operator/network accepted gaps. | PENDING — LIVE AZURE VERIFICATION |
| 23 | Testing | Large unit/integration/frontend/ML/worker/security/pipeline suite. No Playwright E2E. | Live E2E PENDING |
| 24 | Documentation | Roadmap through Phase 18; `SECURITY.md` + this file. Some older READMEs still phase-dated. | N/A |

---

## CRITICAL findings

None identified in repository application code after Phase 17.

Operational items that would become **CRITICAL** if live Azure is misconfigured are listed
under HIGH and marked **PENDING — LIVE AZURE VERIFICATION**. They are not claimed as
verified failures.

---

## HIGH findings

### H1 — Production deploy approval is not enforceable from the repository

| | |
|---|---|
| **Issue** | Production stages reference Azure DevOps Environment `production`. Approvals are configured in the ADO UI, not in YAML. |
| **Affected files** | `infrastructure/pipelines/azure-pipelines.yml`, `infrastructure/pipelines/azure-pipelines.terraform.yml`, `infrastructure/CICD.md` |
| **Impact** | If the Environment exists without an approval check, a `main` run can deploy production after staging smoke. |
| **Recommended fix** | Confirm Approvals + required reviewers on `production`. Re-check after any pipeline or project recreation. |
| **Status** | **PENDING — LIVE AZURE VERIFICATION** |

### H2 — Terraform apply can revert Container Apps to the bootstrap placeholder

| | |
|---|---|
| **Issue** | CD updates images with `az containerapp update`. Terraform still owns `image_tag` (default `bootstrap-placeholder`). A later apply without the current `sha-*` tag resets apps to the public helloworld image. Documented in `infrastructure/CICD.md`. |
| **Affected files** | `infrastructure/terraform/modules/container_apps/main.tf`, `infrastructure/terraform/environments/*/main.tf`, `infrastructure/pipelines/scripts/deploy_containerapps.sh`, `infrastructure/CICD.md` |
| **Impact** | Accidental outage if Terraform is applied independently of the last CD image tag. |
| **Recommended fix** | Always pass `image_tag=sha-<commit>` from CD into Terraform; or `lifecycle { ignore_changes = [template[0].container[0].image] }` after a reviewed infra change. This review does not redesign Phase 15 CD. |
| **Status** | **EXISTING / ACCEPTED** (operator procedure). Prod `terraform.tfvars.example` now warns. |

### H3 — Key Vault and Terraform state storage default to public network Allow

| | |
|---|---|
| **Issue** | Key Vault `public_network_access_enabled = true` / `network_default_action = Allow`. Bootstrap tfstate storage default Allow. Checkov exceptions documented. |
| **Affected files** | `infrastructure/terraform/modules/key_vault/main.tf`, `infrastructure/terraform/modules/platform/main.tf`, `infrastructure/terraform/bootstrap/main.tf`, `infrastructure/terraform/checkov.yaml` |
| **Impact** | Data planes reachable from the internet, relying on Azure AD RBAC. |
| **Recommended fix** | Operator network hardening (Deny + IP/VNet/private endpoint). Do not weaken existing RBAC. |
| **Status** | **EXISTING / ACCEPTED** (repo). **PENDING — LIVE AZURE VERIFICATION** (live firewall state). |

### H4 — Shared runtime identity and broad Key Vault secret mount

| | |
|---|---|
| **Issue** | One user-assigned identity is attached to frontend, backend, worker, and ML. Worker/backend receive Clerk and retailer secrets. |
| **Affected files** | `infrastructure/terraform/modules/identity/main.tf`, `infrastructure/terraform/modules/container_apps/main.tf` |
| **Impact** | Larger blast radius if one container is compromised. |
| **Recommended fix** | Split identities and secret subsets in a reviewed Terraform change (not done here — would be an infra redesign). |
| **Status** | **EXISTING / ACCEPTED** (also Phase 17 H5) |

### H5 — Price-alert / watchlist notification dispatch is not implemented

| | |
|---|---|
| **Issue** | Users can persist watchlists and alert rules. `backend/app/notifications/` is an empty scaffold; `AlertService` does not dispatch. |
| **Affected files** | `backend/app/notifications/README.md`, `backend/app/services/alert_service.py` |
| **Impact** | Alerts do not email or otherwise notify. Marketing “price alerts” as live would over-claim. |
| **Recommended fix** | Implement dispatch in a dedicated increment. Do not invent a notification stack in Phase 18. |
| **Status** | **EXISTING / ACCEPTED** |

### H6 — Phase 16 alerts stay off until `alert_email` is set

| | |
|---|---|
| **Issue** | Metric and query alerts have `count = 0` when `alert_email == ""`. Examples leave it empty. |
| **Affected files** | `infrastructure/terraform/modules/alerts/main.tf`, `infrastructure/terraform/modules/monitoring/main.tf`, `infrastructure/terraform/environments/*/terraform.tfvars.example`, `OBSERVABILITY.md` |
| **Impact** | Silent production failures until operators configure an action group. |
| **Recommended fix** | Set `alert_email` (or webhook) for prod; confirm the action-group email. |
| **Status** | **PENDING — LIVE AZURE VERIFICATION** |

### H7 — ML artifact storage is not mounted on Container Apps

| | |
|---|---|
| **Issue** | Storage account + `ml-artifacts` exist and the identity has blob rights, but apps have no volume mount. `ML_MODEL_ARTIFACT_PATH=/mnt/ml-artifacts` would not exist unless operators mount it another way. |
| **Affected files** | `infrastructure/terraform/modules/storage/main.tf`, `infrastructure/terraform/modules/container_apps/main.tf`, `ml/inference/registry.py` |
| **Impact** | Production training/inference cannot persist or load artifacts via the provisioned account. |
| **Recommended fix** | Mount Azure Files/Blob on the ML app and train job; keep `INSUFFICIENT_DATA` when no artifact exists. |
| **Status** | **EXISTING / ACCEPTED** (repo). **PENDING — LIVE AZURE VERIFICATION** (whether a mount was added out of band). |

### H8 — ACR remains publicly reachable in Terraform prod defaults

| | |
|---|---|
| **Issue** | `acr_public_network_access_enabled = true` in prod. Private-endpoint subnet exists but no `azurerm_private_endpoint` resources. |
| **Affected files** | `infrastructure/terraform/environments/prod/main.tf`, `infrastructure/terraform/modules/acr/main.tf`, `infrastructure/terraform/modules/networking/main.tf` |
| **Impact** | Registry depends on RBAC only. |
| **Recommended fix** | Private endpoint + disable public access when agents can reach it. |
| **Status** | **EXISTING / ACCEPTED** (repo). **PENDING — LIVE AZURE VERIFICATION**. |

### H9 — No browser E2E / live-stack smoke in this review environment

| | |
|---|---|
| **Issue** | No Playwright/Cypress suite. `smoke_test.py` is unit-tested with mocks; CD smoke needs deployed URLs. Docker was unavailable on this review VM so Compose E2E was not run. |
| **Affected files** | `infrastructure/pipelines/scripts/smoke_test.py`, `.github/workflows/ci.yml` |
| **Impact** | CORS, Clerk session, and image env wiring can regress without a full-stack click-path. |
| **Recommended fix** | After Azure is live, run CD smoke plus a short signed-in journey. Do not fabricate Azure resources to claim E2E. |
| **Status** | **PENDING — LIVE AZURE VERIFICATION** for deployed E2E. Local Compose E2E **NOT APPLICABLE** here (no Docker daemon). |

---

## MEDIUM findings

| ID | Issue | Affected files | Impact | Recommended fix | Status |
|---|---|---|---|---|---|
| M1 | Dev/staging Redis public by default (Basic/Standard, no VNet) | `infrastructure/terraform/modules/redis/main.tf`, env `main.tf` | Non-prod broker/cache reachable if keys leak | Disable public access or firewall; Premium+VNet for staging | EXISTING / ACCEPTED |
| M2 | In-process rate limits are per replica; `X-Forwarded-For` is trusted | `backend/app/api/security.py` | Uneven limits; client can spoof IP unless the ingress strips/overwrites XFF | Gateway limiter; trust only the platform-set client IP | EXISTING / ACCEPTED (Phase 17) |
| M3 | Frontend `/api/telemetry` logs JSON to stdout; does not export App Insights custom metrics | `frontend/src/app/api/telemetry/route.ts`, `OBSERVABILITY.md` | `frontend.errors` / navigations may be log-only | Keep log shipping; or document log-only (no observability redesign here) | EXISTING / ACCEPTED |
| M4 | CORS / Clerk / `cicd_principal_id` empty in Terraform examples | `infrastructure/terraform/environments/*/main.tf`, `*.tfvars.example` | Browser API blocked or CI RBAC skipped if operators forget variables | Set per-environment values in ADO/tfvars | EXISTING / ACCEPTED; prod example comments added |
| M5 | Partial diagnostics: ACR, storage, CAE, jobs not fully covered | `infrastructure/terraform/modules/diagnostics/main.tf` | Weaker incident response for registry/storage | Extend diagnostics in a later ops change | EXISTING / ACCEPTED |
| M6 | No Container Apps scale rules (min/max only); prod CAE zone redundancy off | `infrastructure/terraform/modules/container_apps/main.tf`, `environments/prod/main.tf` | Fixed capacity; apps may not survive a zone loss | Add HTTP/CPU rules; enable CAE ZR when quota allows | EXISTING / ACCEPTED |
| M7 | Images rebuilt per CD stage instead of promote-by-digest | `infrastructure/pipelines/azure-pipelines.yml` | Supply-chain consistency residual | Build once, retag by digest (Phase 15 architecture preserved) | EXISTING / ACCEPTED |
| M8 | Catalogue list filters previously loaded full result sets into memory | `backend/app/repositories/product_repository.py`, `retailer_repository.py`, `api/v1/products.py`, `retailers.py` | Memory/latency on large catalogues | DB `LIMIT`/`OFFSET` + `COUNT` | **FIXED** |
| M9 | User-owned list endpoints lazy-loaded `product` (N+1) | watchlist / alert / saved / target-price repositories | Extra queries per row | `selectinload` | **FIXED** |
| M10 | Persistent Key Vault Administrator on the Terraform runner identity | `infrastructure/terraform/modules/platform/main.tf` | Long-lived elevation | PIM / narrower role after secret create | EXISTING / ACCEPTED |
| M11 | Placeholder Key Vault secret values (`PLACEHOLDER_SET_IN_AZURE`) | `infrastructure/terraform/modules/platform/main.tf` | Clerk/retailer integrations silently broken | Replace values; fail smoke if placeholders remain | PENDING — LIVE AZURE VERIFICATION |
| M12 | No WAF / Front Door in Terraform | `infrastructure/terraform/modules/container_apps/main.tf` | Direct internet to API/frontend | Add Front Door + WAF in a later infra increment | EXISTING / ACCEPTED |
| M13 | Terraform plan artifact can age before apply | `infrastructure/pipelines/azure-pipelines.terraform.yml` | Apply may not match the reviewed plan | Re-plan in the apply job or expire plans | EXISTING / ACCEPTED |
| M14 | Services raise `app.api.errors` (domain depends on API) | `backend/app/services/*.py` | Harder to reuse services without FastAPI | Move exceptions to domain in a dedicated refactor | EXISTING / ACCEPTED |
| M15 | Legacy `/health/ready` checks PostgreSQL only | `backend/app/api/health.py` | Orchestrators using the unversioned path miss Redis | Production probes use `/api/v1/health/ready` | EXISTING / ACCEPTED |
| M16 | Dual frontend health paths | `frontend/src/app/health/route.ts`, `frontend/src/app/api/health/route.ts` | Probe/docs confusion | Keep `/health` as the Docker/CA probe | EXISTING / ACCEPTED |

---

## LOW findings

| ID | Issue | Affected files | Impact | Recommended fix | Status |
|---|---|---|---|---|---|
| L1 | GitHub/ADO image Trivy omitted repo `trivy.yaml` | `.github/workflows/ci.yml`, `azure-pipelines.yml` | Inconsistent skip policy vs filesystem scan | Pass `--config` / `--ignorefile` | **FIXED** |
| L2 | ADO ContainerScan frontend build omitted `NEXT_PUBLIC_API_BASE_URL` | `infrastructure/pipelines/azure-pipelines.yml` | Scan image ≠ deploy image | Same build-arg as deploy | **FIXED** |
| L3 | `API_BASE_URL` documented but unused by Settings | `.env.example`, `backend/app/core/config.py` | Operator confusion | Clarified as tooling-only | **FIXED** |
| L4 | Optional `NEXT_PUBLIC_ENVIRONMENT` undocumented | `frontend/src/lib/observability/config.ts` | Telemetry env label may stay `development` | Documented in `.env.example` files | **FIXED** |
| L5 | `AUTHENTICATION.md` / some module READMEs still say later phases are out of scope | `AUTHENTICATION.md`, scattered READMEs | Doc drift | Update when those files are next touched | EXISTING / ACCEPTED |
| L6 | `.cursor/rules/000-phase-gate.mdc` phase numbers are stale | `.cursor/rules/000-phase-gate.mdc` | Agents may mis-gate work | Refresh in a rules-only change | EXISTING / ACCEPTED |
| L7 | Workbooks `isLocked = false` | `infrastructure/terraform/modules/workbooks/main.tf` | Portal drift | Lock or treat Terraform as source of truth | EXISTING / ACCEPTED |
| L8 | No SBOM / image signing | Dockerfiles, pipelines | Supply-chain maturity | Optional later ops work | EXISTING / ACCEPTED |
| L9 | Checkov skips 20+ checks with rationale | `infrastructure/terraform/checkov.yaml` | CI stays green while network exceptions remain | Track skips; remove as network hardens | EXISTING / ACCEPTED |
| L10 | `refuse_secret_echo.sh` not wired into pipelines | `infrastructure/pipelines/scripts/refuse_secret_echo.sh` | Unused defense-in-depth | Optional wrapper | EXISTING / ACCEPTED |
| L11 | No Azure management locks | Terraform modules | Portal/CLI delete still possible | `CanNotDelete` on prod data stores | EXISTING / ACCEPTED |
| L12 | In-memory rate-limit maps can grow with unique IPs | `backend/app/api/security.py`, `frontend/src/app/api/telemetry/route.ts` | Slow memory growth | Periodic prune (not done; low risk at current limits) | EXISTING / ACCEPTED |
| L13 | Next.js 16 deprecates the `middleware` file convention | `frontend/src/middleware.ts` | Build warning only; Clerk still uses `clerkMiddleware` | Migrate when Clerk/Next document a supported `proxy` path | EXISTING / ACCEPTED |

---

## Fixes made in Phase 18

Only clearly safe, localized, backward-compatible changes:

1. Eager-load `product` on user-owned get/list queries (watchlists, alerts, saved products, target prices).
2. Database-level pagination + counts for category/brand product lists and `active_only` retailers.
3. GitHub Actions and Azure DevOps Trivy **image** scans now use `infrastructure/security/trivy.yaml` and `.trivyignore`.
4. Azure DevOps ContainerScan frontend build passes `NEXT_PUBLIC_API_BASE_URL` (same as GitHub CI / deploy).
5. Document `API_BASE_URL` (unused by Settings) and optional `NEXT_PUBLIC_ENVIRONMENT`.
6. Warn in prod `terraform.tfvars.example` about `image_tag`, `alert_email`, CORS, and `cicd_principal_id`.
7. Record Phase 18 on the roadmap and point docs at this file.

**Not changed:** Clerk, Azure services, CI/CD architecture, observability exporters, retailer adapters, matching/pricing/ML/recommendation engines, Terraform resource topology, security headers/rate limits from Phase 17.

---

## Files changed

See the Phase 18 pull request. Primary artifacts:

- Created: `PRODUCTION_READINESS.md`
- Docs: `ROADMAP.md`, `README.md`, `PROJECT_ARCHITECTURE.md`, `TECH_STACK.md`, `ml/README.md`, `.env.example`, `frontend/.env.example`, `infrastructure/terraform/environments/prod/terraform.tfvars.example`
- Code: user-owned repositories; `product_repository.py`; `retailer_repository.py`; `api/v1/products.py`; `api/v1/retailers.py`
- CI: `.github/workflows/ci.yml`, `infrastructure/pipelines/azure-pipelines.yml`

---

## Complete test results

Executed in this Phase 18 review environment (2026-08-30). **Not** a substitute for GitHub Actions on the PR, and **not** live Azure verification.

| Suite | Command | Result |
|---|---|---|
| Backend lint | `cd backend && ruff check app tests` | Passed |
| Backend unit (excl. workers/ML) | `pytest tests/unit --ignore=tests/unit/workers --ignore=tests/unit/ml` | **473 passed** (1 Starlette TestClient deprecation warning) |
| Worker unit | `pytest tests/unit/workers` | **10 passed** |
| ML unit | `pytest tests/unit/ml` | **43 passed** |
| Backend integration | `pytest tests/integration` | **200 passed** (Postgres 16 + Redis 7 on this VM) |
| Security unit | `pytest tests/unit/security tests/unit/api/test_security.py` | **16 passed** (subset of the 473 unit tests) |
| Frontend Vitest | `cd frontend && npm test` | **45 passed** (20 files) |
| Frontend lint / typecheck / build | `npm run lint` / `tsc --noEmit` / `NEXT_PUBLIC_API_BASE_URL=… npm run build` | Passed. Next.js 16 notes the `middleware` file convention is deprecated (`proxy`); not changed here. |
| Pipeline YAML + smoke unit | `validate_yaml.py` + `pytest …/test_smoke_test.py` | YAML ok (4 files); **5 passed** |
| Terraform fmt + validate | bootstrap, dev, staging, prod (`-backend=false`) | Passed (Terraform 1.6.6) |
| Checkov | `checkov -d infrastructure/terraform --config-file …/checkov.yaml` | **68 passed, 0 failed, 0 skipped** |
| Trivy filesystem | `trivy fs` HIGH/CRITICAL (vuln+secret+misconfig) | Clean (0 findings on scanned targets) |
| pip-audit (backend runtime + ML extras) | Clean venv `pip install -e "./backend[ml]"` then `pip-audit` | No known vulnerabilities (`priceradar-backend` skipped — not on PyPI) |
| npm audit | `npm audit --audit-level=high` | 0 vulnerabilities |
| Docker image build + Trivy image | `docker build` ×4 | **NOT APPLICABLE** — Docker daemon unavailable on this VM |
| Local Compose E2E | `docker compose … up` + `smoke_test.py` against localhost | **NOT APPLICABLE** — Docker unavailable |
| Live Azure / ADO deploy / Monitor alerts | — | **PENDING — LIVE AZURE VERIFICATION** |
| Live retailer E2E (Amazon.in / Flipkart) | — | **NOT APPLICABLE** — no approved live credentials used; fixture tests only |

---

## E2E test results

| Check | Result |
|---|---|
| Backend integration (API + Postgres + Redis) | **200 passed** — local Postgres/Redis, not Azure |
| Frontend component tests (jsdom, not a browser user journey) | **45 passed** |
| CD smoke script against deployed URLs | **PENDING — LIVE AZURE VERIFICATION** |
| Playwright / Cypress user journeys | **NOT APPLICABLE** — suite does not exist |
| Compose full-stack smoke | **NOT APPLICABLE** — Docker unavailable |
| Production traffic / Clerk live JWKS | **PENDING — LIVE AZURE VERIFICATION** |

No Azure resources were created to fabricate E2E success.

---

## Azure / live-environment limitations

Reviewed from Terraform, pipelines, `IDENTITY.md`, `CICD.md`, `OBSERVABILITY.md`, and `SECURITY.md` only:

- Networking, ACR, PostgreSQL (VNet + TLS in code), Redis (prod private; dev/staging public defaults), Key Vault (RBAC, public Allow defaults), Container Apps, managed identity, diagnostic settings, workbooks, alerts.
- Azure DevOps: immutable `sha-*` tags, no `terraform destroy`, production Environment name, `addSpnToEnvironment: false`, GitHub CI does not deploy.

**Not verified live:**

1. Subscription apply state (dev/staging/prod exist and match Terraform).
2. Azure DevOps Environment `production` Approvals.
3. Service connections (OIDC vs long-lived secrets).
4. Variable groups / secret marking / log leakage.
5. Key Vault values replaced (not `PLACEHOLDER_SET_IN_AZURE`).
6. `alert_email` / action-group confirmation.
7. Diagnostic settings shipping to Log Analytics; workbook data.
8. Container Apps running `sha-*` (not bootstrap placeholder).
9. Redis / KV / ACR firewall as intended.
10. Entra RBAC vs `IDENTITY.md`.
11. Remote state storage network rules after bootstrap.
12. Custom domains / TLS certificates (not in Terraform).
13. Clerk production JWKS / issuer / audience alignment.
14. Retailer affiliate credentials and quota.

---

## Pending production verification (operator checklist)

1. Confirm ADO `production` Environment approvals.
2. Apply Terraform with the **current** CD `image_tag`; never apply placeholder over a live app.
3. Replace Key Vault placeholders; set CORS to the real frontend origin; set Clerk issuer/audience.
4. Set `alert_email` and confirm Azure Monitor action groups.
5. Run CD smoke against deployed backend, frontend, and ML URLs.
6. Decide whether to mount ML artifact storage before enabling training in Azure.
7. Confirm `RUN_DB_MIGRATIONS=false` on apps and that the migrate **job** ran.
8. Do not enable live Amazon.in / Flipkart adapters without approved credentials and retailer rate-limit monitoring.
9. Do not advertise outbound price-alert notifications until dispatch exists.

---

## Recommended next steps

1. Complete **PENDING — LIVE AZURE VERIFICATION** items above (operational, not a new product phase).
2. Keep Phase 15/16/17 controls; do not auto-deploy production from GitHub.
3. Implement notification dispatch only when explicitly requested as its own increment.
4. Consider private endpoints, WAF, identity/secret split, and digest promotion as future infra work — not started here.

---

## Verdict

| Question | Answer |
|---|---|
| Is the **repository** ready for operators to proceed with an approved Azure rollout? | **Yes, with the HIGH operational caveats above.** |
| Is the **live system** production-verified? | **No.** |
| Classification | **READY WITH PENDING OPERATIONAL VERIFICATION** |

**STOP after Phase 18.** No Phase 19 work is included.
