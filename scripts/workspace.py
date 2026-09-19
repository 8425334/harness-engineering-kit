#!/usr/bin/env python3
"""Workspace federation: unit identity, real-time projection and contracts.

Nothing here is a second source of truth. Every fact is read from the unit that
owns it (``.hek/project/identity.yaml``, ``openspec/changes/**``,
``governance.json``) and aggregated at request time. The projection is a view,
never an authority, and the workspace root never owns a spec.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from workspace_guard import (
    BLOCKED,
    WARNING,
    Diagnostic,
    find_repos,
    git_toplevel,
    git_tracked,
    has_blocked,
    locate_harness_root,
    nested_repos_inside,
    sort_diagnostics,
)


IDENTITY_REL = ".hek/project/identity.yaml"
CHANGES_REL = "openspec/changes"
VERSION_REL = ".hek/VERSION"

IDENTITY_SCHEMA_VERSION = 1
IDENTITY_KIND = "harness-unit"
PROJECTION_SCHEMA_VERSION = 1
PROJECTION_KIND = "workspace-projection"

UNIT_KINDS = ("backend", "frontend", "mobile", "library", "docs", "infra")
CONTRACT_FORMATS = (
    "openapi-3.1",
    "proto3",
    "graphql-sdl",
    "json-schema",
    "static-manifest",
    "custom",
)
BREAKING_POLICIES = ("additive-only", "semver")
VERSION_SOURCE_SCHEMES = ("file", "openapi")
ROLES = ("provider", "consumer", "independent")
URL_SCHEMES = ("https://", "ssh://", "git+ssh://")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
PLACEHOLDERS = {"", "tbd", "todo", "unknown", "none", "n/a"}

MAX_INPUT_BYTES = 262144

IDENTITY_TOP_KEYS = (
    "schema_version",
    "kind",
    "workspace_id",
    "unit_id",
    "unit_kind",
    "repo_url",
    "owner",
    "publishes",
    "consumes",
)
IDENTITY_REQUIRED_KEYS = (
    "schema_version",
    "kind",
    "workspace_id",
    "unit_id",
    "unit_kind",
    "publishes",
    "consumes",
)
PUBLISH_KEYS = ("contract", "artifact", "format", "version_source", "breaking_policy")
PUBLISH_REQUIRED_KEYS = ("contract", "artifact", "format", "version_source")
CONSUME_KEYS = ("contract", "provider_repo", "version", "snapshot")
CONSUME_REQUIRED_KEYS = ("contract", "provider_repo", "version")

GOVERNANCE_WORKSPACE_KEYS = (
    "workspace_id",
    "unit_id",
    "role",
    "change_id",
    "derived_from",
    "related_changes",
    "contracts",
)
GOVERNANCE_WORKSPACE_REQUIRED_KEYS = ("workspace_id", "unit_id", "role")
RELATED_CHANGE_KEYS = ("unit", "change_id", "specs")
RELATED_CHANGE_REQUIRED_KEYS = ("unit", "change_id", "specs")
SPEC_REFERENCE_KEYS = ("unit", "path")


class YamlError(ValueError):
    """Raised when the constrained identity YAML subset cannot be parsed."""


# --------------------------------------------------------------------------
# Minimal YAML subset parser (mappings, lists, inline lists, scalars)
# --------------------------------------------------------------------------


def _strip_comment(line: str) -> str:
    result: list[str] = []
    quote: str | None = None
    for index, character in enumerate(line):
        if quote is not None:
            result.append(character)
            if character == quote:
                quote = None
            continue
        if character in "'\"":
            quote = character
            result.append(character)
        elif character == "#" and (index == 0 or line[index - 1] in " \t"):
            break
        else:
            result.append(character)
    return "".join(result).rstrip()


def _split_inline(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for character in value:
        if quote is not None:
            current.append(character)
            if character == quote:
                quote = None
            continue
        if character in "'\"":
            quote = character
            current.append(character)
        elif character == ",":
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _scalar(value: str) -> Any:
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [] if not inner else [_scalar(part) for part in _split_inline(inner)]
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        return {} if not inner else {part.split(":", 1)[0].strip(): _scalar(part.split(":", 1)[1]) for part in _split_inline(inner)}
    if text in ("", "null", "Null", "NULL", "~"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text


def _is_list_item(line: tuple[int, str]) -> bool:
    return line[1] == "-" or line[1].startswith("- ")


def _looks_like_mapping(content: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_.\-]+:(\s|$)", content))


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index < len(lines) and _is_list_item(lines[index]):
        return _parse_list(lines, index, indent)
    return _parse_map(lines, index, indent)


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines) and lines[index][0] == indent and _is_list_item(lines[index]):
        content = lines[index][1][1:].strip()
        index += 1
        if not content:
            if index < len(lines) and lines[index][0] > indent:
                child, index = _parse_block(lines, index, lines[index][0])
                items.append(child)
            else:
                items.append(None)
            continue
        if _looks_like_mapping(content):
            sub = [(indent + 2, content)]
            while index < len(lines) and lines[index][0] > indent:
                sub.append(lines[index])
                index += 1
            value, _ = _parse_map(sub, 0, indent + 2)
            items.append(value)
        else:
            items.append(_scalar(content))
    return items, index


def _parse_map(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}
    while index < len(lines) and lines[index][0] == indent and not _is_list_item(lines[index]):
        content = lines[index][1]
        key, separator, rest = content.partition(":")
        if not separator:
            raise YamlError(f"expected 'key: value' but found: {content}")
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest:
            mapping[key] = _scalar(rest)
        elif index < len(lines) and lines[index][0] > indent:
            child, index = _parse_block(lines, index, lines[index][0])
            mapping[key] = child
        elif index < len(lines) and lines[index][0] == indent and _is_list_item(lines[index]):
            child, index = _parse_list(lines, index, indent)
            mapping[key] = child
        else:
            mapping[key] = None
    return mapping, index


def parse_yaml(text: str) -> Any:
    """Parse the constrained YAML subset used by identity files."""
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if "\t" in stripped[:indent]:
            raise YamlError("tabs are not allowed for YAML indentation")
        lines.append((indent, stripped.strip()))
    if not lines:
        raise YamlError("identity file is empty")
    value, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise YamlError(f"unparsed YAML content at line: {lines[index][1]}")
    return value


# --------------------------------------------------------------------------
# Path and URL helpers
# --------------------------------------------------------------------------


def normalize_url(value: str) -> str:
    text = value.strip().rstrip("/")
    if text.lower().endswith(".git"):
        text = text[:-4]
    return text.lower()


def is_absolute_url(value: str) -> bool:
    return any(value.startswith(scheme) for scheme in URL_SCHEMES)


def normalize_unit_path(value: str) -> str | None:
    """Return a normalized POSIX unit-relative path, or ``None`` when invalid."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.endswith("/"):
        return None
    if text.startswith("/") or "\\" in text or re.match(r"^[A-Za-z]:", text):
        return None
    parts = PurePosixPath(text).parts
    if not parts or any(part in ("..", "") for part in parts):
        return None
    if parts[0] == ".":
        parts = parts[1:]
        if not parts:
            return None
    return "/".join(parts)


