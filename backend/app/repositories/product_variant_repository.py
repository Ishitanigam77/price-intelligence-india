"""Repository for `ProductVariant`."""

import uuid

from sqlalchemy import select

from app.db.models.product_variant import ProductVariant
from app.domain.validation import build_variant_key, normalize_variant_attributes
from app.repositories.base import BaseRepository


class ProductVariantRepository(BaseRepository[ProductVariant]):
    model = ProductVariant

    def list_for_product(self, product_id: uuid.UUID) -> list[ProductVariant]:
        stmt = select(ProductVariant).where(ProductVariant.product_id == product_id)
        return list(self.session.scalars(stmt).all())

    def get_by_attributes(
        self, product_id: uuid.UUID, attributes: dict[str, str]
    ) -> ProductVariant | None:
        """Look up a variant of a product by its (unordered) attribute set.

        Useful for a future matching/ingestion step that needs to check "does this product
        already have a variant with these exact attributes?" without racing on the unique
        constraint.
        """
        variant_key = build_variant_key(normalize_variant_attributes(attributes))
        stmt = select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.variant_key == variant_key,
        )
        return self.session.scalars(stmt).first()
