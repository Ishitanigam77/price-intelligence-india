"""Collection orchestration: registry → enabled adapters → isolated per-retailer execution.

A failure in one retailer is captured as `CollectionError` and never terminates the rest of
the run. Disabled retailers are not executed. Callers never name a retailer implementation.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.collectors.config import CollectionConfig, collection_config_from_settings
from app.collectors.errors import CollectionFailure
from app.collectors.idempotency import build_idempotency_key
from app.collectors.ingest import CollectionIngestor
from app.collectors.jobs import (
    RetailerJobOutcome,
    run_availability_refresh,
    run_price_refresh,
    run_product_refresh,
    run_product_search,
    run_sale_event_refresh,
)
from app.collectors.mapping import collection_failure_from_adapter, collection_failure_from_exception
from app.collectors.metrics import CollectionMetricsRecorder
from app.collectors.rate_limit import CollectionRateLimiterRegistry
from app.collectors.retry import backoff_seconds, is_retryable
from app.collectors.sanitization import sanitize_mapping, sanitize_text
from app.collectors.timeout import run_with_timeout
from app.db.models import CollectionError, CollectionJob
from app.domain.enums import CollectionJobStatus, CollectionJobType
from app.observability.correlation import correlation_scope, get_correlation_id
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.repositories.collection_error_repository import CollectionErrorRepository
from app.repositories.collection_job_repository import CollectionJobRepository
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import RetailerAdapterError
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.registry import RetailerRegistry
from app.sales.detection import SaleEventDetector

logger = get_logger(__name__)

_JOB_OPERATIONS: dict[CollectionJobType, AdapterOperation | None] = {
    CollectionJobType.PRODUCT_SEARCH: AdapterOperation.SEARCH_PRODUCTS,
    CollectionJobType.PRODUCT_REFRESH: AdapterOperation.GET_PRODUCT,
    CollectionJobType.PRICE_REFRESH: AdapterOperation.GET_PRICE,
    CollectionJobType.AVAILABILITY_REFRESH: AdapterOperation.GET_AVAILABILITY,
    CollectionJobType.SALE_EVENT_REFRESH: None,
}

_TERMINAL_SUCCESS = {CollectionJobStatus.SUCCESS, CollectionJobStatus.PARTIAL_SUCCESS}


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class RetailerRunResult:
    retailer_id: str
    job_id: UUID | None
    status: CollectionJobStatus
    idempotency_key: str
    reused_existing: bool = False
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "retailer_id": self.retailer_id,
            "job_id": str(self.job_id) if self.job_id is not None else None,
            "status": self.status.value,
            "idempotency_key": self.idempotency_key,
            "reused_existing": self.reused_existing,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
        }


@dataclass
class CollectionRunResult:
    job_type: CollectionJobType
    retailers: list[RetailerRunResult] = field(default_factory=list)

    @property
    def status(self) -> CollectionJobStatus:
        if not self.retailers:
            return CollectionJobStatus.SUCCESS
        statuses = {item.status for item in self.retailers}
        if statuses <= {CollectionJobStatus.SUCCESS}:
            return CollectionJobStatus.SUCCESS
        if CollectionJobStatus.SUCCESS in statuses or CollectionJobStatus.PARTIAL_SUCCESS in statuses:
            if CollectionJobStatus.FAILED in statuses or CollectionJobStatus.PARTIAL_SUCCESS in statuses:
                return CollectionJobStatus.PARTIAL_SUCCESS
            return CollectionJobStatus.SUCCESS
        return CollectionJobStatus.FAILED

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_type": self.job_type.value,
            "status": self.status.value,
            "retailers": [item.as_dict() for item in self.retailers],
        }


class CollectionOrchestrator:
    """Runs one collection job type across every capable enabled retailer."""

    def __init__(
        self,
        session: Session,
        registry: RetailerRegistry,
        *,
        config: CollectionConfig | None = None,
        metrics_sink: MetricsSink | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._session = session
        self._registry = registry
        self._config = config if config is not None else collection_config_from_settings()
        sink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._metrics = CollectionMetricsRecorder(sink)
        self._ingestor = CollectionIngestor(session, registry, metrics_sink=sink)
        self._jobs = CollectionJobRepository(session)
        self._errors = CollectionErrorRepository(session)
        self._detector = SaleEventDetector(metrics_sink=sink, clock=clock)
        self._monotonic = monotonic
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._clock = clock
        self._rate_limiters = CollectionRateLimiterRegistry(
            self._config, clock=monotonic, sleep=self._sleep
        )

    @property
    def registry(self) -> RetailerRegistry:
        return self._registry

    async def run(
        self,
        job_type: CollectionJobType,
        *,
        query: str | None = None,
        limit: int | None = None,
        category: str | None = None,
        retailer_ids: Sequence[str] | None = None,
        skus: Sequence[str] | None = None,
        run_key: str | None = None,
        idempotency_key: str | None = None,
    ) -> CollectionRunResult:
        """Execute `job_type` for every matching enabled retailer, isolated from each other."""
        adapters = self._adapters_for(job_type, retailer_ids=retailer_ids)
        results: list[RetailerRunResult] = []
        with correlation_scope():
            logger.info(
                "collection.run_started",
                extra=sanitize_mapping(
                    {
                        "job_type": job_type.value,
                        "retailer_ids": [adapter.retailer_id for adapter in adapters],
                        "correlation_id": get_correlation_id(),
                    }
                ),
            )
            for adapter in adapters:
                result = await self._run_one_retailer(
                    job_type,
                    adapter,
                    query=query,
                    limit=limit,
                    category=category,
                    skus=skus,
                    run_key=run_key,
                    idempotency_key=idempotency_key,
                )
                results.append(result)
        aggregate = CollectionRunResult(job_type=job_type, retailers=results)
        logger.info(
            "collection.run_completed",
            extra=sanitize_mapping(
                {
                    "job_type": job_type.value,
                    "status": aggregate.status.value,
                    "retailer_count": len(results),
                    "correlation_id": get_correlation_id(),
                }
            ),
        )
        return aggregate

    def _adapters_for(
        self,
        job_type: CollectionJobType,
        *,
        retailer_ids: Sequence[str] | None,
    ) -> tuple[RetailerAdapter, ...]:
        operation = _JOB_OPERATIONS[job_type]
        if operation is None:
            adapters = self._registry.adapters(enabled_only=True)
        else:
            adapters = self._registry.adapters_supporting(operation, enabled_only=True)
        if retailer_ids is not None:
            wanted = set(retailer_ids)
            adapters = tuple(adapter for adapter in adapters if adapter.retailer_id in wanted)
        return adapters

    async def _run_one_retailer(
        self,
        job_type: CollectionJobType,
        adapter: RetailerAdapter,
        *,
        query: str | None,
        limit: int | None,
        category: str | None,
        skus: Sequence[str] | None,
        run_key: str | None,
        idempotency_key: str | None,
    ) -> RetailerRunResult:
        scope = _scope(query=query, limit=limit, category=category, skus=skus)
        key = build_idempotency_key(
            job_type,
            adapter.retailer_id,
            scope=scope,
            run_key=run_key or idempotency_key,
        )
        existing = self._jobs.get_by_idempotency_key(key)
        if existing is not None and existing.status in _TERMINAL_SUCCESS:
            logger.info(
                "collection.job_reused",
                extra=sanitize_mapping(self._log_fields(existing, adapter, attempt=0)),
            )
            return RetailerRunResult(
                retailer_id=adapter.retailer_id,
                job_id=existing.id,
                status=existing.status,
                idempotency_key=key,
                reused_existing=True,
            )

        job = existing or self._jobs.add(
            CollectionJob(
                job_type=job_type,
                retailer_id=adapter.retailer_id,
                status=CollectionJobStatus.PENDING,
                retry_count=0,
                idempotency_key=key,
            )
        )
        started = self._clock()
        job.status = CollectionJobStatus.RUNNING
        job.started_at = job.started_at or started
        self._session.flush()
        self._metrics.job_started(job_type, retailer_id=adapter.retailer_id)
        started_mono = self._monotonic()

        try:
            outcome = await self._execute_with_policy(job, adapter, query=query, limit=limit, category=category, skus=skus)
        except CollectionFailure as error:
            duration_ms = (self._monotonic() - started_mono) * 1000.0
            self._finalize_failure(job, adapter, error=error, duration_ms=duration_ms)
            return RetailerRunResult(
                retailer_id=adapter.retailer_id,
                job_id=job.id,
                status=job.status,
                idempotency_key=key,
                failed=1,
            )
        except Exception as exc:
            duration_ms = (self._monotonic() - started_mono) * 1000.0
            error = collection_failure_from_exception(
                exc,
                retailer_id=adapter.retailer_id,
                operation=job_type.value,
            )
            self._finalize_failure(job, adapter, error=error, duration_ms=duration_ms)
            return RetailerRunResult(
                retailer_id=adapter.retailer_id,
                job_id=job.id,
                status=job.status,
                idempotency_key=key,
                failed=1,
            )

        duration_ms = (self._monotonic() - started_mono) * 1000.0
        status = _status_for_outcome(outcome)
        self._record_item_errors(job, outcome.item_errors, attempt=job.retry_count + 1)
        job.status = status
        job.completed_at = self._clock()
        job.duration_ms = duration_ms
        if outcome.item_errors and status is CollectionJobStatus.FAILED:
            last = outcome.item_errors[-1]
            job.error_category = last.category.value
            job.error_message = sanitize_text(last.message)
        else:
            job.error_category = None
            job.error_message = None
        self._session.flush()
        self._metrics.job_finished(
            job_type, retailer_id=adapter.retailer_id, status=status, duration_ms=duration_ms
        )
        await self._record_health_and_freshness(adapter)
        logger.info(
            "collection.job_completed",
            extra=sanitize_mapping(
                self._log_fields(job, adapter, attempt=job.retry_count + 1)
                | {
                    "status": status.value,
                    "duration_ms": duration_ms,
                    "succeeded": outcome.succeeded,
                    "failed": outcome.failed,
                }
            ),
        )
        return RetailerRunResult(
            retailer_id=adapter.retailer_id,
            job_id=job.id,
            status=status,
            idempotency_key=key,
            succeeded=outcome.succeeded,
            failed=outcome.failed,
            skipped=outcome.skipped,
        )

    async def _execute_with_policy(
        self,
        job: CollectionJob,
        adapter: RetailerAdapter,
        *,
        query: str | None,
        limit: int | None,
        category: str | None,
        skus: Sequence[str] | None,
    ) -> RetailerJobOutcome:
        max_attempts = self._config.max_attempts
        last_error: CollectionFailure | None = None
        for attempt in range(1, max_attempts + 1):
            job.retry_count = attempt - 1
            self._session.flush()
            try:
                return await run_with_timeout(
                    lambda: self._execute_job_body(
                        job.job_type,
                        adapter,
                        query=query,
                        limit=limit,
                        category=category,
                        skus=skus,
                    ),
                    timeout_seconds=self._config.retailer_timeout_seconds,
                    retailer_id=adapter.retailer_id,
                    operation_name=job.job_type.value,
                )
            except CollectionFailure as error:
                last_error = error
                self._record_error(job, error, attempt=attempt, max_attempts=max_attempts)
                logger.warning(
                    "collection.attempt_failed",
                    extra=sanitize_mapping(
                        self._log_fields(job, adapter, attempt=attempt)
                        | {
                            "error_category": error.category.value,
                            "success": False,
                            "retryable": is_retryable(
                                error, attempt=attempt, max_attempts=max_attempts
                            ),
                        }
                    ),
                )
                if not is_retryable(error, attempt=attempt, max_attempts=max_attempts):
                    raise
                delay = backoff_seconds(self._config, attempt=attempt)
                await self._sleep(delay)
        assert last_error is not None
        raise last_error

    async def _execute_job_body(
        self,
        job_type: CollectionJobType,
        adapter: RetailerAdapter,
        *,
        query: str | None,
        limit: int | None,
        category: str | None,
        skus: Sequence[str] | None,
    ) -> RetailerJobOutcome:
        limiter = self._rate_limiters.limiter_for(
            adapter.retailer_id,
            adapter_rpm=adapter.config.rate_limit.max_requests_per_minute,
        )
        await limiter.acquire()
        try:
            return await run_with_timeout(
                lambda: self._dispatch(
                    job_type,
                    adapter,
                    query=query,
                    limit=limit,
                    category=category,
                    skus=skus,
                ),
                timeout_seconds=self._config.operation_timeout_seconds,
                retailer_id=adapter.retailer_id,
                operation_name=job_type.value,
            )
        except RetailerAdapterError as error:
            raise collection_failure_from_adapter(error) from error
        finally:
            limiter.release()

    async def _dispatch(
        self,
        job_type: CollectionJobType,
        adapter: RetailerAdapter,
        *,
        query: str | None,
        limit: int | None,
        category: str | None,
        skus: Sequence[str] | None,
    ) -> RetailerJobOutcome:
        search_query = query if query is not None else self._config.default_search_query
        search_limit = limit if limit is not None else self._config.default_search_limit
        search_category = (
            category if category is not None else self._config.default_search_category
        )
        if job_type is CollectionJobType.PRODUCT_SEARCH:
            return await run_product_search(
                adapter,
                self._ingestor,
                query_text=search_query,
                limit=search_limit,
                category=search_category,
            )
        if job_type is CollectionJobType.PRODUCT_REFRESH:
            return await run_product_refresh(adapter, self._ingestor, skus=skus)
        if job_type is CollectionJobType.PRICE_REFRESH:
            return await run_price_refresh(adapter, self._ingestor, skus=skus)
        if job_type is CollectionJobType.AVAILABILITY_REFRESH:
            return await run_availability_refresh(adapter, self._ingestor, skus=skus)
        return await run_sale_event_refresh(adapter, self._ingestor, self._detector)

    def _finalize_failure(
        self,
        job: CollectionJob,
        adapter: RetailerAdapter,
        *,
        error: CollectionFailure,
        duration_ms: float,
    ) -> None:
        job.status = CollectionJobStatus.FAILED
        job.completed_at = self._clock()
        job.duration_ms = duration_ms
        job.error_category = error.category.value
        job.error_message = sanitize_text(error.message)
        self._session.flush()
        self._metrics.job_finished(
            job.job_type,
            retailer_id=adapter.retailer_id,
            status=CollectionJobStatus.FAILED,
            duration_ms=duration_ms,
        )
        logger.error(
            "collection.job_failed",
            extra=sanitize_mapping(
                self._log_fields(job, adapter, attempt=job.retry_count + 1)
                | {
                    "status": CollectionJobStatus.FAILED.value,
                    "duration_ms": duration_ms,
                    "error_category": error.category.value,
                    "success": False,
                }
            ),
        )

    def _record_error(
        self,
        job: CollectionJob,
        error: CollectionFailure,
        *,
        attempt: int,
        max_attempts: int,
    ) -> None:
        self._errors.add(
            CollectionError(
                collection_job_id=job.id,
                retailer_id=error.retailer_id,
                error_category=error.category,
                error_message=sanitize_text(error.message) or "Collection failed.",
                attempt=attempt,
                max_attempts=max_attempts,
                retryable=error.retryable,
                operation=error.operation,
                operation_target=sanitize_text(error.operation_target, max_length=500),
                occurred_at=self._clock(),
            )
        )

    def _record_item_errors(
        self, job: CollectionJob, errors: Sequence[CollectionFailure], *, attempt: int
    ) -> None:
        for error in errors:
            self._record_error(
                job, error, attempt=attempt, max_attempts=self._config.max_attempts
            )

    async def _record_health_and_freshness(self, adapter: RetailerAdapter) -> None:
        health = await adapter.health_check()
        self._metrics.retailer_health(adapter.retailer_id, health.status)
        age = self._ingestor.newest_observation_age_seconds(
            adapter.retailer_id, now=self._clock()
        )
        if age is not None:
            self._metrics.price_freshness(adapter.retailer_id, age)

    def _log_fields(
        self, job: CollectionJob, adapter: RetailerAdapter, *, attempt: int
    ) -> dict[str, Any]:
        return {
            "job_id": str(job.id),
            "job_type": job.job_type.value,
            "retailer_id": adapter.retailer_id,
            "attempt": attempt,
            "status": job.status.value,
            "correlation_id": get_correlation_id(),
        }


def _scope(
    *,
    query: str | None,
    limit: int | None,
    category: str | None,
    skus: Sequence[str] | None,
) -> Mapping[str, object]:
    return {
        "query": query,
        "limit": limit,
        "category": category,
        "skus": list(skus) if skus is not None else None,
    }


def _status_for_outcome(outcome: RetailerJobOutcome) -> CollectionJobStatus:
    if outcome.failed and outcome.succeeded:
        return CollectionJobStatus.PARTIAL_SUCCESS
    if outcome.failed:
        return CollectionJobStatus.FAILED
    return CollectionJobStatus.SUCCESS
