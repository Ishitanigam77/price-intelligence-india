"""Worker liveness/readiness payloads. No secrets, no broker URLs."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.observability.names import WORKER_HEALTH
from app.observability.telemetry import (
    default_metric_tags,
    get_process_metrics_sink,
    telemetry_status,
)


def worker_liveness_payload(settings: Settings | None = None) -> dict[str, str]:
    resolved = settings if settings is not None else get_settings()
    get_process_metrics_sink().set_gauge(
        WORKER_HEALTH, 1.0, tags=default_metric_tags(operation="liveness", status="ok")
    )
    return {
        "status": "ok",
        "service": resolved.service_name if resolved.service_name != "backend" else "worker",
        "environment": resolved.environment,
    }


def worker_readiness_payload(
    *,
    broker_ok: bool,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved = settings if settings is not None else get_settings()
    insights = telemetry_status(connection_string=resolved.applicationinsights_connection_string)
    overall = "ok" if broker_ok else "degraded"
    get_process_metrics_sink().set_gauge(
        WORKER_HEALTH,
        1.0 if broker_ok else 0.0,
        tags=default_metric_tags(operation="readiness", status=overall),
    )
    return {
        "status": overall,
        "service": "worker",
        "environment": resolved.environment,
        "checks": {
            "broker": {"status": "ok" if broker_ok else "unavailable"},
            "application_insights": {"status": insights["application_insights"]},
        },
    }
