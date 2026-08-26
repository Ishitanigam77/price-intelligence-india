"""Product discovery: search enabled retailers, normalize, persist, and return results.

This service is retailer-agnostic. It asks a `RetailerRegistry` (via `RetailerFleet`) which
adapters can search, fans out through the existing adapter contract, and persists whatever
standardized listings come back. It never imports a specific retailer package and never
branches on a retailer identity.

Timeouts, retries, rate limits, adapter-level errors, structured logging, and adapter metrics
are owned by the Phase 3 executor — this module does not reimplement them. Individual retailer
failures are isolated by `RetailerFleet`; successful retailers still contribute results.

Persistence uses existing Phase 1 uniqueness only:

- a `ProductIdentifier` (GTIN/EAN/UPC/MPN/...) that already exists is attached to that variant;
- a `(retailer, retailer_sku)` listing that already exists is updated in place;
- otherwise a new Product / ProductVariant / RetailerProduct is created.

No semantic matching, embeddings, or cross-retailer deduplication beyond those constraints.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import (
    Brand,
    Category,
    PriceSnapshot,
    Product,
    ProductIdentifier,
    ProductVariant,
    Retailer,
    RetailerProduct,
    Seller,
)
from app.domain.exceptions import InvalidSlugError
from app.domain.validation import slugify
from app.observability.correlation import correlation_scope, get_correlation_id
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.repositories.brand_repository import BrandRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_identifier_repository import ProductIdentifierRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.repositories.seller_repository import SellerRepository
from app.retailer_adapters.base.fleet import FleetSearchOutcome, RetailerFailure, RetailerFleet
from app.retailer_adapters.base.models import (
    NormalizedProduct,
    PriceObservation,
    ProductIdentifierValue,
    ProductSearchQuery,
    SellerInformation,
)
from app.retailer_adapters.base.models import (
    RetailerProduct as AdapterRetailerProduct,
)
from app.retailer_adapters.base.registry import RetailerRegistry
from app.schemas.discovery import ProductSearchHit, ProductSearchPage, RetailerSearchFailure
from app.schemas.product import ProductRead, ProductVariantRead
from app.schemas.retailer import RetailerRead, SellerRead

logger = get_logger(__name__)

DISCOVERY_SEARCHES = "product_discovery.searches"
DISCOVERY_RESULTS = "product_discovery.results"
DISCOVERY_RETAILER_FAILURES = "product_discovery.retailer_failures"
DISCOVERY_PERSISTED = "product_discovery.persisted_listings"
DISCOVERY_DURATION_MS = "product_discovery.duration_ms"

#: Matches `ProductIdentifier.value` column length (`String(64)`).
_IDENTIFIER_VALUE_MAX_LENGTH = 64
_PRODUCT_NAME_MAX_LENGTH = 500
_PRODUCT_SLUG_MAX_LENGTH = 550
#: `ProductSearchQuery.limit` is capped at 100 by the adapter contract.
_ADAPTER_SEARCH_LIMIT_MAX = 100


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ProductDiscoveryService:
    """Orchestrates on-demand product discovery across enabled retailer adapters."""

    def __init__(
        self,
        session: Session,
        registry: RetailerRegistry,
        *,
        metrics_sink: MetricsSink | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._registry = registry
        self._fleet = RetailerFleet(registry)
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()
        self._monotonic = monotonic
        self._products = ProductRepository(session)
        self._variants = ProductVariantRepository(session)
        self._brands = BrandRepository(session)
        self._categories = CategoryRepository(session)
        self._retailers = RetailerRepository(session)
        self._sellers = SellerRepository(session)
        self._listings = RetailerProductRepository(session)
        self._snapshots = PriceSnapshotRepository(session)
        self._identifiers = ProductIdentifierRepository(session)

    @property
    def registry(self) -> RetailerRegistry:
        return self._registry

    @property
    def fleet(self) -> RetailerFleet:
        return self._fleet

    async def search(
        self,
        *,
        text: str,
        limit: int,
        offset: int,
        category: str | None = None,
    ) -> ProductSearchPage:
        """Search enabled retailers, persist discovered listings, and return a page of hits."""
        adapter_limit = min(max(offset + limit, 1), _ADAPTER_SEARCH_LIMIT_MAX)
        query = ProductSearchQuery(text=text, category=category, limit=adapter_limit)
        started_at = self._monotonic()
        with correlation_scope():
            logger.info(
                "product_discovery.search_started",
                extra={
                    "query_text": text,
                    "category": category,
                    "limit": limit,
                    "offset": offset,
                    "adapter_limit": adapter_limit,
                    "correlation_id": get_correlation_id(),
                },
            )
            self._metrics.increment(DISCOVERY_SEARCHES, tags={"category": category or "any"})
            outcome = await self._fleet.search(query)
            hits = self._persist_outcome(outcome)
            duration_ms = (self._monotonic() - started_at) * 1000.0
            self._metrics.observe(DISCOVERY_DURATION_MS, duration_ms)
            self._metrics.increment(DISCOVERY_RESULTS, value=len(hits))
            self._metrics.increment(DISCOVERY_RETAILER_FAILURES, value=len(outcome.failures))
            logger.info(
                "product_discovery.search_completed",
                extra={
                    "query_text": text,
                    "category": category,
                    "result_count": len(hits),
                    "failure_count": len(outcome.failures),
                    "consulted_retailer_ids": list(outcome.consulted_retailer_ids),
                    "duration_ms": duration_ms,
                    "success": True,
                    "correlation_id": get_correlation_id(),
                },
            )
        window = hits[offset : offset + limit]
        return ProductSearchPage(
            items=window,
            total=len(hits),
            limit=limit,
            offset=offset,
            query=text,
            failures=[_failure_schema(failure) for failure in outcome.failures],
            consulted_retailer_ids=list(outcome.consulted_retailer_ids),
        )

    def _persist_outcome(self, outcome: FleetSearchOutcome) -> list[ProductSearchHit]:
        normalized_by_key = {
            (item.retailer_id, item.retailer_sku): item for item in outcome.normalized_products
        }
        hits: list[ProductSearchHit] = []
        for adapter_product in outcome.products:
            normalized = normalized_by_key.get(
                (adapter_product.retailer_id, adapter_product.retailer_sku)
            )
            if normalized is None:
                continue
            hit = self._persist_listing(adapter_product, normalized)
            if hit is not None:
                hits.append(hit)
        hits.sort(key=lambda item: (item.retailer.slug, item.retailer_sku))
        return hits

    def _persist_listing(
        self, adapter_product: AdapterRetailerProduct, normalized: NormalizedProduct
    ) -> ProductSearchHit | None:
        retailer = self._upsert_retailer(normalized.retailer_id)
        brand = self._upsert_brand(normalized)
        category = self._upsert_category(normalized, adapter_product)
        variant = self._resolve_variant(normalized, brand, category)
        listing = self._upsert_listing(variant, retailer, adapter_product, normalized)
        seller = self._upsert_seller(retailer, adapter_product.seller)
        snapshot = self._persist_snapshot(listing, seller, adapter_product.price)
        self._metrics.increment(DISCOVERY_PERSISTED, tags={"retailer_id": normalized.retailer_id})
        logger.info(
            "product_discovery.listing_persisted",
            extra={
                "retailer_id": normalized.retailer_id,
                "retailer_sku": normalized.retailer_sku,
                "product_id": str(variant.product_id),
                "variant_id": str(variant.id),
                "has_price": snapshot is not None,
                "correlation_id": get_correlation_id(),
            },
        )
        if snapshot is None:
            return None
        return ProductSearchHit(
            product=ProductRead.model_validate(variant.product),
            variant=ProductVariantRead.model_validate(variant),
            retailer=RetailerRead.model_validate(retailer),
            seller=SellerRead.model_validate(seller) if seller is not None else None,
            retailer_product_id=listing.id,
            retailer_sku=listing.retailer_sku,
            displayed_price=snapshot.displayed_price,
            mrp=snapshot.mrp,
            effective_price=snapshot.effective_price,
            currency=snapshot.currency,
            availability=snapshot.availability,
            source_url=snapshot.source_url,
            observed_at=snapshot.observed_at,
            source_type=snapshot.source_type,
            confidence=snapshot.confidence,
        )

    def _upsert_retailer(self, retailer_id: str) -> Retailer:
        existing = self._retailers.get_by_slug(retailer_id)
        if existing is not None:
            return existing
        adapter = self._registry.get(retailer_id)
        by_name = self._retailers.get_by_name(adapter.retailer_name)
        if by_name is not None:
            return by_name
        return self._retailers.add(
            Retailer(
                name=adapter.retailer_name,
                slug=retailer_id,
                is_active=adapter.enabled,
            )
        )

    def _upsert_brand(self, normalized: NormalizedProduct) -> Brand | None:
        slug = normalized.brand_slug
        if slug is None and normalized.brand_name:
            try:
                slug = slugify(normalized.brand_name)
            except InvalidSlugError:
                slug = None
        if slug is None:
            return None
        existing = self._brands.get_by_slug(slug)
        if existing is not None:
            return existing
        name = normalized.brand_name or slug
        by_name = self._brands.get_by_name(name)
        if by_name is not None:
            return by_name
        return self._brands.add(Brand(name=name, slug=slug, is_active=True))

    def _upsert_category(
        self, normalized: NormalizedProduct, adapter_product: AdapterRetailerProduct
    ) -> Category | None:
        slug = normalized.category_slug
        if slug is None:
            return None
        existing = self._categories.get_by_slug(slug)
        if existing is not None:
            return existing
        name = adapter_product.category_path[-1] if adapter_product.category_path else slug
        return self._categories.add(Category(name=name, slug=slug, is_active=True))

    def _resolve_variant(
        self,
        normalized: NormalizedProduct,
        brand: Brand | None,
        category: Category | None,
    ) -> ProductVariant:
        for ident in _usable_identifiers(normalized.identifiers):
            existing_ident = self._identifiers.get_by_type_and_value(
                ident.identifier_type, ident.value
            )
            if existing_ident is not None:
                self._attach_identifiers(existing_ident.product_variant, normalized.identifiers)
                return existing_ident.product_variant

        retailer = self._retailers.get_by_slug(normalized.retailer_id)
        if retailer is not None:
            existing_listing = self._listings.get_by_retailer_and_sku(
                retailer.id, normalized.retailer_sku
            )
            if existing_listing is not None:
                self._attach_identifiers(existing_listing.product_variant, normalized.identifiers)
                return existing_listing.product_variant

        product = self._products.add(
            Product(
                name=normalized.normalized_title[:_PRODUCT_NAME_MAX_LENGTH],
                slug=self._unique_product_slug(normalized),
                brand_id=brand.id if brand is not None else None,
                category_id=category.id if category is not None else None,
                is_active=True,
            )
        )
        variant = self._variants.add(
            ProductVariant(
                product_id=product.id,
                product=product,
                name=None,
                attributes=dict(normalized.variant_attributes),
                is_active=True,
            )
        )
        self._attach_identifiers(variant, normalized.identifiers)
        return variant

    def _unique_product_slug(self, normalized: NormalizedProduct) -> str:
        try:
            base = slugify(normalized.normalized_title)
        except InvalidSlugError:
            base = f"product-{uuid.uuid4().hex[:12]}"
        candidate = base[:_PRODUCT_SLUG_MAX_LENGTH]
        if self._products.get_by_slug(candidate) is None:
            return candidate
        suffix = slugify(f"{normalized.retailer_id}-{normalized.retailer_sku}")
        combined = f"{candidate[: _PRODUCT_SLUG_MAX_LENGTH - len(suffix) - 1]}-{suffix}"
        if self._products.get_by_slug(combined) is None:
            return combined[:_PRODUCT_SLUG_MAX_LENGTH]
        return f"{candidate[:541]}-{uuid.uuid4().hex[:8]}"

    def _attach_identifiers(
        self, variant: ProductVariant, identifiers: tuple[ProductIdentifierValue, ...]
    ) -> None:
        for ident in _usable_identifiers(identifiers):
            existing = self._identifiers.get_by_type_and_value(ident.identifier_type, ident.value)
            if existing is None:
                self._identifiers.add(
                    ProductIdentifier(
                        product_variant_id=variant.id,
                        identifier_type=ident.identifier_type,
                        value=ident.value,
                    )
                )
            elif existing.product_variant_id != variant.id:
                logger.warning(
                    "product_discovery.identifier_conflict",
                    extra={
                        "identifier_type": ident.identifier_type.value,
                        "existing_variant_id": str(existing.product_variant_id),
                        "requested_variant_id": str(variant.id),
                    },
                )

    def _upsert_listing(
        self,
        variant: ProductVariant,
        retailer: Retailer,
        adapter_product: AdapterRetailerProduct,
        normalized: NormalizedProduct,
    ) -> RetailerProduct:
        existing = self._listings.get_by_retailer_and_sku(retailer.id, normalized.retailer_sku)
        seen_at = adapter_product.retrieved_at
        source_url = adapter_product.url or normalized.source_url
        if existing is not None:
            existing.last_seen_at = seen_at
            if source_url:
                existing.url = source_url
            existing.is_active = True
            self._session.flush()
            return existing
        return self._listings.add(
            RetailerProduct(
                product_variant_id=variant.id,
                retailer_id=retailer.id,
                retailer_sku=normalized.retailer_sku,
                url=source_url,
                is_active=True,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            )
        )

    def _upsert_seller(self, retailer: Retailer, info: SellerInformation | None) -> Seller | None:
        if info is None:
            return None
        if info.retailer_seller_id:
            existing = self._sellers.get_by_external_id(retailer.id, info.retailer_seller_id)
            if existing is not None:
                return existing
        if info.is_first_party:
            existing = self._sellers.get_first_party_seller(retailer.id)
            if existing is not None:
                return existing
        return self._sellers.add(
            Seller(
                retailer_id=retailer.id,
                name=info.name,
                external_seller_id=info.retailer_seller_id,
                is_first_party=info.is_first_party,
                is_active=True,
            )
        )

    def _persist_snapshot(
        self,
        listing: RetailerProduct,
        seller: Seller | None,
        price: PriceObservation | None,
    ) -> PriceSnapshot | None:
        if price is None:
            return None
        seller_id = seller.id if seller is not None else None
        existing = self._snapshots.get_by_observation_key(listing.id, price.observed_at, seller_id)
        if existing is not None:
            return existing
        return self._snapshots.add_snapshot(
            PriceSnapshot(
                retailer_product_id=listing.id,
                seller_id=seller_id,
                observed_at=price.observed_at,
                currency=price.currency,
                mrp=price.mrp,
                displayed_price=Decimal(price.displayed_price),
                effective_price=price.effective_price,
                delivery_fee=price.delivery_fee,
                platform_fee=price.platform_fee,
                availability=price.availability,
                source_type=price.source_type,
                source_url=price.source_url,
                confidence=price.confidence,
                created_at=_utc_now(),
            )
        )


def _usable_identifiers(
    identifiers: tuple[ProductIdentifierValue, ...],
) -> tuple[ProductIdentifierValue, ...]:
    return tuple(
        ident for ident in identifiers if 0 < len(ident.value) <= _IDENTIFIER_VALUE_MAX_LENGTH
    )


def _failure_schema(failure: RetailerFailure) -> RetailerSearchFailure:
    return RetailerSearchFailure(
        retailer_id=failure.retailer_id,
        error_code=failure.error_code.value,
        message=failure.message,
    )
