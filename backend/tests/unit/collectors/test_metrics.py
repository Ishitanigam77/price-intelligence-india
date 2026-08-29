"""Metrics-ready collection names are stable."""

from app.collectors.metrics import (
    JOB_DURATION,
    JOBS_FAILED,
    JOBS_SUCCESSFUL,
    JOBS_TOTAL,
    PRICE_FRESHNESS,
    RETAILER_HEALTH,
    CollectionMetricsRecorder,
)
from app.domain.enums import CollectionJobStatus, CollectionJobType
from app.observability.metrics import InMemoryMetricsSink
from app.retailer_adapters.base.models import HealthStatus


def test_required_metric_names_are_exactly_the_phase13_contract() -> None:
    assert JOBS_TOTAL == "jobs_total"
    assert JOBS_FAILED == "jobs_failed"
    assert JOBS_SUCCESSFUL == "jobs_successful"
    assert JOB_DURATION == "job_duration"
    assert RETAILER_HEALTH == "retailer_health"
    assert PRICE_FRESHNESS == "price_freshness"


def test_recorder_emits_job_and_health_and_freshness_metrics() -> None:
    sink = InMemoryMetricsSink()
    recorder = CollectionMetricsRecorder(sink)
    recorder.job_started(CollectionJobType.PRODUCT_SEARCH, retailer_id="store-a")
    recorder.job_finished(
        CollectionJobType.PRODUCT_SEARCH,
        retailer_id="store-a",
        status=CollectionJobStatus.SUCCESS,
        duration_ms=12.5,
    )
    recorder.job_finished(
        CollectionJobType.PRICE_REFRESH,
        retailer_id="store-b",
        status=CollectionJobStatus.FAILED,
        duration_ms=3.0,
    )
    recorder.retailer_health("store-a", HealthStatus.HEALTHY)
    recorder.price_freshness("store-a", 42.0)

    assert sink.counter_value(JOBS_TOTAL, job_type="product_search", retailer_id="store-a") == 1
    assert (
        sink.counter_value(JOBS_SUCCESSFUL, job_type="product_search", retailer_id="store-a") == 1
    )
    assert sink.counter_value(JOBS_FAILED, job_type="price_refresh", retailer_id="store-b") == 1
    assert sink.observed_values(
        JOB_DURATION, job_type="product_search", retailer_id="store-a", status="success"
    ) == [12.5]
    assert sink.gauge_value(RETAILER_HEALTH, retailer_id="store-a") == 1.0
    assert sink.gauge_value(PRICE_FRESHNESS, retailer_id="store-a") == 42.0
