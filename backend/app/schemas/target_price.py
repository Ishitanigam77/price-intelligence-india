"""API schemas for user-specific target prices.

Owner/user ids are never accepted from the client.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.validation import validate_currency_code
from app.schemas.product import ProductRead


class TargetPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    def normalized_currency(self) -> str:
        return validate_currency_code(self.currency.strip().upper())


class TargetPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    def normalized_currency(self) -> str | None:
        if self.currency is None:
            return None
        return validate_currency_code(self.currency.strip().upper())


class TargetPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    amount: Decimal
    currency: str
    product: ProductRead | None = None
    created_at: datetime
    updated_at: datetime
