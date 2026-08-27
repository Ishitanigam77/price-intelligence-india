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
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.repositories.seller_repository import SellerRepository
from app.retailer_adapters.base.registry import RetailerRegistry
from app.services.price_comparison_service import PriceComparisonService
from app.services.price_history_service import PriceHistoryService
from app.services.price_service import PriceService
from app.services.product_discovery_service import ProductDiscoveryService

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
