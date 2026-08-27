"""Phase 6 price-adjustment persistence.

Adds `price_adjustments` so promotional adjustments (coupon, payment discount, cashback, ...)
can be stored with source, eligibility, timestamp, and confidence. Existing `price_snapshots`
columns (displayed price, MRP, fees, source effective price) are unchanged.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "price_adjustments",
        sa.Column("price_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "coupon",
                "payment_discount",
                "cashback",
                "delivery_fee",
                "platform_fee",
                "displayed_discount",
                "other",
                name="adjustment_kind",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("source", sa.String(length=500), nullable=False),
        sa.Column(
            "eligibility",
            sa.Enum(
                "verified_eligible",
                "ineligible",
                "unverified",
                "unavailable",
                "membership_only",
                "payment_method_specific",
                "conditional",
                name="adjustment_eligibility",
            ),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "confidence",
            sa.Enum("high", "medium", "low", name="confidence_level", create_type=False),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "amount IS NULL OR amount >= 0",
            name=op.f("ck_price_adjustments_amount_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["price_snapshot_id"],
            ["price_snapshots.id"],
            name=op.f("fk_price_adjustments_price_snapshot_id_price_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_adjustments")),
    )
    op.create_index(
        "ix_price_adjustments_price_snapshot_id",
        "price_adjustments",
        ["price_snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_price_adjustments_price_snapshot_id", table_name="price_adjustments")
    op.drop_table("price_adjustments")
    sa.Enum(name="adjustment_eligibility").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="adjustment_kind").drop(op.get_bind(), checkfirst=True)
