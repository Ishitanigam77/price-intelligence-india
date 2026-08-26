"""Repository for `ProductIdentifier`."""

from sqlalchemy import select

from app.db.models.product_identifier import ProductIdentifier
from app.domain.enums import ProductIdentifierType
from app.repositories.base import BaseRepository


class ProductIdentifierRepository(BaseRepository[ProductIdentifier]):
    model = ProductIdentifier

    def get_by_type_and_value(
        self, identifier_type: ProductIdentifierType, value: str
    ) -> ProductIdentifier | None:
        """Look up a globally unique identifier (the Phase 1 uniqueness constraint)."""
        stmt = select(ProductIdentifier).where(
            ProductIdentifier.identifier_type == identifier_type,
            ProductIdentifier.value == value,
        )
        return self.session.scalars(stmt).first()
