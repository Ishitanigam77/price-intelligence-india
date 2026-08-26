"""End-to-end matching engine: classification, scores, methods, and Phase 4 models."""

from datetime import UTC, datetime

from app.domain.enums import ProductIdentifierType, SourceType
from app.matching import MatchCandidate
from app.matching.enums import MatchClassification, MatchConfidence, MatchMethod, MatchStageName
from app.retailer_adapters.base.models import NormalizedProduct, ProductIdentifierValue
from tests.unit.matching.helpers import candidate, ident, make_engine


def _normalized(
    *,
    retailer_id: str,
    retailer_sku: str,
    title: str,
    brand_name: str,
    brand_slug: str,
    category_slug: str,
    attributes: dict[str, str],
    identifiers: tuple[ProductIdentifierValue, ...] = (),
) -> NormalizedProduct:
    return NormalizedProduct(
        retailer_id=retailer_id,
        retailer_sku=retailer_sku,
        normalized_title=title,
        brand_name=brand_name,
        brand_slug=brand_slug,
        category_slug=category_slug,
        variant_attributes=attributes,
        identifiers=identifiers,
        source_url=f"https://{retailer_id}.example.test/p/{retailer_sku}",
        source_type=SourceType.OFFICIAL_API,
        normalized_at=datetime(2026, 1, 15, tzinfo=UTC),
    )


