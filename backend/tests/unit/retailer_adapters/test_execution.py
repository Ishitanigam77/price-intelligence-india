"""Tests for timeout, retry, and error-translation behaviour of `AdapterExecutor`."""

import asyncio
import logging

import pytest

from app.observability.metrics import InMemoryMetricsSink
from app.retailer_adapters.base.config import AdapterOperation, RetryPolicy
from app.retailer_adapters.base.errors import (
    AdapterTimeoutError,
    ProductNotFoundError,
    TemporaryRetailerFailureError,
    UnexpectedAdapterFailureError,
    UnsupportedOperationError,
)
from app.retailer_adapters.base.execution import AdapterExecutor
from app.retailer_adapters.base.metrics import (
    ADAPTER_FAILURES,
    ADAPTER_REQUESTS,
    ADAPTER_RETRIES,
    ADAPTER_SUCCESSES,
    ADAPTER_TIMEOUTS,
    AdapterMetricsRecorder,
)
from app.retailer_adapters.base.rate_limit import NullRateLimiter
from tests.unit.retailer_adapters.helpers import FakeClock, make_config, make_scripted_adapter


def _executor(config=None, *, clock: FakeClock | None = None) -> AdapterExecutor:
    resolved_clock = clock or FakeClock()
    resolved = config or make_config()
    sink = InMemoryMetricsSink()
    return AdapterExecutor(
        resolved,
        rate_limiter=NullRateLimiter(),
        metrics=AdapterMetricsRecorder(resolved.retailer_id, sink),
        sleep=resolved_clock.sleep,
        monotonic=resolved_clock,
        jitter=lambda: 0.0,
    )


class TestTimeout:
    async def test_exceeding_timeout_raises_adapter_timeout(self) -> None:
        async def hang() -> str:
            await asyncio.sleep(10)
            return "never"

        executor_real = AdapterExecutor(
            make_config(timeout_seconds=0.05, retry_policy=RetryPolicy(max_attempts=1)),
            rate_limiter=NullRateLimiter(),
            metrics=AdapterMetricsRecorder("scripted-store", InMemoryMetricsSink()),
        )
        with pytest.raises(AdapterTimeoutError) as exc:
            await executor_real.execute(AdapterOperation.GET_PRICE, hang)
        assert exc.value.code.value == "timeout"
        assert exc.value.retailer_id == "scripted-store"
        assert exc.value.operation == "get_price"

    async def test_timeout_is_recorded_as_a_timeout_metric(self) -> None:
        sink = InMemoryMetricsSink()
        executor = AdapterExecutor(
            make_config(timeout_seconds=0.05, retry_policy=RetryPolicy(max_attempts=1)),
            rate_limiter=NullRateLimiter(),
            metrics=AdapterMetricsRecorder("scripted-store", sink),
        )

        async def hang() -> None:
            await asyncio.sleep(10)

        with pytest.raises(AdapterTimeoutError):
            await executor.execute(AdapterOperation.GET_PRICE, hang)
        assert (
            sink.counter_value(
                ADAPTER_TIMEOUTS, retailer_id="scripted-store", operation="get_price"
            )
            == 1
        )
        assert (
            sink.counter_value(
                ADAPTER_FAILURES,
                retailer_id="scripted-store",
                operation="get_price",
                error_type="timeout",
            )
            == 1
        )


class TestRetry:
    async def test_retries_transient_failure_then_succeeds(self) -> None:
        clock = FakeClock()
        attempts = {"count": 0}

        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise TemporaryRetailerFailureError(
                    "upstream 503", retailer_id="scripted-store", operation="get_price"
                )
            return "ok"

        config = make_config(
            retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.5, jitter_ratio=0.0)
        )
        result = await _executor(config, clock=clock).execute(AdapterOperation.GET_PRICE, flaky)
        assert result == "ok"
        assert attempts["count"] == 3
        assert clock.now == pytest.approx(0.5 + 1.0)

    async def test_does_not_retry_product_not_found(self) -> None:
        attempts = {"count": 0}

        async def missing() -> None:
            attempts["count"] += 1
            raise ProductNotFoundError("gone", retailer_id="scripted-store", operation="get_price")

        config = make_config(retry_policy=RetryPolicy(max_attempts=5, initial_backoff_seconds=0))
        with pytest.raises(ProductNotFoundError):
            await _executor(config).execute(AdapterOperation.GET_PRICE, missing)
        assert attempts["count"] == 1

    async def test_does_not_retry_unsupported_operation(self) -> None:
        attempts = {"count": 0}

        async def unsupported() -> None:
            attempts["count"] += 1
            raise UnsupportedOperationError(
                "nope", retailer_id="scripted-store", operation="get_availability"
            )

        config = make_config(retry_policy=RetryPolicy(max_attempts=4, initial_backoff_seconds=0))
        with pytest.raises(UnsupportedOperationError):
            await _executor(config).execute(AdapterOperation.GET_AVAILABILITY, unsupported)
        assert attempts["count"] == 1

    async def test_retry_count_is_recorded(self) -> None:
        attempts = {"count": 0}

        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TemporaryRetailerFailureError("503", retailer_id="scripted-store")
            return "ok"

        sink = InMemoryMetricsSink()
        config = make_config(
            retry_policy=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.0, jitter_ratio=0.0)
        )
        executor = AdapterExecutor(
            config,
            rate_limiter=NullRateLimiter(),
            metrics=AdapterMetricsRecorder(config.retailer_id, sink),
            jitter=lambda: 0.0,
        )
        await executor.execute(AdapterOperation.GET_PRICE, flaky)
        assert (
            sink.counter_value(
                ADAPTER_RETRIES,
                retailer_id="scripted-store",
                operation="get_price",
                error_type="temporary_retailer_failure",
            )
            == 1
        )
        assert (
            sink.counter_value(
                ADAPTER_SUCCESSES, retailer_id="scripted-store", operation="get_price"
            )
            == 1
        )
        assert (
            sink.counter_value(
                ADAPTER_REQUESTS, retailer_id="scripted-store", operation="get_price"
            )
            == 1
        )


