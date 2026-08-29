"""Metrics-ready names for collection jobs.

These names are the contract a future exporter (Azure Monitor / Application Insights) will
bind to. Collection code records through `MetricsSink` only — no metrics platform is added here.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.enums import CollectionJobStatus, CollectionJobType
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.retailer_adapters.base.models import HealthStatus

JOBS_TOTAL = "jobs_total"
JOBS_FAILED = "jobs_failed"
JOBS_SUCCESSFUL = "jobs_successful"
JOB_DURATION = "job_duration"
RETAILER_HEALTH = "retailer_health"
PRICE_FRESHNESS = "price_freshness"

HEALTH_GAUGE_VALUES: dict[HealthStatus, float] = {
    HealthStatus.HEALTHY: 1.0,
    HealthStatus.DEGRADED: 0.5,
    HealthStatus.UNHEALTHY: 0.0,
    HealthStatus.UNKNOWN: -1.0,
}


class CollectionMetricsRecorder:
    """Emit the Phase 13 collection metric names with consistent tags."""

    def __init__(self, sink: MetricsSink | None = None) -> None:
        self._sink: MetricsSink = sink if sink is not None else NullMetricsSink()

    @property
    def sink(self) -> MetricsSink:
        return self._sink

    def job_started(self, job_type: CollectionJobType, *, retailer_id: str) -> None:
        self._sink.increment(JOBS_TOTAL, tags=self._tags(job_type, retailer_id))

    def job_finished(
        self,
        job_type: CollectionJobType,
        *,
        retailer_id: str,
        status: CollectionJobStatus,
        duration_ms: float,
    ) -> None:
        tags = self._tags(job_type, retailer_id) | {"status": status.value}
        self._sink.observe(JOB_DURATION, duration_ms, tags=tags)
        if status is CollectionJobStatus.FAILED:
            self._sink.increment(JOBS_FAILED, tags=self._tags(job_type, retailer_id))
        elif status in {CollectionJobStatus.SUCCESS, CollectionJobStatus.PARTIAL_SUCCESS}:
            self._sink.increment(JOBS_SUCCESSFUL, tags=self._tags(job_type, retailer_id))

    def retailer_health(self, retailer_id: str, status: HealthStatus) -> None:
        self._sink.set_gauge(
            RETAILER_HEALTH,
            HEALTH_GAUGE_VALUES[status],
            tags={"retailer_id": retailer_id},
        )

    def price_freshness(self, retailer_id: str, age_seconds: float) -> None:
        self._sink.set_gauge(
            PRICE_FRESHNESS,
            age_seconds,
            tags={"retailer_id": retailer_id},
        )

    @staticmethod
    def _tags(job_type: CollectionJobType, retailer_id: str) -> Mapping[str, str]:
        return {"job_type": job_type.value, "retailer_id": retailer_id}
