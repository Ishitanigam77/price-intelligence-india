"""API schemas for the authenticated user's profile and preferences.

Clerk remains the identity provider. These DTOs never accept a password or a client-supplied
user/owner id.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.validation import validate_currency_code


class PreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_alerts_enabled: bool
    default_currency: str


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_alerts_enabled: bool | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)

    def normalized_currency(self) -> str | None:
        if self.default_currency is None:
            return None
        return validate_currency_code(self.default_currency.strip().upper())


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clerk_user_id: str
    email: str | None = None
    display_name: str | None = None
    preferences: PreferenceRead
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    """Writable profile fields. `id`, `clerk_user_id`, and `user_id` are rejected as extra."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=200)
    preferences: PreferenceUpdate | None = None
