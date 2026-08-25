"""Deals API route: foundation only.

There is no deal-detection logic yet — it depends on price-drop detection (`ROADMAP.md`
Phase 4) and sale-event intelligence (Phase 7), neither of which are implemented. This route
exists only to reserve `/api/v1/deals` and return a well-typed, honestly-empty result rather
than a 404, so later phases can implement the real logic here without changing the route
contract's shape.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.common import Page
from app.schemas.deal import DealRead
from app.schemas.pagination import PaginationParams, pagination_params

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=Page[DealRead])
def list_deals(
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
) -> Page[DealRead]:
    """Always returns an empty page. Deal detection is not implemented until a later phase."""
    return Page[DealRead](items=[], total=0, limit=pagination.limit, offset=pagination.offset)
