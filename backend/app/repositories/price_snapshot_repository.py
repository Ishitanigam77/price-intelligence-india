"""Repository for `PriceSnapshot`.

Deliberately exposes no update method: Price Observations are immutable
(`PROJECT_ARCHITECTURE.md` §5). Corrections must be inserted as a new snapshot via `add_snapshot`
(inherited `add`), never as a mutation of an existing row.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.price_snapshot import PriceSnapshot
from app.db.models.retailer_product import RetailerProduct
from app.repositories.base import BaseRepository

_NO_SELLER_SENTINEL = uuid.UUID("00000000-0000-0000-0000-000000000000")


class PriceSnapshotRepository(BaseRepository[PriceSnapshot]):
    model = PriceSnapshot

    def add_snapshot(self, snapshot: PriceSnapshot) -> PriceSnapshot:
        """Insert a new, immutable price/availability observation."""
        return self.add(snapshot)

    def get_by_observation_key(
        self,
        retailer_product_id: uuid.UUID,
        observed_at: datetime,
        seller_id: uuid.UUID | None,
    ) -> PriceSnapshot | None:
        """Look up a snapshot by the uniqueness key used to keep observations immutable."""
        stmt = select(PriceSnapshot).where(
            PriceSnapshot.retailer_product_id == retailer_product_id,
            PriceSnapshot.observed_at == observed_at,
        )
        if seller_id is None:
            stmt = stmt.where(PriceSnapshot.seller_id.is_(None))
        else:
            stmt = stmt.where(PriceSnapshot.seller_id == seller_id)
        return self.session.scalars(stmt).first()

    def latest_for_retailer_product(self, retailer_product_id: uuid.UUID) -> PriceSnapshot | None:
        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.retailer_product_id == retailer_product_id)
            .order_by(PriceSnapshot.observed_at.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def history_for_retailer_product(
        self,
        retailer_product_id: uuid.UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> list[PriceSnapshot]:
        """Return observations for a retailer product, oldest first, optionally date-bounded."""
        stmt = select(PriceSnapshot).where(PriceSnapshot.retailer_product_id == retailer_product_id)
        if since is not None:
            stmt = stmt.where(PriceSnapshot.observed_at >= since)
        if until is not None:
            stmt = stmt.where(PriceSnapshot.observed_at <= until)
        stmt = stmt.order_by(PriceSnapshot.observed_at.asc()).limit(limit)
        return list(self.session.scalars(stmt).all())

    def latest_per_seller_for_retailer_products(
        self, retailer_product_ids: Sequence[uuid.UUID]
    ) -> list[PriceSnapshot]:
        """Latest observation per (listing, seller), with seller/listing/adjustments loaded.

        Uses PostgreSQL `DISTINCT ON`. Listings with no snapshots are not returned — the
        comparison service adds those as missing-observation offers separately.
        """
        if not retailer_product_ids:
            return []
        seller_key = func.coalesce(PriceSnapshot.seller_id, _NO_SELLER_SENTINEL)
        stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.retailer_product_id.in_(tuple(retailer_product_ids)))
            .distinct(PriceSnapshot.retailer_product_id, seller_key)
            .order_by(
                PriceSnapshot.retailer_product_id,
                seller_key,
                PriceSnapshot.observed_at.desc(),
            )
            .options(
                selectinload(PriceSnapshot.seller),
                selectinload(PriceSnapshot.adjustments),
                selectinload(PriceSnapshot.retailer_product).selectinload(RetailerProduct.retailer),
                selectinload(PriceSnapshot.retailer_product).selectinload(
                    RetailerProduct.product_variant
                ),
            )
        )
        return list(self.session.scalars(stmt).all())
