"""Adapter discovery by package convention.

An adapter package under `app/retailer_adapters/` is discoverable when its `__init__.py` exposes

- `RETAILER_ID: str` — the retailer's slug,
- `ADAPTER_KIND: AdapterKind` — whether it is a real integration or a mock,
- `create_adapter(...) -> RetailerAdapter` — a factory.

Discovery deliberately returns *factories* rather than instances: the caller decides what to
instantiate, with which metrics sink and settings, and what to register. It also filters by kind
and defaults to real integrations only, so the mock adapters used for framework tests can never
be picked up by a production wiring path by accident.
"""

import importlib
import pkgutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import ModuleType
from typing import Any

from app.observability.logging import get_logger
from app.retailer_adapters.base.errors import AdapterContractError
from app.retailer_adapters.base.interface import RetailerAdapter

logger = get_logger(__name__)

RETAILER_ID_ATTRIBUTE = "RETAILER_ID"
ADAPTER_KIND_ATTRIBUTE = "ADAPTER_KIND"
ADAPTER_FACTORY_ATTRIBUTE = "create_adapter"

#: Never scanned for adapters: this is the framework itself.
_EXCLUDED_PACKAGES = frozenset({"base"})


class AdapterKind(StrEnum):
    """Whether a discovered adapter talks to a real retailer or is a test double."""

    INTEGRATION = "integration"
    MOCK = "mock"


@dataclass(frozen=True)
class DiscoveredAdapter:
    """A discoverable adapter package: what it is and how to build it."""

    retailer_id: str
    kind: AdapterKind
    module_name: str
    factory: Callable[..., RetailerAdapter]

    def create(self, **kwargs: Any) -> RetailerAdapter:
        """Instantiate the adapter, passing `kwargs` through to its factory."""
        adapter = self.factory(**kwargs)
        if adapter.retailer_id != self.retailer_id:
            raise AdapterContractError(
                f"{self.module_name} declares RETAILER_ID={self.retailer_id!r} but its factory "
                f"produced an adapter for {adapter.retailer_id!r}."
            )
        return adapter


def discover_adapters(
    package: ModuleType | None = None,
    *,
    kinds: Iterable[AdapterKind] = (AdapterKind.INTEGRATION,),
) -> tuple[DiscoveredAdapter, ...]:
    """Find adapter packages under `package` (defaults to `app.retailer_adapters`).

    Packages that expose no factory are skipped silently (they may be scaffolding); a package
    that exposes a factory but omits `RETAILER_ID`/`ADAPTER_KIND` is a contract violation and
    raises, because a half-declared adapter is a wiring bug rather than something to ignore.
    """
    target = package if package is not None else importlib.import_module("app.retailer_adapters")
    wanted = frozenset(kinds)
    discovered: list[DiscoveredAdapter] = []

    for module_info in sorted(pkgutil.iter_modules(target.__path__), key=lambda info: info.name):
        if not module_info.ispkg or module_info.name.startswith("_"):
            continue
        if module_info.name in _EXCLUDED_PACKAGES:
            continue
        module_name = f"{target.__name__}.{module_info.name}"
        module = importlib.import_module(module_name)
        factory = getattr(module, ADAPTER_FACTORY_ATTRIBUTE, None)
        if factory is None:
            logger.debug(
                "retailer_adapter_discovery.skipped_package",
                extra={"module": module_name, "reason": "no create_adapter factory"},
            )
            continue
        if not callable(factory):
            raise AdapterContractError(
                f"{module_name}.{ADAPTER_FACTORY_ATTRIBUTE} is not callable."
            )

        retailer_id = getattr(module, RETAILER_ID_ATTRIBUTE, None)
        kind = getattr(module, ADAPTER_KIND_ATTRIBUTE, None)
        missing = [
            name
            for name, value in (
                (RETAILER_ID_ATTRIBUTE, retailer_id),
                (ADAPTER_KIND_ATTRIBUTE, kind),
            )
            if value is None
        ]
        if missing:
            raise AdapterContractError(
                f"{module_name} exposes {ADAPTER_FACTORY_ATTRIBUTE} but is missing "
                f"{', '.join(missing)}."
            )

        resolved_kind = AdapterKind(kind)
        if resolved_kind not in wanted:
            logger.debug(
                "retailer_adapter_discovery.filtered_out",
                extra={
                    "module": module_name,
                    "retailer_id": retailer_id,
                    "kind": resolved_kind.value,
                },
            )
            continue
        discovered.append(
            DiscoveredAdapter(
                retailer_id=str(retailer_id),
                kind=resolved_kind,
                module_name=module_name,
                factory=factory,
            )
        )

    logger.info(
        "retailer_adapter_discovery.completed",
        extra={
            "package": target.__name__,
            "kinds": sorted(kind.value for kind in wanted),
            "discovered": [entry.retailer_id for entry in discovered],
        },
    )
    return tuple(discovered)
