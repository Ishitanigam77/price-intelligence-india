"""Repository for `RetailerProduct`."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.product_variant import ProductVariant
from app.db.models.retailer import Retailer
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

    def list_active_for_retailer_slug(self, retailer_slug: str) -> list[RetailerProduct]:
        """Active listings for the adapter identity `retailer_slug`."""
        stmt = (
            select(RetailerProduct)
            .join(Retailer, RetailerProduct.retailer_id == Retailer.id)
            .where(Retailer.slug == retailer_slug, RetailerProduct.is_active.is_(True))
            .options(selectinload(RetailerProduct.retailer))
            .order_by(RetailerProduct.retailer_sku.asc())
        )
        return list(self.session.scalars(stmt).all())

    def list_for_product(self, product_id: uuid.UUID) -> list[RetailerProduct]:
        """Every retailer listing attached to any variant of `product_id`."""
        stmt = (
            select(RetailerProduct)
            .join(ProductVariant, RetailerProduct.product_variant_id == ProductVariant.id)
            .where(ProductVariant.product_id == product_id)
            .options(
                selectinload(RetailerProduct.retailer),
                selectinload(RetailerProduct.product_variant),
            )
        )
        return list(self.session.scalars(stmt).all())
