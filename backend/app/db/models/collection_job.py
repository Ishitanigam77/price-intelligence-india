"""CollectionJob: persistent status of one background collection run for one retailer.

Phase 13 stores orchestration outcomes independently of Celery's in-memory/result-backend
state so a worker crash is still visible, and so repeated logical runs can be keyed by
`idempotency_key` without duplicating job rows.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import CollectionJobStatus, CollectionJobType

if TYPE_CHECKING:
    from app.db.models.collection_error import CollectionError


class CollectionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One collection attempt for one job type against one enabled retailer (or a fleet key)."""

    __tablename__ = "collection_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_collection_jobs_idempotency_key"),
        Index("ix_collection_jobs_status", "status"),
        Index("ix_collection_jobs_job_type", "job_type"),
        Index("ix_collection_jobs_retailer_id", "retailer_id"),
        Index("ix_collection_jobs_started_at", "started_at"),
    )

    job_type: Mapped[CollectionJobType] = mapped_column(
        SAEnum(
            CollectionJobType,
            name="collection_job_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    #: Adapter retailer slug (e.g. `mock-retailer-a`), not the ORM `Retailer.id` UUID.
    retailer_id: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[CollectionJobStatus] = mapped_column(
        SAEnum(
            CollectionJobStatus,
            name="collection_job_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=CollectionJobStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False)

    errors: Mapped[list["CollectionError"]] = relationship(
        "CollectionError",
        back_populates="collection_job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"CollectionJob(id={self.id!r}, job_type={self.job_type!r}, "
            f"retailer_id={self.retailer_id!r}, status={self.status!r})"
        )
