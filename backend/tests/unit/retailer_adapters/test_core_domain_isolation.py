"""Prove the core domain never depends on, or branches on, a specific retailer."""

import ast
from pathlib import Path

from app.domain.enums import AvailabilityStatus
from app.retailer_adapters.base.fleet import RetailerFleet
from app.retailer_adapters.base.models import ProductSearchQuery
from app.retailer_adapters.base.registry import RetailerRegistry
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c
from tests.unit.retailer_adapters.helpers import lowest_price, make_price_observation

BACKEND_ROOT = Path(__file__).resolve().parents[3]

CORE_PACKAGES = (
    BACKEND_ROOT / "app/domain",
    BACKEND_ROOT / "app/matching",
    BACKEND_ROOT / "app/normalization",
    BACKEND_ROOT / "app/pricing",
    BACKEND_ROOT / "app/sales",
    BACKEND_ROOT / "app/recommendation",
    BACKEND_ROOT / "app/repositories",
    BACKEND_ROOT / "app/db",
    BACKEND_ROOT / "app/api",
    BACKEND_ROOT / "app/retailer_adapters/base",
)

FORBIDDEN_IMPORT_FRAGMENTS = (
    "app.retailer_adapters.mock_retailer_a",
    "app.retailer_adapters.mock_retailer_b",
    "app.retailer_adapters.mock_retailer_c",
)

REAL_RETAILER_NAMES = (
    "amazon",
    "flipkart",
    "myntra",
    "meesho",
    "croma",
    "reliance",
)


def _python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.name != "__pycache__")


def _module_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_core_packages_do_not_import_specific_adapters() -> None:
    offenders: list[str] = []
    for package in CORE_PACKAGES:
        if not package.exists():
            continue
        for path in _python_files(package):
            source = _module_source(path)
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                if fragment in source:
                    offenders.append(f"{path.relative_to(BACKEND_ROOT)} imports {fragment}")
    assert offenders == []


def test_adapter_framework_does_not_name_real_retailers() -> None:
    """The adapter framework and its mocks are fictional; real retailer names belong later."""
    offenders: list[str] = []
    root = BACKEND_ROOT / "app/retailer_adapters"
    for path in _python_files(root):
        lowered = _module_source(path).lower()
        for name in REAL_RETAILER_NAMES:
            if name in lowered:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} mentions {name!r}")
    assert offenders == []


def test_fleet_and_registry_contain_no_retailer_identity_branches() -> None:
    """AST check: no `if retailer_id == ...` / `if retailer == ...` in the framework core."""
    compared_names = {"retailer", "retailer_id", "retailer_name", "retailer_slug"}
    offenders: list[str] = []
    for path in (
        BACKEND_ROOT / "app/retailer_adapters/base/fleet.py",
        BACKEND_ROOT / "app/retailer_adapters/base/registry.py",
        BACKEND_ROOT / "app/domain",
    ):
        for file_path in _python_files(path):
            tree = ast.parse(_module_source(file_path), filename=str(file_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                left = node.left
                if isinstance(left, ast.Name) and left.id in compared_names:
                    if any(
                        isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
                        for comparator in node.comparators
                    ):
                        offenders.append(
                            f"{file_path.relative_to(BACKEND_ROOT)}:{node.lineno} "
                            f"compares {left.id} to a string constant"
                        )
                if isinstance(left, ast.Attribute) and left.attr in compared_names:
                    # Attribute equality against a constant string would be retailer-specific.
                    if any(isinstance(comparator, ast.Constant) for comparator in node.comparators):
                        offenders.append(
                            f"{file_path.relative_to(BACKEND_ROOT)}:{node.lineno} "
                            f"compares {left.attr} to a constant"
                        )
    assert offenders == []


def test_lowest_price_does_not_branch_on_retailer_identity() -> None:
    cheaper = make_price_observation(
        retailer_id="mock-retailer-b", retailer_sku="b-1", displayed_price="100.00"
    )
    dearer = make_price_observation(
        retailer_id="mock-retailer-a", retailer_sku="a-1", displayed_price="500.00"
    )
    winner = lowest_price((dearer, cheaper))
    assert winner is cheaper
    swapped = lowest_price((cheaper, dearer))
    assert swapped is cheaper


async def test_fleet_consumes_standardized_prices_without_retailer_conditionals() -> None:
    registry = RetailerRegistry()
    registry.register_all([create_a(env={}), create_b(env={}), create_c(env={})])
    outcome = await RetailerFleet(registry).search(ProductSearchQuery(text="aurora"))
    priced = outcome.price_observations
    assert priced
    winner = lowest_price(priced)
    assert winner.availability in set(AvailabilityStatus)
    assert winner.displayed_price == min(item.displayed_price for item in priced)
    # The winner happens to be a mock retailer; the comparison did not ask which one.
    assert winner.retailer_id in {item.retailer_id for item in priced}
