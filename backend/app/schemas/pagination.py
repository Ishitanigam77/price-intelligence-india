"""Shared pagination query-parameter handling for list endpoints."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query


@dataclass
class PaginationParams:
    """Validated `limit`/`offset` query parameters, reused by every `app/api/v1/` list route."""

    limit: int
    offset: int


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=200, description="Max number of items to return.")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of items to skip.")] = 0,
) -> PaginationParams:
    return PaginationParams(limit=limit, offset=offset)
