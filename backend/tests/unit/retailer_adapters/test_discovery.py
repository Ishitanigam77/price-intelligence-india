"""Tests for package-convention adapter discovery."""

import pytest

from app.retailer_adapters.base.discovery import AdapterKind, discover_adapters
from app.retailer_adapters.base.errors import AdapterContractError
from app.retailer_adapters.mock_retailer_a import RETAILER_ID as ID_A
from app.retailer_adapters.mock_retailer_b import RETAILER_ID as ID_B
from app.retailer_adapters.mock_retailer_c import RETAILER_ID as ID_C


def test_discovery_defaults_to_real_integrations_and_finds_none() -> None:
    """Phase 2 ships mock adapters only; production discovery must not pick them up."""
    discovered = discover_adapters()
    assert discovered == ()


def test_mock_adapters_are_discoverable_when_explicitly_requested() -> None:
    discovered = discover_adapters(kinds=(AdapterKind.MOCK,))
    ids = tuple(entry.retailer_id for entry in discovered)
    assert ids == (ID_A, ID_B, ID_C)
    assert {entry.kind for entry in discovered} == {AdapterKind.MOCK}


def test_discovered_factory_builds_an_adapter_with_a_matching_id() -> None:
    discovered = {
        entry.retailer_id: entry for entry in discover_adapters(kinds=(AdapterKind.MOCK,))
    }
    adapter = discovered[ID_A].create(env={})
    assert adapter.retailer_id == ID_A
    assert adapter.enabled is True


def test_factory_id_mismatch_is_a_contract_error() -> None:
    from app.retailer_adapters import mock_retailer_a

    entry = next(
        item for item in discover_adapters(kinds=(AdapterKind.MOCK,)) if item.retailer_id == ID_A
    )
    mismatched = entry.__class__(
        retailer_id=ID_A,
        kind=entry.kind,
        module_name=entry.module_name,
        factory=lambda **kwargs: mock_retailer_a.create_adapter(env={}).__class__(
            mock_retailer_a.build_config(env={}).model_copy(
                update={"retailer_id": "other-store", "retailer_name": "Other"}
            )
        ),
    )
    with pytest.raises(AdapterContractError, match="produced an adapter for"):
        mismatched.create()
