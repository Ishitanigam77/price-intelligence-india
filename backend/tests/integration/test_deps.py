"""Integration tests for `app.api.deps`: dependency providers for repositories/services.

Confirms each provider returns the correctly-typed repository/service bound to the given
session, and that `DbSession`/`RedisClient` (the shared `Annotated` dependency aliases) actually
resolve through FastAPI's dependency injection to a working session/client.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy.orm import Session

from app.api.deps import (
    DbSession,
    RedisClient,
    get_brand_repository,
    get_category_repository,
    get_price_service,
    get_price_snapshot_repository,
    get_product_discovery_service,
    get_product_repository,
    get_product_variant_repository,
    get_retailer_product_repository,
    get_retailer_repository,
    get_seller_repository,
)
from app.observability.metrics import NullMetricsSink
from app.repositories.brand_repository import BrandRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.price_snapshot_repository import PriceSnapshotRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.product_variant_repository import ProductVariantRepository
from app.repositories.retailer_product_repository import RetailerProductRepository
from app.repositories.retailer_repository import RetailerRepository
from app.repositories.seller_repository import SellerRepository
from app.retailer_adapters.base.registry import RetailerRegistry
from app.services.price_service import PriceService
from app.services.product_discovery_service import ProductDiscoveryService


def test_repository_provider_functions_bind_the_given_session(db_session: Session) -> None:
    assert isinstance(get_product_repository(db_session), ProductRepository)
    assert isinstance(get_product_variant_repository(db_session), ProductVariantRepository)
    assert isinstance(get_category_repository(db_session), CategoryRepository)
    assert isinstance(get_brand_repository(db_session), BrandRepository)
    assert isinstance(get_retailer_repository(db_session), RetailerRepository)
    assert isinstance(get_seller_repository(db_session), SellerRepository)
    assert isinstance(get_retailer_product_repository(db_session), RetailerProductRepository)

    snapshot_repo = get_price_snapshot_repository(db_session)
    assert isinstance(snapshot_repo, PriceSnapshotRepository)
    assert snapshot_repo.session is db_session


def test_get_price_service_composes_the_two_repositories_it_needs(db_session: Session) -> None:
    retailer_product_repo = get_retailer_product_repository(db_session)
    snapshot_repo = get_price_snapshot_repository(db_session)

    service = get_price_service(retailer_product_repo, snapshot_repo)

    assert isinstance(service, PriceService)
    assert service._retailer_product_repo is retailer_product_repo
    assert service._price_snapshot_repo is snapshot_repo


def test_get_product_discovery_service_binds_session_and_registry(db_session: Session) -> None:
    registry = RetailerRegistry()
    service = get_product_discovery_service(db_session, registry, NullMetricsSink())
    assert isinstance(service, ProductDiscoveryService)
    assert service.registry is registry


def test_db_session_dependency_alias_resolves_through_fastapi_di() -> None:
    probe_app = FastAPI()

    @probe_app.get("/probe")
    def _probe(db: DbSession) -> dict[str, bool]:
        return {"is_session": isinstance(db, Session)}

    with TestClient(probe_app) as client:
        response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"is_session": True}


def test_redis_client_dependency_alias_resolves_through_fastapi_di() -> None:
    probe_app = FastAPI()

    @probe_app.get("/probe")
    def _probe(redis_client: RedisClient) -> dict[str, bool]:
        return {"is_redis": isinstance(redis_client, Redis), "pong": redis_client.ping()}

    with TestClient(probe_app) as client:
        response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"is_redis": True, "pong": True}
