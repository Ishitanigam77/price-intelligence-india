"""Versioned health and readiness endpoints.

Extends the Phase 1 liveness/readiness checks (`app/api/health.py`, still mounted unversioned
for backward compatibility and for simple container/orchestrator liveness probes) with a
structured, per-dependency readiness report suitable for Docker/Kubernetes/Azure health probes:
it distinguishes application-process health from PostgreSQL availability and Redis availability
independently, per Phase 2 scope. No business logic lives here.
"""

import logging
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import DbSession, RedisClient
from app.core.redis import check_redis_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

DependencyStatus = Literal["ok", "unavailable"]


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class DependencyCheck(BaseModel):
    status: DependencyStatus


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
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
    return LivenessResponse()


@router.get("/ready", response_model=ReadinessResponse)
def get_readiness(db: DbSession, redis_client: RedisClient) -> JSONResponse:
    """Readiness check: reports the application process *and* every infrastructure dependency.

    Returns HTTP 200 when every dependency is reachable and HTTP 503 otherwise (matching the
    Phase 1 `/health/ready` convention), so container/Kubernetes/Azure readiness probes can act
    on the status code alone while the JSON body still attributes *which* dependency is down.
    """
    checks = {
        "postgresql": DependencyCheck(status=_check_postgres(db)),
        "redis": DependencyCheck(status=_check_redis(redis_client)),
    }
    overall: Literal["ok", "degraded"] = (
        "ok" if all(check.status == "ok" for check in checks.values()) else "degraded"
    )
    body = ReadinessResponse(status=overall, checks=checks)
    status_code = status.HTTP_200_OK if overall == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
