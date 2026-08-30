"""Metrics extension points.

Phase 3 deliberately does **not** introduce a monitoring platform. It defines the seam that
instrumented code writes to (`MetricsSink`) plus two trivial implementations: a no-op default
and an in-memory one for tests and local inspection. Exporting to Azure Monitor / Application
Insights is a Phase 11 concern and is added by implementing this protocol — no instrumented
call site has to change.
"""

from collections import defaultdict
from collections.abc import Mapping
from typing import Protocol, runtime_checkable

#: Normalized tag set used as a dictionary key by `InMemoryMetricsSink`.
MetricKey = tuple[str, tuple[tuple[str, str], ...]]


def _key(name: str, tags: Mapping[str, str] | None) -> MetricKey:
    return name, tuple(sorted((str(k), str(v)) for k, v in (tags or {}).items()))


@runtime_checkable
class MetricsSink(Protocol):
    """Where instrumented code sends counters, distributions, and gauges."""

    def increment(
        self, name: str, *, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        """Add `value` to the counter `name`."""

    def observe(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        """Record one sample of a distribution (e.g. a latency measurement)."""

    def set_gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        """Record the current value of a gauge (e.g. a health status code)."""


class NullMetricsSink:
    """Default sink: accepts everything, records nothing.

    Lets instrumentation be unconditional — call sites never need `if metrics is not None`.
    """

    def increment(
        self, name: str, *, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        return None

    def observe(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        return None

    def set_gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        return None


class InMemoryMetricsSink:
    """Keeps metrics in process memory. Intended for tests and local debugging only."""

    def __init__(self) -> None:
        self.counters: dict[MetricKey, int] = defaultdict(int)
        self.observations: dict[MetricKey, list[float]] = defaultdict(list)
        self.gauges: dict[MetricKey, float] = {}

    def increment(
        self, name: str, *, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        self.counters[_key(name, tags)] += value

    def observe(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        self.observations[_key(name, tags)].append(value)

    def set_gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        self.gauges[_key(name, tags)] = value

    def counter_value(self, name: str, **tags: str) -> int:
        """Total for one counter/tag combination (0 when it was never incremented)."""
        return self.counters.get(_key(name, tags), 0)

    def observed_values(self, name: str, **tags: str) -> list[float]:
        """All samples recorded for one distribution/tag combination."""
        return list(self.observations.get(_key(name, tags), []))

    def gauge_value(self, name: str, **tags: str) -> float | None:
        """Latest value of one gauge/tag combination, or `None` if never set."""
        return self.gauges.get(_key(name, tags))

    def total_for_name(self, name: str) -> int:
        """Total of a counter across every tag combination."""
        return sum(value for (metric, _), value in self.counters.items() if metric == name)

    def reset(self) -> None:
        self.counters.clear()
        self.observations.clear()
        self.gauges.clear()


class CompositeMetricsSink:
    """Fan-out sink. Each child is isolated so one exporter cannot break the request path."""

    def __init__(self, sinks: list[MetricsSink] | None = None) -> None:
        self._sinks: list[MetricsSink] = list(sinks or [])

    def add(self, sink: MetricsSink) -> None:
        self._sinks.append(sink)

    def increment(
        self, name: str, *, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        for sink in self._sinks:
            try:
                sink.increment(name, value=value, tags=tags)
            except Exception:
                continue

    def observe(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        for sink in self._sinks:
            try:
                sink.observe(name, value, tags=tags)
            except Exception:
                continue

    def set_gauge(self, name: str, value: float, *, tags: Mapping[str, str] | None = None) -> None:
        for sink in self._sinks:
            try:
                sink.set_gauge(name, value, tags=tags)
            except Exception:
                continue
