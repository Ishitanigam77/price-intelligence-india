# Phase 16 — Observability

This document describes the observability architecture implemented in this increment:
structured logs, custom metrics, health checks, Application Insights / Azure Monitor
integration, dashboards (workbooks), and alerts.

**Live Azure telemetry, workbooks, and alerts were not verified against a real
subscription in this change.** `terraform fmt` and `terraform validate` were run.
`terraform plan` against Azure could not complete in this environment (no Azure CLI
credentials / remote state). `terraform apply` and CD remain operator-controlled
(Phase 15). Do not treat this document as proof that production alerts are firing.

Phase 15 GitHub CI, Azure DevOps pipelines, Docker, ACR, Key Vault, managed identity,
and deployment configuration are unchanged in purpose. This phase only adds
observability resources and application instrumentation.

---

## 1. Architecture

```
Frontend (Next.js)          Backend API (FastAPI)         Workers (Celery)         ML (health process)
  /health, /api/health         /health, /health/ready        /health :8081            /health, /health/ready
  /api/telemetry               /api/v1/health[/ready|/live]  task signals
        │                              │                         │                        │
        │ structured JSON stdout       │ JSON logs + metrics     │ JSON logs + metrics    │ JSON logs
        └──────────────┬───────────────┴────────────┬────────────┴────────────┬───────────┘
                       │                            │                         │
                       ▼                            ▼                         ▼
              Container Apps console logs    Application Insights track API
                       │                     (optional; env connection string)
                       └──────────────┬──────────────┘
                                      ▼
                         Log Analytics workspace
                                      │
                    Azure Monitor workbooks + metric/log alerts
                                      │
                              Action group (email)
```

Configuration is environment-only:

| Variable | Used by | Secret? |
|---|---|---|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | backend, worker, frontend server, ML | Yes — Key Vault → Container App secret. Never committed. |
| `ENVIRONMENT` | all services | No |
| `SERVICE_NAME` | all services | No |
| `LOG_LEVEL` / `LOG_FORMAT` | backend, worker | No |
| `WORKER_HEALTH_HTTP` / `WORKER_HEALTH_PORT` | worker | No |

The Application Insights connection string is stored in Key Vault as
`applicationinsights-connection-string` (Phase 15) and injected at runtime. It is
never hardcoded and must never be logged.

The official `azure-monitor-opentelemetry` distro is **optional**. When it is not
installed, the application still:

1. Emits structured JSON logs (picked up by Container Apps → Log Analytics).
2. Exports custom metrics and request telemetry via the Application Insights track
   API when a connection string is present (`httpx`, 2s timeout, best-effort).

A missing or invalid connection string does **not** prevent startup.

---

## 2. Structured logs

Every JSON log record includes:

- `timestamp` (UTC ISO-8601)
- `level` (`DEBUG` / `INFO` / `WARNING` / `ERROR`)
- `service`
- `environment`
- `logger` / `message`
- `correlation_id` when a request or task scope is active
- operation-specific fields: `operation`, `status`, `duration_ms`, `error_type`,
  `retailer_id` / adapter identifier when relevant

**Never logged:** passwords, API keys, access tokens, Clerk secrets, database
credentials, connection strings, `Authorization` / `Cookie` headers, request bodies,
or Application Insights connection strings. Redaction is applied to credential-looking
keys and to `Bearer …` / `key=value` fragments in the message text.

Health-probe requests are logged at `DEBUG` to reduce noise.

---

## 3. Metrics

Stable names (do not rename without updating workbooks and alerts):

| Name | Kind | Dimensions |
|---|---|---|
| `api.requests` | counter | environment, service, operation, status (`2xx`/`4xx`/`5xx`) |
| `api.request.duration_ms` | distribution | same |
| `api.errors` | counter | operation, status, error_type |
| `api.dependency.failures` | counter | operation (`postgresql`/`redis`) |
| `retailer_adapter.requests` / `.successes` / `.failures` / `.latency_ms` / `.timeouts` / `.retries` | existing | retailer_id, operation, error_type |
| `retailer_adapter.health_status` | gauge | retailer_id |
| `jobs_total` / `jobs_successful` / `jobs_failed` / `job_duration` | existing | job_type, retailer_id, status |
| `retailer_health` / `price_freshness` | gauge | retailer_id |
| `worker.tasks` / `worker.task.duration_ms` / `worker.task.failures` / `worker.task.retries` | counter/dist | operation, status |
| `worker.queue.depth` | gauge | operation=queue |
| `worker.health` | gauge | — |
| `db.query.duration_ms` | distribution | operation (`select`/…) |
| `db.connection.failures` / `db.dependency.failures` | counter | — |
| `db.connection.health` | gauge | — |
| `ml.predictions` / `ml.prediction.duration_ms` / `ml.prediction.failures` | counter/dist | status, model_version |
| `frontend.errors` / `frontend.navigations` | via `/api/telemetry` logs | path (no query string) |