def is_semver_range(value: str) -> bool:
    """Accept the semver range forms the Kit documents (``^1.4.0``, ``>=1.0``)."""
    if not isinstance(value, str) or not value.strip():
        return False
    for alternative in value.split("||"):
        tokens = alternative.strip().split()
        if not tokens:
            return False
        for token in tokens:
            match = re.fullmatch(r"(\^|~|>=|<=|>|<|=)?\s*(.+)", token)
            if not match:
                return False
            version = match.group(2).strip()
            if not re.fullmatch(r"v?\d+(\.\d+)?(\.\d+)?([-+][0-9A-Za-z.\-]+)?|v?\d+(\.\d+)?(\.\d+)?\.?[xX*]|x|\*", version):
                return False
    return True


def _semver_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", value.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2) or 0), int(match.group(3) or 0))


def _range_token_satisfied(target: tuple[int, int, int], token: str) -> bool | None:
    """Evaluate one range token; ``None`` means the token is not decidable."""
    match = re.fullmatch(r"(\^|~|>=|<=|>|<|=)?\s*(.+)", token.strip())
    if not match:
        return None
    operator = match.group(1) or "="
    raw = match.group(2).strip()
    if raw in {"*", "x", "X"} or raw.lower().endswith((".x", ".*")):
        return True
    bound = _semver_tuple(raw)
    if bound is None:
        return None
    if operator == "^":
        return target[0] == bound[0] and target >= bound
    if operator == "~":
        return target[:2] == bound[:2] and target >= bound
    if operator == ">=":
        return target >= bound
    if operator == "<=":
        return target <= bound
    if operator == ">":
        return target > bound
    if operator == "<":
        return target < bound
    # A bare version pins exactly the precision it states: "1.5" means any 1.5.z.
    precision = len([part for part in raw.lstrip("vV").split(".") if part != ""])
    return target[:precision] == bound[:precision]


