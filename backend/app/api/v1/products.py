"""Product API routes: read-only foundation over the Phase 1 `Product`/`ProductVariant` models.

Per Phase 2 scope, this module only exposes the data already captured by the Phase 1 schema
(via `ProductRepository`/`ProductVariantRepository`) — no matching, price comparison, or
recommendation logic. Different variants are always returned as distinct resources, never
merged (`PROJECT_ARCHITECTURE.md` §5).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ProductRepositoryDep, ProductVariantRepositoryDep
from app.api.errors import NotFoundError
from app.schemas.common import Page
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.product import ProductRead, ProductVariantRead

router = APIRouter(prefix="/products", tags=["products"])


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
