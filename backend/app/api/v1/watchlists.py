"""Watchlist API: authenticated user's product watchlist associations.

POST creates a watchlist/product association for the authenticated user. GET returns only that
user's items. Owner/user ids in the request body are rejected (`extra='forbid'`).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import WatchlistServiceDep
from app.auth.dependencies import CurrentUser
from app.schemas.common import Page
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.product import ProductRead
from app.schemas.watchlist import WatchlistCreate, WatchlistRead

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _read(item) -> WatchlistRead:
    product = ProductRead.model_validate(item.product) if item.product is not None else None
    return WatchlistRead(
        id=item.id,
        product_id=item.product_id,
        product=product,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
def create_watchlist(
    payload: WatchlistCreate, user: CurrentUser, service: WatchlistServiceDep
) -> WatchlistRead:
    item = service.create_for_user(user, payload.product_id)
    return _read(item)


@router.get("", response_model=Page[WatchlistRead])
def list_watchlists(
    user: CurrentUser,
    service: WatchlistServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[WatchlistRead]:
    items, total = service.list_for_user(user, limit=pagination.limit, offset=pagination.offset)
    return Page[WatchlistRead](
        items=[_read(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{item_id}", response_model=WatchlistRead)
def get_watchlist(
    item_id: uuid.UUID, user: CurrentUser, service: WatchlistServiceDep
) -> WatchlistRead:
    return _read(service.get_for_user(user, item_id))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    item_id: uuid.UUID, user: CurrentUser, service: WatchlistServiceDep
) -> Response:
    service.delete_for_user(user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
