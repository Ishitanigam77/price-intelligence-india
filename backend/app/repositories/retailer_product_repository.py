"""Repository for `RetailerProduct`."""

import uuid

from sqlalchemy import select

from app.db.models.retailer_product import RetailerProduct
from app.repositories.base import BaseRepository


class RetailerProductRepository(BaseRepository[RetailerProduct]):
    model = RetailerProduct

    def get_by_retailer_and_sku(
        self, retailer_id: uuid.UUID, retailer_sku: str
    ) -> RetailerProduct | None:
        stmt = select(RetailerProduct).where(
            RetailerProduct.retailer_id == retailer_id,
            RetailerProduct.retailer_sku == retailer_sku,
        )
        return self.session.scalars(stmt).first()

    def list_for_variant(self, product_variant_id: uuid.UUID) -> list[RetailerProduct]:
        stmt = select(RetailerProduct).where(
            RetailerProduct.product_variant_id == product_variant_id
        )
        return list(self.session.scalars(stmt).all())
