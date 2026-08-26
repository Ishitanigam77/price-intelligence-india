"""Product matching engine: compare two retailer-agnostic listings.

Independent of FastAPI routes and of specific retailer adapter packages. Callers supply
`MatchCandidate` values (optionally projected from `NormalizedProduct`).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.matching.config import MatchingConfig, get_matching_config
from app.matching.decision import decide
from app.matching.embeddings import EmbeddingProvider, build_embedding_provider
from app.matching.models import MatchCandidate, MatchResult
from app.matching.stages import MatchStage, default_stages
from app.observability.logging import get_logger
from app.observability.metrics import MetricsSink, NullMetricsSink

logger = get_logger(__name__)

MATCH_COMPARISONS = "matching.comparisons"
MATCH_CLASSIFICATIONS = "matching.classifications"


class MatchingEngine:
    """Run the four-stage matching pipeline (plus any injected extra stages)."""

    def __init__(
        self,
        config: MatchingConfig | None = None,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        stages: Sequence[MatchStage] | None = None,
        metrics_sink: MetricsSink | None = None,
    ) -> None:
        self._config = config if config is not None else get_matching_config()
        self._provider = build_embedding_provider(self._config, override=embedding_provider)
        self._stages: tuple[MatchStage, ...] = (
            tuple(stages) if stages is not None else default_stages(self._config, self._provider)
        )
        self._metrics: MetricsSink = metrics_sink if metrics_sink is not None else NullMetricsSink()

    @property
    def config(self) -> MatchingConfig:
        return self._config

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def stages(self) -> tuple[MatchStage, ...]:
        return self._stages

    def compare(self, left: MatchCandidate, right: MatchCandidate) -> MatchResult:
        """Compare two listings and return a fully explained match result."""
        evidence = tuple(stage.evaluate(left, right) for stage in self._stages)
        result = decide(
            evidence=evidence,
            config=self._config,
            left=left.provenance(),
            right=right.provenance(),
        )
        self._metrics.increment(
            MATCH_COMPARISONS,
            tags={"classification": result.classification.value},
        )
        self._metrics.increment(
            MATCH_CLASSIFICATIONS,
            tags={
                "classification": result.classification.value,
                "method": result.match_method.value,
            },
        )
        logger.info(
            "matching.compare_completed",
            extra={
                "classification": result.classification.value,
                "match_score": result.match_score,
                "match_method": result.match_method.value,
                "match_confidence": result.match_confidence.value,
                "left_retailer_id": left.retailer_id,
                "right_retailer_id": right.retailer_id,
                "left_retailer_sku": left.retailer_sku,
                "right_retailer_sku": right.retailer_sku,
                "contributing_stages": [stage.value for stage in result.contributing_stages],
            },
        )
        return result

    def find_best_match(
        self, candidate: MatchCandidate, catalog: Sequence[MatchCandidate]
    ) -> MatchResult | None:
        """Compare `candidate` to every catalog entry and return the strongest result.

        Ranking prefers `SAME_PRODUCT`, then `POSSIBLE_MATCH`, then `NEEDS_REVIEW`, then
        `DIFFERENT_PRODUCT`, breaking ties by `match_score`. Returns `None` when the catalog
        is empty. Never force-merges: the result still carries a non-`SAME_PRODUCT`
        classification when that is what the pipeline decided.
        """
        if not catalog:
            return None
        rank = {
            "SAME_PRODUCT": 0,
            "POSSIBLE_MATCH": 1,
            "NEEDS_REVIEW": 2,
            "DIFFERENT_PRODUCT": 3,
        }
        results = [self.compare(candidate, other) for other in catalog]
        results.sort(
            key=lambda item: (rank[item.classification.value], -item.match_score, item.explanation)
        )
        return results[0]
