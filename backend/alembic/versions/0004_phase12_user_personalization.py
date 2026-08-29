"""Phase 12 user authentication and personalization schema.

Adds the internal user mapping (Clerk user id → PostgreSQL user) plus user-owned watchlists,
saved products, target prices, price alerts, and preferences. No password columns.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29 08:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("clerk_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("clerk_user_id", name=op.f("uq_users_clerk_user_id")),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_alerts_enabled", sa.Boolean(), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_preferences_user_id")),
    )
    op.create_table(
        "watchlists",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_watchlists_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_watchlists_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlists")),
        sa.UniqueConstraint("user_id", "product_id", name=op.f("uq_watchlists_user_id_product_id")),
    )
    op.create_index(op.f("ix_watchlists_product_id"), "watchlists", ["product_id"], unique=False)
    op.create_index(op.f("ix_watchlists_user_id"), "watchlists", ["user_id"], unique=False)
    op.create_table(
        "saved_products",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_saved_products_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_saved_products_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_products")),
        sa.UniqueConstraint(
            "user_id", "product_id", name=op.f("uq_saved_products_user_id_product_id")
        ),
    )
    op.create_index(
        op.f("ix_saved_products_product_id"), "saved_products", ["product_id"], unique=False
    )
    op.create_index(op.f("ix_saved_products_user_id"), "saved_products", ["user_id"], unique=False)
    op.create_table(
        "target_prices",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
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
        sa.CheckConstraint("amount >= 0", name=op.f("ck_target_prices_amount_non_negative")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_target_prices_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_target_prices_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_target_prices")),
        sa.UniqueConstraint(
            "user_id", "product_id", name=op.f("uq_target_prices_user_id_product_id")
        ),
    )
    op.create_index(
        op.f("ix_target_prices_product_id"), "target_prices", ["product_id"], unique=False
    )
    op.create_index(op.f("ix_target_prices_user_id"), "target_prices", ["user_id"], unique=False)
    op.create_table(
        "price_alerts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("threshold_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
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
            "threshold_amount >= 0",
            name=op.f("ck_price_alerts_threshold_amount_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_price_alerts_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_price_alerts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_alerts")),
        sa.UniqueConstraint(
            "user_id", "product_id", name=op.f("uq_price_alerts_user_id_product_id")
        ),
    )
    op.create_index(
        op.f("ix_price_alerts_product_id"), "price_alerts", ["product_id"], unique=False
    )
    op.create_index(op.f("ix_price_alerts_user_id"), "price_alerts", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_price_alerts_user_id"), table_name="price_alerts")
    op.drop_index(op.f("ix_price_alerts_product_id"), table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index(op.f("ix_target_prices_user_id"), table_name="target_prices")
    op.drop_index(op.f("ix_target_prices_product_id"), table_name="target_prices")
    op.drop_table("target_prices")
    op.drop_index(op.f("ix_saved_products_user_id"), table_name="saved_products")
    op.drop_index(op.f("ix_saved_products_product_id"), table_name="saved_products")
    op.drop_table("saved_products")
    op.drop_index(op.f("ix_watchlists_user_id"), table_name="watchlists")
    op.drop_index(op.f("ix_watchlists_product_id"), table_name="watchlists")
    op.drop_table("watchlists")
    op.drop_table("user_preferences")
    op.drop_table("users")
