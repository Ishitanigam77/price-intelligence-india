"""Repository for `CollectionError`."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models.collection_error import CollectionError
from app.repositories.base import BaseRepository


class CollectionErrorRepository(BaseRepository[CollectionError]):
    model = CollectionError

    def list_for_job(self, collection_job_id: uuid.UUID) -> list[CollectionError]:
        stmt = (
            select(CollectionError)
            .where(CollectionError.collection_job_id == collection_job_id)
            .order_by(CollectionError.occurred_at.asc(), CollectionError.id.asc())
        )
        return list(self.session.scalars(stmt).all())
