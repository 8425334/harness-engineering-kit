#!/usr/bin/env python3
"""Validate risk and evidence defaults without duplicating project policy."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ALLOWED_PROFILES = {"light", "standard", "regulated", "experimental"}
ALLOWED_RISKS = {"low", "medium", "high", "critical"}
ALLOWED_SELF_REFINE_POLICIES = {"disabled", "recommended", "required", "required-independent"}
REQUIRED_SECTIONS = ("evidence", "exceptions", "review")
REQUIRED_FIELDS = (
    "version", "profile", "project_risk", "owner", "non_trivial_definition",
    "required_gates", "approval", "production", "record_path",
    "owner_required", "expiry_required", "rule_owner",
    "methodology_version", "next_review",
)
FORBIDDEN_PROJECT_FACTS = ("commands", "agent_permissions", "stack", "readable_paths", "writable_paths")


def value(content: str, key: str) -> str | None:
    match = re.search(rf"^[ \t]*{re.escape(key)}:[ \t]*([^#\n]*)", content, re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else None


def self_refine_policy(path: Path) -> str:
    """Return the configured refinement policy, preserving legacy defaults."""
    if not path.is_file():
        return "recommended"
    content = path.read_text(encoding="utf-8")
    section = re.search(r"^self_refine:\s*$([\s\S]*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*$|\Z)", content, re.MULTILINE)
    if not section:
        return "recommended"
    match = re.search(r"^[ \t]+policy:\s*([^#\n]+)", section.group(1), re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else "recommended"


def self_refine_max_iterations(path: Path) -> int:
    if not path.is_file():
        return 3
    content = path.read_text(encoding="utf-8")
    section = re.search(r"^self_refine:\s*$([\s\S]*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*$|\Z)", content, re.MULTILINE)
    if not section:
        return 3
    match = re.search(r"^[ \t]+max_iterations:\s*([^#\n]+)", section.group(1), re.MULTILINE)
    try:
        return int(match.group(1).strip()) if match else 3
    except ValueError:
        return 3


def validate(path: Path) -> list[str]:
    if not path.is_file():
        return [f"missing profile: {path}"]
    content = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "{{" in content or "}}" in content:
        errors.append("contains unfilled placeholders")
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^{section}:\s*$", content, re.MULTILINE):
            errors.append(f"missing section: {section}")
    for field in REQUIRED_FIELDS:
        if not value(content, field):
            errors.append(f"missing or empty field: {field}")
    if value(content, "version") != "2":
        errors.append("version must be 2")
    if value(content, "profile") not in ALLOWED_PROFILES:
        errors.append(f"profile must be one of {sorted(ALLOWED_PROFILES)}")
    if value(content, "project_risk") not in ALLOWED_RISKS:
        errors.append(f"project_risk must be one of {sorted(ALLOWED_RISKS)}")
    if value(content, "owner_required") != "true" or value(content, "expiry_required") != "true":
        errors.append("exceptions must require owner and expiry")
    for field in FORBIDDEN_PROJECT_FACTS:
        if re.search(rf"^\s*{field}:\s*", content, re.MULTILINE):
            errors.append(f"project fact belongs in agent-policy.yaml, not profile: {field}")
    policy = self_refine_policy(path)
    if policy not in ALLOWED_SELF_REFINE_POLICIES:
        errors.append(f"self_refine.policy must be one of {sorted(ALLOWED_SELF_REFINE_POLICIES)}")
    section = re.search(r"^self_refine:\s*$([\s\S]*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*$|\Z)", content, re.MULTILINE)
    if section:
        iterations = re.search(r"^[ \t]+max_iterations:\s*([^#\n]+)", section.group(1), re.MULTILINE)
        if not iterations:
            errors.append("self_refine.max_iterations is required when self_refine is configured")
        else:
            try:
                value_int = int(iterations.group(1).strip())
                if not 1 <= value_int <= 10:
                    errors.append("self_refine.max_iterations must be between 1 and 10")
            except ValueError:
                errors.append("self_refine.max_iterations must be an integer")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/methodology/profile.yaml")
    errors = validate(path)
    if errors:
        print("PROFILE INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"PROFILE OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
