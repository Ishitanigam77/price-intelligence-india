"""Phase 13 collection jobs against PostgreSQL, using mock/scripted adapters only."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors.config import CollectionConfig
from app.collectors.metrics import (
    JOB_DURATION,
    JOBS_FAILED,
    JOBS_SUCCESSFUL,
    JOBS_TOTAL,
    PRICE_FRESHNESS,
    RETAILER_HEALTH,
)
from app.collectors.orchestrator import CollectionOrchestrator
from app.db.models import CollectionError, CollectionJob, PriceSnapshot, Product, SaleEvent
from app.domain.enums import CollectionJobStatus, CollectionJobType
from app.observability.metrics import InMemoryMetricsSink
from app.retailer_adapters.base.config import RetryPolicy
from app.retailer_adapters.base.errors import (
    InvalidRetailerResponseError,
    ProductNotFoundError,
    TemporaryRetailerFailureError,
)
from app.retailer_adapters.base.registry import RetailerRegistry
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c
from tests.unit.retailer_adapters.helpers import (
    FakeClock,
    make_config,
    make_retailer_product,
    make_scripted_adapter,
)


def _config(**overrides) -> CollectionConfig:
    values = {
        "max_retries": 2,
        "initial_backoff_seconds": 0.5,
        "max_backoff_seconds": 4.0,
        "backoff_multiplier": 2.0,
        "operation_timeout_seconds": 2.0,
        "retailer_timeout_seconds": 5.0,
        "default_search_query": "fictional",
        "default_search_limit": 20,
        "rate_limit_requests_per_minute": 6000,
        "rate_limit_burst_size": 100,
        "rate_limit_max_concurrent": 8,
    }
    values.update(overrides)
    return CollectionConfig(**values)


def _orchestrator(
    session: Session,
    registry: RetailerRegistry,
    *,
    clock: FakeClock | None = None,
    sink: InMemoryMetricsSink | None = None,
    **config_overrides,
) -> CollectionOrchestrator:
    fake = clock or FakeClock()
    return CollectionOrchestrator(
        session,
        registry,
        config=_config(**config_overrides),
        metrics_sink=sink if sink is not None else InMemoryMetricsSink(),
        monotonic=fake,
        sleep=fake.sleep,
    )


def _mock_registry(*, enabled: Sequence[str] | None = None) -> RetailerRegistry:
    registry = RetailerRegistry()
    adapters = [create_a(env={}), create_b(env={}), create_c(env={})]
    if enabled is not None:
        allowed = set(enabled)
        for adapter in adapters:
            if adapter.retailer_id not in allowed:
                adapter.disable()
    registry.register_all(adapters)
    return registry


async def test_product_search_succeeds_for_enabled_mock_retailers(db_session: Session) -> None:
    registry = _mock_registry()
    sink = InMemoryMetricsSink()
    orchestrator = _orchestrator(db_session, registry, sink=sink)
    result = await orchestrator.run(CollectionJobType.PRODUCT_SEARCH)
    assert result.status in {CollectionJobStatus.SUCCESS, CollectionJobStatus.PARTIAL_SUCCESS}
    assert {item.retailer_id for item in result.retailers} == {
        "mock-retailer-a",
        "mock-retailer-b",
        "mock-retailer-c",
    }
    assert all(item.status is CollectionJobStatus.SUCCESS for item in result.retailers)
    jobs = list(db_session.scalars(select(CollectionJob)).all())
    assert len(jobs) == 3
    assert all(job.status is CollectionJobStatus.SUCCESS for job in jobs)
    assert db_session.scalar(select(func.count()).select_from(Product)) >= 1
    assert sink.total_for_name(JOBS_TOTAL) == 3
    assert sink.total_for_name(JOBS_SUCCESSFUL) == 3
    assert sink.total_for_name(JOBS_FAILED) == 0
    assert sink.observed_values(
        JOB_DURATION, job_type="product_search", retailer_id="mock-retailer-a", status="success"
    )
    assert any(metric == RETAILER_HEALTH for metric, _tags in sink.gauges)
    assert any(metric == PRICE_FRESHNESS for metric, _tags in sink.gauges)


async def test_disabled_retailers_are_not_executed(db_session: Session) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    result = await _orchestrator(db_session, registry).run(CollectionJobType.PRODUCT_SEARCH)
    assert [item.retailer_id for item in result.retailers] == ["mock-retailer-a"]
    jobs = list(db_session.scalars(select(CollectionJob)).all())
    assert [job.retailer_id for job in jobs] == ["mock-retailer-a"]


async def test_availability_refresh_skips_retailers_without_the_operation(
    db_session: Session,
) -> None:
    registry = _mock_registry()
    await _orchestrator(db_session, registry).run(CollectionJobType.PRODUCT_SEARCH)
    result = await _orchestrator(db_session, registry).run(CollectionJobType.AVAILABILITY_REFRESH)
    executed = {item.retailer_id for item in result.retailers}
    assert "mock-retailer-a" in executed
    assert "mock-retailer-c" in executed
    assert "mock-retailer-b" not in executed


async def test_product_price_and_sale_event_jobs(
    db_session: Session,
) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    orch = _orchestrator(db_session, registry)
    search = await orch.run(CollectionJobType.PRODUCT_SEARCH)
    assert search.retailers[0].status is CollectionJobStatus.SUCCESS
    product = await orch.run(CollectionJobType.PRODUCT_REFRESH)
    price = await orch.run(CollectionJobType.PRICE_REFRESH)
    sales = await orch.run(CollectionJobType.SALE_EVENT_REFRESH)
    assert product.retailers[0].status is CollectionJobStatus.SUCCESS
    assert price.retailers[0].status is CollectionJobStatus.SUCCESS
    assert sales.retailers[0].status is CollectionJobStatus.SUCCESS
    types = {job.job_type for job in db_session.scalars(select(CollectionJob)).all()}
    assert CollectionJobType.PRODUCT_SEARCH in types
    assert CollectionJobType.PRODUCT_REFRESH in types
    assert CollectionJobType.PRICE_REFRESH in types
    assert CollectionJobType.SALE_EVENT_REFRESH in types


async def test_repeated_search_is_idempotent(db_session: Session) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    orch = _orchestrator(db_session, registry)
    first = await orch.run(CollectionJobType.PRODUCT_SEARCH)
    products_after_first = db_session.scalar(select(func.count()).select_from(Product))
    snapshots_after_first = db_session.scalar(select(func.count()).select_from(PriceSnapshot))
    jobs_after_first = db_session.scalar(select(func.count()).select_from(CollectionJob))
    second = await orch.run(CollectionJobType.PRODUCT_SEARCH)
    assert first.retailers[0].job_id == second.retailers[0].job_id
    assert second.retailers[0].reused_existing is True
    assert db_session.scalar(select(func.count()).select_from(Product)) == products_after_first
    assert (
        db_session.scalar(select(func.count()).select_from(PriceSnapshot)) == snapshots_after_first
    )
    assert db_session.scalar(select(func.count()).select_from(CollectionJob)) == jobs_after_first


async def test_one_retailer_failure_does_not_stop_another(db_session: Session) -> None:
    failing = make_scripted_adapter(
        config=make_config(
            retailer_id="store-fail",
            retailer_name="Failing Store",
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={
            "search_products": lambda query: (_ for _ in ()).throw(
                TemporaryRetailerFailureError(
                    "upstream 503", retailer_id="store-fail", operation="search_products"
                )
            )
        },
    )
    healthy_product = make_retailer_product(retailer_id="store-ok", retailer_sku="OK-1")
    healthy = make_scripted_adapter(
        config=make_config(retailer_id="store-ok", retailer_name="Healthy Store"),
        script={"search_products": (healthy_product,)},
    )
    registry = RetailerRegistry()
    registry.register_all([failing, healthy])
    result = await _orchestrator(db_session, registry, max_retries=0).run(
        CollectionJobType.PRODUCT_SEARCH
    )
    by_id = {item.retailer_id: item for item in result.retailers}
    assert by_id["store-fail"].status is CollectionJobStatus.FAILED
    assert by_id["store-ok"].status is CollectionJobStatus.SUCCESS
    errors = list(db_session.scalars(select(CollectionError)).all())
    assert any(error.retailer_id == "store-fail" for error in errors)
    assert not any(error.retailer_id == "store-ok" for error in errors)


async def test_retry_then_success_records_attempts(db_session: Session) -> None:
    product = make_retailer_product(retailer_id="flaky-store", retailer_sku="FL-1")
    adapter = make_scripted_adapter(
        config=make_config(
            retailer_id="flaky-store",
            retailer_name="Flaky Store",
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={
            "search_products": [
                TemporaryRetailerFailureError(
                    "503", retailer_id="flaky-store", operation="search_products"
                ),
                TemporaryRetailerFailureError(
                    "503", retailer_id="flaky-store", operation="search_products"
                ),
                (product,),
            ]
        },
    )
    registry = RetailerRegistry()
    registry.register(adapter)
    clock = FakeClock()
    result = await _orchestrator(db_session, registry, clock=clock).run(
        CollectionJobType.PRODUCT_SEARCH
    )
    assert result.retailers[0].status is CollectionJobStatus.SUCCESS
    job = db_session.scalars(select(CollectionJob)).one()
    assert job.retry_count == 2
    errors = list(db_session.scalars(select(CollectionError)).all())
    assert len(errors) == 2
    assert clock.now == 0.5 + 1.0  # exponential 0.5, 1.0


async def test_max_retries_exhausted_marks_job_failed(db_session: Session) -> None:
    adapter = make_scripted_adapter(
        config=make_config(
            retailer_id="down-store",
            retailer_name="Down Store",
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={
            "search_products": lambda query: (_ for _ in ()).throw(
                TemporaryRetailerFailureError(
                    "503", retailer_id="down-store", operation="search_products"
                )
            )
        },
    )
    registry = RetailerRegistry()
    registry.register(adapter)
    result = await _orchestrator(db_session, registry, max_retries=2).run(
        CollectionJobType.PRODUCT_SEARCH
    )
    assert result.retailers[0].status is CollectionJobStatus.FAILED
    job = db_session.scalars(select(CollectionJob)).one()
    assert job.status is CollectionJobStatus.FAILED
    assert job.retry_count == 2
    errors = list(db_session.scalars(select(CollectionError)).all())
    assert len(errors) == 3
    assert all(error.retryable is True for error in errors)


async def test_validation_error_is_not_retried(db_session: Session) -> None:
    adapter = make_scripted_adapter(
        config=make_config(
            retailer_id="bad-store",
            retailer_name="Bad Store",
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={
            "search_products": InvalidRetailerResponseError(
                "malformed payload", retailer_id="bad-store", operation="search_products"
            )
        },
    )
    registry = RetailerRegistry()
    registry.register(adapter)
    result = await _orchestrator(db_session, registry, max_retries=3).run(
        CollectionJobType.PRODUCT_SEARCH
    )
    assert result.retailers[0].status is CollectionJobStatus.FAILED
    job = db_session.scalars(select(CollectionJob)).one()
    assert job.retry_count == 0
    errors = list(db_session.scalars(select(CollectionError)).all())
    assert len(errors) == 1
    assert errors[0].retryable is False
    assert errors[0].error_category.value == "validation"


async def test_timeout_records_collection_error_and_allows_other_retailers(
    db_session: Session,
) -> None:
    async def hang(query):
        import asyncio

        await asyncio.sleep(10)
        return (make_retailer_product(retailer_id="slow-store"),)

    slow = make_scripted_adapter(
        config=make_config(
            retailer_id="slow-store",
            retailer_name="Slow Store",
            timeout_seconds=30.0,
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={"search_products": hang},
    )
    ok = make_scripted_adapter(
        config=make_config(retailer_id="fast-store", retailer_name="Fast Store"),
        script={"search_products": (make_retailer_product(retailer_id="fast-store"),)},
    )
    registry = RetailerRegistry()
    registry.register_all([slow, ok])
    result = await _orchestrator(
        db_session, registry, max_retries=0, operation_timeout_seconds=0.05
    ).run(CollectionJobType.PRODUCT_SEARCH)
    by_id = {item.retailer_id: item for item in result.retailers}
    assert by_id["slow-store"].status is CollectionJobStatus.FAILED
    assert by_id["fast-store"].status is CollectionJobStatus.SUCCESS
    error = db_session.scalars(select(CollectionError)).first()
    assert error is not None
    assert error.error_category.value == "timeout"


async def test_partial_success_when_one_sku_fails(db_session: Session) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    orch = _orchestrator(db_session, registry)
    await orch.run(CollectionJobType.PRODUCT_SEARCH)
    failing = make_scripted_adapter(
        config=make_config(
            retailer_id="mock-retailer-a",
            retailer_name="Fictional Mock Mart A",
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={
            "get_price": [
                ProductNotFoundError("gone", retailer_id="mock-retailer-a", operation="get_price"),
                None,
                None,
            ]
        },
    )
    mixed_registry = RetailerRegistry()
    mixed_registry.register(failing, replace=True)
    # Reuse listings already persisted under mock-retailer-a.
    result = await _orchestrator(db_session, mixed_registry).run(CollectionJobType.PRICE_REFRESH)
    assert result.retailers[0].status is CollectionJobStatus.PARTIAL_SUCCESS
    job = db_session.scalars(
        select(CollectionJob).where(CollectionJob.job_type == CollectionJobType.PRICE_REFRESH)
    ).one()
    assert job.status is CollectionJobStatus.PARTIAL_SUCCESS
    assert db_session.scalar(select(func.count()).select_from(CollectionError)) >= 1


async def test_job_lifecycle_fields_are_persisted(db_session: Session) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    await _orchestrator(db_session, registry).run(CollectionJobType.PRODUCT_SEARCH)
    job = db_session.scalars(select(CollectionJob)).one()
    assert job.job_type is CollectionJobType.PRODUCT_SEARCH
    assert job.retailer_id == "mock-retailer-a"
    assert job.status is CollectionJobStatus.SUCCESS
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.duration_ms is not None
    assert job.duration_ms >= 0
    assert job.retry_count == 0
    assert job.idempotency_key
    assert job.error_message is None


async def test_secrets_are_not_stored_on_collection_errors(db_session: Session) -> None:
    adapter = make_scripted_adapter(
        config=make_config(
            retailer_id="leaky-store",
            retailer_name="Leaky Store",
            retry_policy=RetryPolicy(max_attempts=1, jitter_ratio=0.0),
        ),
        script={
            "search_products": lambda query: (_ for _ in ()).throw(
                TemporaryRetailerFailureError(
                    "failed api_key=super-secret-key password=hunter2",
                    retailer_id="leaky-store",
                    operation="search_products",
                )
            )
        },
    )
    registry = RetailerRegistry()
    registry.register(adapter)
    await _orchestrator(db_session, registry, max_retries=0).run(CollectionJobType.PRODUCT_SEARCH)
    error = db_session.scalars(select(CollectionError)).one()
    assert "super-secret-key" not in error.error_message
    assert "hunter2" not in error.error_message
    job = db_session.scalars(select(CollectionJob)).one()
    assert job.error_message is None or "super-secret-key" not in job.error_message


async def test_retailer_registry_is_consulted(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    calls: list[object] = []
    original = registry.adapters_supporting

    def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(registry, "adapters_supporting", wrapped)
    await _orchestrator(db_session, registry).run(CollectionJobType.PRODUCT_SEARCH)
    assert calls, "Collection must discover adapters through RetailerRegistry"


async def test_sale_event_refresh_does_not_duplicate_windows(db_session: Session) -> None:
    registry = _mock_registry(enabled=("mock-retailer-a",))
    orch = _orchestrator(db_session, registry)
    await orch.run(CollectionJobType.PRODUCT_SEARCH)
    first = await orch.run(CollectionJobType.SALE_EVENT_REFRESH)
    count_after_first = db_session.scalar(select(func.count()).select_from(SaleEvent))
    second = await orch.run(CollectionJobType.SALE_EVENT_REFRESH)
    assert first.retailers[0].job_id == second.retailers[0].job_id
    assert second.retailers[0].reused_existing is True
    assert db_session.scalar(select(func.count()).select_from(SaleEvent)) == count_after_first
