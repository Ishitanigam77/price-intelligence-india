"""Schema building blocks shared across entity-specific schemas: pagination and error envelopes."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    """A generic paginated list response.

    Every list endpoint in `app/api/v1/` returns this shape rather than a bare JSON array, so
    clients can always find `total`/`limit`/`offset` in the same place regardless of entity.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[ItemT]
    total: int = Field(ge=0, description="Total number of matching records, ignoring pagination.")
    limit: int = Field(ge=1, description="The page size that was applied.")
    offset: int = Field(ge=0, description="The offset that was applied.")


class ErrorDetail(BaseModel):
    """A single structured error payload, used by every centralized exception handler."""

    code: str = Field(description="Stable machine-readable error code, e.g. 'not_found'.")
    message: str = Field(description="Human-readable error message. Never includes secrets.")
    fields: list[dict] | None = Field(
        default=None,
        description="Optional per-field validation error details (validation errors only).",
    )


class ErrorResponse(BaseModel):
    """The consistent error envelope returned by every failure response.

    Every centralized exception handler (see `app.api.errors`) returns this shape, so API
    clients never need to branch on which failure mode occurred to find the error message.
    """

    error: ErrorDetail
