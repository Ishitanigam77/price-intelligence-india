"""Retailer API routes: read-only foundation over the Phase 1 `Retailer`/`Seller` models.

No retailer adapter, scraping, or integration logic lives here — this only exposes the
retailer-agnostic reference data already captured in Phase 1 (`RETAILER_ARCHITECTURE.md`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import RetailerRepositoryDep, SellerRepositoryDep
from app.api.errors import NotFoundError
from app.schemas.common import Page
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.retailer import RetailerRead, SellerRead

router = APIRouter(prefix="/retailers", tags=["retailers"])


@router.get("", response_model=Page[RetailerRead])
def list_retailers(
    repo: RetailerRepositoryDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    active_only: bool = False,
) -> Page[RetailerRead]:
    if active_only:
        matching = repo.list_active()
        window = matching[pagination.offset : pagination.offset + pagination.limit]
        return Page[RetailerRead](
            items=window, total=len(matching), limit=pagination.limit, offset=pagination.offset
        )

    total = repo.count()
    items = repo.list(limit=pagination.limit, offset=pagination.offset)
    return Page[RetailerRead](
        items=items, total=total, limit=pagination.limit, offset=pagination.offset
    )


@router.get("/{retailer_id}", response_model=RetailerRead)
def get_retailer(retailer_id: uuid.UUID, repo: RetailerRepositoryDep) -> RetailerRead:
    retailer = repo.get_by_id(retailer_id)
    if retailer is None:
        raise NotFoundError(f"Retailer {retailer_id} was not found.")
    return RetailerRead.model_validate(retailer)


@router.get("/slug/{slug}", response_model=RetailerRead)
def get_retailer_by_slug(slug: str, repo: RetailerRepositoryDep) -> RetailerRead:
    retailer = repo.get_by_slug(slug)
    if retailer is None:
        raise NotFoundError(f"Retailer with slug {slug!r} was not found.")
    return RetailerRead.model_validate(retailer)


@router.get("/{retailer_id}/sellers", response_model=Page[SellerRead])
def list_retailer_sellers(
    retailer_id: uuid.UUID,
    repo: SellerRepositoryDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[SellerRead]:
    sellers = repo.list_for_retailer(retailer_id)
    window = sellers[pagination.offset : pagination.offset + pagination.limit]
    return Page[SellerRead](
        items=window, total=len(sellers), limit=pagination.limit, offset=pagination.offset
    )
