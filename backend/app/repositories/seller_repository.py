"""Repository for `Seller`."""

import uuid

from sqlalchemy import select

from app.db.models.seller import Seller
from app.repositories.base import BaseRepository


class SellerRepository(BaseRepository[Seller]):
    model = Seller

    def list_for_retailer(self, retailer_id: uuid.UUID) -> list[Seller]:
        stmt = select(Seller).where(Seller.retailer_id == retailer_id)
        return list(self.session.scalars(stmt).all())

    def get_first_party_seller(self, retailer_id: uuid.UUID) -> Seller | None:
        stmt = select(Seller).where(
            Seller.retailer_id == retailer_id, Seller.is_first_party.is_(True)
        )
        return self.session.scalars(stmt).first()

    def get_by_external_id(self, retailer_id: uuid.UUID, external_seller_id: str) -> Seller | None:
        stmt = select(Seller).where(
            Seller.retailer_id == retailer_id, Seller.external_seller_id == external_seller_id
        )
        return self.session.scalars(stmt).first()
