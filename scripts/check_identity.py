#!/usr/bin/env python3
"""Validate a unit's ``.hek/project/identity.yaml`` (invariants I1, I2, I12)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from workspace import IDENTITY_REL, YamlError, parse_identity, validate_identity
from workspace_guard import git_tracked


def validate(unit_root: Path | str) -> list[str]:
    root = Path(unit_root).resolve()
    path = root / IDENTITY_REL
    if not path.is_file():
        return [f"missing identity: {IDENTITY_REL}"]
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"identity is not readable UTF-8: {exc}"]
    try:
        payload = parse_identity(text)
    except YamlError as exc:
        return [f"identity is not valid YAML: {exc}"]
    errors = validate_identity(payload, root=root)
    if not errors and not git_tracked(root, IDENTITY_REL):
        errors.append(f"{IDENTITY_REL} must be tracked by Git (invariant I12)")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Unit repository root")
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        print("IDENTITY INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"IDENTITY OK: {args.root.resolve() / IDENTITY_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
