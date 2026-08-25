"""Tests for the `RetailerAdapter` contract: capabilities, enablement, and payload checks."""

import pytest

from app.retailer_adapters.base.config import AdapterOperation
from app.retailer_adapters.base.errors import (
    AdapterContractError,
    AdapterDisabledError,
    InvalidRetailerResponseError,
    UnsupportedOperationError,
)
from app.retailer_adapters.base.interface import RetailerAdapter
from app.retailer_adapters.base.models import NormalizedProduct, RetailerProduct
from tests.unit.retailer_adapters.helpers import (
    FIXED_NOW,
    make_config,
    make_price_observation,
    make_scripted_adapter,
)


class TestCapabilityEnforcement:
    async def test_undeclared_operation_raises_unsupported(self) -> None:
        from app.retailer_adapters.mock_retailer_b import create_adapter

        bazaar = create_adapter(env={})
        with pytest.raises(UnsupportedOperationError) as exc:
            await bazaar.get_availability("880011")
        assert exc.value.code.value == "unsupported_operation"
        assert exc.value.retailer_id == "mock-retailer-b"

    async def test_disabled_adapter_raises_before_calling_the_source(self) -> None:
        adapter = make_scripted_adapter(script={"get_price": []})
        adapter.disable()
        with pytest.raises(AdapterDisabledError):
            await adapter.get_price("SKU-1")
        assert adapter.calls == []

    async def test_enable_restores_operations(self) -> None:
        adapter = make_scripted_adapter()
        adapter.disable()
        adapter.enable()
        observation = await adapter.get_price("SKU-1")
        assert observation.retailer_id == "scripted-store"


class TestContractVerification:
    def test_declared_but_unimplemented_hook_fails_at_construction(self) -> None:
        class IncompleteAdapter(RetailerAdapter):
            async def _check_health(self) -> str | None:
                return "ok"

            def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
                raise NotImplementedError

        with pytest.raises(AdapterContractError, match="declared but not implemented"):
            IncompleteAdapter(
                make_config(supported_operations=frozenset({AdapterOperation.GET_PRICE}))
            )

    def test_implemented_but_undeclared_hook_fails_at_construction(self) -> None:
        class OverimplementedAdapter(RetailerAdapter):
            async def _get_price(self, retailer_sku: str):  # type: ignore[override]
                return make_price_observation()

            async def _check_health(self) -> str | None:
                return "ok"

            def normalize_product(self, product: RetailerProduct) -> NormalizedProduct:
                raise NotImplementedError

        with pytest.raises(AdapterContractError, match="implemented but not declared"):
            OverimplementedAdapter(
                make_config(supported_operations=frozenset({AdapterOperation.GET_PRODUCT}))
            )


class TestPayloadAttribution:
    async def test_payload_for_another_retailer_is_rejected(self) -> None:
        adapter = make_scripted_adapter(
            script={"get_price": [make_price_observation(retailer_id="other-store")]}
        )
        with pytest.raises(InvalidRetailerResponseError) as exc:
            await adapter.get_price("SKU-1")
        assert "other-store" in str(exc.value)
        assert exc.value.retailer_id == "scripted-store"


class TestHealthCheck:
    async def test_healthy_probe(self) -> None:
        adapter = make_scripted_adapter()
        result = await adapter.health_check()
        assert result.is_healthy
        assert result.retailer_id == "scripted-store"
        assert result.checked_at == FIXED_NOW
        assert result.duration_ms >= 0

    async def test_disabled_probe_is_unknown_and_does_not_call_the_source(self) -> None:
        adapter = make_scripted_adapter(script={"health_check": []})
        adapter.disable()
        result = await adapter.health_check()
        assert result.status.value == "unknown"
        assert adapter.calls == []
        assert "disabled" in (result.detail or "")

    async def test_transient_probe_failure_is_degraded(self) -> None:
        from app.retailer_adapters.base.errors import AdapterUnavailableError

        adapter = make_scripted_adapter(
            script={
                "health_check": [
                    AdapterUnavailableError("unreachable", retailer_id="scripted-store")
                ]
            }
        )
        result = await adapter.health_check()
        assert result.status.value == "degraded"
        assert result.error_code is not None
        assert result.error_code.value == "adapter_unavailable"

    async def test_permanent_probe_failure_is_unhealthy(self) -> None:
        from app.retailer_adapters.base.errors import InvalidRetailerResponseError

        adapter = make_scripted_adapter(
            script={
                "health_check": [
                    InvalidRetailerResponseError("garbled", retailer_id="scripted-store")
                ]
            }
        )
        result = await adapter.health_check()
        assert result.status.value == "unhealthy"
        assert result.error_code is not None
        assert result.error_code.value == "invalid_retailer_response"
