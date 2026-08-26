"""Stage 3: normalized title / token similarity."""

from app.matching.enums import MatchClassification, MatchMethod
from app.matching.titles import title_similarity, title_tokens
from tests.unit.matching.helpers import candidate, ident, make_config, make_engine


def test_punctuation_and_word_order_do_not_block_similarity() -> None:
    config = make_config()
    details = title_similarity(
        "Fictional Orchard Aurora 5G Smartphone (128 GB, Midnight)",
        "Aurora 5G (128GB, Midnight) - Fictional Orchard",
        config,
    )
    assert float(details["score"]) >= 0.6
    left_tokens = set(title_tokens("Fictional Orchard Aurora 5G Smartphone (128 GB, Midnight)"))
    right_tokens = set(title_tokens("Aurora 5G (128GB, Midnight) - Fictional Orchard"))
    assert "aurora" in left_tokens and "aurora" in right_tokens


def test_spelling_differences_still_score_high() -> None:
    config = make_config()
    details = title_similarity(
        "Fictional Orchard Aurora 5G Smartphone",
        "Fictional Orchard Aurora 5G Smartphne",
        config,
    )
    assert float(details["score"]) >= 0.75


def test_title_similarity_alone_never_classifies_same_product() -> None:
    engine = make_engine()
    left = candidate(
        title="Pocket lantern compact travel light graphite",
        brand_name="Fictional Orchard",
        brand_slug="fictional-orchard",
        variant_attributes={"color": "graphite", "model": "Pocket Lantern"},
    )
    right = candidate(
        title="Pocket lantern compact travel light graphite",
        retailer_id="mock-retailer-b",
        brand_name="Fictional Hearthline",
        brand_slug="fictional-hearthline",
        variant_attributes={"color": "graphite", "model": "Pocket Lantern"},
    )
    result = engine.compare(left, right)
    assert result.classification is not MatchClassification.SAME_PRODUCT
    assert result.match_method is not MatchMethod.TITLE_TOKEN_SIMILARITY


def test_high_title_score_is_recorded_as_evidence() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G Smartphone 128GB Midnight",
        identifiers=(ident("gtin", "0000000001001"),),
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Aurora 5G 128 GB Midnight Fictional Orchard",
        retailer_id="mock-retailer-b",
        identifiers=(ident("gtin", "0000000001001"),),
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    result = engine.compare(left, right)
    title_evidence = result.evidence[2]
    assert title_evidence.score is not None
    assert title_evidence.score >= 0.6
    assert "title" in result.explanation.lower()
