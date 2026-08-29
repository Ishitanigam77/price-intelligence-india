"""Price-alert API: authenticated user's alert rules.

Notification dispatch is out of scope. These routes persist and authorize the rule
(product, threshold, enabled state) for the authenticated user only.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import AlertServiceDep
from app.auth.dependencies import CurrentUser
from app.schemas.alert import AlertCreate, AlertRead, AlertUpdate
from app.schemas.common import Page
from app.schemas.pagination import PaginationParams, pagination_params
from app.schemas.product import ProductRead

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _read(item) -> AlertRead:
    product = ProductRead.model_validate(item.product) if item.product is not None else None
    return AlertRead(
        id=item.id,
        product_id=item.product_id,
        threshold_amount=item.threshold_amount,
        currency=item.currency,
        is_enabled=item.is_enabled,
        product=product,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertCreate, user: CurrentUser, service: AlertServiceDep) -> AlertRead:
    item = service.create_for_user(
        user,
        payload.product_id,
        threshold_amount=payload.threshold_amount,
        currency=payload.normalized_currency(),
        is_enabled=payload.is_enabled,
    )
    return _read(item)


@router.get("", response_model=Page[AlertRead])
def list_alerts(
    user: CurrentUser,
    service: AlertServiceDep,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[AlertRead]:
    items, total = service.list_for_user(user, limit=pagination.limit, offset=pagination.offset)
    return Page[AlertRead](
        items=[_read(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{item_id}", response_model=AlertRead)
def get_alert(item_id: uuid.UUID, user: CurrentUser, service: AlertServiceDep) -> AlertRead:
    return _read(service.get_for_user(user, item_id))


@router.patch("/{item_id}", response_model=AlertRead)
def update_alert(
    item_id: uuid.UUID,
    payload: AlertUpdate,
    user: CurrentUser,
    service: AlertServiceDep,
) -> AlertRead:
    item = service.update_for_user(
        user,
        item_id,
        threshold_amount=payload.threshold_amount,
        currency=payload.normalized_currency(),
        is_enabled=payload.is_enabled,
    )
    return _read(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(item_id: uuid.UUID, user: CurrentUser, service: AlertServiceDep) -> Response:
    service.delete_for_user(user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
