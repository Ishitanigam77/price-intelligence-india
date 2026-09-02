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

    def search_active_by_name(self, text: str, *, limit: int = 50) -> list[Product]:
        """Case-insensitive name contains. Does not invent products that are not stored."""
        needle = text.strip()
        if not needle:
            return []
        escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        stmt = (
            select(Product)
            .where(Product.is_active.is_(True), Product.name.ilike(pattern, escape="\\"))
            .order_by(Product.name.asc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

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
