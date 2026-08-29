"""Celery application for PriceRadar India collection workers."""

from __future__ import annotations

from celery import Celery

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.observability.logging import get_logger
from app.workers.celery_config import build_celery_config, celery_config_public_view

logger = get_logger(__name__)


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Build a Celery app from environment-backed settings. Fails if broker/backend are unset."""
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved)
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
