"""Celery application for PriceRadar India collection workers."""

from __future__ import annotations

from celery import Celery

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.observability.database import instrument_engine
from app.observability.logging import get_logger
from app.observability.telemetry import configure_telemetry
from app.workers.celery_config import build_celery_config, celery_config_public_view
from app.workers.health_server import start_worker_health_server
from app.workers.signals import register_worker_signals

logger = get_logger(__name__)


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Build a Celery app from environment-backed settings. Fails if broker/backend are unset."""
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved)
    service_name = resolved.service_name if resolved.service_name != "backend" else "worker"
    configure_telemetry(
        service_name=service_name,
        environment=resolved.environment,
        connection_string=resolved.applicationinsights_connection_string,
    )
    instrument_engine(engine)
    register_worker_signals()
    start_worker_health_server()
    application = Celery("priceradar")
    config = build_celery_config(resolved)
    application.conf.update(config)
    application.autodiscover_tasks(["app.workers"])
    logger.info(
        "celery.app_configured",
        extra={"celery": celery_config_public_view(config), "environment": resolved.environment},
    )
    return application


celery_app = create_celery_app()
