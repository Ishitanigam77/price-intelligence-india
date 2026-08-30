"""Repository for user-owned price alerts. Every query is scoped by `user_id`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.price_alert import PriceAlert
from app.repositories.base import BaseRepository


class PriceAlertRepository(BaseRepository[PriceAlert]):
    model = PriceAlert

    def get_for_user(self, user_id: uuid.UUID, item_id: uuid.UUID) -> PriceAlert | None:
        stmt = (
            select(PriceAlert)
            .options(selectinload(PriceAlert.product))
            .where(PriceAlert.id == item_id, PriceAlert.user_id == user_id)
        )
        return self.session.scalars(stmt).first()

    def get_by_user_and_product(
        self, user_id: uuid.UUID, product_id: uuid.UUID
    ) -> PriceAlert | None:
        stmt = select(PriceAlert).where(
            PriceAlert.user_id == user_id, PriceAlert.product_id == product_id
        )
        return self.session.scalars(stmt).first()

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[PriceAlert]:
        stmt = (
            select(PriceAlert)
            .options(selectinload(PriceAlert.product))
            .where(PriceAlert.user_id == user_id)
            .order_by(PriceAlert.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(PriceAlert).where(PriceAlert.user_id == user_id)
        return int(self.session.scalar(stmt) or 0)
