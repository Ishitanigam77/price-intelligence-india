"""Tests for `RetailerRegistry` registration, lookup, enablement, and health sweeps."""

import pytest

from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import (
    AdapterDisabledError,
    AdapterUnavailableError,
    RetailerAlreadyRegisteredError,
    RetailerNotRegisteredError,
)
from app.retailer_adapters.base.models import HealthStatus
from app.retailer_adapters.base.registry import RetailerRegistry
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c
from tests.unit.retailer_adapters.helpers import make_config, make_scripted_adapter


def _populated_registry() -> RetailerRegistry:
    registry = RetailerRegistry()
    registry.register_all([create_a(env={}), create_b(env={}), create_c(env={})])
    return registry


class TestRegistration:
    def test_register_and_retrieve_by_id(self) -> None:
        registry = RetailerRegistry()
        adapter = create_a(env={})
        registry.register(adapter)
        assert "mock-retailer-a" in registry
        assert registry.get("mock-retailer-a") is adapter
        assert len(registry) == 1

    def test_duplicate_registration_is_rejected(self) -> None:
        registry = _populated_registry()
        with pytest.raises(RetailerAlreadyRegisteredError):
            registry.register(create_a(env={}))

    def test_replace_swaps_the_adapter(self) -> None:
        registry = RetailerRegistry()
        first = create_a(env={})
        second = create_a(env={})
        registry.register(first)
        registry.register(second, replace=True)
        assert registry.get("mock-retailer-a") is second

    def test_unknown_id_raises(self) -> None:
        with pytest.raises(RetailerNotRegisteredError):
            RetailerRegistry().get("does-not-exist")

    def test_unregister_removes_the_adapter(self) -> None:
        registry = _populated_registry()
        registry.unregister("mock-retailer-b")
        assert "mock-retailer-b" not in registry
        assert registry.retailer_ids() == ("mock-retailer-a", "mock-retailer-c")

    def test_rejects_a_non_adapter(self) -> None:
        with pytest.raises(TypeError):
            RetailerRegistry().register(object())  # type: ignore[arg-type]


class TestEnableDisable:
    def test_disable_hides_adapter_from_enabled_listings(self) -> None:
        registry = _populated_registry()
        registry.disable("mock-retailer-b")
        assert registry.is_enabled("mock-retailer-b") is False
        assert "mock-retailer-b" not in registry.retailer_ids(enabled_only=True)
        assert "mock-retailer-b" in registry.retailer_ids(enabled_only=False)
        with pytest.raises(AdapterDisabledError):
            registry.get_enabled("mock-retailer-b")

    def test_enable_restores_the_adapter(self) -> None:
        registry = _populated_registry()
        registry.disable("mock-retailer-c")
        registry.enable("mock-retailer-c")
        assert registry.get_enabled("mock-retailer-c").enabled is True


class TestDiscoveryByCapability:
    def test_adapters_supporting_filters_by_operation_and_category(self) -> None:
        registry = _populated_registry()
        availability = {
            adapter.retailer_id
            for adapter in registry.adapters_supporting(AdapterOperation.GET_AVAILABILITY)
        }
        assert availability == {"mock-retailer-a", "mock-retailer-c"}

        identifiers = {
            adapter.retailer_id
            for adapter in registry.adapters_supporting(AdapterOperation.GET_PRODUCT_IDENTIFIERS)
        }
        assert identifiers == {"mock-retailer-a", "mock-retailer-b"}

        mobiles = {
            adapter.retailer_id
            for adapter in registry.adapters_supporting(
                AdapterOperation.SEARCH_PRODUCTS, category="mobiles"
            )
        }
        assert mobiles == {"mock-retailer-a", "mock-retailer-b"}

        audio = {
            adapter.retailer_id
            for adapter in registry.adapters_supporting(
                AdapterOperation.SEARCH_PRODUCTS, category="audio"
            )
        }
        assert audio == {"mock-retailer-a", "mock-retailer-c"}

    def test_disabled_adapters_are_omitted_from_capability_queries(self) -> None:
        registry = _populated_registry()
        registry.disable("mock-retailer-a")
        mobiles = {
            adapter.retailer_id
            for adapter in registry.adapters_supporting(
                AdapterOperation.SEARCH_PRODUCTS, category="mobiles"
            )
        }
        assert mobiles == {"mock-retailer-b"}


class TestHealthSweep:
    async def test_health_check_all_records_per_retailer_status(self) -> None:
        registry = _populated_registry()
        results = await registry.health_check_all()
        assert set(results) == {"mock-retailer-a", "mock-retailer-b", "mock-retailer-c"}
        assert all(result.status is HealthStatus.HEALTHY for result in results.values())
        assert registry.last_health("mock-retailer-a") is results["mock-retailer-a"]

    async def test_one_unhealthy_adapter_does_not_hide_the_others(self) -> None:
        registry = RetailerRegistry()
        healthy = make_scripted_adapter(
            config=make_config(retailer_id="healthy-store", retailer_name="Healthy Store")
        )
        sick = make_scripted_adapter(
            script={"health_check": [AdapterUnavailableError("down", retailer_id="sick-store")]},
            config=make_config(retailer_id="sick-store", retailer_name="Sick Store"),
        )
        registry.register(healthy)
        registry.register(sick)
        results = await registry.health_check_all()
        assert results["healthy-store"].status is HealthStatus.HEALTHY
        assert results["sick-store"].status is HealthStatus.DEGRADED

    def test_describe_is_serializable_and_has_no_secrets(self) -> None:
        registry = _populated_registry()
        summary = registry.describe()
        assert {row["retailer_id"] for row in summary} == {
            "mock-retailer-a",
            "mock-retailer-b",
            "mock-retailer-c",
        }
        blob = str(summary)
        assert "api_key" not in blob
        assert "password" not in blob
        for row in summary:
            assert "supported_operations" in row
            assert row["health_status"] == "unknown"
