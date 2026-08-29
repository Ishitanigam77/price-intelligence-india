"""Celery configuration derived from environment-backed `Settings`.

Broker and result backend URLs are never logged — they may contain Redis credentials.
"""

from __future__ import annotations

from typing import Any

from app.collectors.errors import CollectionConfigurationError
from app.core.config import Settings, get_settings
from app.domain.enums import CollectionJobType

TASK_PRODUCT_SEARCH = "priceradar.collection.product_search"
TASK_PRODUCT_REFRESH = "priceradar.collection.product_refresh"
TASK_PRICE_REFRESH = "priceradar.collection.price_refresh"
TASK_AVAILABILITY_REFRESH = "priceradar.collection.availability_refresh"
TASK_SALE_EVENT_REFRESH = "priceradar.collection.sale_event_refresh"

TASK_BY_JOB_TYPE: dict[CollectionJobType, str] = {
    CollectionJobType.PRODUCT_SEARCH: TASK_PRODUCT_SEARCH,
    CollectionJobType.PRODUCT_REFRESH: TASK_PRODUCT_REFRESH,
    CollectionJobType.PRICE_REFRESH: TASK_PRICE_REFRESH,
    CollectionJobType.AVAILABILITY_REFRESH: TASK_AVAILABILITY_REFRESH,
    CollectionJobType.SALE_EVENT_REFRESH: TASK_SALE_EVENT_REFRESH,
}

_SECRET_CONFIG_KEYS = frozenset({"broker_url", "result_backend"})


def validate_celery_settings(settings: Settings) -> None:
    """Fail clearly when required Celery/Redis settings are missing or not Redis URLs."""
    if not settings.celery_broker_url:
        raise CollectionConfigurationError("CELERY_BROKER_URL is required.")
    if not settings.celery_result_backend:
        raise CollectionConfigurationError("CELERY_RESULT_BACKEND is required.")
    if not settings.redis_url:
        raise CollectionConfigurationError("REDIS_URL is required.")


def build_celery_config(settings: Settings | None = None) -> dict[str, Any]:
    """Return a Celery `conf` mapping. URLs come from the environment, never hardcoded."""
    resolved = settings if settings is not None else get_settings()
    validate_celery_settings(resolved)
    config: dict[str, Any] = {
        "broker_url": resolved.celery_broker_url,
        "result_backend": resolved.celery_result_backend,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "task_acks_late": resolved.celery_task_acks_late,
        "task_track_started": True,
        "task_time_limit": resolved.celery_task_time_limit,
        "task_soft_time_limit": resolved.celery_task_soft_time_limit,
        "worker_concurrency": resolved.celery_worker_concurrency,
        "worker_prefetch_multiplier": resolved.celery_worker_prefetch_multiplier,
        "task_always_eager": resolved.celery_task_always_eager,
        "task_eager_propagates": resolved.celery_task_eager_propagates,
        "broker_connection_retry_on_startup": resolved.celery_broker_connection_retry_on_startup,
        "result_expires": resolved.celery_result_expires_seconds,
        "beat_schedule": build_beat_schedule(resolved),
    }
    return config


def build_beat_schedule(settings: Settings) -> dict[str, Any]:
    """Optional Celery Beat entries. Disabled unless `COLLECTION_BEAT_ENABLED` is true."""
    if not settings.collection_beat_enabled:
        return {}
    return {
        "collection-product-search": {
            "task": TASK_PRODUCT_SEARCH,
            "schedule": float(settings.collection_search_interval_seconds),
        },
        "collection-product-refresh": {
            "task": TASK_PRODUCT_REFRESH,
            "schedule": float(settings.collection_product_refresh_interval_seconds),
        },
        "collection-price-refresh": {
            "task": TASK_PRICE_REFRESH,
            "schedule": float(settings.collection_price_refresh_interval_seconds),
        },
        "collection-availability-refresh": {
            "task": TASK_AVAILABILITY_REFRESH,
            "schedule": float(settings.collection_availability_refresh_interval_seconds),
        },
        "collection-sale-event-refresh": {
            "task": TASK_SALE_EVENT_REFRESH,
            "schedule": float(settings.collection_sale_event_refresh_interval_seconds),
        },
    }


def celery_config_public_view(config: dict[str, Any]) -> dict[str, Any]:
    """Copy of Celery config safe to log: broker/result URLs omitted."""
    return {key: value for key, value in config.items() if key not in _SECRET_CONFIG_KEYS}
