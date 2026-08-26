"""Price comparison package stays independent of FastAPI, named retailers, and ML."""

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PRICING_ROOT = BACKEND_ROOT / "app/pricing"

FORBIDDEN_IMPORT_FRAGMENTS = (
    "app.api",
    "fastapi",
    "app.retailer_adapters.mock_retailer_a",
    "app.retailer_adapters.mock_retailer_b",
    "app.retailer_adapters.mock_retailer_c",
    "xgboost",
    "sklearn",
    "sentence_transformers",
)

COMPARED_NAMES = {"retailer", "retailer_id", "retailer_name", "retailer_slug"}


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.name != "__pycache__")


def test_pricing_package_does_not_import_fastapi_named_adapters_or_ml() -> None:
    offenders: list[str] = []
    for path in _python_files(PRICING_ROOT):
        source = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
            if fragment in source:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} mentions {fragment}")
    assert offenders == []


def test_pricing_contains_no_retailer_identity_branches() -> None:
    offenders: list[str] = []
    for path in _python_files(PRICING_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
                        f"{path.relative_to(BACKEND_ROOT)}:{node.lineno} "
                        f"compares {left.id} to a string constant"
                    )
            if isinstance(left, ast.Attribute) and left.attr in COMPARED_NAMES:
                if any(isinstance(comparator, ast.Constant) for comparator in node.comparators):
                    offenders.append(
                        f"{path.relative_to(BACKEND_ROOT)}:{node.lineno} "
                        f"compares {left.attr} to a constant"
                    )
    assert offenders == []
