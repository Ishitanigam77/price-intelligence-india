"""CollectionError: one captured failure during a collection job.

Messages are sanitized before insert — credentials, tokens, and authorization headers must
never be stored. A failure for one retailer is recorded here without aborting other retailers.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin
from app.domain.enums import CollectionErrorCategory

if TYPE_CHECKING:
    from app.db.models.collection_job import CollectionJob


class CollectionError(UUIDPrimaryKeyMixin, Base):
    """A single retailer/operation failure attached to a `CollectionJob`."""

    __tablename__ = "collection_errors"
    __table_args__ = (
        Index("ix_collection_errors_collection_job_id", "collection_job_id"),
        Index("ix_collection_errors_retailer_id", "retailer_id"),
        Index("ix_collection_errors_error_category", "error_category"),
        Index("ix_collection_errors_occurred_at", "occurred_at"),
    )

    collection_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collection_jobs.id", ondelete="CASCADE"), nullable=False
    )
    retailer_id: Mapped[str] = mapped_column(String(220), nullable=False)
    error_category: Mapped[CollectionErrorCategory] = mapped_column(
        SAEnum(
            CollectionErrorCategory,
            name="collection_error_category",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    operation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operation_target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    collection_job: Mapped["CollectionJob"] = relationship(
        "CollectionJob", back_populates="errors"
    )

    def __repr__(self) -> str:
        return (
            f"CollectionError(id={self.id!r}, collection_job_id={self.collection_job_id!r}, "
            f"retailer_id={self.retailer_id!r}, error_category={self.error_category!r})"
        )
