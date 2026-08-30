"""Repository for user-owned watchlist items. Every query is scoped by `user_id`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.watchlist_item import WatchlistItem
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[WatchlistItem]):
    model = WatchlistItem

    def get_for_user(self, user_id: uuid.UUID, item_id: uuid.UUID) -> WatchlistItem | None:
        stmt = (
            select(WatchlistItem)
            .options(selectinload(WatchlistItem.product))
            .where(WatchlistItem.id == item_id, WatchlistItem.user_id == user_id)
        )
        return self.session.scalars(stmt).first()

    def get_by_user_and_product(
        self, user_id: uuid.UUID, product_id: uuid.UUID
    ) -> WatchlistItem | None:
        stmt = select(WatchlistItem).where(
            WatchlistItem.user_id == user_id, WatchlistItem.product_id == product_id
        )
        return self.session.scalars(stmt).first()

    def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[WatchlistItem]:
        stmt = (
            select(WatchlistItem)
            .options(selectinload(WatchlistItem.product))
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count()).select_from(WatchlistItem).where(WatchlistItem.user_id == user_id)
        )
        return int(self.session.scalar(stmt) or 0)
