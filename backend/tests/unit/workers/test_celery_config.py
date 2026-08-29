"""Celery/Redis configuration is env-driven and omits secrets from the public view."""

import pytest
from pydantic import ValidationError

from app.collectors.errors import CollectionConfigurationError
from app.core.config import Settings
from app.workers.celery_config import (
    TASK_AVAILABILITY_REFRESH,
    TASK_PRICE_REFRESH,
    TASK_PRODUCT_REFRESH,
    TASK_PRODUCT_SEARCH,
    TASK_SALE_EVENT_REFRESH,
    build_beat_schedule,
    build_celery_config,
    celery_config_public_view,
    validate_celery_settings,
)


def test_celery_config_uses_redis_urls_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        celery_broker_url="redis://localhost:6379/1",
        celery_result_backend="redis://localhost:6379/2",
        celery_worker_concurrency=4,
        celery_task_time_limit=120,
        celery_task_always_eager=True,
    )
    config = build_celery_config(settings)
    assert config["broker_url"] == "redis://localhost:6379/1"
    assert config["result_backend"] == "redis://localhost:6379/2"
    assert config["worker_concurrency"] == 4
    assert config["task_time_limit"] == 120
    assert config["task_always_eager"] is True
    assert config["task_serializer"] == "json"
    assert config["beat_schedule"] == {}


def test_public_view_omits_broker_and_result_urls() -> None:
    settings = Settings(
        _env_file=None,
        celery_broker_url="redis://:super-secret@localhost:6379/1",
        celery_result_backend="redis://:super-secret@localhost:6379/2",
    )
    public = celery_config_public_view(build_celery_config(settings))
    assert "broker_url" not in public
    assert "result_backend" not in public
    dumped = str(public)
    assert "super-secret" not in dumped


def test_beat_schedule_lists_all_five_jobs_when_enabled() -> None:
    settings = Settings(_env_file=None, collection_beat_enabled=True)
    schedule = build_beat_schedule(settings)
    tasks = {entry["task"] for entry in schedule.values()}
    assert tasks == {
        TASK_PRODUCT_SEARCH,
        TASK_PRODUCT_REFRESH,
        TASK_PRICE_REFRESH,
        TASK_AVAILABILITY_REFRESH,
        TASK_SALE_EVENT_REFRESH,
    }


def test_validate_celery_settings_requires_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None)
    monkeypatch.setattr(settings, "celery_broker_url", "", raising=False)
    with pytest.raises(CollectionConfigurationError):
        validate_celery_settings(settings)


def test_invalid_redis_scheme_rejected_by_settings() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, redis_url="http://localhost:6379/0")
