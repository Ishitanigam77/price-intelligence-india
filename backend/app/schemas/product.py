"""API schemas for `Product`, `ProductVariant`, `Category`, and `Brand`.

Field sets mirror the Phase 1 ORM models (`app/db/models/product.py`,
`app/db/models/product_variant.py`, ...) closely because Phase 1 already defined a clean,
retailer-agnostic shape for these entities — but as plain, framework-independent DTOs so the
API contract does not depend on SQLAlchemy internals (lazy-loading, relationship objects, etc).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BrandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    website_url: str | None = None
    is_active: bool


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None = None
    is_active: bool


class ProductRead(BaseModel):
    """Public representation of a canonical, retailer-agnostic product."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    brand_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductVariantRead(BaseModel):
    """Public representation of a specific sellable configuration of a `Product`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str | None = None
    attributes: dict[str, str]
    variant_key: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
