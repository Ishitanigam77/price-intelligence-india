"""Health check endpoints.

Per `DEVELOPMENT_RULES.md` §5.6, every deployable service exposes a health check. This is
intentionally minimal in Phase 1: liveness (`/health`) and readiness (`/health/ready`, which
verifies the database is reachable). No business logic lives here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Liveness check: the process is up and able to handle requests."""
    return {"status": "ok"}


@router.get("/health/ready")
def get_readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness check: the process is up *and* the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - surfaced as a 503, not swallowed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not reachable.",
        ) from exc
    return {"status": "ok"}
