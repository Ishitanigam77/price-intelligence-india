"""Target-price API: authenticated user's per-product target prices."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import TargetPriceServiceDep
from app.auth.dependencies import CurrentUser
from app.schemas.common import Page
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.product import ProductRead
from app.schemas.target_price import TargetPriceCreate, TargetPriceRead, TargetPriceUpdate

router = APIRouter(prefix="/target-prices", tags=["target-prices"])


def _read(item) -> TargetPriceRead:
    product = ProductRead.model_validate(item.product) if item.product is not None else None
    return TargetPriceRead(
        id=item.id,
        product_id=item.product_id,
        amount=item.amount,
        currency=item.currency,
        product=product,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("", response_model=TargetPriceRead, status_code=status.HTTP_201_CREATED)
def create_target_price(
    payload: TargetPriceCreate, user: CurrentUser, service: TargetPriceServiceDep
) -> TargetPriceRead:
    item = service.create_for_user(
        user,
        payload.product_id,
        amount=payload.amount,
        currency=payload.normalized_currency(),
    )
    return _read(item)


@router.get("", response_model=Page[TargetPriceRead])
def list_target_prices(
    user: CurrentUser,
    service: TargetPriceServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[TargetPriceRead]:
    items, total = service.list_for_user(user, limit=pagination.limit, offset=pagination.offset)
    return Page[TargetPriceRead](
        items=[_read(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{item_id}", response_model=TargetPriceRead)
def get_target_price(
    item_id: uuid.UUID, user: CurrentUser, service: TargetPriceServiceDep
) -> TargetPriceRead:
    return _read(service.get_for_user(user, item_id))


@router.patch("/{item_id}", response_model=TargetPriceRead)
def update_target_price(
    item_id: uuid.UUID,
    payload: TargetPriceUpdate,
    user: CurrentUser,
    service: TargetPriceServiceDep,
) -> TargetPriceRead:
    item = service.update_for_user(
        user,
        item_id,
        amount=payload.amount,
        currency=payload.normalized_currency(),
    )
    return _read(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target_price(
    item_id: uuid.UUID, user: CurrentUser, service: TargetPriceServiceDep
) -> Response:
    service.delete_for_user(user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
