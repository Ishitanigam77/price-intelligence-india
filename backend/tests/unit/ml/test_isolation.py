"""ML package stays independent of FastAPI, named retailers, and the API layer."""

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
ML_ROOT = REPO_ROOT / "ml"

FORBIDDEN_IMPORT_FRAGMENTS = (
    "app.api",
    "fastapi",
    "app.retailer_adapters.mock_retailer_a",
    "app.retailer_adapters.mock_retailer_b",
    "app.retailer_adapters.mock_retailer_c",
    "app.recommendation",
)

COMPARED_NAMES = {"retailer", "retailer_id", "retailer_name", "retailer_slug"}


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.name != "__pycache__" and "artifacts" not in path.parts
    )


def _imported_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_ml_package_does_not_import_fastapi_named_adapters_or_recommendations() -> None:
    offenders: list[str] = []
    for path in _python_files(ML_ROOT):
        for name in _imported_names(path):
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                if name == fragment or name.startswith(f"{fragment}."):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports {name}")
    assert offenders == []


def test_ml_contains_no_retailer_identity_branches() -> None:
    offenders: list[str] = []
    for path in _python_files(ML_ROOT):
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
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} "
                        f"compares {left.id} to a string constant"
                    )
            if isinstance(left, ast.Attribute) and left.attr in COMPARED_NAMES:
                if any(isinstance(comparator, ast.Constant) for comparator in node.comparators):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno} "
                        f"compares {left.attr} to a constant"
                    )
    assert offenders == []


def test_pricing_and_sales_still_do_not_import_ml() -> None:
    for relative in ("backend/app/pricing", "backend/app/sales"):
        root = REPO_ROOT / relative
        offenders: list[str] = []
        for path in _python_files(root):
            source = path.read_text(encoding="utf-8")
            if "import ml" in source or "from ml" in source:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        assert offenders == []
