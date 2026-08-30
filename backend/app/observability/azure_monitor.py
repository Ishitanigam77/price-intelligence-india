"""Application Insights export without baking credentials into source.

Reads `APPLICATIONINSIGHTS_CONNECTION_STRING` from the environment (or an explicit
argument). The connection string is never logged. Export is best-effort: failures are
swallowed so telemetry cannot take the application down.

The official `azure-monitor-opentelemetry` package is optional. When it is installed and a
connection string is present, `configure_azure_monitor()` is attempted. Custom metrics are
always sent through the public ingestion track API via httpx (already a project dependency)
so production images do not require the full Azure OpenTelemetry distro.
"""

from __future__ import annotations

import atexit
import logging
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.observability.context import get_environment, get_service
from app.observability.correlation import get_correlation_id
from app.observability.metrics import MetricsSink

logger = logging.getLogger(__name__)

_MAX_QUEUE = 256
_FLUSH_SIZE = 20
_HTTP_TIMEOUT_SECONDS = 2.0


def parse_application_insights_connection_string(value: str) -> dict[str, str]:
    """Split an Application Insights connection string into keys. Never log the result."""
    parsed: dict[str, str] = {}
    for item in value.split(";"):
        stripped = item.strip()
        if not stripped or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        parsed[key.strip()] = raw.strip()
    return parsed


def connection_string_is_configured(value: str | None) -> bool:
    """True when a non-empty, non-placeholder connection string is present."""
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if lowered in {"changeme", "placeholder", "todo"}:
        return False
    return "instrumentationkey=" in lowered.replace(" ", "")


def _ingestion_url(parsed: Mapping[str, str]) -> str:
    endpoint = parsed.get("IngestionEndpoint") or parsed.get("ingestionendpoint") or ""
    if endpoint:
        return urljoin(endpoint.rstrip("/") + "/", "v2/track")
    return "https://dc.services.visualstudio.com/v2/track"


def _instrumentation_key(parsed: Mapping[str, str]) -> str:
    return parsed.get("InstrumentationKey") or parsed.get("instrumentationkey") or ""


def configure_official_azure_monitor(
    *,
    connection_string: str,
    service_name: str,
    environment: str,
) -> bool:
    """Try the official Azure Monitor OpenTelemetry distro. Never raise. Never log secrets."""
    if not connection_string_is_configured(connection_string):
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        logger.info(
            "azure_monitor.sdk_unavailable",
            extra={"service": service_name, "environment": environment, "status": "skipped"},
        )
        return False
    try:
        configure_azure_monitor(connection_string=connection_string, enable_live_metrics=False)
    except Exception:
        logger.exception(
            "azure_monitor.configure_failed",
            extra={"service": service_name, "environment": environment, "status": "error"},
        )
        return False
    logger.info(
        "azure_monitor.configured",
        extra={"service": service_name, "environment": environment, "status": "ok"},
    )
    return True


