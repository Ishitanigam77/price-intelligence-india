"""Shared FastAPI dependencies for the API layer.

Wires the existing Phase 1 repositories, the process `RetailerRegistry`, and the services that
compose them into the API via dependency injection, so routers never construct a `Session`, a
repository, or a retailer adapter directly. Keeping this in one place also means the
request-scoped database session (`app.db.session.get_db`) is defined exactly once and reused by
every route module.
"""

from typing import Annotated

from fastapi import Depends, Request
from redis import Redis
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.db.session import get_db
from app.observability.metrics import MetricsSink, NullMetricsSink
from app.repositories.brand_repository import BrandRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.price_alert_repository import PriceAlertRepository
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.repositories.sale_event_repository import SaleEventRepository
from app.repositories.saved_product_repository import SavedProductRepository
from app.repositories.seller_repository import SellerRepository
from app.repositories.target_price_repository import TargetPriceRepository
from app.repositories.user_preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.retailer_adapters.base.registry import RetailerRegistry
from app.services.alert_service import AlertService
from app.services.price_comparison_service import PriceComparisonService
from app.services.price_history_service import PriceHistoryService
from app.services.price_service import PriceService
from app.services.product_discovery_service import ProductDiscoveryService
from app.services.recommendation_service import RecommendationService
from app.services.sale_event_service import SaleEventService
from app.services.sale_intelligence_service import SaleIntelligenceService
from app.services.sale_price_prediction_service import SalePricePredictionService
from app.services.saved_product_service import SavedProductService
from app.services.target_price_service import TargetPriceService
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistService

DbSession = Annotated[Session, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]


def get_product_repository(db: DbSession) -> ProductRepository:
    return ProductRepository(db)


def get_product_variant_repository(db: DbSession) -> ProductVariantRepository:
    return ProductVariantRepository(db)


def get_category_repository(db: DbSession) -> CategoryRepository:
    return CategoryRepository(db)


def get_brand_repository(db: DbSession) -> BrandRepository:
    return BrandRepository(db)


def get_retailer_repository(db: DbSession) -> RetailerRepository:
    return RetailerRepository(db)


def get_seller_repository(db: DbSession) -> SellerRepository:
    return SellerRepository(db)


def get_retailer_product_repository(db: DbSession) -> RetailerProductRepository:
    return RetailerProductRepository(db)


def get_price_snapshot_repository(db: DbSession) -> PriceSnapshotRepository:
    return PriceSnapshotRepository(db)


def get_sale_event_repository(db: DbSession) -> SaleEventRepository:
    return SaleEventRepository(db)


ProductRepositoryDep = Annotated[ProductRepository, Depends(get_product_repository)]
ProductVariantRepositoryDep = Annotated[
    ProductVariantRepository, Depends(get_product_variant_repository)
]
CategoryRepositoryDep = Annotated[CategoryRepository, Depends(get_category_repository)]
BrandRepositoryDep = Annotated[BrandRepository, Depends(get_brand_repository)]
RetailerRepositoryDep = Annotated[RetailerRepository, Depends(get_retailer_repository)]
SellerRepositoryDep = Annotated[SellerRepository, Depends(get_seller_repository)]
RetailerProductRepositoryDep = Annotated[
    RetailerProductRepository, Depends(get_retailer_product_repository)
]
PriceSnapshotRepositoryDep = Annotated[
    PriceSnapshotRepository, Depends(get_price_snapshot_repository)
]
SaleEventRepositoryDep = Annotated[SaleEventRepository, Depends(get_sale_event_repository)]


def get_price_service(
    retailer_product_repo: RetailerProductRepositoryDep,
    price_snapshot_repo: PriceSnapshotRepositoryDep,
) -> PriceService:
    return PriceService(retailer_product_repo, price_snapshot_repo)


PriceServiceDep = Annotated[PriceService, Depends(get_price_service)]


def get_retailer_registry(request: Request) -> RetailerRegistry:
    """Return the process-wide registry populated at application startup."""
    registry = getattr(request.app.state, "retailer_registry", None)
    if not isinstance(registry, RetailerRegistry):
        raise RuntimeError("Retailer registry has not been initialized.")
    return registry


def get_metrics_sink(request: Request) -> MetricsSink:
    sink = getattr(request.app.state, "metrics_sink", None)
    return sink if isinstance(sink, MetricsSink) else NullMetricsSink()


RetailerRegistryDep = Annotated[RetailerRegistry, Depends(get_retailer_registry)]
MetricsSinkDep = Annotated[MetricsSink, Depends(get_metrics_sink)]


