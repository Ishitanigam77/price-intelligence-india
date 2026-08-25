"""The retailer registry: the only place that knows *which* retailers exist.

The registry is a keyed collection of adapters plus their runtime state. It is deliberately
dumb: it holds no retailer-specific business logic, no per-retailer branching, and no knowledge
of what any adapter does internally. Adding retailer #100 means registering one more adapter —
nothing in this module changes.

Each adapter carries its own configuration, so enablement, timeouts, retry policy, and rate
limits are per-retailer and independent; the registry never merges or overrides them.
"""

import asyncio
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.observability.logging import get_logger
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import (
    AdapterDisabledError,
    RetailerAlreadyRegisteredError,
    RetailerNotRegisteredError,
)
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import HealthCheckResult, HealthStatus

logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class RetailerRegistration:
    """An adapter plus the registry's bookkeeping for it."""

    adapter: RetailerAdapter
    registered_at: datetime
    last_health: HealthCheckResult | None = None

    @property
    def retailer_id(self) -> str:
        return self.adapter.retailer_id

    @property
    def enabled(self) -> bool:
        return self.adapter.enabled

    @property
    def health_status(self) -> HealthStatus:
        """Last observed health, or `UNKNOWN` when never checked."""
        return self.last_health.status if self.last_health else HealthStatus.UNKNOWN


