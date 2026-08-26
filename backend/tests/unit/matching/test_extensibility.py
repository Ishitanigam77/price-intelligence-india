"""The matching engine can be extended without editing existing stages."""

from app.matching import MatchingEngine
from app.matching.embeddings import StaticEmbeddingProvider
from app.matching.enums import MatchStageName
from app.matching.models import MatchCandidate, StageEvidence
from app.matching.stages import default_stages
from tests.unit.matching.helpers import candidate, make_config


class ExtraNoteStage:
    """Fixture-only extra stage proving the pipeline is injectable."""

    @property
    def name(self) -> MatchStageName:
        return MatchStageName.TITLE_TOKEN_SIMILARITY

    def evaluate(self, left: MatchCandidate, right: MatchCandidate) -> StageEvidence:
        _ = left, right
        return StageEvidence(
            stage=MatchStageName.TITLE_TOKEN_SIMILARITY,
            applicable=True,
            score=0.5,
            summary="custom extra stage",
            details={"custom": True},
        )


def test_custom_embedding_provider_is_used() -> None:
    provider = StaticEmbeddingProvider(
        {
            "alpha": (1.0, 0.0, 0.0),
            "beta": (1.0, 0.0, 0.0),
        },
        name="custom-static",
    )
    engine = MatchingEngine(make_config(), embedding_provider=provider)
    assert engine.embedding_provider is provider
    left = candidate(title="alpha", variant_attributes={"color": "black", "model": "Alpha"})
    right = candidate(
        title="beta",
        retailer_id="mock-retailer-b",
        variant_attributes={"color": "black", "model": "Alpha"},
    )
    result = engine.compare(left, right)
    embedding = result.evidence_for(MatchStageName.EMBEDDING_SIMILARITY)
    assert embedding is not None
    assert embedding.details["backend"] == "custom-static"


def test_stages_can_be_replaced_without_changing_engine() -> None:
    config = make_config()
    provider = StaticEmbeddingProvider(name="custom-static")
    original = default_stages(config, provider)
    # Replace the title stage with a custom implementation; other stages stay.
    stages = (original[0], original[1], ExtraNoteStage(), original[3])
    engine = MatchingEngine(config, embedding_provider=provider, stages=stages)
    result = engine.compare(
        candidate(
            title="Fictional Orchard Aurora 5G 128GB Midnight",
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
        candidate(
            title="Aurora 5G 128GB Midnight Fictional Orchard",
            retailer_id="mock-retailer-b",
            variant_attributes={"storage": "128GB", "color": "midnight", "model": "Aurora 5G"},
        ),
    )
    title = result.evidence_for(MatchStageName.TITLE_TOKEN_SIMILARITY)
    assert title is not None
    assert title.details["custom"] is True
    assert title.summary == "custom extra stage"
    assert result.classification is not None