High-cardinality dimensions (raw user IDs, tokens, request bodies, arbitrary URLs)
are not used.

---

## 4. Health checks

| Service | Liveness | Readiness | Notes |
|---|---|---|---|
| Backend | `GET /health` → `{"status":"ok"}`; `GET /api/v1/health` (+ service/environment); `GET /api/v1/health/live` | `GET /health/ready` (DB); `GET /api/v1/health/ready` (PostgreSQL + Redis; 503 if either down) | Adapter and Application Insights status are informational and do not fail the probe. No secrets in the body. |
| Frontend | `GET /health`, `GET /api/health` | same (process-only) | `status` remains `ok` for Phase 15 smoke tests. |
| Worker | `GET /health` on `WORKER_HEALTH_PORT` (default 8081) when `WORKER_HEALTH_HTTP=true` | `GET /health/ready` (Redis/broker ping) | Docker HEALTHCHECK still uses `celery inspect ping`. |
| ML | `GET /health` | `GET /health/ready` | Artifact presence is reported; a missing artifact does not fail readiness (inference returns `INSUFFICIENT_DATA`). |

---

## 5. Dashboards (Azure Monitor workbooks)

Terraform module `infrastructure/terraform/modules/workbooks/` creates five workbooks
scoped to the environment's Application Insights resource:

1. **Application / API health** — request volume, error rate, latency, custom API metrics
2. **Retailer collection health** — job volume, adapter failures, freshness, duration
3. **Worker health** — tasks, failures, retries, queue depth, duration
4. **Database health** — query latency, connection/dependency failures
5. **ML health** — prediction volume, latency, failures

Workbooks query `requests` and `customMetrics`. They populate only after
`terraform apply` and after the apps emit telemetry.

---

## 6. Alerts

Alerts are created only when an action-group email is configured (`alert_email`)
and, for log alerts, when Application Insights exists. Thresholds are intentionally
coarse to avoid noise.

| Alert | Signal | Threshold | Window | Severity |
|---|---|---|---|---|
| Backend / frontend / worker / ML unavailable | Container Apps `ReplicasUnhealthy` | > 0 | 15m | 2 |
| High API latency | Container Apps `ResponseTime` | > 2000 ms average | 15m | 2 |
| High API error rate | App Insights `requests` | > 5% (2 of 3 evaluations) | 15m | 2 |
| Retailer collection failures | `jobs_failed` | > 5 | 30m | 2 |
| Stale retailer data | `price_freshness` | > 86400 s (24h) | 30m | 3 |
| Worker task failures | `worker.task.failures` | > 5 (2 of 3) | 15m | 2 |
| Excessive queue depth | `worker.queue.depth` | > 100 (2 of 3) | 15m | 3 |
| Database connection failures | PostgreSQL `connections_failed` | > 5 | 15m | 2 |
| PostgreSQL storage (Phase 15) | `storage_percent` | > 80% | 15m | 2 |
| Redis load (Phase 15) | `serverLoad` | > 80 | 15m | 3 |
| ML prediction failures / high latency | `ml.prediction.failures` or p95 duration | > 5 failures or > 5000 ms | 15m | 2 |

---

## 7. Azure configuration (automated vs manual)

**Automated by Terraform (after an operator `apply`):**

- Log Analytics workspace and Application Insights (Phase 15)
- Action group (when `alert_email` is set)
- Key Vault secret `applicationinsights-connection-string` (Phase 15)
- Container App env injection of the connection string (backend, worker, frontend, ML)
- Diagnostic settings (PostgreSQL, Redis, Key Vault, Container Apps)
- Workbooks and alerts listed above

**Manual / operator-only (cannot be safely automated here):**

- Provide `alert_email` via tfvars or pipeline variable (not committed)
- Confirm the action group email subscription
- `terraform apply` of the Phase 16 modules (this change does **not** apply)
- Optional: install `azure-monitor-opentelemetry` in a custom image extra if you want
  the official auto-instrumentation distro in addition to the built-in exporter
- Optional: pin Azure Portal workbook edits — the Terraform `data_json` is the source
  of truth and will overwrite portal-only edits on the next apply

**Never commit** Application Insights connection strings, instrumentation keys, or
action-group secrets.

---

## 8. Local development

Leave `APPLICATIONINSIGHTS_CONNECTION_STRING` empty. The API, workers, frontend, and
ML process start normally, emit JSON logs, and record metrics to the in-process sink /
debug logs. Health endpoints remain available.

---

## 9. Related documents

- `infrastructure/CICD.md` — Phase 15 CI/CD (unchanged deploy path)
- `infrastructure/IDENTITY.md` — managed identity / Key Vault
- `PROJECT_ARCHITECTURE.md` — layering
- `backend/app/observability/README.md` — code-level primitives
