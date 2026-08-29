"""Product API routes: read-only catalogue plus on-demand product discovery.

Catalogue routes (`GET /products`, `GET /products/{id}`, ...) expose the Phase 1
`Product`/`ProductVariant` models via repositories. Discovery (`GET /products/search`)
fans out to enabled retailer adapters through `ProductDiscoveryService` and is the Phase 4
write path that persists newly observed listings. Comparison (`GET /products/{id}/prices`)
ranks retailer offers per variant through `PriceComparisonService`. Historical intelligence
(`GET /products/{id}/history`) computes per-variant aggregates from stored observations
through `PriceHistoryService`. Sale-event history (`GET /products/{id}/sale-history`) reports
applicable sale windows and observed prices during those windows through `SaleEventService`.
Different variants are always returned as distinct resources, never merged
(`PROJECT_ARCHITECTURE.md` §5).
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from app.api.deps import (
    PriceComparisonServiceDep,
    PriceHistoryServiceDep,
    ProductDiscoveryServiceDep,
    ProductRepositoryDep,
    ProductVariantRepositoryDep,
    SaleEventServiceDep,
)
from app.api.errors import NotFoundError
from app.schemas.common import Page
from app.schemas.comparison import ProductPricesRead
from app.schemas.discovery import ProductSearchPage
from app.schemas.history import ProductHistoryRead
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.product import ProductRead, ProductVariantRead
from app.schemas.sale_event import ProductSaleHistoryRead

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/search", response_model=ProductSearchPage)
async def search_products(
    service: ProductDiscoveryServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    q: Annotated[
        str,
        Query(
            min_length=1,
            max_length=500,
            description="Search text passed to every enabled retailer adapter.",
        ),
    ],
    category: Annotated[
        str | None,
        Query(description="Optional category slug used to scope which adapters are consulted."),
    ] = None,
) -> ProductSearchPage:
    """Discover products across enabled retailers and persist the observed listings.

    Individual retailer failures are isolated: successful retailers still contribute results.
    """
    text = q.strip()
    if not text:
        raise RequestValidationError(
            [
                {
                    "type": "string_too_short",
                    "loc": ("query", "q"),
                    "msg": "Search text must not be blank.",
                    "input": q,
                    "ctx": {"min_length": 1},
                }
            ]
        )
    try:
        return await service.search(
            text=text,
            category=category,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except PydanticValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("", response_model=Page[ProductRead])
def list_products(
    repo: ProductRepositoryDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    category_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
) -> Page[ProductRead]:
    """List products, optionally filtered by category or brand."""
    if category_id is not None:
        matching = repo.list_by_category(category_id)
    elif brand_id is not None:
        matching = repo.list_by_brand(brand_id)
    else:
        total = repo.count()
        items = repo.list(limit=pagination.limit, offset=pagination.offset)
        return Page[ProductRead](
            items=items, total=total, limit=pagination.limit, offset=pagination.offset
        )

    window = matching[pagination.offset : pagination.offset + pagination.limit]
    return Page[ProductRead](
        items=window, total=len(matching), limit=pagination.limit, offset=pagination.offset
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, repo: ProductRepositoryDep) -> ProductRead:
    product = repo.get_by_id(product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} was not found.")
    return ProductRead.model_validate(product)


@router.get("/slug/{slug}", response_model=ProductRead)
def get_product_by_slug(slug: str, repo: ProductRepositoryDep) -> ProductRead:
    product = repo.get_by_slug(slug)
    if product is None:
        raise NotFoundError(f"Product with slug {slug!r} was not found.")
    return ProductRead.model_validate(product)


@router.get("/{product_id}/prices", response_model=ProductPricesRead)
def get_product_prices(
    product_id: uuid.UUID, service: PriceComparisonServiceDep
) -> ProductPricesRead:
    """Compare retailer offers for every variant of a product.

    Offers are ranked per variant using verified effective price; unverified coupons,
    cashback, and payment discounts never win the lowest-verified-price slot. Different
    variants are never combined.
    """
    return service.compare_product(product_id)


@router.get("/{product_id}/history", response_model=ProductHistoryRead)
def get_product_history(
    product_id: uuid.UUID,
    service: PriceHistoryServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    variant_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> ProductHistoryRead:
    """Return stored historical observations and calculated intelligence per variant.

    Aggregates are computed from verified observed snapshots only. Insufficient history is
    reported explicitly; values are never fabricated. Predicted prices are not returned.
    Observation lists are paginated; calculations use the full qualifying history.
    """
    return service.get_product_history(
        product_id,
        variant_id=variant_id,
        since=since,
        until=until,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{product_id}/sale-history", response_model=ProductSaleHistoryRead)
def get_product_sale_history(
    product_id: uuid.UUID,
    service: SaleEventServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    variant_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> ProductSaleHistoryRead:
    """Return sale events applicable to a product and observed prices during those windows.

    Aggregates are calculated from verified observed snapshots only. Insufficient history is
    reported explicitly. Predicted sale prices are not returned. Different variants are never
    combined.
    """
    return service.get_product_sale_history(
        product_id,
        variant_id=variant_id,
        since=since,
        until=until,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{product_id}/variants", response_model=Page[ProductVariantRead])
def list_product_variants(
    product_id: uuid.UUID,
    repo: ProductVariantRepositoryDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[ProductVariantRead]:
    variants = repo.list_for_product(product_id)
    window = variants[pagination.offset : pagination.offset + pagination.limit]
    return Page[ProductVariantRead](
        items=window, total=len(variants), limit=pagination.limit, offset=pagination.offset
    )
