"""Repository for `Category`."""

from sqlalchemy import select

from app.db.models.category import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

    def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        return self.session.scalars(stmt).first()

    def list_children(self, parent_id) -> list[Category]:
        stmt = select(Category).where(Category.parent_id == parent_id)
        return list(self.session.scalars(stmt).all())
