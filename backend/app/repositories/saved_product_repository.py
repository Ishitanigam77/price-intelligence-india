"""Repository for user-owned saved products. Every query is scoped by `user_id`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.saved_product import SavedProduct
from app.repositories.base import BaseRepository


class SavedProductRepository(BaseRepository[SavedProduct]):
    model = SavedProduct

    def get_for_user(self, user_id: uuid.UUID, item_id: uuid.UUID) -> SavedProduct | None:
        stmt = (
            select(SavedProduct)
            .options(selectinload(SavedProduct.product))
            .where(SavedProduct.id == item_id, SavedProduct.user_id == user_id)
        )
        return self.session.scalars(stmt).first()

    def get_by_user_and_product(
        self, user_id: uuid.UUID, product_id: uuid.UUID
    ) -> SavedProduct | None:
        stmt = select(SavedProduct).where(
            SavedProduct.user_id == user_id, SavedProduct.product_id == product_id
        )
        return self.session.scalars(stmt).first()

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[SavedProduct]:
        stmt = (
            select(SavedProduct)
            .options(selectinload(SavedProduct.product))
            .where(SavedProduct.user_id == user_id)
            .order_by(SavedProduct.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(SavedProduct).where(SavedProduct.user_id == user_id)
        return int(self.session.scalar(stmt) or 0)