class RetailerRegistry:
    """Registers, looks up, enables/disables, and health-checks retailer adapters."""

    def __init__(self, *, clock: Any = _utc_now) -> None:
        self._registrations: dict[str, RetailerRegistration] = {}
        self._clock = clock

    # ------------------------------------------------------------------------- registration

    def register(self, adapter: RetailerAdapter, *, replace: bool = False) -> RetailerRegistration:
        """Register `adapter` under its own retailer ID.

        Raises `RetailerAlreadyRegisteredError` unless `replace=True`, so two adapters can never
        silently claim the same retailer.
        """
        if not isinstance(adapter, RetailerAdapter):
            raise TypeError(
                f"{type(adapter).__name__} does not implement the RetailerAdapter contract."
            )
        retailer_id = adapter.retailer_id
        if retailer_id in self._registrations and not replace:
            raise RetailerAlreadyRegisteredError(retailer_id)
        registration = RetailerRegistration(adapter=adapter, registered_at=self._clock())
        self._registrations[retailer_id] = registration
        logger.info(
            "retailer_registry.registered",
            extra={
                "retailer_id": retailer_id,
                "adapter": type(adapter).__name__,
                "enabled": adapter.enabled,
                "operations": sorted(operation.value for operation in adapter.supported_operations),
            },
        )
        return registration

    def register_all(
        self, adapters: Iterable[RetailerAdapter], *, replace: bool = False
    ) -> tuple[RetailerRegistration, ...]:
        """Register several adapters in one call."""
        return tuple(self.register(adapter, replace=replace) for adapter in adapters)

    def unregister(self, retailer_id: str) -> None:
        """Remove a retailer's adapter. Raises `RetailerNotRegisteredError` when absent."""
        if retailer_id not in self._registrations:
            raise RetailerNotRegisteredError(retailer_id)
        del self._registrations[retailer_id]
        logger.info("retailer_registry.unregistered", extra={"retailer_id": retailer_id})

    # ------------------------------------------------------------------------------ lookup

    def get(self, retailer_id: str) -> RetailerAdapter:
        """Return the adapter for `retailer_id`, whether enabled or not."""
        return self.registration(retailer_id).adapter

    def get_enabled(self, retailer_id: str) -> RetailerAdapter:
        """Return the adapter for `retailer_id`, refusing a disabled one."""
        adapter = self.get(retailer_id)
        if not adapter.enabled:
            raise AdapterDisabledError("Adapter is disabled.", retailer_id=retailer_id)
        return adapter

    def registration(self, retailer_id: str) -> RetailerRegistration:
        """Return the full registration record for `retailer_id`."""
        try:
            return self._registrations[retailer_id]
        except KeyError as exc:
            raise RetailerNotRegisteredError(retailer_id) from exc

    def retailer_ids(self, *, enabled_only: bool = False) -> tuple[str, ...]:
        """Registered retailer IDs, in registration order."""
        return tuple(
            registration.retailer_id
            for registration in self._registrations.values()
            if registration.enabled or not enabled_only
        )

    def adapters(self, *, enabled_only: bool = False) -> tuple[RetailerAdapter, ...]:
        """Registered adapters, in registration order."""
        return tuple(
            registration.adapter
            for registration in self._registrations.values()
            if registration.enabled or not enabled_only
        )

    def registrations(self) -> tuple[RetailerRegistration, ...]:
        return tuple(self._registrations.values())

    def adapters_supporting(
        self,
        operation: AdapterOperation,
        *,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> tuple[RetailerAdapter, ...]:
        """Adapters that can serve `operation` (optionally within `category`).

        This is how callers fan out without knowing any retailer: they ask for capability, not
        for a named retailer.
        """
        return tuple(
            adapter
            for adapter in self.adapters(enabled_only=enabled_only)
            if adapter.supports(operation)
            and (category is None or adapter.serves_category(category))
        )

    def describe(self) -> tuple[dict[str, Any], ...]:
        """A serializable summary of every registration, for diagnostics and future health APIs."""
        return tuple(
            {
                "retailer_id": registration.retailer_id,
                "retailer_name": registration.adapter.retailer_name,
                "enabled": registration.enabled,
                "source_type": registration.adapter.config.source_type.value,
                "supported_operations": sorted(
                    operation.value for operation in registration.adapter.supported_operations
                ),
                "supported_categories": list(registration.adapter.supported_categories),
                "timeout_seconds": registration.adapter.config.timeout_seconds,
                "max_attempts": registration.adapter.config.retry_policy.max_attempts,
                "max_requests_per_minute": (
                    registration.adapter.config.rate_limit.max_requests_per_minute
                ),
                "health_status": registration.health_status.value,
                "last_checked_at": (
                    registration.last_health.checked_at.isoformat()
                    if registration.last_health
                    else None
                ),
            }
            for registration in self._registrations.values()
        )

    # -------------------------------------------------------------------------- enablement

    def enable(self, retailer_id: str) -> None:
        """Enable a registered adapter."""
        adapter = self.get(retailer_id)
        adapter.enable()
        logger.info("retailer_registry.enabled", extra={"retailer_id": retailer_id})

    def disable(self, retailer_id: str) -> None:
        """Disable a registered adapter without unregistering it."""
        adapter = self.get(retailer_id)
        adapter.disable()
        logger.info("retailer_registry.disabled", extra={"retailer_id": retailer_id})

    def is_enabled(self, retailer_id: str) -> bool:
        return self.get(retailer_id).enabled

    # ------------------------------------------------------------------------ health checks

    async def health_check(self, retailer_id: str) -> HealthCheckResult:
        """Health-check one adapter and remember the result."""
        registration = self.registration(retailer_id)
        result = await registration.adapter.health_check()
        registration.last_health = result
        return result

    async def health_check_all(
        self, *, include_disabled: bool = True
    ) -> dict[str, HealthCheckResult]:
        """Health-check every registration concurrently, keyed by retailer ID.

        Adapter health checks never raise, so one unreachable retailer cannot hide the state of
        the others.
        """
        registrations = [
            registration
            for registration in self._registrations.values()
            if include_disabled or registration.enabled
        ]
        results = await asyncio.gather(
            *(registration.adapter.health_check() for registration in registrations)
        )
        for registration, result in zip(registrations, results, strict=True):
            registration.last_health = result
        return {result.retailer_id: result for result in results}

    def last_health(self, retailer_id: str) -> HealthCheckResult | None:
        """Most recent health result for `retailer_id`, or `None` if never checked."""
        return self.registration(retailer_id).last_health

    # ------------------------------------------------------------------------ collection api

    def __contains__(self, retailer_id: object) -> bool:
        return retailer_id in self._registrations

    def __len__(self) -> int:
        return len(self._registrations)

    def __iter__(self) -> Iterator[RetailerAdapter]:
        return iter(self.adapters())

    def __repr__(self) -> str:
        return f"RetailerRegistry(retailers={list(self._registrations)!r})"
