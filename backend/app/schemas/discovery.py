"""API schemas for on-demand product discovery (`GET /api/v1/products/search`)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AvailabilityStatus, ConfidenceLevel, SourceType
from app.schemas.common import Page
from app.schemas.product import ProductRead, ProductVariantRead
from app.schemas.retailer import RetailerRead, SellerRead


class RetailerSearchFailure(BaseModel):
    """One retailer's failure during a discovery search, in retailer-agnostic terms."""

    retailer_id: str
    error_code: str
    message: str


class ProductSearchHit(BaseModel):
    """One discovered offer: a variant as listed by a retailer, with its observed price.

    Nested product/variant/retailer/seller identities are the persisted Phase 1 entities.
    Price, availability, source URL, and observation timestamp are the observed facts from the
    adapter — never calculated or predicted.
    """

    model_config = ConfigDict(from_attributes=True)

    product: ProductRead
    variant: ProductVariantRead
    retailer: RetailerRead
    seller: SellerRead | None = None
    retailer_product_id: uuid.UUID
    retailer_sku: str
    displayed_price: Decimal
    mrp: Decimal | None = None
    effective_price: Decimal | None = None
    currency: str
    availability: AvailabilityStatus
    source_url: str | None = None
    observed_at: datetime
    source_type: SourceType
    confidence: ConfidenceLevel


class ProductSearchPage(Page[ProductSearchHit]):
    """Paginated discovery results, plus which retailers were consulted and which failed."""

    query: str
    failures: list[RetailerSearchFailure] = Field(default_factory=list)
    consulted_retailer_ids: list[str] = Field(default_factory=list)
