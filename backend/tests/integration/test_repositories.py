"""Integration tests for the repository layer (thin wrappers over common queries)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.brand_repository import BrandRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.repositories.seller_repository import SellerRepository
from tests.factories import (
    make_brand,
    make_category,
    make_price_snapshot,
    make_product,
    make_retailer,
    make_retailer_product,
    make_seller,
    make_variant,
)


def test_category_repository_get_by_slug(db_session: Session) -> None:
    repo = CategoryRepository(db_session)
    category = repo.add(make_category(slug="repo-electronics"))

    found = repo.get_by_slug("repo-electronics")
    assert found is not None
    assert found.id == category.id
    assert repo.get_by_slug("does-not-exist") is None


def test_brand_repository_get_by_slug(db_session: Session) -> None:
    repo = BrandRepository(db_session)
    brand = repo.add(make_brand(slug="repo-brand"))

    assert repo.get_by_slug("repo-brand").id == brand.id


def test_product_repository_lookups(db_session: Session) -> None:
    brand_repo = BrandRepository(db_session)
    category_repo = CategoryRepository(db_session)
    product_repo = ProductRepository(db_session)

    brand = brand_repo.add(make_brand())
    category = category_repo.add(make_category())
    product = product_repo.add(
        make_product(slug="repo-product", brand_id=brand.id, category_id=category.id)
    )

    assert product_repo.get_by_slug("repo-product").id == product.id
    assert [p.id for p in product_repo.list_by_brand(brand.id)] == [product.id]
    assert [p.id for p in product_repo.list_by_category(category.id)] == [product.id]


def test_product_repository_search_active_by_name(db_session: Session) -> None:
    product_repo = ProductRepository(db_session)
    visible = product_repo.add(make_product(name="DEVELOPMENT FIXTURE Searchable Phone Z"))
    product_repo.add(make_product(name="Unrelated Fixture Speaker"))
    hidden = make_product(name="DEVELOPMENT FIXTURE Hidden Phone Z", is_active=False)
    product_repo.add(hidden)

    found = product_repo.search_active_by_name("Searchable Phone")
    assert [item.id for item in found] == [visible.id]
    assert product_repo.search_active_by_name("   ") == []


def test_product_variant_repository_get_by_attributes(db_session: Session) -> None:
    product_repo = ProductRepository(db_session)
    variant_repo = ProductVariantRepository(db_session)

    product = product_repo.add(make_product())
    variant = variant_repo.add(make_variant(product, attributes={"storage": "64GB"}))

    found = variant_repo.get_by_attributes(product.id, {"Storage": " 64GB "})
    assert found is not None
    assert found.id == variant.id

    assert variant_repo.get_by_attributes(product.id, {"storage": "256gb"}) is None
    assert [v.id for v in variant_repo.list_for_product(product.id)] == [variant.id]


def test_retailer_repository_lookups(db_session: Session) -> None:
    repo = RetailerRepository(db_session)
    active = repo.add(make_retailer(slug="repo-retailer-active", is_active=True))
    inactive = repo.add(make_retailer(slug="repo-retailer-inactive", is_active=False))

    assert repo.get_by_slug("repo-retailer-active").id == active.id
    active_ids = {r.id for r in repo.list_active()}
    assert active.id in active_ids
    assert inactive.id not in active_ids


def test_seller_repository_lookups(db_session: Session) -> None:
    retailer_repo = RetailerRepository(db_session)
    seller_repo = SellerRepository(db_session)

    retailer = retailer_repo.add(make_retailer())
    first_party = seller_repo.add(make_seller(retailer, name="First Party", is_first_party=True))
    seller_repo.add(make_seller(retailer, name="Third Party", is_first_party=False))

    assert len(seller_repo.list_for_retailer(retailer.id)) == 2
    assert seller_repo.get_first_party_seller(retailer.id).id == first_party.id


def test_retailer_product_repository_lookups(db_session: Session) -> None:
    product_repo = ProductRepository(db_session)
    variant_repo = ProductVariantRepository(db_session)
    retailer_repo = RetailerRepository(db_session)
    retailer_product_repo = RetailerProductRepository(db_session)

    product = product_repo.add(make_product())
    variant = variant_repo.add(make_variant(product))
    retailer = retailer_repo.add(make_retailer())
    rp = retailer_product_repo.add(
        make_retailer_product(variant, retailer, retailer_sku="REPO-SKU-1")
    )

    found = retailer_product_repo.get_by_retailer_and_sku(retailer.id, "REPO-SKU-1")
    assert found is not None
    assert found.id == rp.id
    assert [r.id for r in retailer_product_repo.list_for_variant(variant.id)] == [rp.id]


def test_price_snapshot_repository_add_and_query(db_session: Session) -> None:
    product_repo = ProductRepository(db_session)
    variant_repo = ProductVariantRepository(db_session)
    retailer_repo = RetailerRepository(db_session)
    retailer_product_repo = RetailerProductRepository(db_session)
    snapshot_repo = PriceSnapshotRepository(db_session)

    product = product_repo.add(make_product())
    variant = variant_repo.add(make_variant(product))
    retailer = retailer_repo.add(make_retailer())
    rp = retailer_product_repo.add(make_retailer_product(variant, retailer))

    now = datetime.now(UTC)
    snapshot_repo.add_snapshot(
        make_price_snapshot(rp, displayed_price=Decimal("100"), observed_at=now - timedelta(days=1))
    )
    latest = snapshot_repo.add_snapshot(
        make_price_snapshot(rp, displayed_price=Decimal("90"), observed_at=now)
    )

    assert snapshot_repo.latest_for_retailer_product(rp.id).id == latest.id
    assert len(snapshot_repo.history_for_retailer_product(rp.id)) == 2
    product_history = snapshot_repo.history_for_product(product.id)
    assert [snap.displayed_price for snap in product_history] == [
        Decimal("100"),
        Decimal("90"),
    ]


def test_price_snapshot_repository_history_for_product_isolates_variants(
    db_session: Session,
) -> None:
    product = ProductRepository(db_session).add(make_product())
    variant_a = ProductVariantRepository(db_session).add(
        make_variant(product, attributes={"storage": "128GB", "color": "Black"})
    )
    variant_b = ProductVariantRepository(db_session).add(
        make_variant(product, attributes={"storage": "256GB", "color": "Black"})
    )
    retailer = RetailerRepository(db_session).add(make_retailer())
    listing_a = RetailerProductRepository(db_session).add(
        make_retailer_product(variant_a, retailer, retailer_sku="HIST-128")
    )
    listing_b = RetailerProductRepository(db_session).add(
        make_retailer_product(variant_b, retailer, retailer_sku="HIST-256")
    )
    now = datetime.now(UTC)
    snapshot_repo = PriceSnapshotRepository(db_session)
    snapshot_repo.add_snapshot(
        make_price_snapshot(listing_a, displayed_price=Decimal("100"), observed_at=now)
    )
    snapshot_repo.add_snapshot(
        make_price_snapshot(listing_b, displayed_price=Decimal("200"), observed_at=now)
    )

    only_a = snapshot_repo.history_for_product(product.id, variant_id=variant_a.id)
    assert [snap.displayed_price for snap in only_a] == [Decimal("100")]
    both = snapshot_repo.history_for_product(product.id)
    assert {snap.displayed_price for snap in both} == {Decimal("100"), Decimal("200")}


def test_price_snapshot_repository_has_no_update_method(db_session: Session) -> None:
    """Price observations are immutable: the repository must not expose an `update` method."""
    assert not hasattr(PriceSnapshotRepository, "update")