def version_satisfies(version: str, expression: str) -> bool | None:
    """Whether ``version`` satisfies ``expression``; ``None`` when undecidable."""
    target = _semver_tuple(version)
    if target is None or not isinstance(expression, str) or not expression.strip():
        return None
    for alternative in expression.split("||"):
        tokens = alternative.split()
        if not tokens:
            continue
        results = [_range_token_satisfied(target, token) for token in tokens]
        if any(result is None for result in results):
            return None
        if all(results):
            return True
    return False


def unit_scoped_path(payload: Any) -> tuple[str, str]:
    """Parse and validate an I7 ``{"unit": ..., "path": ...}`` reference."""
    if not isinstance(payload, dict):
        raise ValueError("unit-scoped path must be a mapping")
    if set(payload) != set(SPEC_REFERENCE_KEYS):
        raise ValueError(f"unit-scoped path keys must be exactly {list(SPEC_REFERENCE_KEYS)}")
    unit = payload.get("unit")
    path = payload.get("path")
    if not isinstance(unit, str) or not ID_PATTERN.match(unit):
        raise ValueError(f"unit-scoped path has an invalid unit id: {unit!r}")
    normalized = normalize_unit_path(path) if isinstance(path, str) else None
    if normalized is None:
        raise ValueError(f"unit-scoped path must be a normalized unit-relative POSIX path: {path!r}")
    return unit, normalized


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def parse_identity(text: str) -> dict[str, Any]:
    payload = parse_yaml(text)
    if not isinstance(payload, dict):
        raise YamlError("identity.yaml must be a mapping")
    return payload


