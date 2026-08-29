"""Repository for `CollectionJob`."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.collection_job import CollectionJob
from app.domain.enums import CollectionJobStatus, CollectionJobType
from app.repositories.base import BaseRepository


class CollectionJobRepository(BaseRepository[CollectionJob]):
    model = CollectionJob

    def get_by_idempotency_key(self, idempotency_key: str) -> CollectionJob | None:
        stmt = select(CollectionJob).where(CollectionJob.idempotency_key == idempotency_key)
        return self.session.scalars(stmt).first()

    def list_for_retailer(
        self,
        retailer_id: str,
        *,
        job_type: CollectionJobType | None = None,
        status: CollectionJobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CollectionJob]:
        stmt = select(CollectionJob).where(CollectionJob.retailer_id == retailer_id)
        if job_type is not None:
            stmt = stmt.where(CollectionJob.job_type == job_type)
        if status is not None:
            stmt = stmt.where(CollectionJob.status == status)
        stmt = stmt.order_by(CollectionJob.created_at.asc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())
