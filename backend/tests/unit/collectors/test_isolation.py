"""Collectors stay on the RetailerRegistry abstraction — no named retailer packages."""

import ast
from pathlib import Path

COLLECTORS_ROOT = Path(__file__).resolve().parents[3] / "app/collectors"
WORKERS_ROOT = Path(__file__).resolve().parents[3] / "app/workers"

FORBIDDEN_IMPORT_FRAGMENTS = (
    "app.retailer_adapters.mock_retailer_a",
    "app.retailer_adapters.mock_retailer_b",
    "app.retailer_adapters.mock_retailer_c",
    "app.retailer_adapters.amazon_in",
    "app.retailer_adapters.flipkart",
    "app.api",
    "app.notifications",
)


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


def test_collectors_and_workers_do_not_import_named_retailers_or_notifications() -> None:
    offenders: list[str] = []
    for root in (COLLECTORS_ROOT, WORKERS_ROOT):
        for path in _python_files(root):
            source = path.read_text(encoding="utf-8")
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                if fragment in source:
                    offenders.append(f"{path} contains {fragment}")
            for name in _imported_names(path):
                for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                    if name == fragment or name.startswith(f"{fragment}."):
                        offenders.append(f"{path} imports {name}")
    assert offenders == []


def test_orchestrator_mentions_retailer_registry() -> None:
    source = (COLLECTORS_ROOT / "orchestrator.py").read_text(encoding="utf-8")
    assert "RetailerRegistry" in source
    assert "adapters_supporting" in source or "adapters(enabled_only" in source
