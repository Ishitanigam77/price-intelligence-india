#!/usr/bin/env python3
"""Parse Azure Pipelines and GitHub Actions YAML so malformed pipelines fail in Validate."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FILES = [
    ROOT / "infrastructure/pipelines/azure-pipelines.yml",
    ROOT / "infrastructure/pipelines/azure-pipelines.terraform.yml",
    ROOT / ".github/workflows/ci.yml",
    ROOT / "infrastructure/docker/docker-compose.yml",
]


def main() -> None:
    failed = False
    for path in FILES:
        if not path.is_file():
            print(f"MISSING {path}")
            failed = True
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            print(f"INVALID YAML {path}: {exc}")
            failed = True
        else:
            print(f"ok {path.relative_to(ROOT)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
