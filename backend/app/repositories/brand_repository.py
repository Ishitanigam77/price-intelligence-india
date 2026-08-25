"""Repository for `Brand`."""

from sqlalchemy import select

from app.db.models.brand import Brand
from app.repositories.base import BaseRepository


class BrandRepository(BaseRepository[Brand]):
    model = Brand

    def get_by_slug(self, slug: str) -> Brand | None:
        stmt = select(Brand).where(Brand.slug == slug)
        return self.session.scalars(stmt).first()
