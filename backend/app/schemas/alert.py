"""API schemas for price alerts. Owner/user ids are never accepted from the client."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.validation import validate_currency_code
from app.schemas.product import ProductRead


class AlertCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    threshold_amount: Decimal = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    is_enabled: bool = True

    def normalized_currency(self) -> str:
        return validate_currency_code(self.currency.strip().upper())


class AlertUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_enabled: bool | None = None

    def normalized_currency(self) -> str | None:
        if self.currency is None:
            return None
        return validate_currency_code(self.currency.strip().upper())


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    threshold_amount: Decimal
    currency: str
    is_enabled: bool
    product: ProductRead | None = None
    created_at: datetime
    updated_at: datetime
