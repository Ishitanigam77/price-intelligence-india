"""Shared builders for adapter-framework unit tests.

Everything here is fictional test data: invented retailer IDs, SKUs, and prices. No test talks
to a network or a real retailer.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.enums import (
    AvailabilityStatus,
    ConfidenceLevel,
    ProductIdentifierType,
    SourceType,
)
from app.domain.validation import slugify
from app.retailer_adapters.base.config import (
    AdapterOperation,
    RateLimitConfig,
    RetailerAdapterConfig,
    RetryPolicy,
)
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import (
    AvailabilityObservation,
    NormalizedProduct,
    PriceObservation,
    ProductIdentifierValue,
    ProductSearchQuery,
    ProductSearchResult,
    RetailerProduct,
    SellerInformation,
)
from app.retailer_adapters.base.rate_limit import NullRateLimiter

FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

ALL_OPERATIONS: frozenset[AdapterOperation] = frozenset(
    {
        AdapterOperation.SEARCH_PRODUCTS,
        AdapterOperation.GET_PRODUCT,
        AdapterOperation.GET_PRICE,
        AdapterOperation.GET_AVAILABILITY,
        AdapterOperation.GET_PRODUCT_IDENTIFIERS,
    }
)


class FakeClock:
    """Monotonic clock whose `sleep` advances time instantly — no real waiting in tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


def make_config(**overrides: Any) -> RetailerAdapterConfig:
    """Build a `RetailerAdapterConfig` with conservative, fully explicit test defaults."""
    values: dict[str, Any] = {
        "retailer_id": "scripted-store",
        "retailer_name": "Scripted Store",
        "source_type": SourceType.OTHER_PERMITTED,
        "supported_categories": ("mobiles",),
        "supported_operations": ALL_OPERATIONS,
        "enabled": True,
        "timeout_seconds": 1.0,
        "retry_policy": RetryPolicy(max_attempts=1, initial_backoff_seconds=0.0, jitter_ratio=0.0),
        "rate_limit": RateLimitConfig(
            max_requests_per_minute=6000, burst_size=100, max_concurrent_requests=8
        ),
        "options": {"mode": "scripted"},
    }
    values.update(overrides)
    return RetailerAdapterConfig(**values)


def make_seller(*, name: str = "Scripted Seller", first_party: bool = True) -> SellerInformation:
    return SellerInformation(name=name, retailer_seller_id="seller-1", is_first_party=first_party)


def make_price_observation(
    *,
    retailer_id: str = "scripted-store",
    retailer_sku: str = "SKU-1",
    displayed_price: str = "999.00",
    mrp: str | None = "1299.00",
    availability: AvailabilityStatus = AvailabilityStatus.IN_STOCK,
    source_type: SourceType = SourceType.OTHER_PERMITTED,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    observed_at: datetime = FIXED_NOW,
    **kwargs: Any,
) -> PriceObservation:
    return PriceObservation(
        retailer_id=retailer_id,
        retailer_sku=retailer_sku,
        observed_at=observed_at,
        currency="INR",
        displayed_price=Decimal(displayed_price),
        mrp=None if mrp is None else Decimal(mrp),
        availability=availability,
        source_type=source_type,
        source_url=f"https://scripted-store.example.test/p/{retailer_sku}",
        confidence=confidence,
        seller=kwargs.pop("seller", make_seller()),
        **kwargs,
    )


def make_availability_observation(
    *,
    retailer_id: str = "scripted-store",
    retailer_sku: str = "SKU-1",
    status: AvailabilityStatus = AvailabilityStatus.IN_STOCK,
    observed_at: datetime = FIXED_NOW,
    **kwargs: Any,
) -> AvailabilityObservation:
    return AvailabilityObservation(
        retailer_id=retailer_id,
        retailer_sku=retailer_sku,
        status=status,
        observed_at=observed_at,
        source_type=kwargs.pop("source_type", SourceType.OTHER_PERMITTED),
        source_url=kwargs.pop(
            "source_url", f"https://scripted-store.example.test/p/{retailer_sku}"
        ),
        confidence=kwargs.pop("confidence", ConfidenceLevel.HIGH),
        seller=kwargs.pop("seller", make_seller()),
        **kwargs,
    )


def make_retailer_product(
    *,
    retailer_id: str = "scripted-store",
    retailer_sku: str = "SKU-1",
    title: str = "Fictional Scripted Phone",
    retrieved_at: datetime = FIXED_NOW,
    **kwargs: Any,
) -> RetailerProduct:
    price = kwargs.pop(
        "price", make_price_observation(retailer_id=retailer_id, retailer_sku=retailer_sku)
    )
    return RetailerProduct(
        retailer_id=retailer_id,
        retailer_sku=retailer_sku,
        title=title,
        url=kwargs.pop("url", f"https://scripted-store.example.test/p/{retailer_sku}"),
        brand_name=kwargs.pop("brand_name", "Fictional Scripted Brand"),
        category_path=kwargs.pop("category_path", ("Electronics", "Mobiles")),
        attributes=kwargs.pop("attributes", {"Colour": "Black", "Storage": "128 GB"}),
        identifiers=kwargs.pop(
            "identifiers",
            (
                ProductIdentifierValue(
                    identifier_type=ProductIdentifierType.GTIN, value="0000000000999"
                ),
            ),
        ),
        seller=kwargs.pop("seller", make_seller()),
        price=price,
        availability=kwargs.pop(
            "availability",
            make_availability_observation(retailer_id=retailer_id, retailer_sku=retailer_sku),
        ),
        source_type=kwargs.pop("source_type", SourceType.OTHER_PERMITTED),
        retrieved_at=retrieved_at,
        **kwargs,
    )


