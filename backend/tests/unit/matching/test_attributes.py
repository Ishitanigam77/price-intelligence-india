"""Stage 2: normalized attributes and variant separation."""

from app.matching.attributes import canonical_attribute_value, normalize_attribute_map
from app.matching.enums import MatchClassification, MatchMethod, MatchStageName
from tests.unit.matching.helpers import candidate, ident, make_engine


def test_storage_and_ram_units_canonicalize() -> None:
    assert canonical_attribute_value("storage", "128 GB") == canonical_attribute_value(
        "storage", "128gb"
    )
    assert canonical_attribute_value("ram", "8 GB") == "8gb"
    assert canonical_attribute_value("ram", "16GB") == "16gb"


def test_colour_alias_maps_to_color() -> None:
    normalized = normalize_attribute_map({"Colour": "Midnight", "Storage": "128 GB"})
    assert normalized["color"] == "midnight"
    assert normalized["storage"] == "128gb"


def test_different_storage_is_not_same_product() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G 128GB Midnight",
        variant_attributes={"storage": "128 GB", "color": "Midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Fictional Orchard Aurora 5G 256GB Midnight",
        retailer_id="mock-retailer-b",
        variant_attributes={"storage": "256 GB", "color": "Midnight", "model": "Aurora 5G"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert result.match_method is MatchMethod.NORMALIZED_ATTRIBUTES
    evidence = result.evidence_for(MatchStageName.NORMALIZED_ATTRIBUTES)
    assert evidence is not None
    assert evidence.details["variant_conflicts"]


def test_different_ram_is_not_same_product() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Ridgeline Notebook 14 16GB RAM 512GB",
        brand_name="Fictional Ridgeline",
        brand_slug="fictional-ridgeline",
        category_slug="laptops",
        variant_attributes={"ram": "16GB", "storage": "512GB", "model": "Notebook 14"},
    )
    right = candidate(
        title="Fictional Ridgeline Notebook 14 8GB RAM 512GB",
        retailer_id="mock-retailer-b",
        brand_name="Fictional Ridgeline",
        brand_slug="fictional-ridgeline",
        category_slug="laptops",
        variant_attributes={"ram": "8GB", "storage": "512GB", "model": "Notebook 14"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert "ram" in result.explanation.lower()


def test_different_colors_are_different_variants() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G 128GB Black",
        variant_attributes={"storage": "128GB", "color": "black", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Fictional Orchard Aurora 5G 128GB White",
        retailer_id="mock-retailer-b",
        variant_attributes={"storage": "128GB", "colour": "white", "model": "Aurora 5G"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert "color" in result.explanation.lower()


def test_different_generations_are_not_merged() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Hearthline Air Purifier 300 Gen 2",
        brand_name="Fictional Hearthline",
        brand_slug="fictional-hearthline",
        category_slug="home-appliances",
        variant_attributes={
            "generation": "2",
            "capacity": "300 sq ft",
            "model": "Air Purifier 300",
        },
    )
    right = candidate(
        title="Fictional Hearthline Air Purifier 300 Generation 3",
        retailer_id="mock-retailer-c",
        brand_name="Fictional Hearthline",
        brand_slug="fictional-hearthline",
        category_slug="home-appliances",
        variant_attributes={
            "generation": "3",
            "capacity": "300 sq ft",
            "model": "Air Purifier 300",
        },
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT


def test_different_capacity_is_not_same_product() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Hearthline Air Purifier 300",
        brand_name="Fictional Hearthline",
        brand_slug="fictional-hearthline",
        category_slug="home-appliances",
        variant_attributes={"capacity": "300 sq ft", "model": "Air Purifier 300"},
    )
    right = candidate(
        title="Fictional Hearthline Air Purifier 500",
        retailer_id="mock-retailer-c",
        brand_name="Fictional Hearthline",
        brand_slug="fictional-hearthline",
        category_slug="home-appliances",
        variant_attributes={"capacity": "500 sq ft", "model": "Air Purifier 500"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT


def test_accessory_versus_main_product() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G Smartphone 128GB Midnight",
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Case cover for Fictional Orchard Aurora 5G Midnight",
        retailer_id="mock-retailer-b",
        category_slug="mobile-accessories",
        variant_attributes={"color": "midnight", "model": "Aurora 5G Case"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert "accessor" in result.explanation.lower()


def test_missing_attribute_on_one_side_is_not_a_conflict() -> None:
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
        identifiers=(ident("gtin", "0000000002001"),),
        variant_attributes={"model": "Buds Pro"},
    )
    result = engine.compare(left, right)
    assert result.classification is MatchClassification.SAME_PRODUCT
    evidence = result.evidence_for(MatchStageName.NORMALIZED_ATTRIBUTES)
    assert evidence is not None
    assert evidence.details["variant_conflicts"] == []
