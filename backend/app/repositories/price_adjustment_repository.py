"""Repository for `PriceAdjustment`.

No update method: like Price Observations, adjustments are immutable facts. A correction is a
new row via `add`.
"""

import uuid

from sqlalchemy import select

from app.db.models.price_adjustment import PriceAdjustment
from app.repositories.base import BaseRepository


class PriceAdjustmentRepository(BaseRepository[PriceAdjustment]):
    model = PriceAdjustment

    def list_for_snapshot(self, price_snapshot_id: uuid.UUID) -> list[PriceAdjustment]:
        stmt = (
            select(PriceAdjustment)
            .where(PriceAdjustment.price_snapshot_id == price_snapshot_id)
            .order_by(PriceAdjustment.created_at.asc())
        )
        return list(self.session.scalars(stmt).all())

    def list_for_snapshots(self, price_snapshot_ids: list[uuid.UUID]) -> list[PriceAdjustment]:
        if not price_snapshot_ids:
            return []
        stmt = select(PriceAdjustment).where(
            PriceAdjustment.price_snapshot_id.in_(price_snapshot_ids)
        )
        return list(self.session.scalars(stmt).all())
