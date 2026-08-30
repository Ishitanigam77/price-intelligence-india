"""SQLAlchemy telemetry: query latency, connection failures, pool health.

Never logs SQL text with bound parameters (those can contain credentials or PII).
Only the statement kind (SELECT/INSERT/…) and duration are recorded.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.observability.names import (
    DB_CONNECTION_FAILURES,
    DB_CONNECTION_HEALTH,
    DB_DEPENDENCY_FAILURES,
    DB_POOL_CHECKED_OUT,
    DB_QUERY_DURATION_MS,
)
from app.observability.telemetry import default_metric_tags, get_process_metrics_sink

logger = get_logger(__name__)

_instrumented_engine_ids: set[int] = set()


def _sink() -> MetricsSink:
    return get_process_metrics_sink() or NullMetricsSink()


def _statement_kind(statement: Any) -> str:
    text = str(statement or "").lstrip()
    if not text:
        return "unknown"
    first = text.split(None, 1)[0].upper()
    if first in {"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"}:
        return first.lower()
    return "other"


def instrument_engine(engine: Engine) -> None:
    """Attach listeners once per engine. Safe to call repeatedly."""
    engine_id = id(engine)
    if engine_id in _instrumented_engine_ids:
        return
    _instrumented_engine_ids.add(engine_id)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: Any,
    ) -> None:
        context._pr_query_start = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: Any,
    ) -> None:
        start = getattr(context, "_pr_query_start", None)
        duration_ms = (time.perf_counter() - start) * 1000 if start is not None else 0.0
        kind = _statement_kind(statement)
        tags = default_metric_tags(operation=kind, status="ok")
        _sink().observe(DB_QUERY_DURATION_MS, duration_ms, tags=tags)
        logger.debug(
            "db.query",
            extra={
                **tags,
                "operation": kind,
                "status": "ok",
                "duration_ms": round(duration_ms, 3),
            },
        )

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context: Any) -> None:
        tags = default_metric_tags(operation="query", status="error", error_type="sqlalchemy")
        _sink().increment(DB_CONNECTION_FAILURES, tags=tags)
        _sink().increment(DB_DEPENDENCY_FAILURES, tags=tags)
        _sink().set_gauge(DB_CONNECTION_HEALTH, 0.0, tags=default_metric_tags())
        logger.error(
            "db.dependency_failure",
            extra={
                **default_metric_tags(),
                "operation": "query",
                "status": "error",
                "error_type": type(getattr(exception_context, "original_exception", None)).__name__,
            },
        )

    @event.listens_for(engine, "checkout")
    def _checkout(dbapi_connection: Any, connection_record: Any, connection_proxy: Any) -> None:
        _sink().set_gauge(DB_POOL_CHECKED_OUT, 1.0, tags=default_metric_tags(operation="checkout"))

    logger.info(
        "db.telemetry_instrumented",
        extra={**default_metric_tags(), "operation": "instrument_engine", "status": "ok"},
    )


def record_connection_health(*, ok: bool) -> None:
    """Update the connection-health gauge from an explicit probe (readiness)."""
    _sink().set_gauge(
        DB_CONNECTION_HEALTH,
        1.0 if ok else 0.0,
        tags=default_metric_tags(operation="probe", status="ok" if ok else "error"),
    )
    if not ok:
        _sink().increment(
            DB_DEPENDENCY_FAILURES,
            tags=default_metric_tags(operation="probe", status="error"),
        )
