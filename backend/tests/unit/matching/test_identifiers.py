"""Stage 1: exact identifier matching after format normalization."""

from app.matching.enums import (
    MatchClassification,
    MatchConfidence,
    MatchIdentifierType,
    MatchMethod,
)
from app.matching.identifiers import normalize_barcode, normalize_isbn, normalize_part
from tests.unit.matching.helpers import candidate, ident, make_engine


def test_gtin_hyphens_and_spaces_normalize_to_same_value() -> None:
    assert normalize_barcode("0000-0000-01001") == normalize_barcode("0000000001001")
    assert normalize_barcode("  0000000001001 ") == normalize_barcode("0000000001001")


def test_upc_matches_ean13_with_leading_zero() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Ridgeline Notebook 14",
        identifiers=(ident(MatchIdentifierType.UPC, "123456789012"),),
        variant_attributes={"ram": "16GB", "storage": "512GB", "model": "Notebook 14"},
        brand_name="Fictional Ridgeline",
        brand_slug="fictional-ridgeline",
        category_slug="laptops",
    )
    right = candidate(
        title="Ridgeline Notebook 14 16GB 512GB",
        retailer_id="mock-retailer-b",
        retailer_sku="sku-2",
        identifiers=(ident(MatchIdentifierType.EAN, "0123456789012"),),
        variant_attributes={"ram": "16GB", "storage": "512GB", "model": "Notebook 14"},
        brand_name="Fictional Ridgeline",
        brand_slug="fictional-ridgeline",
        category_slug="laptops",
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.SAME_PRODUCT
    assert result.match_method is MatchMethod.EXACT_IDENTIFIER
    assert result.match_confidence is MatchConfidence.HIGH
    assert result.match_score >= 0.9


def test_isbn_hyphens_match() -> None:
    assert normalize_isbn("978-0-123456-47-2") == normalize_isbn("9780123456472")


def test_mpn_ignores_spaces_and_case() -> None:
    assert normalize_part("FO-AUR-128-MID") == normalize_part("fo aur 128 mid")


def test_missing_identifiers_are_not_a_match() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G 128GB Midnight",
        identifiers=(),
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Fictional Hearthline Air Purifier 300",
        retailer_id="mock-retailer-c",
        brand_name="Fictional Hearthline",
        brand_slug="fictional-hearthline",
        category_slug="home-appliances",
        identifiers=(),
        variant_attributes={"capacity": "300 sq ft", "color": "white", "model": "Air Purifier 300"},
    )
    result = engine.compare(left, right)
    identifier_evidence = result.evidence[0]
    assert identifier_evidence.applicable is False
    assert identifier_evidence.score is None
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT


def test_blank_normalized_identifier_is_not_a_match() -> None:
    assert normalize_barcode("---") is None
    assert normalize_part("***") is None


def test_conflicting_gtins_are_different_products() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G 128GB Midnight",
        identifiers=(ident("gtin", "0000000001001"),),
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Fictional Orchard Aurora 5G 128GB Midnight",
        retailer_id="mock-retailer-b",
        identifiers=(ident("gtin", "0000000001999"),),
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert result.match_method is MatchMethod.EXACT_IDENTIFIER
    assert result.match_confidence is MatchConfidence.HIGH
    assert "conflict" in result.explanation.lower()


def test_unilateral_identifier_is_not_a_conflict() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Wavecrest Buds Pro Charcoal",
        brand_name="Fictional Wavecrest",
        brand_slug="fictional-wavecrest",
        category_slug="audio",
        identifiers=(ident("gtin", "0000000002001"),),
        variant_attributes={"color": "charcoal", "model": "Buds Pro"},
    )
    right = candidate(
        title="Fictional Wavecrest Buds Pro",
        retailer_id="mock-retailer-c",
        brand_name="Fictional Wavecrest",
        brand_slug="fictional-wavecrest",
        category_slug="audio",
        identifiers=(),
        variant_attributes={"colour": "charcoal", "model": "Buds Pro"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.SAME_PRODUCT
    assert result.match_method is MatchMethod.NORMALIZED_ATTRIBUTES
