"""Saved-products API: authenticated user's saved catalogue products."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SavedProductServiceDep
from app.auth.dependencies import CurrentUser
from app.schemas.common import Page
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.product import ProductRead
from app.schemas.saved_product import SavedProductCreate, SavedProductRead

router = APIRouter(prefix="/saved-products", tags=["saved-products"])


def _read(item) -> SavedProductRead:
    product = ProductRead.model_validate(item.product) if item.product is not None else None
    return SavedProductRead(
        id=item.id,
        product_id=item.product_id,
        product=product,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("", response_model=SavedProductRead, status_code=status.HTTP_201_CREATED)
def create_saved_product(
    payload: SavedProductCreate, user: CurrentUser, service: SavedProductServiceDep
) -> SavedProductRead:
    item = service.create_for_user(user, payload.product_id)
    return _read(item)


@router.get("", response_model=Page[SavedProductRead])
def list_saved_products(
    user: CurrentUser,
    service: SavedProductServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[SavedProductRead]:
    items, total = service.list_for_user(user, limit=pagination.limit, offset=pagination.offset)
    return Page[SavedProductRead](
        items=[_read(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{item_id}", response_model=SavedProductRead)
def get_saved_product(
    item_id: uuid.UUID, user: CurrentUser, service: SavedProductServiceDep
) -> SavedProductRead:
    return _read(service.get_for_user(user, item_id))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_product(
    item_id: uuid.UUID, user: CurrentUser, service: SavedProductServiceDep
) -> Response:
    service.delete_for_user(user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
