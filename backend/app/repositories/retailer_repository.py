"""Repository for `Retailer`."""

from sqlalchemy import func, select

from app.db.models.retailer import Retailer
from app.repositories.base import BaseRepository


class RetailerRepository(BaseRepository[Retailer]):
    model = Retailer

    def get_by_slug(self, slug: str) -> Retailer | None:
        stmt = select(Retailer).where(Retailer.slug == slug)
        return self.session.scalars(stmt).first()

    def get_by_name(self, name: str) -> Retailer | None:
        stmt = select(Retailer).where(Retailer.name == name)
        return self.session.scalars(stmt).first()

    def list_active(self, *, limit: int | None = None, offset: int = 0) -> list[Retailer]:
        stmt = select(Retailer).where(Retailer.is_active.is_(True)).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def count_active(self) -> int:
        stmt = select(func.count()).select_from(Retailer).where(Retailer.is_active.is_(True))
        return int(self.session.scalar(stmt) or 0)
