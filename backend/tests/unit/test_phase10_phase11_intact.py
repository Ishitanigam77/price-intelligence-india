"""Phase 10, Phase 11, and Phase 12 entrypoints remain importable after Phase 13 collection."""

from app.auth.identity import ClerkIdentity
from app.auth.tokens import ClerkTokenVerifier, decode_clerk_payload
from app.recommendation.engine import RecommendationEngine
from app.services.recommendation_service import RecommendationService
from app.services.sale_price_prediction_service import SalePricePredictionService
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistService


def test_phase10_prediction_service_is_still_present() -> None:
    assert SalePricePredictionService.__name__ == "SalePricePredictionService"


def test_phase11_recommendation_engine_is_still_present() -> None:
    assert RecommendationEngine.__name__ == "RecommendationEngine"
    assert RecommendationService.__name__ == "RecommendationService"


def test_phase12_clerk_auth_is_still_present() -> None:
    assert ClerkIdentity.__name__ == "ClerkIdentity"
    assert ClerkTokenVerifier.__name__ == "ClerkTokenVerifier"
    assert callable(decode_clerk_payload)
    assert UserService.__name__ == "UserService"
    assert WatchlistService.__name__ == "WatchlistService"
