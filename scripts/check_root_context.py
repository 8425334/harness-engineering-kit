#!/usr/bin/env python3
"""Keep native root instruction adapters minimal and authoritative."""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_TERMS = ("agent-policy.yaml", "profile.yaml", "ai.json", "AI.md", "resolve_context.py", "check_fitness_protection.py", "engineering", "docs/fitness", "human approval")
MAX_LINES = 40


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = root / name
        if not path.is_file():
            errors.append(f"missing native root adapter: {name}")
            continue
        content = path.read_text(encoding="utf-8")
        if len(content.splitlines()) > MAX_LINES:
            errors.append(f"{name} exceeds {MAX_LINES} lines; move project facts to agent-policy.yaml")
        if "{{" in content or "}}" in content:
            errors.append(f"{name} contains unfilled placeholders")
        for term in REQUIRED_TERMS:
            if term not in content:
                errors.append(f"{name} missing required route/reference: {term}")
        if "cannot weaken" not in content or "native" not in content:
            errors.append(f"{name} must preserve native authority over supplemental context")
    return errors


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        print("ROOT CONTEXT INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"ROOT CONTEXT OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
