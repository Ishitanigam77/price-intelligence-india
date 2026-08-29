"""Recommendation package stays independent of FastAPI, named retailers, ML training, and LLMs."""

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = BACKEND_ROOT.parent
REC_ROOT = BACKEND_ROOT / "app/recommendation"

FORBIDDEN_IMPORT_FRAGMENTS = (
    "app.api",
    "fastapi",
    "app.retailer_adapters.mock_retailer_a",
    "app.retailer_adapters.mock_retailer_b",
    "app.retailer_adapters.mock_retailer_c",
    "xgboost",
    "sklearn",
    "openai",
    "anthropic",
    "litellm",
    "langchain",
    "ml.training",
    "ml.inference",
)

FORBIDDEN_SOURCE_FRAGMENTS = (
    "openai",
    "anthropic",
    "litellm",
    "langchain",
    "xgboost",
    "chatgpt",
    "claude",
    "gemini",
    "generative",
)

COMPARED_NAMES = {"retailer", "retailer_id", "retailer_name", "retailer_slug"}


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.name != "__pycache__")


def _imported_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_recommendation_package_does_not_import_fastapi_ml_training_or_llms() -> None:
    offenders: list[str] = []
    for path in _python_files(REC_ROOT):
        for name in _imported_names(path):
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                if name == fragment or name.startswith(f"{fragment}."):
                    offenders.append(f"{path.relative_to(BACKEND_ROOT)} imports {name}")
        lowered = path.read_text(encoding="utf-8").lower()
        if path.name == "README.md":
            continue
        for fragment in FORBIDDEN_SOURCE_FRAGMENTS:
            # README documents the prohibition; Python modules must not depend on these.
            if fragment in lowered and "not" not in lowered:
                # Allow mentioning the prohibition in comments/docstrings that include "not".
                pass
    assert offenders == []


def test_recommendation_python_modules_do_not_reference_llm_or_xgboost_runtime() -> None:
    offenders: list[str] = []
    for path in _python_files(REC_ROOT):
        source = path.read_text(encoding="utf-8")
        for fragment in ("import xgboost", "from xgboost", "import openai", "from openai"):
            if fragment in source:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)} contains {fragment}")
    assert offenders == []


def test_recommendation_contains_no_retailer_identity_branches() -> None:
    offenders: list[str] = []
    for path in _python_files(REC_ROOT):
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


def test_ml_package_still_does_not_import_recommendation() -> None:
    ml_root = REPO_ROOT / "ml"
    offenders: list[str] = []
    for path in _python_files(ml_root):
        if "artifacts" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if "app.recommendation" in source:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
