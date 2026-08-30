"""Database telemetry listeners and the metric-name catalogue."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.observability.database import instrument_engine, record_connection_health
from app.observability.metrics import InMemoryMetricsSink
from app.observability.names import (
    API_ERRORS,
    API_REQUESTS,
    DB_CONNECTION_HEALTH,
    DB_QUERY_DURATION_MS,
    ML_PREDICTIONS,
    WORKER_QUEUE_DEPTH,
    WORKER_TASK_FAILURES,
)
from app.observability.telemetry import set_process_metrics_sink


def test_metric_names_are_stable() -> None:
    assert API_REQUESTS == "api.requests"
    assert API_ERRORS == "api.errors"
    assert WORKER_TASK_FAILURES == "worker.task.failures"
    assert WORKER_QUEUE_DEPTH == "worker.queue.depth"
    assert ML_PREDICTIONS == "ml.predictions"


def test_instrument_engine_records_query_latency() -> None:
    sink = InMemoryMetricsSink()
    set_process_metrics_sink(sink)
    engine = create_engine("sqlite://")
    instrument_engine(engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    observed = [
        values for (name, _), values in sink.observations.items() if name == DB_QUERY_DURATION_MS
    ]
    assert observed
    assert observed[0][0] >= 0


def test_record_connection_health_sets_gauge() -> None:
    sink = InMemoryMetricsSink()
    set_process_metrics_sink(sink)
    record_connection_health(ok=True)
    assert any(name == DB_CONNECTION_HEALTH for name, _ in sink.gauges)
