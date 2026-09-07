#!/usr/bin/env python3
"""Validate OpenSpec-owned changes that opt into Harness governance."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from openspec_common import validate_orchestration


CHANGES_REL = "openspec/changes"
ARCHIVE_NAME = "archive"
REQUIRED_SCHEMA = "harness-engineering"
SCHEMA_LINE = re.compile(r"^\s*schema\s*:\s*([^#\s]+)\s*(?:#.*)?$", re.MULTILINE)


def change_schema(change_dir: Path) -> str | None:
    marker = change_dir / ".openspec.yaml"
    try:
        content = marker.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = SCHEMA_LINE.search(content)
    return match.group(1) if match else None


def live_change_dirs(changes_root: Path) -> list[Path]:
    if not changes_root.is_dir():
        return []
    return sorted(
        child
        for child in changes_root.iterdir()
        if child.is_dir() and child.name != ARCHIVE_NAME and not child.name.startswith(".")
    )


def validate_change(change_dir: Path) -> list[str]:
    errors: list[str] = []
    if not (change_dir / ".openspec.yaml").is_file():
        errors.append("missing OpenSpec change marker .openspec.yaml")
    else:
        schema = change_schema(change_dir)
        if schema != REQUIRED_SCHEMA:
            errors.append(
                f"OpenSpec change schema must be {REQUIRED_SCHEMA} (got {schema!r}); "
                f"create governed changes with --schema {REQUIRED_SCHEMA}"
            )
    governance_path = change_dir / "governance.json"
    if not governance_path.is_file():
        errors.append("missing Harness governance.json; run init_governance.py after OpenSpec creates the change")
        return errors
    try:
        record = json.loads(governance_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append("governance.json is not readable JSON")
        return errors
    if not isinstance(record, dict):
        errors.append("governance.json must be a JSON object")
        return errors
    if record.get("schema_version") != 1:
        errors.append(f"governance.json schema_version must be 1 (got {record.get('schema_version')!r})")
    if str(record.get("change_id", "")) != change_dir.name:
        errors.append(f"governance.json change_id must match the change directory name: {change_dir.name}")
    errors.extend(validate_orchestration(record))
    return errors


def check_workspace(project_root: Path | str) -> list[str]:
    root = Path(project_root).resolve()
    errors: list[str] = []
    for change_dir in live_change_dirs(root / CHANGES_REL):
        errors.extend(f"{change_dir.relative_to(root)}: {error}" for error in validate_change(change_dir))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    errors = check_workspace(args.root)
    if errors:
        print("OPENSPEC GOVERNANCE BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 2
    print("OPENSPEC GOVERNANCE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
