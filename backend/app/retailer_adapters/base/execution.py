"""Reusable timeout, retry, rate-limit, logging, and metrics behaviour for adapter operations.

Every adapter call goes through `AdapterExecutor`, which is entirely retailer-agnostic: it only
reads the adapter's `RetailerAdapterConfig`. That means an adapter author writes just the
retailer-specific fetch-and-map logic and automatically inherits

- a hard per-attempt timeout (no unbounded blocking call can escape),
- retries with a configurable backoff curve, only for failure kinds worth retrying,
- pacing through the retailer's own rate limiter,
- one structured log record per attempt and per outcome,
- request/success/failure/latency/timeout/retry/rate-limit metrics,
- translation of any stray exception into a framework error, so nothing retailer-specific
  reaches the core domain.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.observability.correlation import get_correlation_id
from app.observability.logging import get_logger
from app.retailer_adapters.base.config import AdapterOperation, RetailerAdapterConfig
from app.retailer_adapters.base.errors import (
    AdapterTimeoutError,
    RetailerAdapterError,
    UnexpectedAdapterFailureError,
)
from app.retailer_adapters.base.metrics import AdapterMetricsRecorder
from app.retailer_adapters.base.rate_limit import RateLimiter, build_rate_limiter

T = TypeVar("T")

logger = get_logger(__name__)


class AdapterExecutor:
    """Runs one adapter operation under its configured timeout, retry, and rate-limit policy."""

    def __init__(
        self,
        config: RetailerAdapterConfig,
        *,
        rate_limiter: RateLimiter | None = None,
        metrics: AdapterMetricsRecorder | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._config = config
        self._rate_limiter = rate_limiter or build_rate_limiter(config.rate_limit)
        self._metrics = metrics or AdapterMetricsRecorder(config.retailer_id)
        self._sleep = sleep
        self._monotonic = monotonic
        self._jitter = jitter

    @property
    def config(self) -> RetailerAdapterConfig:
        return self._config

    @property
    def metrics(self) -> AdapterMetricsRecorder:
        return self._metrics

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._rate_limiter

    async def execute(
        self,
        operation: AdapterOperation,
        call: Callable[[], Awaitable[T]],
        *,
        correlation_id: str | None = None,
    ) -> T:
        """Execute `call`, applying the full policy. Raises only `RetailerAdapterError`."""
        policy = self._config.retry_policy
        timeout_seconds = self._config.attempt_timeout_seconds
        context = {
            "retailer_id": self._config.retailer_id,
            "operation": operation.value,
            "correlation_id": correlation_id or get_correlation_id(),
        }
        self._metrics.request_started(operation)
        started_at = self._monotonic()

        for attempt in range(1, policy.max_attempts + 1):
            attempt_started_at = self._monotonic()
            try:
                result = await self._run_attempt(operation, call, timeout_seconds)
            except RetailerAdapterError as error:
                attempt_ms = self._elapsed_ms(attempt_started_at)
                should_retry = policy.is_retryable(error) and attempt < policy.max_attempts
                if should_retry:
                    delay = policy.delay_for(error, attempt=attempt, jitter_fraction=self._jitter())
                    self._metrics.retry_scheduled(operation, error_code=error.code)
                    logger.warning(
                        "retailer_adapter.attempt_failed_retrying",
                        extra={
                            **context,
                            **error.log_fields(),
                            "attempt": attempt,
                            "max_attempts": policy.max_attempts,
                            "duration_ms": attempt_ms,
                            "retry_delay_seconds": delay,
                            "success": False,
                        },
                    )
                    await self._sleep(delay)
                    continue
                total_ms = self._elapsed_ms(started_at)
                self._metrics.request_failed(operation, duration_ms=total_ms, error_code=error.code)
                logger.error(
                    "retailer_adapter.operation_failed",
                    extra={
                        **context,
                        **error.log_fields(),
                        "attempt": attempt,
                        "max_attempts": policy.max_attempts,
                        "duration_ms": total_ms,
                        "retryable": policy.is_retryable(error),
                        "success": False,
                    },
                )
                raise
            else:
                total_ms = self._elapsed_ms(started_at)
                self._metrics.request_succeeded(operation, duration_ms=total_ms)
                logger.info(
                    "retailer_adapter.operation_succeeded",
                    extra={
                        **context,
                        "attempt": attempt,
                        "duration_ms": total_ms,
                        "success": True,
                    },
                )
                return result

        # Unreachable: the loop either returns or raises on its final attempt. Kept explicit so a
        # future change to the loop bounds fails loudly instead of returning `None`.
        raise AssertionError("Retry loop exited without a result.")

    async def _run_attempt(
        self,
        operation: AdapterOperation,
        call: Callable[[], Awaitable[T]],
        timeout_seconds: float,
    ) -> T:
        """One attempt: pace, run under the timeout, and normalize any failure."""
        waited = await self._rate_limiter.acquire()
        if waited > 0:
            self._metrics.rate_limit_waited(operation, waited_seconds=waited)
            logger.info(
                "retailer_adapter.rate_limit_wait",
                extra={
                    "retailer_id": self._config.retailer_id,
                    "operation": operation.value,
                    "correlation_id": get_correlation_id(),
                    "waited_seconds": waited,
                },
            )
        try:
            return await asyncio.wait_for(call(), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise AdapterTimeoutError(
                f"Operation exceeded its {timeout_seconds}s timeout.",
                retailer_id=self._config.retailer_id,
                operation=operation.value,
            ) from exc
        except RetailerAdapterError:
            raise
        except Exception as exc:
            # The adapter leaked a retailer-specific exception. Log the detail (redacted) and
            # replace it with a framework error so the core domain never sees vendor internals.
            logger.exception(
                "retailer_adapter.untranslated_exception",
                extra={
                    "retailer_id": self._config.retailer_id,
                    "operation": operation.value,
                    "correlation_id": get_correlation_id(),
                    "exception_type": type(exc).__name__,
                    "success": False,
                },
            )
            raise UnexpectedAdapterFailureError.from_exception(
                exc, retailer_id=self._config.retailer_id, operation=operation.value
            ) from exc
        finally:
            self._rate_limiter.release()

    def _elapsed_ms(self, since: float) -> float:
        return (self._monotonic() - since) * 1000.0
