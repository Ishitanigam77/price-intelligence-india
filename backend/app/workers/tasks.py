"""Celery tasks for the five Phase 13 collection jobs.

Tasks discover enabled adapters through `RetailerRegistry` (via `build_retailer_registry`).
They never import a named retailer adapter package.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from celery import shared_task

from app.collectors.orchestrator import CollectionOrchestrator, CollectionRunResult
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.domain.enums import CollectionJobType
from app.observability.metrics import NullMetricsSink
from app.retailer_adapters.wiring import build_retailer_registry
from app.workers.celery_config import (
    TASK_AVAILABILITY_REFRESH,
    TASK_PRICE_REFRESH,
    TASK_PRODUCT_REFRESH,
    TASK_PRODUCT_SEARCH,
    TASK_SALE_EVENT_REFRESH,
)


def _run_collection_job(
    job_type: CollectionJobType,
    *,
    query: str | None = None,
    limit: int | None = None,
    category: str | None = None,
    retailer_ids: Sequence[str] | None = None,
    skus: Sequence[str] | None = None,
    run_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    session = SessionLocal()
    settings = get_settings()
    try:
        registry = build_retailer_registry(settings=settings)
        orchestrator = CollectionOrchestrator(
            session, registry, metrics_sink=NullMetricsSink()
        )
        result: CollectionRunResult = asyncio.run(
            orchestrator.run(
                job_type,
                query=query,
                limit=limit,
                category=category,
                retailer_ids=retailer_ids,
                skus=skus,
                run_key=run_key,
                idempotency_key=idempotency_key,
            )
        )
        session.commit()
        return result.as_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@shared_task(name=TASK_PRODUCT_SEARCH)
def collect_product_search(
    query: str | None = None,
    limit: int | None = None,
    category: str | None = None,
    retailer_ids: list[str] | None = None,
    run_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Search enabled retailers and persist discovered listings."""
    return _run_collection_job(
        CollectionJobType.PRODUCT_SEARCH,
        query=query,
        limit=limit,
        category=category,
        retailer_ids=retailer_ids,
        run_key=run_key,
        idempotency_key=idempotency_key,
    )


@shared_task(name=TASK_PRODUCT_REFRESH)
def collect_product_refresh(
    retailer_ids: list[str] | None = None,
    skus: list[str] | None = None,
    run_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Refresh product payloads for known listings at enabled retailers."""
    return _run_collection_job(
        CollectionJobType.PRODUCT_REFRESH,
        retailer_ids=retailer_ids,
        skus=skus,
        run_key=run_key,
        idempotency_key=idempotency_key,
    )


@shared_task(name=TASK_PRICE_REFRESH)
def collect_price_refresh(
    retailer_ids: list[str] | None = None,
    skus: list[str] | None = None,
    run_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Refresh prices for known listings at enabled retailers."""
    return _run_collection_job(
        CollectionJobType.PRICE_REFRESH,
        retailer_ids=retailer_ids,
        skus=skus,
        run_key=run_key,
        idempotency_key=idempotency_key,
    )


@shared_task(name=TASK_AVAILABILITY_REFRESH)
def collect_availability_refresh(
    retailer_ids: list[str] | None = None,
    skus: list[str] | None = None,
    run_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Refresh availability for known listings at enabled retailers that support it."""
    return _run_collection_job(
        CollectionJobType.AVAILABILITY_REFRESH,
        retailer_ids=retailer_ids,
        skus=skus,
        run_key=run_key,
        idempotency_key=idempotency_key,
    )


@shared_task(name=TASK_SALE_EVENT_REFRESH)
def collect_sale_event_refresh(
    retailer_ids: list[str] | None = None,
    run_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Recompute inferred sale windows from stored observations per enabled retailer."""
    return _run_collection_job(
        CollectionJobType.SALE_EVENT_REFRESH,
        retailer_ids=retailer_ids,
        run_key=run_key,
        idempotency_key=idempotency_key,
    )
