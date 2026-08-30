"""Scan tracked files for live-looking secrets. Failures report paths only."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

# Assembled so this file does not itself contain a contiguous live marker.
_LIVE_SECRET_PATTERNS = (
    (("BEGIN ", "RSA PRIVATE KEY"), "pem"),
    (("BEGIN ", "OPENSSH PRIVATE KEY"), "pem"),
    (("sk_", "live_"), "clerk"),
    (("wh", "sec_"), "clerk_webhook"),
    (("DefaultEndpointsProtocol=https;", "AccountKey="), "azure_storage"),
)

_SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".pyc",
}
_SKIP_DIR_NAMES = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv"}


def _tracked_text_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


@pytest.mark.parametrize(("parts", "kind"), _LIVE_SECRET_PATTERNS)
def test_tracked_files_do_not_contain_live_secret_markers(parts: tuple[str, ...], kind: str) -> None:
    needle = "".join(parts)
    hits: list[str] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in text:
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert hits == [], f"Live-looking {kind} marker found in: {', '.join(hits)}"
