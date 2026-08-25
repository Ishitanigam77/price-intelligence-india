"""Repository for `Product`."""

import uuid

from sqlalchemy import select

from app.db.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    def get_by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(Product.slug == slug)
        return self.session.scalars(stmt).first()

    def list_by_category(self, category_id: uuid.UUID) -> list[Product]:
        stmt = select(Product).where(Product.category_id == category_id)
        return list(self.session.scalars(stmt).all())

    def list_by_brand(self, brand_id: uuid.UUID) -> list[Product]:
        stmt = select(Product).where(Product.brand_id == brand_id)
        return list(self.session.scalars(stmt).all())