def validate_identity(payload: Any, *, root: Path | None = None) -> list[str]:
    """Validate ``.hek/project/identity.yaml`` against spec section 3.1."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["identity.yaml must be a mapping"]

    unknown = sorted(set(payload) - set(IDENTITY_TOP_KEYS))
    if unknown:
        errors.append(f"unknown top-level keys: {', '.join(unknown)}")
    for key in IDENTITY_REQUIRED_KEYS:
        if key not in payload:
            errors.append(f"missing required key: {key}")
    if errors and any(error.startswith("missing required key") for error in errors):
        return errors

    if payload.get("schema_version") != IDENTITY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {IDENTITY_SCHEMA_VERSION}")
    if payload.get("kind") != IDENTITY_KIND:
        errors.append(f"kind must be {IDENTITY_KIND}")
    for key in ("workspace_id", "unit_id"):
        value = payload.get(key)
        if not isinstance(value, str) or not ID_PATTERN.match(value):
            errors.append(f"{key} must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
    if payload.get("unit_kind") not in UNIT_KINDS:
        errors.append(f"unit_kind must be one of {list(UNIT_KINDS)}")

    repo_url = payload.get("repo_url")
    if repo_url is not None:
        if not isinstance(repo_url, str) or not is_absolute_url(repo_url):
            errors.append("repo_url must be an absolute https/ssh/git+ssh URL")
    owner = payload.get("owner")
    if owner is not None and str(owner).strip().casefold() in PLACEHOLDERS:
        errors.append("owner must not be a placeholder")

    publishes = payload.get("publishes")
    if not isinstance(publishes, list):
        errors.append("publishes must be a list")
        publishes = []
    if publishes and not repo_url:
        errors.append("repo_url is required when publishes is not empty")
    seen_contracts: set[str] = set()
    for index, entry in enumerate(publishes):
        label = f"publishes[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be a mapping")
            continue
        unknown = sorted(set(entry) - set(PUBLISH_KEYS))
        if unknown:
            errors.append(f"{label} has unknown keys: {', '.join(unknown)}")
        for key in PUBLISH_REQUIRED_KEYS:
            if key not in entry:
                errors.append(f"{label} is missing {key}")
        contract = entry.get("contract")
        if not isinstance(contract, str) or not ID_PATTERN.match(contract):
            errors.append(f"{label}.contract must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
        elif contract in seen_contracts:
            errors.append(f"{label}.contract is duplicated: {contract}")
        else:
            seen_contracts.add(contract)
        if normalize_unit_path(entry.get("artifact")) is None:
            errors.append(f"{label}.artifact must be a normalized unit-relative POSIX path")
        if entry.get("format") not in CONTRACT_FORMATS:
            errors.append(f"{label}.format must be one of {list(CONTRACT_FORMATS)}")
        version_source = entry.get("version_source")
        if not isinstance(version_source, str) or ":" not in version_source:
            errors.append(f"{label}.version_source must look like '<scheme>:<arg>'")
        else:
            scheme, _, argument = version_source.partition(":")
            if scheme not in VERSION_SOURCE_SCHEMES:
                errors.append(f"{label}.version_source scheme must be one of {list(VERSION_SOURCE_SCHEMES)}")
            elif scheme == "file" and normalize_unit_path(argument) is None:
                errors.append(f"{label}.version_source file argument must be a unit-relative POSIX path")
            elif scheme == "openapi" and not argument.strip():
                errors.append(f"{label}.version_source openapi argument must not be empty")
        breaking = entry.get("breaking_policy", "additive-only")
        if breaking not in BREAKING_POLICIES:
            errors.append(f"{label}.breaking_policy must be one of {list(BREAKING_POLICIES)}")

    consumes = payload.get("consumes")
    if not isinstance(consumes, list):
        errors.append("consumes must be a list")
        consumes = []
    seen_consumed: set[str] = set()
    for index, entry in enumerate(consumes):
        label = f"consumes[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be a mapping")
            continue
        unknown = sorted(set(entry) - set(CONSUME_KEYS))
        if unknown:
            errors.append(f"{label} has unknown keys: {', '.join(unknown)}")
        for key in CONSUME_REQUIRED_KEYS:
            if key not in entry:
                errors.append(f"{label} is missing {key}")
        contract = entry.get("contract")
        if not isinstance(contract, str) or not ID_PATTERN.match(contract):
            errors.append(f"{label}.contract must match ^[a-z0-9][a-z0-9-]{{1,63}}$")
        elif contract in seen_consumed:
            errors.append(f"{label}.contract is duplicated: {contract}")
        else:
            seen_consumed.add(contract)
        provider_repo = entry.get("provider_repo")
        if not isinstance(provider_repo, str) or not is_absolute_url(provider_repo):
            errors.append(f"{label}.provider_repo must be an absolute https/ssh/git+ssh URL")
        if not is_semver_range(entry.get("version", "")):
            errors.append(f"{label}.version must be a valid semver range")
        snapshot = entry.get("snapshot")
        if snapshot is not None and normalize_unit_path(snapshot) is None:
            errors.append(f"{label}.snapshot must be a normalized unit-relative POSIX path")
    return errors


def load_identity(unit_root: Path) -> dict[str, Any]:
    """Load and validate ``unit_root``'s identity, raising ``ValueError``."""
    path = unit_root / IDENTITY_REL
    if not path.is_file():
        raise ValueError(f"missing identity: {IDENTITY_REL}")
    payload = parse_identity(path.read_text(encoding="utf-8"))
    errors = validate_identity(payload, root=unit_root)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------


@dataclass
class Unit:
    unit_id: str
    workspace_id: str
    unit_kind: str
    root: Path
    harness_root: Path
    root_index: int
    path: str
    harness_rel: str
    kit_version: str | None
    identity_sha256: str
    tracked: bool
    repo_url: str | None
    owner: str | None
    publishes: list[dict[str, Any]] = field(default_factory=list)
    consumes: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "root_index": self.root_index,
            "path": self.path,
            "harness_root": self.harness_rel,
            "kit_version": self.kit_version,
            "identity_sha256": self.identity_sha256,
            "tracked": self.tracked,
            "repo_url": self.repo_url,
        }


@dataclass
class Projection:
    roots: list[str]
    workspace_id: str | None
    units: list[Unit]
    contracts: list[dict[str, Any]]
    diagnostics: list[Diagnostic]
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "kind": PROJECTION_KIND,
            "workspace_id": self.workspace_id,
            "roots": list(self.roots),
            "digest": self.digest,
            "units": [unit.as_dict() for unit in self.units],
            "contracts": list(self.contracts),
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }


