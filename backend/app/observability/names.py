"""Stable metric names for Phase 16 telemetry.

Dimensions must stay low-cardinality: environment, service, adapter/retailer_id, operation,
status, status_class. Never tag with user IDs, tokens, request bodies, or raw URLs.
"""

from __future__ import annotations

# -- API ---------------------------------------------------------------------------------------
API_REQUESTS = "api.requests"
API_REQUEST_DURATION_MS = "api.request.duration_ms"
API_ERRORS = "api.errors"
API_DEPENDENCY_FAILURES = "api.dependency.failures"

# -- Retailer adapters (existing names in retailer_adapters.base.metrics; repeated here
# for the observability catalogue. Do not rename — dashboards/alerts bind to these.)
ADAPTER_REQUESTS = "retailer_adapter.requests"
ADAPTER_SUCCESSES = "retailer_adapter.successes"
ADAPTER_FAILURES = "retailer_adapter.failures"
ADAPTER_LATENCY_MS = "retailer_adapter.latency_ms"
ADAPTER_TIMEOUTS = "retailer_adapter.timeouts"
ADAPTER_RETRIES = "retailer_adapter.retries"
ADAPTER_HEALTH_STATUS = "retailer_adapter.health_status"

# -- Collection (existing names in collectors.metrics)
COLLECTION_JOBS_TOTAL = "jobs_total"
COLLECTION_JOBS_FAILED = "jobs_failed"
COLLECTION_JOBS_SUCCESSFUL = "jobs_successful"
COLLECTION_JOB_DURATION = "job_duration"
COLLECTION_RETAILER_HEALTH = "retailer_health"
COLLECTION_PRICE_FRESHNESS = "price_freshness"

# -- Workers -----------------------------------------------------------------------------------
WORKER_TASKS = "worker.tasks"
WORKER_TASK_DURATION_MS = "worker.task.duration_ms"
WORKER_TASK_FAILURES = "worker.task.failures"
WORKER_TASK_RETRIES = "worker.task.retries"
WORKER_QUEUE_DEPTH = "worker.queue.depth"
WORKER_HEALTH = "worker.health"

# -- Database ----------------------------------------------------------------------------------
DB_QUERY_DURATION_MS = "db.query.duration_ms"
DB_CONNECTION_FAILURES = "db.connection.failures"
DB_CONNECTION_HEALTH = "db.connection.health"
DB_DEPENDENCY_FAILURES = "db.dependency.failures"
DB_POOL_CHECKED_OUT = "db.pool.checked_out"

# -- ML ----------------------------------------------------------------------------------------
ML_PREDICTIONS = "ml.predictions"
ML_PREDICTION_DURATION_MS = "ml.prediction.duration_ms"
ML_PREDICTION_FAILURES = "ml.prediction.failures"
ML_HEALTH = "ml.health"

# -- Frontend (server-received) ----------------------------------------------------------------
FRONTEND_ERRORS = "frontend.errors"
FRONTEND_NAVIGATIONS = "frontend.navigations"
FRONTEND_HEALTH = "frontend.health"
