"""Process-level wiring: instantiate discovered adapters and register them.

This module is the only application-startup caller of adapter discovery. It never names a
specific retailer: it asks `discover_adapters` for the configured kinds and registers whatever
factories that returns. Product Discovery (and every other core consumer) then talks only to
the resulting `RetailerRegistry`.
"""

from collections.abc import Mapping

from app.core.config import Settings, get_settings
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink
from app.retailer_adapters.base.discovery import AdapterKind, discover_adapters
from app.retailer_adapters.base.registry import RetailerRegistry

logger = get_logger(__name__)


def adapter_kinds_from_settings(settings: Settings) -> tuple[AdapterKind, ...]:
    """Parse `Settings.retailer_adapter_kinds` into `AdapterKind` values."""
    return tuple(AdapterKind(kind) for kind in settings.retailer_adapter_kind_values)


def build_retailer_registry(
    *,
    settings: Settings | None = None,
    metrics_sink: MetricsSink | None = None,
    env: Mapping[str, str] | None = None,
) -> RetailerRegistry:
    """Discover adapters of the configured kinds and register them.

    Adding a retailer is a matter of shipping an adapter package that follows the discovery
    convention — this function does not change.
    """
    resolved = settings if settings is not None else get_settings()
    kinds = adapter_kinds_from_settings(resolved)
    registry = RetailerRegistry()
    discovered = discover_adapters(kinds=kinds)
    for entry in discovered:
        adapter = entry.create(settings=resolved, env=env, metrics_sink=metrics_sink)
        registry.register(adapter)
    logger.info(
        "retailer_registry.wired",
        extra={
            "kinds": [kind.value for kind in kinds],
            "registered": list(registry.retailer_ids()),
            "enabled": list(registry.retailer_ids(enabled_only=True)),
        },
    )
    return registry
