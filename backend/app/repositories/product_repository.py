"""Repository for `Product`."""

import uuid

from sqlalchemy import func, select

from app.db.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    def get_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(Product.slug == slug)
        return self.session.scalars(stmt).first()

    def list_by_category(
        self,
        category_id: uuid.UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Product]:
        stmt = select(Product).where(Product.category_id == category_id).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def count_by_category(self, category_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Product).where(Product.category_id == category_id)
        return int(self.session.scalar(stmt) or 0)

    def list_by_brand(
        self,
        brand_id: uuid.UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Product]:
        stmt = select(Product).where(Product.brand_id == brand_id).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def count_by_brand(self, brand_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
        return int(self.session.scalar(stmt) or 0)
