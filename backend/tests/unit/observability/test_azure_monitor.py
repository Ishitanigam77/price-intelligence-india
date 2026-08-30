"""Application Insights configuration is optional and never logs secrets."""

from __future__ import annotations

from app.observability.azure_monitor import (
    AzureMonitorExporter,
    AzureMonitorMetricsSink,
    connection_string_is_configured,
    parse_application_insights_connection_string,
)
from app.observability.names import API_REQUESTS
from app.observability.telemetry import (
    configure_telemetry,
    reset_telemetry_for_tests,
    telemetry_status,
)


def test_placeholder_connection_string_is_not_configured() -> None:
    assert connection_string_is_configured("") is False
    assert connection_string_is_configured("changeme") is False
    assert connection_string_is_configured("InstrumentationKey=abc;IngestionEndpoint=https://x/") is True


def test_parse_connection_string_does_not_require_logging() -> None:
    parsed = parse_application_insights_connection_string(
        "InstrumentationKey=abc-def;IngestionEndpoint=https://example.invalid/"
    )
    assert parsed["InstrumentationKey"] == "abc-def"
    assert parsed["IngestionEndpoint"] == "https://example.invalid/"


def test_exporter_disabled_without_connection_string() -> None:
    exporter = AzureMonitorExporter(
        connection_string="", service_name="backend", environment="test"
    )
    assert exporter.enabled is False
    exporter.metric(API_REQUESTS, 1)
    exporter.flush()


def test_exporter_sends_metrics_through_injected_sender() -> None:
    sent: list[tuple[str, list]] = []

    def sender(url: str, batch: list) -> None:
        sent.append((url, batch))

    exporter = AzureMonitorExporter(
        connection_string="InstrumentationKey=abc;IngestionEndpoint=https://example.invalid/",
        service_name="backend",
        environment="test",
        sender=sender,
    )
    sink = AzureMonitorMetricsSink(exporter)
    for _ in range(20):
        sink.increment(API_REQUESTS, tags={"operation": "health", "status": "2xx"})
    assert sent
    url, batch = sent[0]
    assert "example.invalid" in url
    assert "abc" not in url
    dumped = str(batch)
    assert "api.requests" in dumped
    assert "password" not in dumped


def test_configure_telemetry_without_connection_string_does_not_raise() -> None:
    reset_telemetry_for_tests()
    sink = configure_telemetry(
        service_name="backend",
        environment="test",
        connection_string="",
    )
    sink.increment(API_REQUESTS, tags={"operation": "health", "status": "2xx"})
    status = telemetry_status(connection_string="")
    assert status["application_insights"] == "not_configured"
    reset_telemetry_for_tests()
