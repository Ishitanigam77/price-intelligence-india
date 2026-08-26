"""Stage 4: embedding cosine similarity and provider isolation."""

from app.matching.embeddings import (
    HashingNgramEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    StaticEmbeddingProvider,
    build_embedding_provider,
    cosine_similarity,
    reset_loaded_sentence_transformer_models,
)
from app.matching.enums import MatchClassification, MatchStageName
from tests.unit.matching.helpers import candidate, make_config, make_engine


def test_cosine_similarity_is_1_for_identical_vectors() -> None:
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == 0.0


def test_hashing_embeddings_are_higher_for_similar_titles() -> None:
    provider = HashingNgramEmbeddingProvider(dimension=256, cache_size=32)
    similar = provider.similarity(
        "fictional orchard aurora 5g smartphone 128gb midnight",
        "aurora 5g 128gb midnight fictional orchard",
    )
    different = provider.similarity(
        "fictional orchard aurora 5g smartphone 128gb midnight",
        "fictional hearthline air purifier 300 white",
    )
    assert similar > different
    assert similar >= 0.45


def test_hashing_provider_reuses_cached_vectors() -> None:
    provider = HashingNgramEmbeddingProvider(dimension=64, cache_size=8)
    first = provider.embed("aurora 5g midnight")
    second = provider.embed("aurora 5g midnight")
    assert first == second


def test_static_provider_returns_configured_vectors() -> None:
    provider = StaticEmbeddingProvider(
        {"alpha": (1.0, 0.0), "beta": (0.8, 0.6)},
        name="fixture-static",
    )
    assert provider.name == "fixture-static"
    assert cosine_similarity(provider.embed("alpha"), provider.embed("beta")) > 0.7


def test_sentence_transformer_provider_loads_model_once() -> None:
    reset_loaded_sentence_transformer_models()
    loads: list[str] = []

    class FakeModel:
        def encode(self, text: str, convert_to_numpy: bool = True, show_progress_bar: bool = False):
            _ = convert_to_numpy, show_progress_bar
            if "purifier" in text:
                return [0.0, 1.0]
            return [1.0, 0.0]

    def loader(name: str) -> FakeModel:
        loads.append(name)
        return FakeModel()

    first = SentenceTransformerEmbeddingProvider("unit-test-model", loader=loader, cache_size=8)
    second = SentenceTransformerEmbeddingProvider("unit-test-model", loader=loader, cache_size=8)
    left = first.embed("aurora phone")
    right = second.embed("aurora phone")
    other = first.embed("air purifier")
    assert loads == ["unit-test-model"]
    assert left == right
    assert cosine_similarity(left, other) == 0.0
    reset_loaded_sentence_transformer_models()


def test_build_embedding_provider_honours_override() -> None:
    config = make_config(embedding_backend="sentence_transformers")
    override = HashingNgramEmbeddingProvider(dimension=32)
    built = build_embedding_provider(config, override=override)
    assert built is override


def test_embeddings_do_not_override_variant_conflict() -> None:
    """Near-identical titles still cannot merge 128GB vs 256GB."""
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G Smartphone 128GB Midnight",
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Fictional Orchard Aurora 5G Smartphone 256GB Midnight",
        retailer_id="mock-retailer-b",
        variant_attributes={"storage": "256GB", "color": "midnight", "model": "Aurora 5G"},
    )
    result = engine.compare(left, right)
    embedding = result.evidence_for(MatchStageName.EMBEDDING_SIMILARITY)
    assert embedding is not None
    assert embedding.score is not None
    assert result.classification is MatchClassification.DIFFERENT_PRODUCT
    assert "embedding" in result.explanation.lower()


def test_embedding_similarity_is_present_on_same_product() -> None:
    engine = make_engine()
    left = candidate(
        title="Fictional Orchard Aurora 5G 128GB Midnight",
        variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
    )
    right = candidate(
        title="Aurora 5G 128GB Midnight Fictional Orchard",
        retailer_id="mock-retailer-b",
        variant_attributes={"storage": "128GB", "colour": "midnight", "model": "Aurora 5G"},
    )
    result = engine.compare(left, right)
    embedding = result.evidence_for(MatchStageName.EMBEDDING_SIMILARITY)
    assert embedding is not None
    assert embedding.applicable is True
    assert embedding.details["backend"].startswith("hashing_ngram")
    assert result.classification is MatchClassification.SAME_PRODUCT
