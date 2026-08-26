"""Product identity matching engine.

Resolves whether two retailer-agnostic listings refer to the same physical product variant.
The pipeline is independent of FastAPI routes and of specific retailer adapters.
"""

from app.matching.config import MatchingConfig, get_matching_config
from app.matching.embeddings import (
    EmbeddingProvider,
    HashingNgramEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    StaticEmbeddingProvider,
    build_embedding_provider,
    cosine_similarity,
)
from app.matching.engine import MatchingEngine
from app.matching.enums import (
    MatchClassification,
    MatchConfidence,
    MatchIdentifierType,
    MatchMethod,
    MatchStageName,
)
from app.matching.evaluation import EvaluationReport, evaluate_predictions
from app.matching.models import (
    ListingProvenance,
    MatchCandidate,
    MatchIdentifier,
    MatchResult,
    StageEvidence,
)
from app.matching.stages import MatchStage, default_stages

__all__ = [
    "EmbeddingProvider",
    "EvaluationReport",
    "HashingNgramEmbeddingProvider",
    "ListingProvenance",
    "MatchCandidate",
    "MatchClassification",
    "MatchConfidence",
    "MatchIdentifier",
    "MatchIdentifierType",
    "MatchMethod",
    "MatchResult",
    "MatchStage",
    "MatchStageName",
    "MatchingConfig",
    "MatchingEngine",
    "SentenceTransformerEmbeddingProvider",
    "StageEvidence",
    "StaticEmbeddingProvider",
    "build_embedding_provider",
    "cosine_similarity",
    "default_stages",
    "evaluate_predictions",
    "get_matching_config",
]
