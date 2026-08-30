"""Worker health payloads and Celery signal metrics."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.config import Settings
from app.observability.metrics import InMemoryMetricsSink
from app.observability.names import WORKER_TASK_FAILURES, WORKER_TASK_RETRIES, WORKER_TASKS
from app.observability.telemetry import set_process_metrics_sink
from app.workers import signals as signals_mod
from app.workers.health import worker_liveness_payload, worker_readiness_payload


def test_worker_liveness_payload_has_no_secrets() -> None:
    settings = Settings(
        _env_file=None,
        service_name="worker",
        environment="test",
        applicationinsights_connection_string="InstrumentationKey=abc",
    )
    payload = worker_liveness_payload(settings)
    assert payload["status"] == "ok"
    assert payload["service"] == "worker"
    dumped = str(payload)
    assert "InstrumentationKey" not in dumped
    assert "abc" not in dumped


def test_worker_readiness_degraded_when_broker_down() -> None:
    settings = Settings(_env_file=None, service_name="worker", environment="test")
    payload = worker_readiness_payload(broker_ok=False, settings=settings)
    assert payload["status"] == "degraded"
    assert payload["checks"]["broker"]["status"] == "unavailable"


def test_worker_signals_emit_task_metrics() -> None:
    sink = InMemoryMetricsSink()
    set_process_metrics_sink(sink)
    signals_mod._TASK_START.clear()
    sender = SimpleNamespace(name="priceradar.collection.product_search")
    signals_mod.on_task_prerun(sender=sender, task_id="t1")
    signals_mod.on_task_postrun(sender=sender, task_id="t1", state="SUCCESS")
    signals_mod.on_task_failure(sender=sender, exception=RuntimeError("boom"))
    signals_mod.on_task_retry(sender=sender, reason=RuntimeError("again"))
    assert sink.total_for_name(WORKER_TASKS) >= 1
    assert sink.total_for_name(WORKER_TASK_FAILURES) >= 1
    assert sink.total_for_name(WORKER_TASK_RETRIES) >= 1
