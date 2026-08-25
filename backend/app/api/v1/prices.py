"""Price API routes: read-only access to stored `PriceSnapshot` observations.

Per Phase 2 scope, this only surfaces observations exactly as recorded — no effective-price
calculation, price comparison across retailers, or drop detection (`ROADMAP.md` Phase 4). Every
value returned is either directly observed or left `None`, never guessed.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import PriceServiceDep
from app.api.errors import NotFoundError
from app.schemas.common import Page
from app.schemas.price import PriceSnapshotRead

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/retailer-products/{retailer_product_id}/latest", response_model=PriceSnapshotRead)
def get_latest_price(
    retailer_product_id: uuid.UUID, price_service: PriceServiceDep
) -> PriceSnapshotRead:
    snapshot = price_service.get_latest_snapshot(retailer_product_id)
    if snapshot is None:
        raise NotFoundError(
            f"No price observation has been recorded yet for retailer product "
            f"{retailer_product_id}."
        )
    return PriceSnapshotRead.model_validate(snapshot)


@router.get(
    "/retailer-products/{retailer_product_id}/history", response_model=Page[PriceSnapshotRead]
)
def get_price_history(
    retailer_product_id: uuid.UUID,
    price_service: PriceServiceDep,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> Page[PriceSnapshotRead]:
    history = price_service.get_history(retailer_product_id, since=since, until=until, limit=limit)
    return Page[PriceSnapshotRead](items=history, total=len(history), limit=limit, offset=0)
