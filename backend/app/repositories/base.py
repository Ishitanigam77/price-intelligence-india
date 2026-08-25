"""Generic base repository shared by every entity-specific repository."""

import uuid
from datetime import datetime
from typing import Generic, Protocol, TypeVar, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Mapped, Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class _HasCreatedAt(Protocol):
    """Structural type asserting a model exposes `created_at` (every Phase 1 model does, via
    `TimestampMixin` or an explicit column — see `app/db/models/mixins.py`)."""

    created_at: Mapped[datetime]


class BaseRepository(Generic[ModelType]):
    """Common CRUD operations for a single SQLAlchemy model, bound to a session."""

    model: type[ModelType]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        return self.session.get(self.model, entity_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelType]:
        audited_model = cast(type[_HasCreatedAt], self.model)
        stmt = select(self.model).order_by(audited_model.created_at).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def count(self) -> int:
        """Total number of rows for this model, ignoring pagination.

        Used by API list endpoints (`app/api/v1/`) to populate a `Page`'s `total` field
        alongside `list(...)`.
        """
        stmt = select(func.count()).select_from(self.model)
        return int(self.session.scalar(stmt) or 0)

    def add(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelType) -> None:
        self.session.delete(entity)
        self.session.flush()
