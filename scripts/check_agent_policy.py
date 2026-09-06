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
FIELD_SECTIONS = {
    "name": "project", "owner": "project", "stack": "project",
    "order": "authority", "context_documents_are_supplemental": "authority",
    "untrusted_instruction_sources": "authority",
    "fast_test": "commands", "test": "commands", "build": "commands", "fitness": "commands",
    "index_document_name": "context", "detail_document_name": "context",
    "index_max_bytes": "context", "detail_max_lines": "context",
    "architecture_overview": "context", "dependency_rules": "context",
    "readable_paths": "permissions", "writable_paths": "permissions", "denied_paths": "permissions",
    "protected_paths": "permissions", "fitness_changes": "permissions", "network": "permissions",
    "production_writes": "permissions", "destructive_operations": "permissions",
    "migration_guide": "delivery", "production_policy": "delivery",
    "lifecycle": "methodology", "engineering_skill": "methodology",
}
PATH_FIELDS = (
    "architecture_overview", "dependency_rules", "migration_guide",
    "production_policy", "lifecycle",
)
AUTHORITY_ORDER = (
    "system-developer-user", "native-instructions", "agent-policy",
    "context-index", "path-ai-md", "engineering-profile",
)


def section_values(content: str, section: str, key: str) -> list[str]:
    values: list[str] = []
    current_section: str | None = None
    for line in content.splitlines():
        section_match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):[ \t]*$", line)
        if section_match:
            current_section = section_match.group(1)
            continue
        if current_section != section:
            continue
        field_match = re.match(rf"^[ \t]+{re.escape(key)}:[ \t]*(.*?)[ \t]*$", line)
        if field_match:
            values.append(field_match.group(1).strip().strip("'\""))
    return values


def scalar(content: str, section: str, key: str) -> str | None:
    values = section_values(content, section, key)
    return values[0] if len(values) == 1 else None


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
        section = FIELD_SECTIONS[field]
        values = section_values(content, section, field)
        if len(values) != 1 or not values[0] or values[0] in {"[]", "{}"}:
            errors.append(f"missing, duplicated, or empty field: {section}.{field}")

    order = scalar(content, "authority", "order")
    if order:
        actual = tuple(item.strip() for item in order.strip("[]").split(","))
        if actual != AUTHORITY_ORDER:
            errors.append("authority.order must preserve native instructions above agent-policy and AI.md")
    if scalar(content, "authority", "context_documents_are_supplemental") != "true":
        errors.append("context_documents_are_supplemental must be true")
    if scalar(content, "context", "index_document_name") != "ai.json" or scalar(content, "context", "detail_document_name") != "AI.md":
        errors.append("context documents must be root ai.json plus indexed AI.md details")
    if scalar(content, "context", "index_max_bytes") != "4096" or scalar(content, "context", "detail_max_lines") != "400":
        errors.append("context limits must be index_max_bytes=4096 and detail_max_lines=400")
    if scalar(content, "methodology", "engineering_skill") != "engineering":
        errors.append("methodology.engineering_skill must be engineering")
    if scalar(content, "permissions", "protected_paths") != "[docs/fitness]":
        errors.append("permissions.protected_paths must protect docs/fitness")
    if scalar(content, "permissions", "fitness_changes") != "human-approval-required":
        errors.append("permissions.fitness_changes must be human-approval-required")
    if scalar(content, "permissions", "network") not in {"deny-by-default", "allowlisted"}:
        errors.append("permissions.network must be deny-by-default or allowlisted")
    for field in ("production_writes", "destructive_operations"):
        if scalar(content, "permissions", field) != "approval-required":
            errors.append(f"permissions.{field} must be approval-required")

    resolved = path.resolve()
    if resolved.parts[-3:] != CANONICAL_LOCATION:
        # PATH_FIELDS are resolved against the project root, which is only
        # derivable from the canonical <root>/docs/methodology location.
        errors.append("agent policy must be located at <project root>/docs/methodology/agent-policy.yaml")
    else:
        project_root = resolved.parents[2]
        for field in PATH_FIELDS:
            value = scalar(content, FIELD_SECTIONS[field], field)
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
