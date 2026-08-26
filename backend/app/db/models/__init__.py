"""ORM models for every Phase 1 domain entity.

Every model module is imported here so that (a) `Base.metadata` is fully populated for Alembic
autogenerate and for `Base.metadata.create_all(...)` in tests, and (b) callers can do
`from app.db.models import Product, PriceSnapshot, ...`.
"""

from app.db.models.brand import Brand
from app.db.models.category import Category
from app.db.models.price_adjustment import PriceAdjustment
from app.db.models.price_snapshot import PriceSnapshot
from app.db.models.product import Product
from app.db.models.product_identifier import ProductIdentifier
from app.db.models.product_variant import ProductVariant
from app.db.models.retailer import Retailer
from app.db.models.retailer_product import RetailerProduct
from app.db.models.seller import Seller

__all__ = [
    "Brand",
    "Category",
    "PriceAdjustment",
    "PriceSnapshot",
    "Product",
    "ProductIdentifier",
    "ProductVariant",
    "Retailer",
    "RetailerProduct",
    "Seller",
]
