"""Celery tasks map onto the five collection job types without naming retailers."""

from app.domain.enums import CollectionJobType
from app.workers import tasks as tasks_mod
from app.workers.celery_config import (
    TASK_AVAILABILITY_REFRESH,
    TASK_PRICE_REFRESH,
    TASK_PRODUCT_REFRESH,
    TASK_PRODUCT_SEARCH,
    TASK_SALE_EVENT_REFRESH,
)


def test_each_job_type_has_a_celery_task(monkeypatch) -> None:
    seen: list[CollectionJobType] = []

    def fake_run(job_type: CollectionJobType, **kwargs):
        seen.append(job_type)
        return {"job_type": job_type.value, "status": "success", "retailers": []}

    monkeypatch.setattr(tasks_mod, "_run_collection_job", fake_run)

    assert tasks_mod.collect_product_search.run()["job_type"] == "product_search"
    assert tasks_mod.collect_product_refresh.run()["job_type"] == "product_refresh"
    assert tasks_mod.collect_price_refresh.run()["job_type"] == "price_refresh"
    assert tasks_mod.collect_availability_refresh.run()["job_type"] == "availability_refresh"
    assert tasks_mod.collect_sale_event_refresh.run()["job_type"] == "sale_event_refresh"
    assert seen == [
        CollectionJobType.PRODUCT_SEARCH,
        CollectionJobType.PRODUCT_REFRESH,
        CollectionJobType.PRICE_REFRESH,
        CollectionJobType.AVAILABILITY_REFRESH,
        CollectionJobType.SALE_EVENT_REFRESH,
    ]


def test_task_names_are_stable() -> None:
    assert tasks_mod.collect_product_search.name == TASK_PRODUCT_SEARCH
    assert tasks_mod.collect_product_refresh.name == TASK_PRODUCT_REFRESH
    assert tasks_mod.collect_price_refresh.name == TASK_PRICE_REFRESH
    assert tasks_mod.collect_availability_refresh.name == TASK_AVAILABILITY_REFRESH
    assert tasks_mod.collect_sale_event_refresh.name == TASK_SALE_EVENT_REFRESH
