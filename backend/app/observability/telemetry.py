"""Process-wide telemetry wiring. Safe to call from API, workers, and ML.

Never raises. Never logs connection strings, Key Vault URLs, or other secrets.
"""

from __future__ import annotations

import logging

from app.observability.azure_monitor import (
    AzureMonitorExporter,
    AzureMonitorMetricsSink,
    LoggingMetricsSink,
    configure_official_azure_monitor,
    connection_string_is_configured,
)
from app.observability.context import set_log_context
from app.observability.metrics import CompositeMetricsSink, MetricsSink, NullMetricsSink

logger = logging.getLogger(__name__)

_process_sink: MetricsSink = NullMetricsSink()
_exporter: AzureMonitorExporter | None = None
_configured = False


def get_process_metrics_sink() -> MetricsSink:
    """Sink bound at process startup. Tests may replace it via `set_process_metrics_sink`."""
    return _process_sink


def set_process_metrics_sink(sink: MetricsSink) -> None:
    global _process_sink
    _process_sink = sink


def get_azure_exporter() -> AzureMonitorExporter | None:
    return _exporter


def telemetry_status(*, connection_string: str) -> dict[str, str]:
    """Public health fragment: configured or not. Never includes the connection string."""
    return {
        "application_insights": (
            "configured" if connection_string_is_configured(connection_string) else "not_configured"
        )
    }


def configure_telemetry(
    *,
    service_name: str,
    environment: str,
    connection_string: str = "",
    extra_sink: MetricsSink | None = None,
) -> MetricsSink:
    """Install log context, optional Azure Monitor, and the process metrics sink.

    Idempotent for a given process. A missing or invalid connection string is not an error.
    """
    global _process_sink, _exporter, _configured
    set_log_context(service=service_name, environment=environment)
    if _configured:
        if extra_sink is not None and isinstance(_process_sink, CompositeMetricsSink):
            _process_sink.add(extra_sink)
        return _process_sink

    sinks: list[MetricsSink] = [LoggingMetricsSink()]
    if extra_sink is not None:
        sinks.append(extra_sink)

    official = configure_official_azure_monitor(
        connection_string=connection_string,
        service_name=service_name,
        environment=environment,
    )
    exporter = AzureMonitorExporter(
        connection_string=connection_string,
        service_name=service_name,
        environment=environment,
    )
    if exporter.enabled:
        sinks.append(AzureMonitorMetricsSink(exporter))
        _exporter = exporter

    _process_sink = CompositeMetricsSink(sinks)
    _configured = True
    logger.info(
        "telemetry.configured",
        extra={
            "service": service_name,
            "environment": environment,
            "operation": "configure_telemetry",
            "status": "ok",
            "application_insights": (
                "configured" if exporter.enabled or official else "not_configured"
            ),
        },
    )
    return _process_sink


def reset_telemetry_for_tests() -> None:
    """Test helper: allow `configure_telemetry` to run again in the same process."""
    global _process_sink, _exporter, _configured
    _process_sink = NullMetricsSink()
    _exporter = None
    _configured = False


def default_metric_tags(**extra: str) -> dict[str, str]:
    """Low-cardinality tags shared by most custom metrics."""
    from app.observability.context import get_environment, get_service

    tags = {"service": get_service(), "environment": get_environment()}
    tags.update({key: value for key, value in extra.items() if value})
    return tags
