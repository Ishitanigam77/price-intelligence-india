"""FastAPI application entrypoint and factory.

Application factory, startup/shutdown lifecycle, versioned routing (`/api/v1/`), CORS,
centralized exception handling, and (Phase 4) product discovery wiring: mock retailer adapters
are discovered and registered at startup so `GET /api/v1/products/search` can query them
through the existing `RetailerRegistry`. Search, comparison, watchlist, and other later-phase
business endpoints remain out of scope (see `ROADMAP.md`).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.health import router as legacy_health_router
from app.api.v1 import api_router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis_pool, get_redis_pool
from app.observability.metrics import NullMetricsSink
from app.retailer_adapters.wiring import build_retailer_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle.

    Startup: warms the Redis connection pool and registers retailer adapters of the configured
    kinds (fixture-backed mocks by default). Shutdown: releases the Redis connection pool. The
    SQLAlchemy engine (`app.db.session`) is process-scoped by design (per Phase 1) and does not
    need explicit disposal here.
    """
    settings = get_settings()
    logger.info("Starting PriceRadar India API (environment=%s).", settings.environment)
    get_redis_pool()
    metrics_sink = getattr(app.state, "metrics_sink", None) or NullMetricsSink()
    app.state.metrics_sink = metrics_sink
    if getattr(app.state, "retailer_registry", None) is None:
        app.state.retailer_registry = build_retailer_registry(
            settings=settings, metrics_sink=metrics_sink
        )
    try:
        yield
    finally:
        logger.info("Shutting down PriceRadar India API.")
        close_redis_pool()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory: builds and returns a fully configured `FastAPI` instance.

    Accepting an optional `Settings` override (rather than always calling `get_settings()`
    internally) makes it straightforward to build an app with test-specific configuration
    without mutating process-wide environment variables.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    application = FastAPI(
        title="PriceRadar India API",
        version="0.1.0",
        description="India-focused price intelligence platform — API layer.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    # Unversioned liveness/readiness, kept for Phase 1 compatibility and simple orchestrator
    # probes; `/api/v1/health` (below) is the richer, per-dependency Phase 2 equivalent.
    application.include_router(legacy_health_router)
    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