class TestErrorTranslation:
    async def test_untranslated_exception_becomes_unexpected_adapter_failure(self) -> None:
        class VendorClientError(Exception):
            """Stands in for a retailer-native SDK exception."""

        async def boom() -> None:
            raise VendorClientError("raw payload from vendor, including an api_key=secret")

        with pytest.raises(UnexpectedAdapterFailureError) as exc:
            await _executor().execute(AdapterOperation.GET_PRODUCT, boom)
        assert exc.value.code.value == "unexpected_adapter_failure"
        assert "VendorClientError" in str(exc.value)
        assert "api_key" not in str(exc.value)
        assert "secret" not in str(exc.value)

    async def test_framework_errors_propagate_unchanged(self) -> None:
        error = ProductNotFoundError("gone", retailer_id="scripted-store", operation="get_product")

        async def missing() -> None:
            raise error

        with pytest.raises(ProductNotFoundError) as exc:
            await _executor().execute(AdapterOperation.GET_PRODUCT, missing)
        assert exc.value is error


def _capture_execution_logs() -> tuple[list[logging.LogRecord], logging.Handler, logging.Logger]:
    """Attach a handler to the executor logger, undoing Alembic's disable_existing_loggers."""
    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("app.retailer_adapters.base.execution")
    logger.disabled = False
    logger.setLevel(logging.DEBUG)
    handler = _ListHandler()
    logger.addHandler(handler)
    return records, handler, logger


class TestExecutorLogging:
    async def test_success_log_carries_required_fields(self) -> None:
        records, handler, logger = _capture_execution_logs()

        async def ok() -> str:
            return "ok"

        try:
            await _executor().execute(AdapterOperation.GET_PRICE, ok, correlation_id="corr-123")
        finally:
            logger.removeHandler(handler)
        record = next(
            entry
            for entry in records
            if entry.getMessage() == "retailer_adapter.operation_succeeded"
        )
        assert record.retailer_id == "scripted-store"
        assert record.operation == "get_price"
        assert record.correlation_id == "corr-123"
        assert record.success is True
        assert record.duration_ms >= 0

    async def test_failure_log_carries_error_type(self) -> None:
        records, handler, logger = _capture_execution_logs()

        async def missing() -> None:
            raise ProductNotFoundError("gone", retailer_id="scripted-store", operation="get_price")

        try:
            with pytest.raises(ProductNotFoundError):
                await _executor().execute(AdapterOperation.GET_PRICE, missing)
        finally:
            logger.removeHandler(handler)
        record = next(
            entry for entry in records if entry.getMessage() == "retailer_adapter.operation_failed"
        )
        assert record.error_type == "product_not_found"
        assert record.success is False


class TestAdapterLevelTimeoutAndRetry:
    async def test_scripted_adapter_times_out(self) -> None:
        async def hang(_sku: str) -> None:
            await asyncio.sleep(10)

        adapter = make_scripted_adapter(
            script={"get_price": hang},
            config=make_config(timeout_seconds=0.05, retry_policy=RetryPolicy(max_attempts=1)),
        )
        with pytest.raises(AdapterTimeoutError):
            await adapter.get_price("SKU-1")

    async def test_scripted_adapter_retries_then_succeeds(self) -> None:
        adapter = make_scripted_adapter(
            script={
                "get_price": [
                    TemporaryRetailerFailureError(
                        "503", retailer_id="scripted-store", operation="get_price"
                    ),
                    None,
                ]
            },
            config=make_config(
                retry_policy=RetryPolicy(
                    max_attempts=3, initial_backoff_seconds=0.0, jitter_ratio=0.0
                )
            ),
        )
        observation = await adapter.get_price("SKU-1")
        assert observation.retailer_sku == "SKU-1"
        assert adapter.calls == ["get_price", "get_price"]
