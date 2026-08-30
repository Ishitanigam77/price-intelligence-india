"""Request telemetry and structured log field/redaction tests."""

from __future__ import annotations

import json
import logging
from io import StringIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.context import set_log_context
from app.observability.correlation import correlation_scope
from app.observability.logging import REDACTED, JsonLogFormatter, configure_logging, looks_sensitive
from app.observability.metrics import InMemoryMetricsSink
from app.observability.middleware import RequestTelemetryMiddleware, route_group
from app.observability.names import API_ERRORS, API_REQUEST_DURATION_MS, API_REQUESTS


def test_route_group_is_low_cardinality() -> None:
    assert route_group("/health") == "health"
    assert route_group("/api/v1/products/abc") == "products"
    assert route_group("/api/v1/health/ready") == "health"
    assert route_group("/other") == "other"


def test_request_middleware_records_metrics_and_correlation_header() -> None:
    app = FastAPI()
    sink = InMemoryMetricsSink()
    app.add_middleware(RequestTelemetryMiddleware, metrics_sink=sink)

    @app.get("/api/v1/products")
    def products() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/api/v1/products", headers={"x-correlation-id": "fixed-id"})
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "fixed-id"
    assert sink.total_for_name(API_REQUESTS) >= 1
    durations = [
        samples
        for (name, _), samples in sink.observations.items()
        if name == API_REQUEST_DURATION_MS
    ]
    assert durations


def test_request_middleware_counts_errors() -> None:
    app = FastAPI()
    sink = InMemoryMetricsSink()
    app.add_middleware(RequestTelemetryMiddleware, metrics_sink=sink)

    @app.get("/api/v1/boom")
    def boom() -> dict[str, str]:
        return {"status": "error"}

    # 404 is an error-class status for an unknown path
    with TestClient(app) as client:
        response = client.get("/api/v1/missing")
    assert response.status_code == 404
    assert sink.total_for_name(API_ERRORS) >= 1


def test_structured_log_includes_standard_fields_and_redacts_secrets() -> None:
    set_log_context(service="backend", environment="test")
    record = logging.LogRecord(
        name="app.api",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="api.request token=super-secret-value",
        args=(),
        exc_info=None,
    )
    record.applicationinsights_connection_string = "InstrumentationKey=should-not-appear"
    record.database_url = "postgresql+psycopg://user:hunter2@localhost/db"
    record.clerk_secret_key = "clerk-secret"
    with correlation_scope("corr-1"):
        payload = json.loads(JsonLogFormatter().format(record))
    assert payload["service"] == "backend"
    assert payload["environment"] == "test"
    assert payload["correlation_id"] == "corr-1"
    assert payload["timestamp"]
    assert payload["level"] == "INFO"
    dumped = json.dumps(payload)
    assert "super-secret-value" not in dumped
    assert "should-not-appear" not in dumped
    assert "hunter2" not in dumped
    assert "clerk-secret" not in dumped
    assert payload["applicationinsights_connection_string"] == REDACTED
    assert payload["database_url"] == REDACTED
    assert payload["clerk_secret_key"] == REDACTED


def test_looks_sensitive_covers_connection_strings() -> None:
    assert looks_sensitive("applicationinsights_connection_string") is True
    assert looks_sensitive("database_url") is True
    assert looks_sensitive("redis_url") is True
    assert looks_sensitive("operation") is False


def test_configure_logging_emits_json_with_service_fields() -> None:
    stream = StringIO()
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    try:
        set_log_context(service="backend", environment="test")
        configure_logging("INFO", stream=stream)
        logging.getLogger("test.obs").info("hello", extra={"operation": "probe", "status": "ok"})
        line = stream.getvalue().strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["message"] == "hello"
        assert payload["service"] == "backend"
        assert payload["environment"] == "test"
        assert payload["operation"] == "probe"
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in previous_handlers:
            root.addHandler(handler)
        root.setLevel(previous_level)
