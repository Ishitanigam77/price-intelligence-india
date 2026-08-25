"""FastAPI application entrypoint.

Phase 1/2 scope: an app skeleton exposing health check endpoints, with structured JSON
logging configured at process start. Search, comparison, watchlist, and other business
endpoints are introduced in later phases (see `ROADMAP.md`).
"""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.observability.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="PriceRadar India API",
    version="0.1.0",
    description="India-focused price intelligence platform — API layer.",
)

app.include_router(health_router)
