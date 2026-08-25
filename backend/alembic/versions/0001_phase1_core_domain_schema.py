"""Phase 1 core domain schema.

Introduces the Phase 1 core domain/database foundation: Category, Brand, Product,
ProductVariant, ProductIdentifier, Retailer, Seller, RetailerProduct, and PriceSnapshot, along
with their indexes, foreign keys, unique constraints, and check constraints.

Revision ID: 0001
Revises:
Create Date: 2026-08-25 07:34:22.947889

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "brands",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brands")),
        sa.UniqueConstraint("name", name=op.f("uq_brands_name")),
        sa.UniqueConstraint("slug", name=op.f("uq_brands_slug")),
    )
    op.create_table(
        "categories",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            ["parent_id"],
            ["categories.id"],
            name=op.f("fk_categories_parent_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name=op.f("uq_categories_slug")),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"], unique=False)
    op.create_table(
        "retailers",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retailers")),
        sa.UniqueConstraint("name", name=op.f("uq_retailers_name")),
        sa.UniqueConstraint("slug", name=op.f("uq_retailers_slug")),
    )
    op.create_table(
        "products",
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=550), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            ["brand_id"],
            ["brands.id"],
            name=op.f("fk_products_brand_id_brands"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_products_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("slug", name=op.f("uq_products_slug")),
    )
    op.create_index("ix_products_brand_id", "products", ["brand_id"], unique=False)
    op.create_index("ix_products_category_id", "products", ["category_id"], unique=False)
    op.create_table(
        "sellers",
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("external_seller_id", sa.String(length=200), nullable=True),
        sa.Column("is_first_party", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            ["retailer_id"],
            ["retailers.id"],
            name=op.f("fk_sellers_retailer_id_retailers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sellers")),
    )
    op.create_index(op.f("ix_sellers_retailer_id"), "sellers", ["retailer_id"], unique=False)
    op.create_index(
        "uq_sellers_one_first_party_per_retailer",
        "sellers",
        ["retailer_id"],
        unique=True,
        postgresql_where=sa.text("is_first_party"),
    )
    op.create_index(
        "uq_sellers_retailer_id_external_seller_id",
        "sellers",
        ["retailer_id", "external_seller_id"],
        unique=True,
        postgresql_where=sa.text("external_seller_id IS NOT NULL"),
    )
    op.create_table(
        "product_variants",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("variant_key", sa.String(length=1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variants")),
        sa.UniqueConstraint(
            "product_id", "variant_key", name="uq_product_variants_product_variant_key"
        ),
    )
    op.create_index(
        op.f("ix_product_variants_product_id"), "product_variants", ["product_id"], unique=False
    )
    op.create_table(
        "product_identifiers",
        sa.Column("product_variant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "identifier_type",
            sa.Enum("gtin", "ean", "upc", "isbn", "mpn", "other", name="product_identifier_type"),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=64), nullable=False),
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
            ["product_variant_id"],
            ["product_variants.id"],
            name=op.f("fk_product_identifiers_product_variant_id_product_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_identifiers")),
        sa.UniqueConstraint(
            "identifier_type", "value", name="uq_product_identifiers_identifier_type_value"
        ),
    )
    op.create_index(
        op.f("ix_product_identifiers_product_variant_id"),
        "product_identifiers",
        ["product_variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_identifiers_value"), "product_identifiers", ["value"], unique=False
    )
    op.create_table(
        "retailer_products",
        sa.Column("product_variant_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_sku", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
            ["product_variant_id"],
            ["product_variants.id"],
            name=op.f("fk_retailer_products_product_variant_id_product_variants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retailer_id"],
            ["retailers.id"],
            name=op.f("fk_retailer_products_retailer_id_retailers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retailer_products")),
        sa.UniqueConstraint(
            "retailer_id", "retailer_sku", name="uq_retailer_products_retailer_id_retailer_sku"
        ),
    )
    op.create_index(
        "ix_retailer_products_product_variant_id",
        "retailer_products",
        ["product_variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_retailer_products_retailer_id"), "retailer_products", ["retailer_id"], unique=False
    )
    op.create_table(
        "price_snapshots",
        sa.Column("retailer_product_id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("mrp", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("displayed_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("effective_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("delivery_fee", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("platform_fee", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "availability",
            sa.Enum(
                "in_stock", "out_of_stock", "limited_stock", "unknown", name="availability_status"
            ),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum(
                "official_api",
                "affiliate_feed",
                "product_feed",
                "other_permitted",
                name="source_type",
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "confidence", sa.Enum("high", "medium", "low", name="confidence_level"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "delivery_fee IS NULL OR delivery_fee >= 0",
            name=op.f("ck_price_snapshots_delivery_fee_non_negative"),
        ),
        sa.CheckConstraint(
            "displayed_price >= 0", name=op.f("ck_price_snapshots_displayed_price_non_negative")
        ),
        sa.CheckConstraint(
            "effective_price IS NULL OR effective_price >= 0",
            name=op.f("ck_price_snapshots_effective_price_non_negative"),
        ),
        sa.CheckConstraint(
            "mrp IS NULL OR mrp >= 0", name=op.f("ck_price_snapshots_mrp_non_negative")
        ),
        sa.CheckConstraint(
            "platform_fee IS NULL OR platform_fee >= 0",
            name=op.f("ck_price_snapshots_platform_fee_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["retailer_product_id"],
            ["retailer_products.id"],
            name=op.f("fk_price_snapshots_retailer_product_id_retailer_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"],
            ["sellers.id"],
            name=op.f("fk_price_snapshots_seller_id_sellers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_snapshots")),
    )
    op.create_index(
        "ix_price_snapshots_observed_at", "price_snapshots", ["observed_at"], unique=False
    )
    op.create_index(
        "ix_price_snapshots_retailer_product_id_observed_at",
        "price_snapshots",
        ["retailer_product_id", "observed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_price_snapshots_seller_id"), "price_snapshots", ["seller_id"], unique=False
    )
    op.create_index(
        "uq_price_snapshots_dedupe",
        "price_snapshots",
        [
            "retailer_product_id",
            "observed_at",
            sa.literal_column("COALESCE(seller_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
        ],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_price_snapshots_dedupe", table_name="price_snapshots")
    op.drop_index(op.f("ix_price_snapshots_seller_id"), table_name="price_snapshots")
    op.drop_index(
        "ix_price_snapshots_retailer_product_id_observed_at", table_name="price_snapshots"
    )
    op.drop_index("ix_price_snapshots_observed_at", table_name="price_snapshots")
    op.drop_table("price_snapshots")
    # Native Postgres ENUM types are not dropped automatically when the table that used them
    # is dropped; drop them explicitly so `downgrade` fully reverses `upgrade`.
    sa.Enum(name="confidence_level").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="source_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="availability_status").drop(op.get_bind(), checkfirst=True)
    op.drop_index(op.f("ix_retailer_products_retailer_id"), table_name="retailer_products")
    op.drop_index("ix_retailer_products_product_variant_id", table_name="retailer_products")
    op.drop_table("retailer_products")
    op.drop_index(op.f("ix_product_identifiers_value"), table_name="product_identifiers")
    op.drop_index(
        op.f("ix_product_identifiers_product_variant_id"), table_name="product_identifiers"
    )
    op.drop_table("product_identifiers")
    sa.Enum(name="product_identifier_type").drop(op.get_bind(), checkfirst=True)
    op.drop_index(op.f("ix_product_variants_product_id"), table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_index(
        "uq_sellers_retailer_id_external_seller_id",
        table_name="sellers",
        postgresql_where=sa.text("external_seller_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_sellers_one_first_party_per_retailer",
        table_name="sellers",
        postgresql_where=sa.text("is_first_party"),
    )
    op.drop_index(op.f("ix_sellers_retailer_id"), table_name="sellers")
    op.drop_table("sellers")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_index("ix_products_brand_id", table_name="products")
    op.drop_table("products")
    op.drop_table("retailers")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")
    op.drop_table("brands")
