"""API schemas for saved products. Owner/user ids are never accepted from the client."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.product import ProductRead


class SavedProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID


class SavedProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product: ProductRead | None = None
    created_at: datetime
    updated_at: datetime
