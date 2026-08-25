"""Price service: read-only orchestration over `RetailerProduct` + `PriceSnapshot`.

This is a genuinely-needed service boundary (rather than a route calling a repository directly)
because "get the price history/latest price for a retailer listing" requires first confirming
that the `RetailerProduct` exists — a 404 for an unknown listing is a materially different
outcome than "this listing exists but has no observations yet" (an empty list). Both
repositories involved are Phase 1 repositories; this module adds no new persistence logic, no
price computation, and no comparison/prediction logic.
"""

import uuid
from datetime import datetime

from app.api.errors import NotFoundError
from app.db.models import PriceSnapshot
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.retailer_product_repository import RetailerProductRepository


class PriceService:
    def __init__(
        self,
        retailer_product_repo: RetailerProductRepository,
        price_snapshot_repo: PriceSnapshotRepository,
    ) -> None:
        self._retailer_product_repo = retailer_product_repo
        self._price_snapshot_repo = price_snapshot_repo

    def _require_retailer_product(self, retailer_product_id: uuid.UUID) -> None:
        if self._retailer_product_repo.get_by_id(retailer_product_id) is None:
            raise NotFoundError(f"Retailer product {retailer_product_id} was not found.")

    def get_latest_snapshot(self, retailer_product_id: uuid.UUID) -> PriceSnapshot | None:
        """Return the most recent price observation, or `None` if none has been recorded yet.

        Raises `NotFoundError` if the retailer listing itself does not exist (distinct from "no
        observations yet", which is a normal, expected state for a newly-discovered listing).
        """
        self._require_retailer_product(retailer_product_id)
        return self._price_snapshot_repo.latest_for_retailer_product(retailer_product_id)

    def get_history(
        self,
        retailer_product_id: uuid.UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> list[PriceSnapshot]:
        self._require_retailer_product(retailer_product_id)
        return self._price_snapshot_repo.history_for_retailer_product(
            retailer_product_id, since=since, until=until, limit=limit
        )
