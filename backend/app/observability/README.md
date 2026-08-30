# app/observability/

Structured logging, correlation IDs, metrics, request telemetry, and Azure Monitor
export shared across the backend, workers, and (via the same primitives) ML.

**Status**: started in **Phase 1** (health endpoints under `app/api/health.py`),
extended in **Phase 2** with JSON logs / correlation IDs / `MetricsSink`, and
completed for export in **Phase 16**:

- `logging.py` — JSON formatter with credential redaction and standard fields
  (`timestamp`, `service`, `environment`, `correlation_id`).
- `correlation.py` — `ContextVar`-backed correlation IDs.
- `context.py` — process service/environment bindings.
- `metrics.py` — `MetricsSink` protocol, null / in-memory / composite sinks.
- `names.py` — stable custom metric names.
- `azure_monitor.py` — optional Application Insights track-API exporter. Never logs
  the connection string. Missing config does not fail startup.
- `telemetry.py` — process-wide `configure_telemetry()`.
- `middleware.py` — API request count, latency, status class, correlation header.
- `database.py` — SQLAlchemy query latency and connection-failure metrics (no SQL
  parameter logging).

Adapter and collection call sites already emit through `MetricsSink`. Phase 16 adds
the Azure Monitor implementation of that seam.
