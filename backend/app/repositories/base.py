"""Generic base repository shared by every entity-specific repository."""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Common CRUD operations for a single SQLAlchemy model, bound to a session."""

    model: type[ModelType]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        return self.session.get(self.model, entity_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelType]:
        stmt = select(self.model).order_by(self.model.created_at).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def add(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelType) -> None:
        self.session.delete(entity)
        self.session.flush()
