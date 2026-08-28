"""Phase 9 sale-event intelligence schema.

Adds `sale_events` so retailer-specific, brand, category, seasonal, national-shopping,
manually curated, and externally sourced sale windows can be stored with provenance
(source + optional source_ref) and confidence. Lifecycle status is not stored; it is
derived from start_date/end_date.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-28 08:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sale_events",
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("brand_id", sa.Uuid(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "retailer_specific",
                "brand",
                "category",
                "seasonal",
                "national_shopping",
                "manually_curated",
                "externally_sourced",
                name="sale_event_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "manual_curation",
                "official_api",
                "affiliate_feed",
                "product_feed",
                "other_permitted",
                "observed_price_inference",
                name="sale_event_source",
            ),
            nullable=False,
        ),
        sa.Column("source_ref", sa.String(length=2048), nullable=True),
        sa.Column(
            "confidence",
            sa.Enum("high", "medium", "low", name="confidence_level", create_type=False),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "end_date >= start_date",
            name=op.f("ck_sale_events_end_date_not_before_start_date"),
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brands.id"],
            name=op.f("fk_sale_events_brand_id_brands"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_sale_events_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            name=op.f("fk_sale_events_retailer_id_retailers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_events")),
    )
    op.create_index("ix_sale_events_start_date", "sale_events", ["start_date"], unique=False)
    op.create_index("ix_sale_events_end_date", "sale_events", ["end_date"], unique=False)
    op.create_index("ix_sale_events_event_type", "sale_events", ["event_type"], unique=False)
    op.create_index("ix_sale_events_source", "sale_events", ["source"], unique=False)
    op.create_index("ix_sale_events_retailer_id", "sale_events", ["retailer_id"], unique=False)
    op.create_index("ix_sale_events_category_id", "sale_events", ["category_id"], unique=False)
    op.create_index("ix_sale_events_brand_id", "sale_events", ["brand_id"], unique=False)
    op.create_index(
        "ix_sale_events_start_date_end_date",
        "sale_events",
        ["start_date", "end_date"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sale_events_start_date_end_date", table_name="sale_events")
    op.drop_index("ix_sale_events_brand_id", table_name="sale_events")
    op.drop_index("ix_sale_events_category_id", table_name="sale_events")
    op.drop_index("ix_sale_events_retailer_id", table_name="sale_events")
    op.drop_index("ix_sale_events_source", table_name="sale_events")
    op.drop_index("ix_sale_events_event_type", table_name="sale_events")
    op.drop_index("ix_sale_events_end_date", table_name="sale_events")
    op.drop_index("ix_sale_events_start_date", table_name="sale_events")
    op.drop_table("sale_events")
    sa.Enum(name="sale_event_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sale_event_type").drop(op.get_bind(), checkfirst=True)