class AzureMonitorExporter:
    """Best-effort Application Insights track-API client with an in-process buffer."""

    def __init__(
        self,
        *,
        connection_string: str,
        service_name: str,
        environment: str,
        sender: Any | None = None,
    ) -> None:
        self._enabled = connection_string_is_configured(connection_string)
        self._service_name = service_name
        self._environment = environment
        self._lock = threading.Lock()
        self._queue: list[dict[str, Any]] = []
        self._ikey = ""
        self._url = ""
        self._sender = sender
        if self._enabled:
            parsed = parse_application_insights_connection_string(connection_string)
            self._ikey = _instrumentation_key(parsed)
            self._url = _ingestion_url(parsed)
            if not self._ikey:
                self._enabled = False
        if self._enabled:
            atexit.register(self.flush)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enqueue(self, item: dict[str, Any]) -> None:
        if not self._enabled:
            return
        should_flush = False
        with self._lock:
            if len(self._queue) >= _MAX_QUEUE:
                self._queue.pop(0)
            self._queue.append(item)
            should_flush = len(self._queue) >= _FLUSH_SIZE
        if should_flush:
            self.flush()

    def metric(
        self,
        name: str,
        value: float,
        *,
        tags: Mapping[str, str] | None = None,
        count: int = 1,
    ) -> None:
        properties = {
            "environment": self._environment,
            "service": self._service_name,
            **{str(k): str(v) for k, v in (tags or {}).items()},
        }
        self.enqueue(
            {
                "name": "Microsoft.ApplicationInsights.Metric",
                "time": datetime.now(UTC).isoformat(),
                "iKey": self._ikey,
                "tags": self._ai_tags(),
                "data": {
                    "baseType": "MetricData",
                    "baseData": {
                        "ver": 2,
                        "metrics": [
                            {"name": name, "kind": 3, "value": float(value), "count": int(count)}
                        ],
                        "properties": properties,
                    },
                },
            }
        )

    def request(
        self,
        *,
        name: str,
        duration_ms: float,
        success: bool,
        response_code: str,
        url_path: str,
    ) -> None:
        duration = _format_duration_ms(duration_ms)
        self.enqueue(
            {
                "name": "Microsoft.ApplicationInsights.Request",
                "time": datetime.now(UTC).isoformat(),
                "iKey": self._ikey,
                "tags": self._ai_tags(),
                "data": {
                    "baseType": "RequestData",
                    "baseData": {
                        "ver": 2,
                        "id": get_correlation_id() or "",
                        "name": name,
                        "duration": duration,
                        "success": success,
                        "responseCode": response_code,
                        "url": url_path,
                        "properties": {
                            "environment": self._environment,
                            "service": self._service_name,
                        },
                    },
                },
            }
        )

    def flush(self) -> None:
        if not self._enabled:
            return
        with self._lock:
            batch = list(self._queue)
            self._queue.clear()
        if not batch:
            return
        try:
            if self._sender is not None:
                self._sender(self._url, batch)
                return
            with httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = client.post(self._url, json=batch)
                if response.status_code >= 400:
                    logger.warning(
                        "azure_monitor.flush_rejected",
                        extra={
                            "service": self._service_name,
                            "environment": self._environment,
                            "status": str(response.status_code),
                            "operation": "flush",
                        },
                    )
        except Exception:
            logger.warning(
                "azure_monitor.flush_failed",
                extra={
                    "service": self._service_name,
                    "environment": self._environment,
                    "status": "error",
                    "operation": "flush",
                },
            )

    def _ai_tags(self) -> dict[str, str]:
        tags = {
            "ai.cloud.role": self._service_name,
            "ai.cloud.roleInstance": self._environment,
        }
        correlation = get_correlation_id()
        if correlation:
            tags["ai.operation.id"] = correlation
        return tags


def _format_duration_ms(duration_ms: float) -> str:
    total_ms = max(0, int(duration_ms))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}0000"


class AzureMonitorMetricsSink:
    """`MetricsSink` that forwards counters, distributions, and gauges to Application Insights."""

    def __init__(self, exporter: AzureMonitorExporter) -> None:
        self._exporter = exporter

    def increment(
        self, name: str, *, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        self._exporter.metric(name, float(value), tags=tags, count=value)

    def observe(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        self._exporter.metric(name, float(value), tags=tags, count=1)

    def set_gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        self._exporter.metric(name, float(value), tags=tags, count=1)


class LoggingMetricsSink:
    """Emits metrics as DEBUG structured logs so Log Analytics can query them without App Insights."""

    def increment(
        self, name: str, *, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        logger.debug(
            "metric.increment",
            extra=_metric_extra(name, float(value), tags, kind="counter"),
        )

    def observe(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        logger.debug(
            "metric.observe",
            extra=_metric_extra(name, float(value), tags, kind="distribution"),
        )

    def set_gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        logger.debug(
            "metric.gauge",
            extra=_metric_extra(name, float(value), tags, kind="gauge"),
        )


def _metric_extra(
    name: str, value: float, tags: Mapping[str, str] | None, *, kind: str
) -> dict[str, Any]:
    return {
        "metric": name,
        "value": value,
        "kind": kind,
        "tags": {str(k): str(v) for k, v in (tags or {}).items()},
        "service": get_service(),
        "environment": get_environment(),
        "timestamp": datetime.now(UTC).isoformat(),
    }

