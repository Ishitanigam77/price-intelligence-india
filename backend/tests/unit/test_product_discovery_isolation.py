"""Prove Product Discovery depends on the retailer abstraction, not named retailers."""

import ast
from pathlib import Path

from app.core.config import Settings
from app.retailer_adapters.wiring import build_retailer_registry

BACKEND_ROOT = Path(__file__).resolve().parents[2]

DISCOVERY_PATHS = (
    BACKEND_ROOT / "app/services/product_discovery_service.py",
    BACKEND_ROOT / "app/retailer_adapters/wiring.py",
    BACKEND_ROOT / "app/api/v1/products.py",
    BACKEND_ROOT / "app/schemas/discovery.py",
)

FORBIDDEN_IMPORT_FRAGMENTS = (
    "app.retailer_adapters.mock_retailer_a",
    "app.retailer_adapters.mock_retailer_b",
    "app.retailer_adapters.mock_retailer_c",
    "app.retailer_adapters.amazon_in",
    "app.retailer_adapters.flipkart",
)

COMPARED_NAMES = {"retailer", "retailer_id", "retailer_name", "retailer_slug"}


def test_discovery_modules_do_not_import_specific_adapters() -> None:
    offenders: list[str] = []
    for path in DISCOVERY_PATHS:
        source = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
            if fragment in source:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} imports {fragment}")
    assert offenders == []


def test_discovery_service_contains_no_retailer_identity_branches() -> None:
    path = BACKEND_ROOT / "app/services/product_discovery_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if isinstance(left, ast.Name) and left.id in COMPARED_NAMES:
            if any(
                isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
                for comparator in node.comparators
            ):
                offenders.append(
                    f"{path.name}:{node.lineno} compares {left.id} to a string constant"
                )
        if isinstance(left, ast.Attribute) and left.attr in COMPARED_NAMES:
            if any(isinstance(comparator, ast.Constant) for comparator in node.comparators):
                offenders.append(f"{path.name}:{node.lineno} compares {left.attr} to a constant")
    assert offenders == []


def test_wiring_discovers_integrations_without_naming_them() -> None:
    source = (BACKEND_ROOT / "app/retailer_adapters/wiring.py").read_text(encoding="utf-8")
    assert "amazon_in" not in source
    assert "flipkart" not in source
    registry = build_retailer_registry(
        settings=Settings(_env_file=None, retailer_adapter_kinds="integration"),
        env={},
    )
    assert set(registry.retailer_ids()) == {"amazon-in", "flipkart"}


def test_wiring_discovers_mocks_without_naming_them() -> None:
    """Startup wiring asks discovery for kinds; it does not import mock packages by name."""
    source = (BACKEND_ROOT / "app/retailer_adapters/wiring.py").read_text(encoding="utf-8")
    assert "discover_adapters" in source
    assert "RetailerRegistry" in source
    assert "mock_retailer_a" not in source

    registry = build_retailer_registry(
        settings=Settings(_env_file=None, retailer_adapter_kinds="mock")
    )
    assert set(registry.retailer_ids()) == {
        "mock-retailer-a",
        "mock-retailer-b",
        "mock-retailer-c",
    }
