"""Tests for structured logging, correlation IDs, and the metrics sink protocol."""

import json
import logging
from io import StringIO

from app.observability.correlation import correlation_scope, get_correlation_id, new_correlation_id
from app.observability.logging import (
    REDACTED,
    JsonLogFormatter,
    configure_logging,
    looks_sensitive,
    redact,
)
from app.observability.metrics import InMemoryMetricsSink, NullMetricsSink
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.metrics import (
    ADAPTER_HEALTH_STATUS,
    ADAPTER_LATENCY_MS,
    ADAPTER_REQUESTS,
    HEALTH_STATUS_GAUGE_VALUES,
    AdapterMetricsRecorder,
)
from app.retailer_adapters.base.models import HealthStatus


class TestRedaction:
    def test_credential_looking_keys_are_sensitive(self) -> None:
        assert looks_sensitive("api_key") is True
        assert looks_sensitive("Authorization") is True
        assert looks_sensitive("password") is True
        assert looks_sensitive("retailer_id") is False
        assert looks_sensitive("endpoint") is False

    def test_nested_secrets_are_redacted(self) -> None:
        payload = redact(
            "headers",
            {"authorization": "Bearer secret", "content-type": "application/json"},
        )
        assert payload["authorization"] == REDACTED
        assert payload["content-type"] == "application/json"


class TestJsonLogFormatter:
    def test_emits_one_json_object_with_extras(self) -> None:
        record = logging.LogRecord(
            name="app.retailer_adapters.base.execution",
            level=logging.INFO,
            pathname="execution.py",
            lineno=1,
            msg="retailer_adapter.operation_succeeded",
            args=(),
            exc_info=None,
        )
        record.retailer_id = "mock-retailer-a"
        record.operation = "get_price"
        record.correlation_id = "abc"
        record.duration_ms = 12.5
        record.success = True
        payload = json.loads(JsonLogFormatter().format(record))
        assert payload["message"] == "retailer_adapter.operation_succeeded"
        assert payload["retailer_id"] == "mock-retailer-a"
        assert payload["operation"] == "get_price"
        assert payload["correlation_id"] == "abc"
        assert payload["duration_ms"] == 12.5
        assert payload["success"] is True
        assert payload["level"] == "INFO"

    def test_redacts_secret_extras(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="x.py",
            lineno=1,
            msg="should not leak",
            args=(),
            exc_info=None,
        )
        record.api_key = "super-secret"
        payload = json.loads(JsonLogFormatter().format(record))
        assert payload["api_key"] == REDACTED
        assert "super-secret" not in json.dumps(payload)

    def test_configure_logging_installs_the_json_formatter(self) -> None:
        stream = StringIO()
        root = logging.getLogger()
        previous_handlers = list(root.handlers)
        previous_level = root.level
        try:
            configure_logging("INFO", stream=stream)
            logging.getLogger("test.logger").info(
                "hello", extra={"retailer_id": "scripted-store", "success": True}
            )
            line = stream.getvalue().strip().splitlines()[-1]
            payload = json.loads(line)
            assert payload["message"] == "hello"
            assert payload["retailer_id"] == "scripted-store"
        finally:
            for handler in list(root.handlers):
                root.removeHandler(handler)
            for handler in previous_handlers:
                root.addHandler(handler)
            root.setLevel(previous_level)


class TestCorrelation:
    def test_scope_binds_and_restores(self) -> None:
        assert get_correlation_id() is None
        with correlation_scope("fixed-id") as bound:
            assert bound == "fixed-id"
            assert get_correlation_id() == "fixed-id"
        assert get_correlation_id() is None

    def test_new_ids_are_unique(self) -> None:
        assert new_correlation_id() != new_correlation_id()


class TestMetricsSink:
    def test_null_sink_accepts_everything(self) -> None:
        NullMetricsSink().increment("x")
        NullMetricsSink().observe("y", 1.0)
        NullMetricsSink().set_gauge("z", 0.0)

    def test_in_memory_sink_records_counters_and_gauges(self) -> None:
        sink = InMemoryMetricsSink()
        recorder = AdapterMetricsRecorder("scripted-store", sink)
        recorder.health_reported(HealthStatus.HEALTHY)
        assert (
            sink.gauge_value(ADAPTER_HEALTH_STATUS, retailer_id="scripted-store")
            == (HEALTH_STATUS_GAUGE_VALUES[HealthStatus.HEALTHY])
        )
        recorder.request_started(AdapterOperation.GET_PRICE)
        assert (
            sink.counter_value(
                ADAPTER_REQUESTS, retailer_id="scripted-store", operation="get_price"
            )
            == 1
        )
        recorder.request_succeeded(AdapterOperation.GET_PRICE, duration_ms=8.0)
        assert sink.observed_values(
            ADAPTER_LATENCY_MS, retailer_id="scripted-store", operation="get_price"
        ) == [8.0]
