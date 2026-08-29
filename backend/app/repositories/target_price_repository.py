"""Repository for user-owned target prices. Every query is scoped by `user_id`."""

import uuid

from sqlalchemy import func, select

from app.db.models.target_price import TargetPrice
from app.repositories.base import BaseRepository


class TargetPriceRepository(BaseRepository[TargetPrice]):
    model = TargetPrice

    def get_for_user(self, user_id: uuid.UUID, item_id: uuid.UUID) -> TargetPrice | None:
        stmt = select(TargetPrice).where(TargetPrice.id == item_id, TargetPrice.user_id == user_id)
        return self.session.scalars(stmt).first()

    def get_by_user_and_product(
        self, user_id: uuid.UUID, product_id: uuid.UUID
    ) -> TargetPrice | None:
        stmt = select(TargetPrice).where(
            TargetPrice.user_id == user_id, TargetPrice.product_id == product_id
        )
        return self.session.scalars(stmt).first()

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[TargetPrice]:
        stmt = (
            select(TargetPrice)
            .where(TargetPrice.user_id == user_id)
            .order_by(TargetPrice.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(TargetPrice).where(TargetPrice.user_id == user_id)
        return int(self.session.scalar(stmt) or 0)
