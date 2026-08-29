"""BUY_NOW / WAIT / WATCH recommendation engine.

Deterministic, explainable rules over current/historical prices, upcoming sale events, and
optional Phase 10 predictions. Independent of FastAPI, named retailer adapters, XGBoost, and
generative AI.
"""

from app.recommendation.config import (
    RECOMMENDATION_DISCLAIMER,
    RecommendationConfig,
    get_recommendation_config,
)
from app.recommendation.engine import RecommendationEngine, input_from_variant_history
from app.recommendation.enums import (
    InsufficientRecommendationReason,
    Recommendation,
    RuleId,
)
from app.recommendation.models import (
    PredictionInput,
    RecommendationInput,
    RecommendationResult,
    UpcomingSaleInput,
)

__all__ = [
    "InsufficientRecommendationReason",
    "PredictionInput",
    "RECOMMENDATION_DISCLAIMER",
    "Recommendation",
    "RecommendationConfig",
    "RecommendationEngine",
    "RecommendationInput",
    "RecommendationResult",
    "RuleId",
    "UpcomingSaleInput",
    "get_recommendation_config",
    "input_from_variant_history",
]
