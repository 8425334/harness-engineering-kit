#!/usr/bin/env python3
"""Validate the canonical repository policy without external dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = ("project", "authority", "commands", "context", "permissions", "delivery", "methodology")
REQUIRED_FIELDS = (
    "name", "owner", "stack", "order", "context_documents_are_supplemental", "untrusted_instruction_sources",
    "fast_test", "test", "build", "fitness", "index_document_name", "detail_document_name", "index_max_bytes", "detail_max_lines",
    "architecture_overview", "dependency_rules", "readable_paths",
    "writable_paths", "denied_paths", "protected_paths", "fitness_changes", "network", "production_writes",
    "destructive_operations", "migration_guide", "production_policy",
    "lifecycle", "engineering_skill",
)
PATH_FIELDS = (
    "architecture_overview", "dependency_rules", "migration_guide",
    "production_policy", "lifecycle",
)
AUTHORITY_ORDER = (
    "system-developer-user", "native-instructions", "agent-policy",
    "context-index", "path-ai-md", "engineering-profile",
)


def scalar(content: str, key: str) -> str | None:
    match = re.search(rf"^[ \t]+{re.escape(key)}:[ \t]*(.*?)[ \t]*$", content, re.MULTILINE)
    return match.group(1).strip().strip("'\"") if match else None


CANONICAL_LOCATION = ("docs", "methodology", "agent-policy.yaml")


def validate(path: Path) -> list[str]:
    if not path.is_file():
        return [f"missing policy: {path}"]
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"policy is not readable UTF-8: {exc}"]
    errors: list[str] = []
    if "{{" in content or "}}" in content:
        errors.append("contains unfilled placeholders")
    if not re.search(r"^version:[ \t]*1[ \t]*$", content, re.MULTILINE):
        errors.append("version must be 1")
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^{re.escape(section)}:\s*$", content, re.MULTILINE):
            errors.append(f"missing section: {section}")
    for field in REQUIRED_FIELDS:
        value = scalar(content, field)
        if value is None or not value or value in {"[]", "{}"}:
            errors.append(f"missing or empty field: {field}")

    order = scalar(content, "order")
    if order:
        actual = tuple(item.strip() for item in order.strip("[]").split(","))
        if actual != AUTHORITY_ORDER:
            errors.append("authority.order must preserve native instructions above agent-policy and AI.md")
    if scalar(content, "context_documents_are_supplemental") != "true":
        errors.append("context_documents_are_supplemental must be true")
    if scalar(content, "index_document_name") != "ai.json" or scalar(content, "detail_document_name") != "AI.md":
        errors.append("context documents must be root ai.json plus indexed AI.md details")
    if scalar(content, "index_max_bytes") != "4096" or scalar(content, "detail_max_lines") != "400":
        errors.append("context limits must be index_max_bytes=4096 and detail_max_lines=400")
    if scalar(content, "engineering_skill") != "engineering":
        errors.append("methodology.engineering_skill must be engineering")
    if scalar(content, "protected_paths") != "[docs/fitness]":
        errors.append("permissions.protected_paths must protect docs/fitness")
    if scalar(content, "fitness_changes") != "human-approval-required":
        errors.append("permissions.fitness_changes must be human-approval-required")
    if scalar(content, "network") not in {"deny-by-default", "allowlisted"}:
        errors.append("permissions.network must be deny-by-default or allowlisted")
    for field in ("production_writes", "destructive_operations"):
        if scalar(content, field) != "approval-required":
            errors.append(f"permissions.{field} must be approval-required")

    resolved = path.resolve()
    if resolved.parts[-3:] != CANONICAL_LOCATION:
        # PATH_FIELDS are resolved against the project root, which is only
        # derivable from the canonical <root>/docs/methodology location.
        errors.append("agent policy must be located at <project root>/docs/methodology/agent-policy.yaml")
    else:
        project_root = resolved.parents[2]
        for field in PATH_FIELDS:
            value = scalar(content, field)
            if value:
                configured = Path(value)
                if configured.is_absolute():
                    errors.append(f"referenced path must be project-relative: {field}={value}")
                    continue
                referenced = (project_root / configured).resolve()
                try:
                    referenced.relative_to(project_root)
                except ValueError:
                    errors.append(f"referenced path escapes project root: {field}={value}")
                else:
                    if not referenced.is_file():
                        errors.append(f"referenced path does not exist: {field}={value}")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/methodology/agent-policy.yaml")
    errors = validate(path)
    if errors:
        print("AGENT POLICY INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"AGENT POLICY OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