def get_product_discovery_service(
    db: DbSession,
    registry: RetailerRegistryDep,
    metrics_sink: MetricsSinkDep,
) -> ProductDiscoveryService:
    return ProductDiscoveryService(db, registry, metrics_sink=metrics_sink)


ProductDiscoveryServiceDep = Annotated[
    ProductDiscoveryService, Depends(get_product_discovery_service)
]


def get_price_comparison_service(
    db: DbSession,
    metrics_sink: MetricsSinkDep,
) -> PriceComparisonService:
    return PriceComparisonService(db, metrics_sink=metrics_sink)


PriceComparisonServiceDep = Annotated[PriceComparisonService, Depends(get_price_comparison_service)]


def get_price_history_service(
    db: DbSession,
    metrics_sink: MetricsSinkDep,
) -> PriceHistoryService:
    return PriceHistoryService(db, metrics_sink=metrics_sink)


PriceHistoryServiceDep = Annotated[PriceHistoryService, Depends(get_price_history_service)]


def get_sale_event_service(
    db: DbSession,
    metrics_sink: MetricsSinkDep,
) -> SaleEventService:
    return SaleEventService(db, metrics_sink=metrics_sink)


SaleEventServiceDep = Annotated[SaleEventService, Depends(get_sale_event_service)]


def get_sale_price_prediction_service(
    db: DbSession,
    metrics_sink: MetricsSinkDep,
) -> SalePricePredictionService:
    return SalePricePredictionService(db, metrics_sink=metrics_sink)


SalePricePredictionServiceDep = Annotated[
    SalePricePredictionService, Depends(get_sale_price_prediction_service)
]


def get_recommendation_service(
    db: DbSession,
    metrics_sink: MetricsSinkDep,
) -> RecommendationService:
    return RecommendationService(db, metrics_sink=metrics_sink)


RecommendationServiceDep = Annotated[RecommendationService, Depends(get_recommendation_service)]


def get_sale_intelligence_service(
    db: DbSession,
    metrics_sink: MetricsSinkDep,
) -> SaleIntelligenceService:
    return SaleIntelligenceService(db, metrics_sink=metrics_sink)


SaleIntelligenceServiceDep = Annotated[
    SaleIntelligenceService, Depends(get_sale_intelligence_service)
]


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_user_preference_repository(db: DbSession) -> UserPreferenceRepository:
    return UserPreferenceRepository(db)


def get_watchlist_repository(db: DbSession) -> WatchlistRepository:
    return WatchlistRepository(db)


def get_saved_product_repository(db: DbSession) -> SavedProductRepository:
    return SavedProductRepository(db)


def get_target_price_repository(db: DbSession) -> TargetPriceRepository:
    return TargetPriceRepository(db)


def get_price_alert_repository(db: DbSession) -> PriceAlertRepository:
    return PriceAlertRepository(db)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
UserPreferenceRepositoryDep = Annotated[
    UserPreferenceRepository, Depends(get_user_preference_repository)
]
WatchlistRepositoryDep = Annotated[WatchlistRepository, Depends(get_watchlist_repository)]
SavedProductRepositoryDep = Annotated[SavedProductRepository, Depends(get_saved_product_repository)]
TargetPriceRepositoryDep = Annotated[TargetPriceRepository, Depends(get_target_price_repository)]
PriceAlertRepositoryDep = Annotated[PriceAlertRepository, Depends(get_price_alert_repository)]


def get_user_service(
    users: UserRepositoryDep,
    preferences: UserPreferenceRepositoryDep,
) -> UserService:
    return UserService(users, preferences)


def get_watchlist_service(
    watchlists: WatchlistRepositoryDep,
    products: ProductRepositoryDep,
) -> WatchlistService:
    return WatchlistService(watchlists, products)


def get_saved_product_service(
    saved_products: SavedProductRepositoryDep,
    products: ProductRepositoryDep,
) -> SavedProductService:
    return SavedProductService(saved_products, products)


def get_target_price_service(
    target_prices: TargetPriceRepositoryDep,
    products: ProductRepositoryDep,
) -> TargetPriceService:
    return TargetPriceService(target_prices, products)


def get_alert_service(
    alerts: PriceAlertRepositoryDep,
    products: ProductRepositoryDep,
) -> AlertService:
    return AlertService(alerts, products)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
WatchlistServiceDep = Annotated[WatchlistService, Depends(get_watchlist_service)]
SavedProductServiceDep = Annotated[SavedProductService, Depends(get_saved_product_service)]
TargetPriceServiceDep = Annotated[TargetPriceService, Depends(get_target_price_service)]
AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]
