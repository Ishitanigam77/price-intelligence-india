"""ORM models for every persisted domain entity.

Every model module is imported here so that (a) `Base.metadata` is fully populated for Alembic
autogenerate and for `Base.metadata.create_all(...)` in tests, and (b) callers can do
`from app.db.models import Product, PriceSnapshot, ...`.
"""

from app.db.models.brand import Brand
from app.db.models.category import Category
from app.db.models.collection_error import CollectionError
from app.db.models.collection_job import CollectionJob
from app.db.models.price_adjustment import PriceAdjustment
from app.db.models.price_alert import PriceAlert
from app.db.models.price_snapshot import PriceSnapshot
from app.db.models.product import Product
from app.db.models.product_identifier import ProductIdentifier
from app.db.models.product_variant import ProductVariant
from app.db.models.retailer import Retailer
from app.db.models.retailer_product import RetailerProduct
from app.db.models.sale_event import SaleEvent
from app.db.models.saved_product import SavedProduct
from app.db.models.seller import Seller
from app.db.models.target_price import TargetPrice
from app.db.models.user import User
from app.db.models.user_preference import UserPreference
from app.db.models.watchlist_item import WatchlistItem

__all__ = [
    "Brand",
    "Category",
    "CollectionError",
    "CollectionJob",
    "PriceAdjustment",
    "PriceAlert",
    "PriceSnapshot",
    "Product",
    "ProductIdentifier",
    "ProductVariant",
    "Retailer",
    "RetailerProduct",
    "SaleEvent",
    "SavedProduct",
    "Seller",
    "TargetPrice",
    "User",
    "UserPreference",
    "WatchlistItem",
]
