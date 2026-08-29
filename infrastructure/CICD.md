# Phase 15 — Production DevOps (CI/CD, Docker, Terraform, Azure)

This document describes what is **implemented in code**, what operators must **configure in Azure / Azure DevOps**, and which **credentials must be supplied** (never committed).

**Real Azure deployment was not performed as part of this change.** Apply and CD require an Azure subscription, service connections, and environment approvals that only operators can create.

Phase 13 collection workers and Phase 14A retailer adapters are unchanged.

---

## 1. CI/CD architecture

```
GitHub (source of truth)
  │
  ├─ GitHub Actions (`.github/workflows/ci.yml`)
  │    Validate → lint → unit (frontend / backend / workers / ML)
  │    → integration → pip-audit / npm audit / Checkov / Trivy fs
  │    → frontend+backend+worker+ML compile/build
  │    → Docker build + Trivy image scan
  │    No deploy. No ACR push. No terraform apply.
  │
  └─ Azure DevOps (`infrastructure/pipelines/azure-pipelines.yml`)
       Same quality gates, then:
       Docker build → container scan → push immutable tags to ACR
       → Deploy development (Environment `development`)
       → Smoke tests (`/health`, `/health/ready`, frontend `/health`, ML `/health`)
       → Deploy staging (Environment `staging` — configure a check if desired)
       → Production Environment `production` **approval/check**
       → Deploy production (same git SHA tag, never `latest` only)
```

Terraform has a dedicated pipeline (`azure-pipelines.terraform.yml`):

```
terraform fmt → validate → Checkov → plan → environment approval → apply saved plan
```

Production Terraform apply uses the Azure DevOps Environment `production`. It is not a YAML-only `ManualValidation` fake. **Never `terraform destroy`.** Production apply uses a previously reviewed plan; it is not an unreviewed `-auto-approve`.

### Branch / deployment flow

| Event | GitHub Actions | Azure DevOps app pipeline | Azure DevOps Terraform pipeline |
|---|---|---|---|
| Pull request to `main` | Full CI, Docker build+scan, no push | Validate through container scan; **no ACR push, no deploy** | fmt / validate / Checkov / plan only |
| Push to `main` | Same CI | Push to ACR → dev → smoke → staging → **prod approval** → prod | Plan; apply only for the selected environment after its Environment check |

Image tag: `sha-<git commit SHA>`. Deployments reference that tag exactly.

---

## 2. Pipeline stages (Azure DevOps app pipeline)

1. Validate (YAML parse, Docker artifacts, Terraform fmt/validate)
2. Lint (ruff, ESLint, TypeScript)
3. Unit tests (frontend, backend, workers, ML, smoke-script tests)
4. Integration tests
5. Dependency/security scanning (pip-audit on **shipped** backend/`[ml]` extras, npm audit, Checkov, Trivy filesystem)
6. Frontend build (`next build`)
7. Backend build (`compileall`)
8. Worker build (`compileall`)
9. ML build (`compileall`)
10. Docker build (four images)
11. Container security scanning (Trivy image, HIGH/CRITICAL)
12. Push images to ACR (main only)
13. Deploy development
14. Smoke tests
15. Production approval (Azure DevOps Environment `production`)
16. Deploy staging, then production (separate stages; staging first)

Any failure in 1–11 skips deploy. Failed security or tests cannot proceed to deployment.

---

## 3. Docker

| Image / ACR repository | Dockerfile | Target | Runtime user | Health |
|---|---|---|---|---|
| `priceradar/frontend` | `frontend/Dockerfile` | `runner` | `nextjs` | `GET /health` |
| `priceradar/backend` | `backend/Dockerfile` | `api` | `appuser` | `GET /health` |
| `priceradar/workers` | `backend/Dockerfile` | `worker` | `appuser` | Celery ping |
| `priceradar/ml` | `ml/Dockerfile` (repo-root context) | `runtime` | `appuser` | `GET /health` on port 8080 |

Multi-stage builds, lockfile/pyproject installs, no secrets in layers. `CLERK_SECRET_KEY` is runtime-only. `NEXT_PUBLIC_*` are build-args because Next.js inlines them for the browser (they are not server secrets). Runtime stages run `apt-get upgrade` / `apk upgrade` so Debian/Alpine security patches (for example OpenSSL) land in the image Trivy scans; do not ignore HIGH/CRITICAL image CVEs that already have a fix.

Local stack: `infrastructure/docker/docker-compose.yml` — PostgreSQL, Redis, backend, worker, frontend, ML. Copy `.env.example` → `.env` first.

---

## 4. Terraform infrastructure (dev / staging / prod)

Empty scaffold **before** this phase; nothing is destroyed or imported automatically. If Azure resources already exist, adopt them with `terraform import` (see `infrastructure/terraform/IMPORT.md`) — do not recreate.

Per environment (`infrastructure/terraform/environments/{dev,staging,prod}`):

- Resource group, VNet, NSGs, subnets (Container Apps, PostgreSQL, Redis, private endpoints)
- Azure Container Registry (admin disabled; AcrPull via managed identity)
- Key Vault (RBAC, purge protection in staging/prod)
- PostgreSQL Flexible Server 16 (VNet injection, TLS, generated admin password in Key Vault)
- Azure Cache for Redis (TLS 1.2, no non-SSL port; Premium + VNet in prod)
- Storage account (ML artifacts + diagnostics; Azure AD, no shared keys)
- Log Analytics, Application Insights, metric alerts (when `alert_email` is set)
- User-assigned managed identity for runtime
- Container Apps Environment + apps: frontend, backend, worker, ML
- Jobs: Alembic migrate, ML train
- `lifecycle.prevent_destroy` on data stores (RG, ACR, Key Vault, PostgreSQL, Redis, storage)

