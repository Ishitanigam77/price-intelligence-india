"""Framework-level fan-out across every registered retailer.

`RetailerFleet` is the generic consumer of the standardized models: it asks the registry which
adapters can serve an operation, runs them concurrently, and returns their standardized output
plus a per-retailer failure list. It contains no retailer names, no per-retailer branching, and
no persistence or scheduling — collectors and workers own that, in a later phase.

Two properties matter architecturally:

- A retailer failing (timeout, rate limit, outage) never fails the whole fan-out; it is reported
  as a `RetailerFailure` alongside the successful results.
- Adding a retailer requires no change here. The fleet only ever sees the adapter contract.
"""

import asyncio
from dataclasses import dataclass

from app.observability.logging import get_logger
from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import (
    AdapterErrorCode,
    RetailerAdapterError,
)
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    HealthCheckResult,
    NormalizedProduct,
    PriceObservation,
    ProductSearchQuery,
    RetailerProduct,
)
from app.retailer_adapters.base.registry import RetailerRegistry

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetailerFailure:
    """One retailer's failure during a fan-out, in retailer-agnostic terms."""

    retailer_id: str
    error_code: AdapterErrorCode
    message: str

    @classmethod
    def from_error(cls, error: RetailerAdapterError) -> "RetailerFailure":
        return cls(retailer_id=error.retailer_id, error_code=error.code, message=error.message)


@dataclass(frozen=True)
class FleetSearchOutcome:
    """Aggregated result of searching every capable retailer for one query."""

    query: ProductSearchQuery
    products: tuple[RetailerProduct, ...] = ()
    normalized_products: tuple[NormalizedProduct, ...] = ()
    failures: tuple[RetailerFailure, ...] = ()
    #: Retailers that were asked and answered (successfully or not).
    consulted_retailer_ids: tuple[str, ...] = ()

    @property
    def price_observations(self) -> tuple[PriceObservation, ...]:
        """Price observations carried by the returned listings, in result order."""
        return tuple(product.price for product in self.products if product.price is not None)

    def products_for(self, retailer_id: str) -> tuple[RetailerProduct, ...]:
        return tuple(product for product in self.products if product.retailer_id == retailer_id)


class RetailerFleet:
    """Runs adapter operations across all capable, enabled retailers."""

    def __init__(self, registry: RetailerRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> RetailerRegistry:
        return self._registry

    async def search(self, query: ProductSearchQuery) -> FleetSearchOutcome:
        """Search every enabled retailer that supports search and serves the query's category."""
        adapters = self._registry.adapters_supporting(
            AdapterOperation.SEARCH_PRODUCTS, category=query.category
        )
        if not adapters:
            logger.info(
                "retailer_fleet.no_capable_retailers",
                extra={
                    "operation": AdapterOperation.SEARCH_PRODUCTS.value,
                    "category": query.category,
                },
            )
            return FleetSearchOutcome(query=query)

        outcomes = await asyncio.gather(
            *(adapter.search_products(query) for adapter in adapters),
            return_exceptions=True,
        )

        products: list[RetailerProduct] = []
        normalized: list[NormalizedProduct] = []
        failures: list[RetailerFailure] = []
        for adapter, outcome in zip(adapters, outcomes, strict=True):
            if isinstance(outcome, RetailerAdapterError):
                failures.append(RetailerFailure.from_error(outcome))
                continue
            if isinstance(outcome, BaseException):
                raise outcome
            for product in outcome.products:
                products.append(product)
                normalized_product = self._normalize(adapter, product)
                if normalized_product is None:
                    failures.append(
                        RetailerFailure(
                            retailer_id=adapter.retailer_id,
                            error_code=AdapterErrorCode.INVALID_RETAILER_RESPONSE,
                            message="Adapter could not normalize one of its own listings.",
                        )
                    )
                    continue
                normalized.append(normalized_product)

        return FleetSearchOutcome(
            query=query,
            products=tuple(products),
            normalized_products=tuple(normalized),
            failures=tuple(failures),
            consulted_retailer_ids=tuple(adapter.retailer_id for adapter in adapters),
        )

    async def health_report(self, *, include_disabled: bool = True) -> dict[str, HealthCheckResult]:
        """Health-check the whole fleet. Delegates to the registry, which caches the results."""
        return await self._registry.health_check_all(include_disabled=include_disabled)

    def capable_retailer_ids(
        self, operation: AdapterOperation, *, category: str | None = None
    ) -> tuple[str, ...]:
        """Which enabled retailers can currently serve `operation`."""
        return tuple(
            adapter.retailer_id
            for adapter in self._registry.adapters_supporting(operation, category=category)
        )

    def _normalize(
        self, adapter: RetailerAdapter, product: RetailerProduct
    ) -> NormalizedProduct | None:
        """Normalize via the owning adapter, treating a mapping failure as that retailer's failure.

        `normalize_product` is pure and synchronous, so it is not wrapped by the executor; this
        keeps a buggy mapping in one adapter from breaking the fan-out for every other retailer.
        """
        try:
            return adapter.normalize_product(product)
        except Exception:
            logger.exception(
                "retailer_fleet.normalization_failed",
                extra={
                    "retailer_id": adapter.retailer_id,
                    "retailer_sku": product.retailer_sku,
                    "success": False,
                },
            )
            return None