_UNSCRIPTED = object()


def _next_scripted_action(script: dict[str, Any], operation: str) -> Any:
    """Pop the next action for `operation`, repeating a non-list value forever."""
    action = script.get(operation, script.get("default", _UNSCRIPTED))
    if action is _UNSCRIPTED:
        return None
    if isinstance(action, list):
        if not action:
            raise AssertionError(f"Script exhausted for operation {operation!r}.")
        return action.pop(0)
    return action


async def _apply_action(action: Any, *args: Any) -> Any:
    if isinstance(action, BaseException):
        raise action
    if inspect.iscoroutinefunction(action):
        return await action(*args)
    if callable(action):
        result = action(*args)
        if inspect.isawaitable(result):
            return await result
        return result
    return action


class ScriptedAdapter(RetailerAdapter):
    """Test double that plays back a per-operation script of return values / errors / callables.

    Used to exercise timeout, retry, error translation, and contract behaviour without involving
    the mock retailers' fixtures.
    """

    def __init__(
        self,
        config: RetailerAdapterConfig | None = None,
        *,
        script: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.script: dict[str, Any] = dict(script or {})
        self.calls: list[str] = []
        kwargs.setdefault("rate_limiter", NullRateLimiter())
        kwargs.setdefault("clock", lambda: FIXED_NOW)
        super().__init__(config or make_config(), **kwargs)

    async def _run(self, operation: str, *args: Any) -> Any:
        self.calls.append(operation)
        return await _apply_action(_next_scripted_action(self.script, operation), *args)

    async def _search_products(self, query: ProductSearchQuery) -> ProductSearchResult:
        result = await self._run("search_products", query)
        if isinstance(result, ProductSearchResult):
            return result
        products = result if isinstance(result, Sequence) else (make_retailer_product(),)
        return ProductSearchResult(
            retailer_id=self.retailer_id,
            query=query,
            products=tuple(products),
            retrieved_at=self._now(),
        )

    async def _get_product(self, retailer_sku: str) -> RetailerProduct:
        result = await self._run("get_product", retailer_sku)
        if isinstance(result, RetailerProduct):
            return result
        return make_retailer_product(retailer_id=self.retailer_id, retailer_sku=retailer_sku)

    async def _get_price(self, retailer_sku: str) -> PriceObservation:
        result = await self._run("get_price", retailer_sku)
        if isinstance(result, PriceObservation):
            return result
        return make_price_observation(retailer_id=self.retailer_id, retailer_sku=retailer_sku)

    async def _get_availability(self, retailer_sku: str) -> AvailabilityObservation:
        result = await self._run("get_availability", retailer_sku)
        if isinstance(result, AvailabilityObservation):
            return result
        return make_availability_observation(
            retailer_id=self.retailer_id, retailer_sku=retailer_sku
        )

    async def _get_product_identifiers(
        self, retailer_sku: str
    ) -> tuple[ProductIdentifierValue, ...]:
        result = await self._run("get_product_identifiers", retailer_sku)
        if isinstance(result, tuple):
            return result
        return (
            ProductIdentifierValue(
                identifier_type=ProductIdentifierType.GTIN, value="0000000000999"
            ),
        )

    async def _check_health(self) -> str | None:
        if "health_check" not in self.script and "default" not in self.script:
            self.calls.append("health_check")
            return "scripted adapter healthy"
        result = await self._run("health_check")
        return result if isinstance(result, str) or result is None else "ok"

    def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
        return NormalizedProduct(
            retailer_id=product.retailer_id,
            retailer_sku=product.retailer_sku,
            normalized_title=" ".join(product.title.split()),
            brand_name=product.brand_name,
            brand_slug=slugify(product.brand_name) if product.brand_name else None,
            category_slug=slugify(product.category_path[-1]) if product.category_path else None,
            variant_attributes=dict(product.attributes) or {"color": "black"},
            identifiers=product.identifiers,
            source_url=product.url,
            source_type=product.source_type,
            normalized_at=self._now(),
        )


def make_scripted_adapter(
    *,
    script: Mapping[str, Any] | None = None,
    config: RetailerAdapterConfig | None = None,
    **kwargs: Any,
) -> ScriptedAdapter:
    return ScriptedAdapter(config, script=script, **kwargs)


def lowest_price(observations: Sequence[PriceObservation]) -> PriceObservation:
    """Retailer-agnostic comparison helper used to prove core logic never branches on retailer.

    Picks the observation with the lowest `displayed_price`. `retailer_id` is a label on the
    result, never a decision input — there is no `if observation.retailer_id == ...` here.
    """
    if not observations:
        raise ValueError("Cannot compare an empty set of price observations.")
    return min(observations, key=lambda observation: observation.displayed_price)
