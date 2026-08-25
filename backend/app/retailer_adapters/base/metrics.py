"""Metric names and the recorder adapters emit through.

Phase 3 only wires the *seam*: every adapter operation already reports request/success/failure
counts, latency, timeouts, retries, rate-limit waits, and health status to a `MetricsSink`. The
default sink discards them. Making them visible in Azure Monitor is a Phase 11 task that
implements `MetricsSink` — no call site here changes.
"""

from app.observability.metrics import MetricsSink, NullMetricsSink
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import AdapterErrorCode
from app.retailer_adapters.base.models import HealthStatus

ADAPTER_REQUESTS = "retailer_adapter.requests"
ADAPTER_SUCCESSES = "retailer_adapter.successes"
ADAPTER_FAILURES = "retailer_adapter.failures"
ADAPTER_LATENCY_MS = "retailer_adapter.latency_ms"
ADAPTER_TIMEOUTS = "retailer_adapter.timeouts"
ADAPTER_RETRIES = "retailer_adapter.retries"
ADAPTER_RATE_LIMIT_WAITS = "retailer_adapter.rate_limit_waits"
ADAPTER_RATE_LIMIT_WAIT_SECONDS = "retailer_adapter.rate_limit_wait_seconds"
ADAPTER_HEALTH_STATUS = "retailer_adapter.health_status"

#: Numeric encoding of health status so it can be recorded as a gauge.
HEALTH_STATUS_GAUGE_VALUES: dict[HealthStatus, float] = {
    HealthStatus.HEALTHY: 1.0,
    HealthStatus.DEGRADED: 0.5,
    HealthStatus.UNHEALTHY: 0.0,
    HealthStatus.UNKNOWN: -1.0,
}


class AdapterMetricsRecorder:
    """Records adapter metrics, tagging every sample with retailer and operation.

    A thin wrapper so instrumented code never has to assemble tag dictionaries by hand and tag
    naming stays consistent across operations.
    """

    def __init__(self, retailer_id: str, sink: MetricsSink | None = None) -> None:
        self._retailer_id = retailer_id
        self._sink: MetricsSink = sink if sink is not None else NullMetricsSink()

    @property
    def sink(self) -> MetricsSink:
        return self._sink

    def _tags(self, operation: AdapterOperation) -> dict[str, str]:
        return {"retailer_id": self._retailer_id, "operation": operation.value}

    def request_started(self, operation: AdapterOperation) -> None:
        self._sink.increment(ADAPTER_REQUESTS, tags=self._tags(operation))

    def request_succeeded(self, operation: AdapterOperation, *, duration_ms: float) -> None:
        self._sink.increment(ADAPTER_SUCCESSES, tags=self._tags(operation))
        self._sink.observe(ADAPTER_LATENCY_MS, duration_ms, tags=self._tags(operation))

    def request_failed(
        self, operation: AdapterOperation, *, duration_ms: float, error_code: AdapterErrorCode
    ) -> None:
        tags = self._tags(operation) | {"error_type": error_code.value}
        self._sink.increment(ADAPTER_FAILURES, tags=tags)
        self._sink.observe(ADAPTER_LATENCY_MS, duration_ms, tags=self._tags(operation))
        if error_code is AdapterErrorCode.TIMEOUT:
            self._sink.increment(ADAPTER_TIMEOUTS, tags=self._tags(operation))

    def retry_scheduled(self, operation: AdapterOperation, *, error_code: AdapterErrorCode) -> None:
        self._sink.increment(
            ADAPTER_RETRIES, tags=self._tags(operation) | {"error_type": error_code.value}
        )

    def rate_limit_waited(self, operation: AdapterOperation, *, waited_seconds: float) -> None:
        self._sink.increment(ADAPTER_RATE_LIMIT_WAITS, tags=self._tags(operation))
        self._sink.observe(
            ADAPTER_RATE_LIMIT_WAIT_SECONDS, waited_seconds, tags=self._tags(operation)
        )

    def health_reported(self, status: HealthStatus) -> None:
        self._sink.set_gauge(
            ADAPTER_HEALTH_STATUS,
            HEALTH_STATUS_GAUGE_VALUES[status],
            tags={"retailer_id": self._retailer_id},
        )
