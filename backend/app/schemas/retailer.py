"""API schemas for `Retailer` and `Seller`.

Per `RETAILER_ARCHITECTURE.md`, `Retailer` is a retailer-agnostic reference/metadata table —
no retailer-specific fields exist here in Phase 1 or Phase 2. Real retailer adapters and
integrations are introduced in a later phase.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RetailerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    website_url: str | None = None
    country_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SellerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retailer_id: uuid.UUID
    name: str
    external_seller_id: str | None = None
    is_first_party: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