def digest_units(units: list[Unit]) -> str:
    """Content hash of the normalized unit tuples; clone layout is excluded."""
    tuples = sorted(
        (unit.unit_id, unit.identity_sha256, unit.kit_version or "", "tracked" if unit.tracked else "untracked")
        for unit in units
    )
    payload = json.dumps(tuples, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity_sha256(unit_root: Path) -> str:
    return hashlib.sha256((unit_root / IDENTITY_REL).read_bytes()).hexdigest()


def read_version(unit_root: Path) -> str | None:
    path = unit_root / VERSION_REL
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except (OSError, UnicodeError):
        return None


def read_governance(change_dir: Path) -> dict[str, Any] | None:
    path = change_dir / "governance.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def change_dirs(unit_root: Path) -> list[Path]:
    changes = unit_root / CHANGES_REL
    if not changes.is_dir():
        return []
    return sorted(
        child
        for child in changes.iterdir()
        if child.is_dir() and child.name != "archive" and not child.name.startswith(".")
    )


def active_workspace_change(unit_root: Path) -> tuple[str | None, dict[str, Any] | None]:
    """Return ``(change_id, workspace_section)`` for the unit's current change."""
    for change_dir in change_dirs(unit_root):
        record = read_governance(change_dir)
        if record is None:
            continue
        workspace = record.get("workspace")
        if isinstance(workspace, dict):
            change_id = str(workspace.get("change_id") or change_dir.name)
            return change_id, workspace
    return None, None


def spec_files(change_dir: Path) -> list[Path]:
    specs = change_dir / "specs"
    if not specs.is_dir():
        return []
    return sorted(path for path in specs.rglob("*.md") if path.is_file())


def resolve_contract_version(unit_root: Path, publish: dict[str, Any]) -> str | None:
    source = str(publish.get("version_source", ""))
    scheme, _, argument = source.partition(":")
    if scheme != "file":
        return None
    relative = normalize_unit_path(argument)
    if relative is None:
        return None
    path = unit_root / relative
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except (OSError, UnicodeError):
        return None


def _central_spec_diagnostics(root: Path, unit_roots: set[Path]) -> list[Diagnostic]:
    # A root that is itself a Git work tree is a unit, not a workspace: its own
    # ``openspec/changes/`` is legitimate. Only a root that merely *contains*
    # units may not own a central spec.
    if root in unit_roots:
        return []
    diagnostics: list[Diagnostic] = []
    for marker in ("workspace-spec.md",):
        if (root / marker).is_file():
            diagnostics.append(
                Diagnostic(BLOCKED, "spec.reference", f"workspace root must not own a central spec: {marker}")
            )
    if (root / "specs").is_dir():
        diagnostics.append(
            Diagnostic(BLOCKED, "spec.reference", "workspace root must not own a central specs/ directory")
        )
    if (root / CHANGES_REL).is_dir():
        diagnostics.append(
            Diagnostic(BLOCKED, "spec.reference", f"workspace root must not own {CHANGES_REL}/")
        )
    return diagnostics


def _spec_reference_diagnostics(units: list[Unit]) -> list[Diagnostic]:
    """Validate I15: every participant owns exactly one local change with specs."""
    by_id = {unit.unit_id: unit for unit in units}
    referenced: set[str] = set()
    diagnostics: list[Diagnostic] = []

    for unit in units:
        change_id, workspace = active_workspace_change(unit.root)
        if workspace is None:
            continue
        label = f"{unit.unit_id}/{change_id}"
        unknown = sorted(set(workspace) - set(GOVERNANCE_WORKSPACE_KEYS))
        if unknown:
            diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{label}: unknown keys {', '.join(unknown)}", unit.unit_id))
        for key in GOVERNANCE_WORKSPACE_REQUIRED_KEYS:
            if key not in workspace:
                diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{label}: missing {key}", unit.unit_id))
        if workspace.get("role") not in ROLES:
            diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{label}: role must be one of {list(ROLES)}", unit.unit_id))

        local_change = unit.root / CHANGES_REL / str(change_id)
        if not local_change.is_dir():
            diagnostics.append(Diagnostic(BLOCKED, "spec.missing", f"{label}: local change directory is missing", unit.unit_id))
        elif not spec_files(local_change):
            diagnostics.append(
                Diagnostic(BLOCKED, "spec.missing", f"{label}: local change has no specs/**/*.md", unit.unit_id)
            )

        related = workspace.get("related_changes")
        if related is None:
            continue
        if not isinstance(related, list):
            diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{label}: related_changes must be a list", unit.unit_id))
            continue
        seen_units: set[str] = set()
        for index, entry in enumerate(related):
            entry_label = f"{label}: related_changes[{index}]"
            if not isinstance(entry, dict):
                diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{entry_label} must be a mapping", unit.unit_id))
                continue
            unknown = sorted(set(entry) - set(RELATED_CHANGE_KEYS))
            if unknown:
                diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{entry_label} has unknown keys: {', '.join(unknown)}", unit.unit_id))
            for key in RELATED_CHANGE_REQUIRED_KEYS:
                if key not in entry:
                    diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{entry_label} is missing {key}", unit.unit_id))
            member_id = entry.get("unit")
            if not isinstance(member_id, str):
                diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{entry_label}.unit must be a string", unit.unit_id))
                continue
            if member_id in seen_units:
                diagnostics.append(Diagnostic(BLOCKED, "spec.duplicate", f"{entry_label} repeats unit {member_id}", unit.unit_id))
            seen_units.add(member_id)
            referenced.add(member_id)
            member = by_id.get(member_id)
            if member is None:
                diagnostics.append(
                    Diagnostic(BLOCKED, "spec.missing", f"{entry_label} references an invisible unit: {member_id}", unit.unit_id)
                )
                continue
            member_change_id = entry.get("change_id")
            member_change = member.root / CHANGES_REL / str(member_change_id)
            if not member_change.is_dir():
                diagnostics.append(
                    Diagnostic(
                        BLOCKED,
                        "spec.missing",
                        f"{entry_label} references a missing change directory: {member_id}/{member_change_id}",
                        unit.unit_id,
                    )
                )
            specs = entry.get("specs")
            if not isinstance(specs, list) or not specs:
                diagnostics.append(Diagnostic(BLOCKED, "spec.missing", f"{entry_label} must list at least one spec", unit.unit_id))
                continue
            for spec_index, spec in enumerate(specs):
                spec_label = f"{entry_label}.specs[{spec_index}]"
                if not isinstance(spec, dict) or set(spec) != set(SPEC_REFERENCE_KEYS):
                    diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{spec_label} keys must be exactly {list(SPEC_REFERENCE_KEYS)}", unit.unit_id))
                    continue
                if spec.get("unit") != member_id:
                    diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{spec_label}.unit must equal {member_id}", unit.unit_id))
                relative = normalize_unit_path(spec.get("path"))
                if relative is None:
                    diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{spec_label}.path is not a normalized unit path", unit.unit_id))
                    continue
                resolved = member.root / relative
                if not resolved.is_file():
                    diagnostics.append(Diagnostic(BLOCKED, "spec.missing", f"{spec_label}.path does not exist: {relative}", unit.unit_id))
                    continue
                if not resolved.is_relative_to(member_change):
                    diagnostics.append(
                        Diagnostic(BLOCKED, "spec.reference", f"{spec_label}.path is outside {member_id}/{member_change_id}", unit.unit_id)
                    )
        if unit.unit_id not in seen_units:
            diagnostics.append(Diagnostic(BLOCKED, "spec.reference", f"{label}: related_changes must include the owning unit", unit.unit_id))

    for unit in units:
        if unit.unit_id in referenced and not (unit.root / CHANGES_REL).is_dir():
            diagnostics.append(
                Diagnostic(BLOCKED, "spec.missing", f"participating unit {unit.unit_id} has no openspec/changes/", unit.unit_id)
            )
    return diagnostics


def _contract_diagnostics(units: list[Unit]) -> tuple[list[dict[str, Any]], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    publishers: dict[str, list[Unit]] = {}
    for unit in units:
        for publish in unit.publishes:
            publishers.setdefault(str(publish["contract"]), []).append(unit)

    contracts: list[dict[str, Any]] = []
    for contract, owners in sorted(publishers.items()):
        if len(owners) > 1:
            diagnostics.append(
                Diagnostic(
                    BLOCKED,
                    "contract.duplicate-provider",
                    f"contract {contract} is published by {', '.join(owner.unit_id for owner in owners)}",
                )
            )
        owner = owners[0]
        publish = next(item for item in owner.publishes if item["contract"] == contract)
        consumers = sorted(
            consumer.unit_id
            for consumer in units
            for item in consumer.consumes
            if item["contract"] == contract
        )
        contracts.append(
            {
                "contract": contract,
                "provider": owner.unit_id,
                "consumers": consumers,
                "version": resolve_contract_version(owner.root, publish),
                "artifact": publish["artifact"],
                "format": publish["format"],
                "breaking_policy": publish.get("breaking_policy", "additive-only"),
            }
        )

    visible_urls = {normalize_url(unit.repo_url): unit for unit in units if unit.repo_url}
    edges: dict[str, set[str]] = {unit.unit_id: set() for unit in units}
    for unit in units:
        for consume in unit.consumes:
            contract = str(consume["contract"])
            provider_repo = normalize_url(str(consume["provider_repo"]))
            owners = publishers.get(contract, [])
            if len(owners) > 1:
                continue
            owner = owners[0] if owners else None
            if owner is None:
                if provider_repo in visible_urls:
                    diagnostics.append(
                        Diagnostic(
                            BLOCKED,
                            "contract.orphan",
                            f"{unit.unit_id} consumes {contract} but the visible provider does not publish it",
                            unit.unit_id,
                        )
                    )
                else:
                    diagnostics.append(
                        Diagnostic(
                            WARNING,
                            "contract.orphan",
                            f"{unit.unit_id} consumes {contract} from an uncloned provider: {consume['provider_repo']}",
                            unit.unit_id,
                        )
                    )
                continue
            if normalize_url(owner.repo_url or "") != provider_repo:
                diagnostics.append(
                    Diagnostic(
                        BLOCKED,
                        "contract.provider-mismatch",
                        (
                            f"{unit.unit_id} declares provider_repo={consume['provider_repo']} "
                            f"but {contract} is published by {owner.unit_id} ({owner.repo_url})"
                        ),
                        unit.unit_id,
                    )
                )
                continue
            if owner.unit_id != unit.unit_id:
                edges[unit.unit_id].add(owner.unit_id)

    # Cycle detection over consumer -> provider edges.
    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> None:
        state[node] = 1
        for neighbour in sorted(edges.get(node, ())):
            if state.get(neighbour, 0) == 1:
                cycle = " -> ".join([*stack, node, neighbour])
                diagnostics.append(Diagnostic(BLOCKED, "contract.cycle", f"contract graph cycle: {cycle}"))
            elif state.get(neighbour, 0) == 0:
                visit(neighbour, [*stack, node])
        state[node] = 2

    for unit in units:
        if state.get(unit.unit_id, 0) == 0:
            visit(unit.unit_id, [])
    return contracts, diagnostics


def discover(roots: list[Path | str], depth: int = 1) -> Projection:
    """Aggregate the federation projection from the given roots."""
    root_paths = [Path(root).resolve() for root in roots] or [Path.cwd().resolve()]
    diagnostics: list[Diagnostic] = []

    candidates: list[tuple[Path, int]] = []
    seen: set[Path] = set()
    for index, root in enumerate(root_paths):
        for repo in find_repos(root, depth):
            if repo not in seen:
                seen.add(repo)
                candidates.append((repo, index))

    # Structural nesting (I4) is independent of depth and of identity.
    nested: set[tuple[Path, Path]] = set()
    for repo, _ in candidates:
        for inner in nested_repos_inside(repo):
            nested.add((repo, inner))
    for outer, inner in sorted(nested):
        diagnostics.append(
            Diagnostic(BLOCKED, "unit.nested", f"unit repository {inner} is nested inside {outer}")
        )

    identity_present = any((repo / IDENTITY_REL).is_file() for repo, _ in candidates)
    federation = len(candidates) >= 2 or identity_present

    candidate_roots = {repo for repo, _ in candidates}
    units: list[Unit] = []
    for repo, root_index in candidates:
        identity_path = repo / IDENTITY_REL
        if not identity_path.is_file():
            if federation and len(candidates) >= 2:
                diagnostics.append(
                    Diagnostic(
                        BLOCKED,
                        "identity.missing",
                        f"{IDENTITY_REL} is missing in candidate unit {repo}",
                    )
                )
            continue
        try:
            payload = parse_identity(identity_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, YamlError) as exc:
            diagnostics.append(Diagnostic(BLOCKED, "identity.schema", f"{repo}: {exc}"))
            continue
        schema_errors = validate_identity(payload, root=repo)
        if schema_errors:
            for error in schema_errors:
                diagnostics.append(Diagnostic(BLOCKED, "identity.schema", f"{repo}: {error}", payload.get("unit_id")))
            continue

        harness_root = locate_harness_root(repo)
        if harness_root != repo:
            diagnostics.append(
                Diagnostic(
                    BLOCKED,
                    "unit.no-harness",
                    f"{repo} must be its own harness root (found {harness_root})",
                    payload.get("unit_id"),
                )
            )
        tracked = git_tracked(repo, IDENTITY_REL)
        if not tracked:
            diagnostics.append(
                Diagnostic(
                    BLOCKED,
                    "identity.untracked",
                    f"{IDENTITY_REL} must be tracked by Git in {repo}",
                    payload.get("unit_id"),
                )
            )
        try:
            relative_path = repo.relative_to(root_paths[root_index]).as_posix() if repo != root_paths[root_index] else "."
        except ValueError:
            relative_path = repo.name
        harness_rel = harness_root.relative_to(root_paths[root_index]).as_posix() if harness_root and harness_root.is_relative_to(root_paths[root_index]) else ""
        units.append(
            Unit(
                unit_id=str(payload.get("unit_id")),
                workspace_id=str(payload.get("workspace_id")),
                unit_kind=str(payload.get("unit_kind")),
                root=repo,
                harness_root=harness_root or repo,
                root_index=root_index,
                path=relative_path,
                harness_rel=harness_rel,
                kit_version=read_version(repo),
                identity_sha256=identity_sha256(repo),
                tracked=tracked,
                repo_url=payload.get("repo_url"),
                owner=payload.get("owner"),
                publishes=[dict(item) for item in payload.get("publishes") or []],
                consumes=[dict(item) for item in payload.get("consumes") or []],
            )
        )

    duplicate_ids: set[str] = set()
    seen_ids: set[str] = set()
    for unit in units:
        if unit.unit_id in seen_ids:
            duplicate_ids.add(unit.unit_id)
        seen_ids.add(unit.unit_id)
    for unit_id in sorted(duplicate_ids):
        diagnostics.append(Diagnostic(BLOCKED, "identity.duplicate", f"unit_id is duplicated: {unit_id}", unit_id))

    workspace_ids = {unit.workspace_id for unit in units}
    if len(workspace_ids) > 1:
        diagnostics.append(
            Diagnostic(
                BLOCKED,
                "workspace.mixed",
                f"one discover/verify call accepts a single workspace_id, found: {', '.join(sorted(workspace_ids))}",
            )
        )
    versions = {unit.kit_version for unit in units if unit.kit_version}
    if len(versions) > 1:
        diagnostics.append(
            Diagnostic(
                BLOCKED,
                "kit.version-mismatch",
                f".hek/VERSION differs across units: {', '.join(sorted(versions))}",
            )
        )

    contracts, contract_diagnostics = _contract_diagnostics(units)
    diagnostics.extend(contract_diagnostics)
    diagnostics.extend(_spec_reference_diagnostics(units))
    unit_roots = {unit.root for unit in units} | candidate_roots
    for root in root_paths:
        diagnostics.extend(_central_spec_diagnostics(root, unit_roots))

    diagnostics = sort_diagnostics(diagnostics)
    return Projection(
        roots=[str(root) for root in root_paths],
        workspace_id=sorted(workspace_ids)[0] if len(workspace_ids) == 1 else None,
        units=sorted(units, key=lambda item: item.unit_id),
        contracts=contracts,
        diagnostics=diagnostics,
        digest=digest_units(units),
    )


def verify(roots: list[Path | str], depth: int = 1) -> tuple[int, Projection]:
    projection = discover(roots, depth)
    return (2 if has_blocked(projection.diagnostics) else 0), projection


def aggregation_findings(projection: Projection) -> list[dict[str, Any]]:
    return [item.as_dict() for item in projection.diagnostics]


def graph(projection: Projection) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {unit.unit_id: [] for unit in projection.units}
    providers = {
        str(publish["contract"]): unit.unit_id
        for unit in projection.units
        for publish in unit.publishes
    }
    for unit in projection.units:
        for consume in unit.consumes:
            provider = providers.get(str(consume["contract"]))
            if provider and provider not in adjacency[unit.unit_id]:
                adjacency[unit.unit_id].append(provider)
    return {key: sorted(value) for key, value in sorted(adjacency.items())}