def test_result_includes_required_output_fields() -> None:
    engine = make_engine()
    result = engine.compare(
        candidate(
            title="Fictional Orchard Aurora 5G 128GB Midnight",
            identifiers=(ident("gtin", "0000000001001"),),
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
        candidate(
            title="Aurora 5G 128GB Midnight Fictional Orchard",
            retailer_id="mock-retailer-b",
            identifiers=(ident("gtin", "0000000001001"),),
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
    )
    assert result.classification in set(MatchClassification)
    assert 0.0 <= result.match_score <= 1.0
    assert result.match_method in set(MatchMethod)
    assert result.match_confidence in set(MatchConfidence)
    assert result.explanation
    assert result.left.retailer_id == "mock-retailer-a"
    assert result.right.retailer_id == "mock-retailer-b"
    assert result.left.source_url
    assert result.right.source_url
    assert MatchStageName.EXACT_IDENTIFIERS in result.contributing_stages


def test_from_normalized_product_reuses_phase2_shape() -> None:
    left = MatchCandidate.from_normalized_product(
        _normalized(
            retailer_id="mock-retailer-a",
            retailer_sku="a-1",
            title="Fictional Orchard Aurora 5G Smartphone 128GB Midnight",
            brand_name="Fictional Orchard",
            brand_slug="fictional-orchard",
            category_slug="mobiles",
            attributes={"storage": "128 GB", "color": "Midnight", "model": "Aurora 5G"},
            identifiers=(
                ProductIdentifierValue(
                    identifier_type=ProductIdentifierType.GTIN, value="0000000001001"
                ),
            ),
        )
    )
    right = MatchCandidate.from_normalized_product(
        _normalized(
            retailer_id="mock-retailer-b",
            retailer_sku="b-1",
            title="Aurora 5G (128GB, Midnight) - Fictional Orchard",
            brand_name="Fictional Orchard",
            brand_slug="fictional-orchard",
            category_slug="mobiles",
            attributes={"storage": "128GB", "colour": "Midnight", "model": "Aurora 5G"},
            identifiers=(
                ProductIdentifierValue(
                    identifier_type=ProductIdentifierType.MPN, value="FO-AUR-128-MID"
                ),
            ),
        )
    )
    result = make_engine().compare(left, right)
    assert result.classification is MatchClassification.SAME_PRODUCT
    assert result.left.retailer_id == "mock-retailer-a"
    assert result.right.retailer_id == "mock-retailer-b"


async def test_mock_adapter_listings_do_not_false_merge_storage_variants() -> None:
    from app.retailer_adapters.mock_retailer_a import create_adapter as create_a

    adapter = create_a(env={})
    left = MatchCandidate.from_normalized_product(
        adapter.normalize_product(await adapter.get_product("A-MOB-1001"))
    )
    right = MatchCandidate.from_normalized_product(
        adapter.normalize_product(await adapter.get_product("A-MOB-1002"))
    )
    result = make_engine().compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert result.match_method in {
        MatchMethod.NORMALIZED_ATTRIBUTES,
        MatchMethod.EXACT_IDENTIFIER,
    }


async def test_cross_retailer_naming_for_same_aurora_128() -> None:
    from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
    from app.retailer_adapters.mock_retailer_b import create_adapter as create_b

    left_adapter = create_a(env={})
    right_adapter = create_b(env={})
    left = MatchCandidate.from_normalized_product(
        left_adapter.normalize_product(await left_adapter.get_product("A-MOB-1001"))
    )
    right = MatchCandidate.from_normalized_product(
        right_adapter.normalize_product(await right_adapter.get_product("880011"))
    )
    result = make_engine().compare(left, right)
    assert result.classification is MatchClassification.SAME_PRODUCT
    assert result.match_score >= 0.78
    assert result.left.retailer_id == "mock-retailer-a"
    assert result.right.retailer_id == "mock-retailer-b"


def test_conflicting_identifiers_plus_similar_titles_still_differ() -> None:
    engine = make_engine()
    result = engine.compare(
        candidate(
            title="Fictional Orchard Aurora 5G Smartphone 128GB Midnight",
            identifiers=(ident("gtin", "0000000001001"),),
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
        candidate(
            title="Fictional Orchard Aurora 5G Smartphone 128GB Midnight",
            retailer_id="mock-retailer-b",
            identifiers=(ident("gtin", "0000000001999"),),
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
    )
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert result.match_method is MatchMethod.EXACT_IDENTIFIER


def test_identifier_match_with_variant_conflict_needs_review() -> None:
    engine = make_engine()
    result = engine.compare(
        candidate(
            title="Fictional Orchard Aurora 5G 128GB Midnight",
            identifiers=(ident("gtin", "0000000007777"),),
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
        candidate(
            title="Fictional Orchard Aurora 5G 256GB Midnight",
            retailer_id="mock-retailer-b",
            identifiers=(ident("ean", "0000000007777"),),
            variant_attributes={"storage": "256GB", "color": "midnight", "model": "Aurora 5G"},
        ),
    )
    assert result.classification is MatchClassification.NEEDS_REVIEW
    assert result.match_method is MatchMethod.CONFLICTING_EVIDENCE
    assert result.match_confidence is MatchConfidence.MEDIUM


def test_find_best_match_ranks_same_product_first() -> None:
    engine = make_engine()
    query = candidate(
        title="Fictional Orchard Aurora 5G 128GB Midnight",
        identifiers=(ident("gtin", "0000000001001"),),
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    catalog = (
        candidate(
            title="Fictional Hearthline Air Purifier 300",
            retailer_id="mock-retailer-c",
            retailer_sku="c-1",
            brand_name="Fictional Hearthline",
            brand_slug="fictional-hearthline",
            category_slug="home-appliances",
            variant_attributes={"capacity": "300 sq ft", "model": "Air Purifier 300"},
        ),
        candidate(
            title="Aurora 5G 128GB Midnight Fictional Orchard",
            retailer_id="mock-retailer-b",
            retailer_sku="b-1",
            identifiers=(ident("gtin", "0000000001001"),),
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
    )
    best = engine.find_best_match(query, catalog)
    assert best is not None
    assert best.classification is MatchClassification.SAME_PRODUCT
    assert best.right.retailer_id == "mock-retailer-b"


def test_find_best_match_empty_catalog() -> None:
    assert make_engine().find_best_match(candidate(title="Anything at all"), ()) is None
