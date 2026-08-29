"""Phase 13 collection job and collection error schema.

Adds `collection_jobs` and `collection_errors` so background collection runs persist status,
retries, duration, and sanitized failures independently per retailer.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-29 09:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "collection_jobs",
        sa.Column(
            "job_type",
            sa.Enum(
                "product_search",
                "product_refresh",
                "price_refresh",
                "availability_refresh",
                "sale_event_refresh",
                name="collection_job_type",
            ),
            nullable=False,
        ),
        sa.Column("retailer_id", sa.String(length=220), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "success",
                "partial_success",
                "failed",
                name="collection_job_status",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=512), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_jobs")),
        sa.UniqueConstraint("idempotency_key", name="uq_collection_jobs_idempotency_key"),
    )
    op.create_index("ix_collection_jobs_status", "collection_jobs", ["status"], unique=False)
    op.create_index("ix_collection_jobs_job_type", "collection_jobs", ["job_type"], unique=False)
    op.create_index(
        "ix_collection_jobs_retailer_id", "collection_jobs", ["retailer_id"], unique=False
    )
    op.create_index(
        "ix_collection_jobs_started_at", "collection_jobs", ["started_at"], unique=False
    )

    op.create_table(
        "collection_errors",
        sa.Column("collection_job_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.String(length=220), nullable=False),
        sa.Column(
            "error_category",
            sa.Enum(
                "timeout",
                "rate_limited",
                "temporary_failure",
                "validation",
                "permanent",
                "configuration",
                "unexpected",
                name="collection_error_category",
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=True),
        sa.Column("operation_target", sa.String(length=500), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_job_id"],
            ["collection_jobs.id"],
            name=op.f("fk_collection_errors_collection_job_id_collection_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_errors")),
    )
    op.create_index(
        "ix_collection_errors_collection_job_id",
        "collection_errors",
        ["collection_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_collection_errors_retailer_id",
        "collection_errors",
        ["retailer_id"],
        unique=False,
    )
    op.create_index(
        "ix_collection_errors_error_category",
        "collection_errors",
        ["error_category"],
        unique=False,
    )
    op.create_index(
        "ix_collection_errors_occurred_at",
        "collection_errors",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_collection_errors_occurred_at", table_name="collection_errors")
    op.drop_index("ix_collection_errors_error_category", table_name="collection_errors")
    op.drop_index("ix_collection_errors_retailer_id", table_name="collection_errors")
    op.drop_index("ix_collection_errors_collection_job_id", table_name="collection_errors")
    op.drop_table("collection_errors")
    sa.Enum(name="collection_error_category").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_collection_jobs_started_at", table_name="collection_jobs")
    op.drop_index("ix_collection_jobs_retailer_id", table_name="collection_jobs")
    op.drop_index("ix_collection_jobs_job_type", table_name="collection_jobs")
    op.drop_index("ix_collection_jobs_status", table_name="collection_jobs")
    op.drop_table("collection_jobs")
    sa.Enum(name="collection_job_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="collection_job_type").drop(op.get_bind(), checkfirst=True)