First create uses image tag `bootstrap-placeholder` (public Container Apps sample image) so apps can be created before ACR has this application's images. CI then updates each app to `sha-<commit>`. Subsequent Terraform applies should pass that same `image_tag` from CI.

Remote state: apply `infrastructure/terraform/bootstrap` **once**, then copy the storage account name into each environment's `backend.hcl` (gitignored).

---

## 5. Identity and RBAC

See `infrastructure/IDENTITY.md`.

---

## 6. Key Vault

Terraform writes:

- `database-url`, `redis-url`, `celery-broker-url`, `celery-result-backend`, `applicationinsights-connection-string` (generated; do not commit)

Terraform creates **placeholders** (ignored on later applies) that operators must replace in Azure:

- `clerk-secret-key`
- `amazon-credential-id`, `amazon-credential-secret`, `amazon-partner-tag`
- `flipkart-affiliate-id`, `flipkart-affiliate-token`

Container Apps reference these secrets via managed identity. No secrets in Git, YAML, Dockerfiles, or `.tfvars.example`.

---

## 7. Manual Azure / Azure DevOps configuration

**Must be done by operators (not in this repository):**

1. Azure subscription, Entra tenant, and a resource provider registration (`Microsoft.App`, `Microsoft.DBforPostgreSQL`, `Microsoft.Cache`, `Microsoft.ContainerRegistry`, `Microsoft.KeyVault`, `Microsoft.OperationalInsights`).
2. Apply Terraform bootstrap, then each environment (dev first). Production apply only after the `production` Environment approval.
3. Azure DevOps project connected to this GitHub repo.
4. Service connections (OIDC/federated; **not** long-lived client secrets if your org supports workload identity):
   - `azure-sc-dev`, `azure-sc-staging`, `azure-sc-prod`
   - Restrict `azure-sc-prod` to the production service connection role and the production Environment.
5. Environments: `development`, `staging`, `production`. On **production**, add an Approvals check (and optionally on staging).
6. Variable groups `priceradar-dev`, `priceradar-staging`, `priceradar-prod` (see below). Mark secrets as secret; never echo them in logs.
7. Grant the service connection principals Contributor + User Access Administrator on the environment resource group (or equivalent least privilege) and AcrPush / Key Vault Secrets Officer if not using `cicd_principal_id` in Terraform.
8. Replace Key Vault placeholder secrets with real Clerk and (optional) retailer credentials.
9. Set Container Apps CORS / `NEXT_PUBLIC_API_BASE_URL` to the real frontend/backend FQDNs after first apply.
10. Optional: lock Key Vault and ACR firewalls to agent IPs or move CD to a self-hosted agent on the VNet (see Checkov exceptions).

### Variable group keys (non-secret unless noted)

| Name | Purpose |
|---|---|
| `ACR_NAME` | ACR resource name |
| `ACR_LOGIN_SERVER` | e.g. `acrprdevxxxxxx.azurecr.io` |
| `AZURE_RESOURCE_GROUP` | `rg-priceradar-<env>` |
| `BACKEND_APP_NAME` / `FRONTEND_APP_NAME` / `WORKER_APP_NAME` / `ML_APP_NAME` | Container App names from Terraform outputs |
| `MIGRATE_JOB_NAME` / `ML_TRAIN_JOB_NAME` | Job names from outputs |
| `SMOKE_BACKEND_URL` | `https://<backend FQDN>` |
| `SMOKE_FRONTEND_URL` | `https://<frontend FQDN>` |
| `SMOKE_ML_URL` | Internal ML FQDN if reachable from the agent; omit if not |
| `NEXT_PUBLIC_API_BASE_URL` | Public backend origin baked into the frontend image |
| `TF_STATE_RESOURCE_GROUP` / `TF_STATE_STORAGE_ACCOUNT` / `TF_STATE_CONTAINER` | Terraform backend (Terraform pipeline) |
| `CICD_PRINCIPAL_ID` | Object ID of the service connection (optional Terraform var) |
| `ALERT_EMAIL` | Optional |
| `CLERK_PUBLISHABLE_KEY`, `CLERK_JWKS_URL`, `CLERK_ISSUER`, `CLERK_AUDIENCE` | Non-secret Clerk config for Terraform |
| `CLERK_SECRET_KEY` | **Secret** — set in Key Vault, not in Git. Variable group only if a pipeline step must read it (prefer Key Vault). |

---

## 8. How to deploy safely

1. Merge to `main` only after GitHub CI is green.
2. Let Azure DevOps run tests and scans again; do not skip gates.
3. Confirm development smoke tests hit **this** application's `/health` and `/health/ready`.
4. Approve staging/production in the Azure DevOps Environment UI.
5. For infra changes, inspect `terraform plan` and apply via the Terraform pipeline. Reject plans that replace PostgreSQL, Key Vault, or ACR.
6. Never run `terraform destroy`. Never add destroy to a pipeline.
7. Do not deploy the `latest` tag to production.

---

## 9. Local Docker Compose

```bash
cp .env.example .env    # edit placeholders; never commit .env
docker compose -f infrastructure/docker/docker-compose.yml up --build
```

Smoke against local:

```bash
python infrastructure/pipelines/scripts/smoke_test.py \
  --backend-url http://localhost:8000 \
  --frontend-url http://localhost:3000 \
  --ml-url http://localhost:8080
```

---

## 10. Security scanning exceptions

Documented in `infrastructure/terraform/checkov.yaml` and `.trivyignore`. They are
network-bootstrap exceptions for Microsoft-hosted agents (including AVD-AZURE-0012 on
tfstate storage), not a suppression of application vulnerabilities. Do not add CVE
ignores without a written justification in that file or in a PR.
