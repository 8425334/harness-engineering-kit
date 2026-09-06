#!/usr/bin/env python3
"""Record and validate the change-level requirement reflection contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from methodology_common import read_json, utc_now, write_json


FIELDS = ("requirement_id", "source", "summary", "scope", "acceptance", "constraints", "authority")


def meaningful(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and "{{" not in value and "}}" not in value
    if isinstance(value, list):
        return bool(value) and all(meaningful(item) for item in value)
    return False


def digest_for(data: dict[str, Any]) -> str:
    payload = {field: data.get(field) for field in FIELDS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("requirement-reflection.json schema_version must be 1")
    if data.get("status") != "passed" or data.get("outcome") != "ready":
        errors.append("requirement-reflection.json must have status=passed and outcome=ready")
    for field in (*FIELDS, "actor", "at", "requirement_digest"):
        if not meaningful(data.get(field)):
            errors.append(f"requirement-reflection.json missing or placeholder: {field}")
    if meaningful(data.get("requirement_digest")) and data.get("requirement_digest") != digest_for(data):
        errors.append("requirement-reflection.json requirement_digest does not match the reflected requirement")
    return errors


def record(change_dir: Path, source: Path, actor: str) -> dict[str, Any]:
    data = read_json(source)
    data.update({"schema_version": 1, "status": "passed", "outcome": "ready", "actor": actor, "at": utc_now()})
    data["requirement_digest"] = digest_for(data)
    errors = validate(data)
    if errors:
        raise ValueError("; ".join(errors))
    write_json(change_dir / "requirement-reflection.json", data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("change_dir", type=Path)
    record_parser.add_argument("--input", type=Path, required=True)
    record_parser.add_argument("--actor", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "record":
            payload, code = record(args.change_dir.resolve(), args.input.resolve(), args.actor), 0
        else:
            payload = read_json(args.path.resolve())
            errors = validate(payload)
            code = 0 if not errors else 2
            if errors:
                print("REQUIREMENT REFLECTION INVALID", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return code
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"REQUIREMENT REFLECTION FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
