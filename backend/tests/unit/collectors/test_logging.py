"""Structured collection logs carry job context and never leak secrets."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from uuid import uuid4

from app.collectors.orchestrator import CollectionOrchestrator
from app.collectors.sanitization import sanitize_mapping
from app.domain.enums import CollectionJobStatus, CollectionJobType
from app.observability.logging import REDACTED, JsonLogFormatter


def _format(record: logging.LogRecord) -> dict[str, object]:
    return json.loads(JsonLogFormatter().format(record))


def test_collection_log_record_includes_required_fields() -> None:
    record = logging.LogRecord(
        name="app.collectors.orchestrator",
        level=logging.INFO,
        pathname="orchestrator.py",
        lineno=1,
        msg="collection.job_completed",
        args=(),
        exc_info=None,
    )
    record.job_id = "11111111-1111-1111-1111-111111111111"
    record.job_type = CollectionJobType.PRODUCT_SEARCH.value
    record.retailer_id = "mock-retailer-a"
    record.product_id = "SKU-FICTIONAL-1"
    record.attempt = 2
    record.status = CollectionJobStatus.SUCCESS.value
    record.duration_ms = 42.5
    record.error_category = None
    payload = _format(record)
    assert payload["message"] == "collection.job_completed"
    assert payload["job_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["job_type"] == "product_search"
    assert payload["retailer_id"] == "mock-retailer-a"
    assert payload["product_id"] == "SKU-FICTIONAL-1"
    assert payload["attempt"] == 2
    assert payload["status"] == "success"
    assert payload["duration_ms"] == 42.5
    assert payload["error_category"] is None
    assert payload["logger"] == "app.collectors.orchestrator"


def test_orchestrator_log_fields_cover_job_retailer_and_attempt() -> None:
    job = SimpleNamespace(
        id=uuid4(),
        job_type=CollectionJobType.PRICE_REFRESH,
        status=CollectionJobStatus.RUNNING,
    )
    adapter = SimpleNamespace(retailer_id="mock-retailer-a")
    orch = CollectionOrchestrator.__new__(CollectionOrchestrator)
    fields = CollectionOrchestrator._log_fields(orch, job, adapter, attempt=3)
    assert fields["job_id"] == str(job.id)
    assert fields["job_type"] == "price_refresh"
    assert fields["retailer_id"] == "mock-retailer-a"
    assert fields["attempt"] == 3
    assert fields["status"] == "running"
    extras = sanitize_mapping(fields | {"duration_ms": 11.0, "error_category": "timeout"})
    record = logging.LogRecord(
        name="app.collectors.orchestrator",
        level=logging.WARNING,
        pathname="orchestrator.py",
        lineno=1,
        msg="collection.attempt_failed",
        args=(),
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    payload = _format(record)
    assert payload["job_id"] == str(job.id)
    assert payload["job_type"] == "price_refresh"
    assert payload["retailer_id"] == "mock-retailer-a"
    assert payload["attempt"] == 3
    assert payload["status"] == "running"
    assert payload["duration_ms"] == 11.0
    assert payload["error_category"] == "timeout"


def test_secret_extras_are_redacted_from_collection_logs() -> None:
    extras = sanitize_mapping(
        {
            "job_id": "abc",
            "job_type": "product_search",
            "retailer_id": "mock-retailer-a",
            "attempt": 1,
            "status": "failed",
            "api_key": "super-secret-key",
            "password": "hunter2",
            "clerk_secret_key": "clerk-secret",
            "authorization": "Bearer leaked-token",
            "redis_url": "redis://:hunter2@localhost:6379/1",
        }
    )
    record = logging.LogRecord(
        name="app.collectors.orchestrator",
        level=logging.ERROR,
        pathname="orchestrator.py",
        lineno=1,
        msg="collection.job_failed",
        args=(),
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    payload = _format(record)
    dumped = json.dumps(payload)
    assert "super-secret-key" not in dumped
    assert "hunter2" not in dumped
    assert "clerk-secret" not in dumped
    assert "leaked-token" not in dumped
    assert payload["api_key"] == REDACTED
    assert payload["password"] == REDACTED
    assert payload["clerk_secret_key"] == REDACTED
    assert payload["authorization"] == REDACTED
    assert payload["job_id"] == "abc"
    assert payload["retailer_id"] == "mock-retailer-a"
