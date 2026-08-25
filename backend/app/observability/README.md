# app/observability/

Structured logging configuration, correlation IDs, and metrics instrumentation shared across
the backend.

**Status**: started in **Phase 1** (health endpoints live under `app/api/health.py`) and
extended in **Phase 2** with:

- `logging.py` — JSON log formatter with credential redaction; installed at process start by
  `app.main`.
- `correlation.py` — `ContextVar`-backed correlation IDs for one logical operation.
- `metrics.py` — `MetricsSink` protocol plus `NullMetricsSink` / `InMemoryMetricsSink`.
  Adapter execution already emits request/success/failure/latency/timeout/retry/rate-limit
  and health samples through this seam. Exporting them to Azure Monitor is Phase 11.
