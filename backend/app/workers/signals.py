"""Celery signal handlers for task duration, failures, retries, and queue depth."""

from __future__ import annotations

import time
from typing import Any

from celery import signals

from app.observability.correlation import new_correlation_id
from app.observability.logging import get_logger
from app.observability.names import (
    WORKER_QUEUE_DEPTH,
    WORKER_TASK_DURATION_MS,
    WORKER_TASK_FAILURES,
    WORKER_TASK_RETRIES,
    WORKER_TASKS,
)
from app.observability.telemetry import default_metric_tags, get_process_metrics_sink

logger = get_logger(__name__)

_TASK_START: dict[str, float] = {}
_REGISTERED = False


def _task_name(sender: Any, kwargs: dict[str, Any] | None = None) -> str:
    name = getattr(sender, "name", None) or (kwargs or {}).get("name")
    if isinstance(name, str) and name:
        return name.rsplit(".", 1)[-1]
    return "unknown"


def _record_queue_depth() -> None:
    try:
        from app.core.redis import create_redis_client

        client = create_redis_client()
        depth = int(client.llen("celery") or 0)
        get_process_metrics_sink().set_gauge(
            WORKER_QUEUE_DEPTH,
            float(depth),
            tags=default_metric_tags(operation="queue", status="ok"),
        )
    except Exception:
        logger.debug(
            "worker.queue_depth_unavailable",
            extra={"operation": "queue_depth", "status": "error", "service": "worker"},
        )


def on_task_prerun(sender: Any = None, task_id: str | None = None, **kwargs: Any) -> None:
    if task_id:
        _TASK_START[task_id] = time.perf_counter()
    name = _task_name(sender, kwargs)
    get_process_metrics_sink().increment(
        WORKER_TASKS, tags=default_metric_tags(operation=name, status="started")
    )
    _record_queue_depth()
    logger.info(
        "worker.task_started",
        extra={
            **default_metric_tags(operation=name, status="started"),
            "correlation_id": new_correlation_id(),
        },
    )


def on_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    state: str | None = None,
    **kwargs: Any,
) -> None:
    name = _task_name(sender, kwargs)
    start = _TASK_START.pop(task_id, None) if task_id else None
    duration_ms = (time.perf_counter() - start) * 1000 if start is not None else 0.0
    status = (state or "SUCCESS").lower()
    get_process_metrics_sink().observe(
        WORKER_TASK_DURATION_MS,
        duration_ms,
        tags=default_metric_tags(operation=name, status=status),
    )
    logger.info(
        "worker.task_finished",
        extra={
            **default_metric_tags(operation=name, status=status),
            "duration_ms": round(duration_ms, 3),
        },
    )
    _record_queue_depth()


def on_task_failure(sender: Any = None, exception: BaseException | None = None, **kwargs: Any) -> None:
    name = _task_name(sender, kwargs)
    error_type = type(exception).__name__ if exception is not None else "task_failure"
    get_process_metrics_sink().increment(
        WORKER_TASK_FAILURES,
        tags=default_metric_tags(operation=name, status="error", error_type=error_type),
    )
    logger.error(
        "worker.task_failed",
        extra={
            **default_metric_tags(operation=name, status="error"),
            "error_type": error_type,
        },
    )


def on_task_retry(sender: Any = None, reason: Any = None, **kwargs: Any) -> None:
    name = _task_name(sender, kwargs)
    error_type = type(reason).__name__ if reason is not None else "retry"
    get_process_metrics_sink().increment(
        WORKER_TASK_RETRIES,
        tags=default_metric_tags(operation=name, status="retry", error_type=error_type),
    )
    logger.warning(
        "worker.task_retry",
        extra={
            **default_metric_tags(operation=name, status="retry"),
            "error_type": error_type,
        },
    )


def register_worker_signals() -> None:
    """Connect Celery signals. Safe to call more than once."""
    global _REGISTERED
    if _REGISTERED:
        return
    signals.task_prerun.connect(on_task_prerun, weak=False)
    signals.task_postrun.connect(on_task_postrun, weak=False)
    signals.task_failure.connect(on_task_failure, weak=False)
    signals.task_retry.connect(on_task_retry, weak=False)
    _REGISTERED = True
