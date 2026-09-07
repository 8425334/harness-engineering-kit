#!/usr/bin/env python3
"""Validate the implementation-ready Engineering design review packet."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = (
    "Design Summary", "Scope and Constraints", "Current State",
    "Architecture and Relationship Topology", "Responsibilities", "Runtime Flows",
    "Interfaces and Data", "Quality and Operations", "Delivery and Rollback",
    "Decisions and Alternatives", "Verification Strategy", "Risks and Open Questions",
    "Developer Confirmation",
)
HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
DECISION = re.compile(r"^###\s+D[1-9][0-9]*:\s+.+$", re.MULTILINE)
CONFIRMATION = re.compile(r"^-\s+\[[ xX]\]\s+C[1-9][0-9]*\b", re.MULTILINE)


def sections(content: str) -> tuple[dict[str, str], list[str]]:
    matches = list(HEADING.finditer(content))
    result: dict[str, str] = {}
    errors: list[str] = []
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        if name in result:
            errors.append(f"design.md contains duplicate section: {name}")
        else:
            result[name] = content[match.end():body_end].strip()
    return result, errors


def meaningful_body(body: str) -> bool:
    normalized = re.sub(r"[`#>*_|\[\]()-]", "", body).strip()
    return len(normalized) >= 12 and "{{" not in body and "}}" not in body


def has_mermaid(body: str) -> bool:
    return bool(re.search(r"```mermaid\s+.+?```", body, re.DOTALL | re.IGNORECASE))


def has_markdown_table(body: str) -> bool:
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    return len(lines) >= 3 and any(re.fullmatch(r"\|?[\s:|-]+\|?", line) for line in lines)


def validate(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ["design.md must be a readable UTF-8 file"]
    errors: list[str] = []
    if "{{" in content or "}}" in content:
        errors.append("design.md contains unresolved template placeholders")
    parsed, section_errors = sections(content)
    errors.extend(section_errors)
    for name in REQUIRED_SECTIONS:
        body = parsed.get(name)
        if body is None:
            errors.append(f"design.md missing required section: {name}")
        elif not meaningful_body(body):
            errors.append(f"design.md section is empty or not meaningful: {name}")
    architecture = parsed.get("Architecture and Relationship Topology", "")
    if architecture and not has_mermaid(architecture):
        errors.append("Architecture and Relationship Topology requires a Mermaid diagram")
    responsibilities = parsed.get("Responsibilities", "")
    if responsibilities and not has_markdown_table(responsibilities):
        errors.append("Responsibilities requires a Markdown ownership/dependency table")
    runtime = parsed.get("Runtime Flows", "")
    if runtime and not has_mermaid(runtime):
        errors.append("Runtime Flows requires a Mermaid diagram")
    decisions = parsed.get("Decisions and Alternatives", "")
    if decisions:
        if not DECISION.search(decisions):
            errors.append("Decisions and Alternatives requires at least one numbered D<n> decision")
        for field in ("Choice:", "Reason:", "Alternatives:"):
            if field not in decisions:
                errors.append(f"Decisions and Alternatives requires {field}")
    confirmation = parsed.get("Developer Confirmation", "")
    if confirmation and not CONFIRMATION.search(confirmation):
        errors.append("Developer Confirmation requires at least one C<n> confirmation item")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design", type=Path, help="Path to design.md or its change directory")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    path = args.design.resolve()
    if path.is_dir():
        path /= "design.md"
    errors = validate(path)
    payload = {"design": str(path), "status": "PASS" if not errors else "BLOCKED", "errors": errors}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"DESIGN {payload['status']}: {path}")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
