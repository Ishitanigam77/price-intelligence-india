"""Repository for `Retailer`."""

from sqlalchemy import select

from app.db.models.retailer import Retailer
from app.repositories.base import BaseRepository


class RetailerRepository(BaseRepository[Retailer]):
    model = Retailer

    def get_by_slug(self, slug: str) -> Retailer | None:
        stmt = select(Retailer).where(Retailer.slug == slug)
        return self.session.scalars(stmt).first()

    def list_active(self) -> list[Retailer]:
        stmt = select(Retailer).where(Retailer.is_active.is_(True))
        return list(self.session.scalars(stmt).all())
