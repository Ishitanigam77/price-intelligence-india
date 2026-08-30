"""HTTP request telemetry: correlation IDs, latency, status codes, structured request logs.

Never logs Authorization, Cookie, or other sensitive headers. Never logs request bodies.
URL paths are recorded without query strings (tokens sometimes appear in query parameters).
"""

from __future__ import annotations

import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.observability.azure_monitor import AzureMonitorExporter
from app.observability.context import get_environment, get_service
from app.observability.correlation import correlation_scope, get_correlation_id
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.observability.names import API_ERRORS, API_REQUEST_DURATION_MS, API_REQUESTS
from app.observability.telemetry import (
    default_metric_tags,
    get_azure_exporter,
    get_process_metrics_sink,
)

logger = get_logger(__name__)

CORRELATION_HEADER = "x-correlation-id"

_HEALTH_PREFIXES = ("/health", "/api/v1/health")


def route_group(path: str) -> str:
    """Map a request path to a low-cardinality operation label."""
    if path.startswith("/api/v1/health") or path.startswith("/health"):
        return "health"
    if path.startswith("/api/v1/"):
        parts = [part for part in path.split("/") if part]
        return parts[2] if len(parts) >= 3 else "api"
    return "other"


def status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _path_without_query(scope: Scope) -> str:
    raw = scope.get("path") or "/"
    return raw.split("?", 1)[0]


class RequestTelemetryMiddleware:
    """ASGI middleware that records API request metrics and structured logs."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        metrics_sink: MetricsSink | None = None,
        exporter: AzureMonitorExporter | None = None,
    ) -> None:
        self.app = app
        self._metrics = metrics_sink
        self._exporter = exporter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = ""
        for key, value in scope.get("headers") or []:
            if key == b"x-correlation-id":
                incoming = value.decode("latin-1").strip()
                break
        path = _path_without_query(scope)
        method = (scope.get("method") or "GET").upper()
        operation = route_group(path)

        with correlation_scope(incoming or None) as correlation_id:
            start = time.perf_counter()
            status_code_box = {"value": 500}

            async def send_wrapper(message: dict) -> None:
                if message["type"] == "http.response.start":
                    status_code_box["value"] = int(message.get("status") or 500)
                    headers = list(message.get("headers") or [])
                    headers.append((b"x-correlation-id", correlation_id.encode("latin-1")))
                    message = {**message, "headers": headers}
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                self._record(
                    method=method,
                    path=path,
                    operation=operation,
                    status_code=500,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                    error_type="unhandled_exception",
                )
                raise

            duration_ms = (time.perf_counter() - start) * 1000
            self._record(
                method=method,
                path=path,
                operation=operation,
                status_code=status_code_box["value"],
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                error_type=None,
            )

    def _sink(self) -> MetricsSink:
        return self._metrics if self._metrics is not None else get_process_metrics_sink()

    def _ai(self) -> AzureMonitorExporter | None:
        return self._exporter if self._exporter is not None else get_azure_exporter()

    def _record(
        self,
        *,
        method: str,
        path: str,
        operation: str,
        status_code: int,
        duration_ms: float,
        correlation_id: str,
        error_type: str | None,
    ) -> None:
        klass = status_class(status_code)
        success = 200 <= status_code < 400
        tags = default_metric_tags(operation=operation, status=klass)
        sink = self._sink() or NullMetricsSink()
        sink.increment(API_REQUESTS, tags=tags)
        sink.observe(API_REQUEST_DURATION_MS, duration_ms, tags=tags)
        if not success:
            sink.increment(
                API_ERRORS,
                tags=default_metric_tags(
                    operation=operation,
                    status=klass,
                    error_type=error_type or klass,
                ),
            )

        extra = {
            "service": get_service(),
            "environment": get_environment(),
            "correlation_id": correlation_id or get_correlation_id(),
            "operation": f"{method} {operation}",
            "status": str(status_code),
            "duration_ms": round(duration_ms, 3),
            "path": path,
            "error_type": error_type,
        }
        is_health = any(path.startswith(prefix) for prefix in _HEALTH_PREFIXES)
        if is_health:
            logger.debug("api.request", extra=extra)
        elif success:
            logger.info("api.request", extra=extra)
        else:
            logger.error("api.request", extra=extra)

        exporter = self._ai()
        if exporter is not None and exporter.enabled:
            exporter.request(
                name=f"{method} {operation}",
                duration_ms=duration_ms,
                success=success,
                response_code=str(status_code),
                url_path=path,
            )


def install_request_telemetry(app: ASGIApp, **kwargs: object) -> RequestTelemetryMiddleware:
    """Helper for tests that want an explicit sink."""
    return RequestTelemetryMiddleware(app, **kwargs)  # type: ignore[arg-type]
