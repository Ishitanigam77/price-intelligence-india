"""Versioned health and readiness endpoints.

Extends the Phase 1 liveness/readiness checks (`app/api/health.py`, still mounted unversioned
for backward compatibility and for simple container/orchestrator liveness probes) with a
structured, per-dependency readiness report suitable for Docker/Kubernetes/Azure health probes:
it distinguishes application-process health from PostgreSQL availability and Redis availability
independently, per Phase 2 scope. No business logic lives here.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import DbSession, RedisClient
from app.core.config import get_settings
from app.core.redis import check_redis_connection
from app.observability.database import record_connection_health
from app.observability.names import API_DEPENDENCY_FAILURES
from app.observability.telemetry import (
    default_metric_tags,
    get_process_metrics_sink,
    telemetry_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

DependencyStatus = Literal["ok", "unavailable", "degraded", "not_configured"]


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "backend"
    environment: str = "development"


class DependencyCheck(BaseModel):
    status: DependencyStatus


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "backend"
    environment: str = "development"
    checks: dict[str, DependencyCheck]


def _check_postgres(db: Session) -> DependencyStatus:
    try:
        db.execute(text("SELECT 1"))
        return "ok"
    except SQLAlchemyError:
        logger.exception("Readiness check: PostgreSQL is not reachable.")
        return "unavailable"


def _check_redis(client: Redis) -> DependencyStatus:
    return "ok" if check_redis_connection(client) else "unavailable"


@router.get("", response_model=LivenessResponse)
def get_health() -> LivenessResponse:
    """Liveness check: the application process is up and able to handle requests.

    Deliberately checks nothing external — a liveness probe should only fail when the process
    itself is unhealthy, never because a downstream dependency is temporarily unavailable.
    """
    settings = get_settings()
    return LivenessResponse(service=settings.service_name, environment=settings.environment)


@router.get("/live", response_model=LivenessResponse)
def get_live() -> LivenessResponse:
    """Alias of `/health` for probes that distinguish live vs ready by path."""
    return get_health()


@router.get("/ready", response_model=ReadinessResponse)
def get_readiness(db: DbSession, redis_client: RedisClient, request: Request) -> JSONResponse:
    """Readiness check: reports the application process *and* every infrastructure dependency.

    Returns HTTP 200 when every dependency is reachable and HTTP 503 otherwise (matching the
    Phase 1 `/health/ready` convention), so container/Kubernetes/Azure readiness probes can act
    on the status code alone while the JSON body still attributes *which* dependency is down.
    """
    settings = get_settings()
    postgres_status = _check_postgres(db)
    redis_status = _check_redis(redis_client)
    record_connection_health(ok=postgres_status == "ok")
    if postgres_status != "ok":
        get_process_metrics_sink().increment(
            API_DEPENDENCY_FAILURES,
            tags=default_metric_tags(operation="postgresql", status="error"),
        )
    if redis_status != "ok":
        get_process_metrics_sink().increment(
            API_DEPENDENCY_FAILURES,
            tags=default_metric_tags(operation="redis", status="error"),
        )

    adapter_status = _check_adapters(request)
    insights = telemetry_status(connection_string=settings.applicationinsights_connection_string)
    checks = {
        "postgresql": DependencyCheck(status=postgres_status),
        "redis": DependencyCheck(status=redis_status),
        "adapters": DependencyCheck(status=adapter_status),
        "application_insights": DependencyCheck(status=insights["application_insights"]),
    }
    # Probes fail only when infrastructure dependencies are down. Adapter/App Insights
    # status is informational so a single retailer outage cannot take the API out of rotation.
    overall: Literal["ok", "degraded"] = (
        "ok" if postgres_status == "ok" and redis_status == "ok" else "degraded"
    )
    body = ReadinessResponse(
        status=overall,
        service=settings.service_name,
        environment=settings.environment,
        checks=checks,
    )
    status_code = status.HTTP_200_OK if overall == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _check_adapters(request: Request) -> DependencyStatus:
    """Use last observed adapter health only — never make live retailer calls from a probe."""
    registry = getattr(request.app.state, "retailer_registry", None)
    if registry is None:
        return "not_configured"
    try:
        registrations = list(registry.registrations())
    except Exception:
        logger.exception("Readiness check: retailer registry could not be enumerated.")
        return "unavailable"
    enabled = [item for item in registrations if item.enabled]
    if not enabled:
        return "not_configured"
    observed = [item for item in enabled if item.last_health is not None]
    if not observed:
        return "ok"
    unhealthy = sum(1 for item in observed if item.health_status.value == "unhealthy")
    if unhealthy == 0:
        return "ok"
    if unhealthy < len(observed):
        return "degraded"
    return "unavailable"
