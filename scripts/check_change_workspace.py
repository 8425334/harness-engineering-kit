#!/usr/bin/env python3
"""Validate OpenSpec-owned changes that opt into Harness governance."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from openspec_common import validate_orchestration, workspace_contract


CHANGES_REL = "openspec/changes"
ARCHIVE_NAME = "archive"
REQUIRED_SCHEMA = "harness-engineering"
SCHEMA_LINE = re.compile(r"^\s*schema\s*:\s*([^#\s]+)\s*(?:#.*)?$", re.MULTILINE)
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")
PLACEHOLDERS = {"", "tbd", "todo", "unknown", "none", "n/a"}


def normalize_unit_path(value: object) -> str | None:
    """Accept only normalized, unit-relative POSIX paths (invariant I7)."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("/") or text.startswith("/") or "\\" in text or re.match(r"^[A-Za-z]:", text):
        return None
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def resolve_project_relative(project_root: Path, relative: str) -> Path | None:
    resolved = (project_root / relative).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return None
    return resolved


def validate_related_changes(project_root: Path, workspace: dict) -> list[str]:
    """Unit-local half of I15: local files must exist, foreign refs must be well-formed."""
    errors: list[str] = []
    contract = workspace_contract()
    related = workspace.get("related_changes")
    if related is None:
        return errors
    if not isinstance(related, list):
        return ["governance.json workspace.related_changes must be a list"]
    unit_id = workspace.get("unit_id")
    seen: set[str] = set()
    for index, entry in enumerate(related):
        label = f"governance.json workspace.related_changes[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        unknown = sorted(set(entry) - set(contract["related_change_keys"]))
        if unknown:
            errors.append(f"{label} has unknown keys: {', '.join(unknown)}")
        for key in contract["related_change_required_keys"]:
            if key not in entry:
                errors.append(f"{label} is missing {key}")
        member = entry.get("unit")
        if not isinstance(member, str) or not ID_PATTERN.match(member):
            errors.append(f"{label}.unit must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
            continue
        if member in seen:
            errors.append(f"{label}.unit is duplicated: {member}")
        seen.add(member)
        change_id = entry.get("change_id")
        if not isinstance(change_id, str) or not ID_PATTERN.match(change_id):
            errors.append(f"{label}.change_id must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
        specs = entry.get("specs")
        if not isinstance(specs, list) or not specs:
            errors.append(f"{label}.specs must list at least one spec file")
            continue
        for position, spec in enumerate(specs):
            spec_label = f"{label}.specs[{position}]"
            if not isinstance(spec, dict) or set(spec) != set(contract["spec_reference_keys"]):
                errors.append(f"{spec_label} keys must be exactly {sorted(contract['spec_reference_keys'])}")
                continue
            if spec.get("unit") != member:
                errors.append(f"{spec_label}.unit must equal {member}")
            relative = normalize_unit_path(spec.get("path"))
            if relative is None:
                errors.append(f"{spec_label}.path must be a normalized unit-relative POSIX path")
                continue
            if member != unit_id:
                # Aggregate `hek workspace verify` checks the other units' files;
                # a unit-local run cannot see them and must not fake a pass.
                continue
            resolved = resolve_project_relative(project_root, relative)
            if resolved is None or not resolved.is_file():
                errors.append(f"{spec_label}.path does not exist in this unit: {relative}")
                continue
            change_dir = project_root / "openspec/changes" / str(change_id)
            if change_dir.is_dir() and not resolved.is_relative_to(change_dir.resolve()):
                errors.append(f"{spec_label}.path must live inside openspec/changes/{change_id}/")
        if member == unit_id and isinstance(change_id, str):
            change_dir = project_root / "openspec/changes" / change_id
            if not change_dir.is_dir():
                errors.append(f"{label}.change_id does not match a local change directory: {change_id}")
    if isinstance(unit_id, str) and unit_id not in seen:
        errors.append("governance.json workspace.related_changes must include the owning unit")
    return errors


def validate_workspace_contracts(project_root: Path, workspace: dict) -> list[str]:
    errors: list[str] = []
    contract = workspace_contract()
    entries = workspace.get("contracts")
    if entries is None:
        return errors
    if not isinstance(entries, list):
        return ["governance.json workspace.contracts must be a list"]
    unit_id = workspace.get("unit_id")
    breaking = [entry for entry in entries if isinstance(entry, dict) and entry.get("breaking") is True]
    if breaking and not workspace.get("derived_from"):
        errors.append("governance.json workspace.derived_from is required for a breaking contract change")
    for index, entry in enumerate(entries):
        label = f"governance.json workspace.contracts[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        unknown = sorted(set(entry) - set(contract["contract_keys"]))
        if unknown:
            errors.append(f"{label} has unknown keys: {', '.join(unknown)}")
        for key in contract["contract_required_keys"]:
            if key not in entry:
                errors.append(f"{label} is missing {key}")
        for key in ("contract", "provider"):
            value = entry.get(key)
            if not isinstance(value, str) or not ID_PATTERN.match(value):
                errors.append(f"{label}.{key} must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
        if not isinstance(entry.get("breaking"), bool):
            errors.append(f"{label}.breaking must be a boolean")
        for key in ("from_version", "to_version"):
            value = entry.get(key)
            if not isinstance(value, str) or not SEMVER_PATTERN.match(value):
                errors.append(f"{label}.{key} must be a semantic version")
        if entry.get("breaking") is True:
            deprecated = entry.get("deprecated_until")
            if not isinstance(deprecated, str) or not DATE_PATTERN.match(deprecated):
                errors.append(f"{label}.deprecated_until must be an ISO date (YYYY-MM-DD) for a breaking change")
            if not entry.get("verification"):
                errors.append(f"{label}.verification is required for a breaking change")
        verification = entry.get("verification")
        if verification is not None:
            if not isinstance(verification, dict) or set(verification) != set(contract["spec_reference_keys"]):
                errors.append(f"{label}.verification keys must be exactly {sorted(contract['spec_reference_keys'])}")
            else:
                relative = normalize_unit_path(verification.get("path"))
                if relative is None:
                    errors.append(f"{label}.verification.path must be a normalized unit-relative POSIX path")
                elif verification.get("unit") == unit_id:
                    resolved = resolve_project_relative(project_root, relative)
                    if resolved is None or not resolved.is_file():
                        errors.append(f"{label}.verification.path does not exist in this unit: {relative}")
    return errors


def validate_governance_workspace(project_root: Path, record: dict) -> list[str]:
    """Validate the optional ``workspace`` section; absent keys keep old changes valid."""
    workspace = record.get("workspace")
    if workspace is None:
        return []
    if not isinstance(workspace, dict):
        return ["governance.json workspace must be an object"]
    contract = workspace_contract()
    errors: list[str] = []
    unknown = sorted(set(workspace) - set(contract["keys"]))
    if unknown:
        errors.append(f"governance.json workspace has unknown keys: {', '.join(unknown)}")
    for key in contract["required_keys"]:
        if key not in workspace:
            errors.append(f"governance.json workspace is missing {key}")
    if workspace.get("role") not in contract["roles"]:
        errors.append(f"governance.json workspace.role must be one of {sorted(contract['roles'])}")
    for key in ("workspace_id", "unit_id"):
        value = workspace.get(key)
        if not isinstance(value, str) or not ID_PATTERN.match(value):
            errors.append(f"governance.json workspace.{key} must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
    change_id = workspace.get("change_id")
    if change_id is not None:
        if not isinstance(change_id, str) or not ID_PATTERN.match(change_id):
            errors.append("governance.json workspace.change_id must match ^[a-z0-9][a-z0-9-]{1,63}$")
        elif change_id != record.get("change_id"):
            errors.append("governance.json workspace.change_id must equal the change directory name")
    derived_from = workspace.get("derived_from")
    if derived_from is not None and (not isinstance(derived_from, str) or not ID_PATTERN.match(derived_from)):
        errors.append("governance.json workspace.derived_from must match ^[a-z0-9][a-z0-9-]{1,63}$")
    errors.extend(validate_related_changes(project_root, workspace))
    errors.extend(validate_workspace_contracts(project_root, workspace))
    return errors


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


def validate_change(change_dir: Path, project_root: Path | None = None) -> list[str]:
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
    root = project_root or (change_dir.parents[2] if len(change_dir.parents) > 2 else change_dir.parent)
    errors.extend(validate_governance_workspace(Path(root), record))
    return errors


def check_workspace(project_root: Path | str) -> list[str]:
    root = Path(project_root).resolve()
    errors: list[str] = []
    for change_dir in live_change_dirs(root / CHANGES_REL):
        errors.extend(
            f"{change_dir.relative_to(root).as_posix()}: {error}"
            for error in validate_change(change_dir, root)
        )
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
