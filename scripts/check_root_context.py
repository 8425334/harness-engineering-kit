#!/usr/bin/env python3
"""Keep native root instruction adapters minimal and authoritative."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_TERMS = ("agent-policy.yaml", "profile.yaml", "ai.json", "AI.md", "resolve_context.py", "check_fitness_protection.py", "engineering", "docs/fitness", "human approval")
MAX_LINES = 40


def validate(root: Path, context_files: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")) -> list[str]:
    errors: list[str] = []
    for name in context_files:
        path = root / name
        if not path.is_file():
            errors.append(f"missing native root adapter: {name}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{name} is not readable UTF-8: {exc}")
            continue
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--context-file",
        dest="context_files",
        nargs="+",
        default=("AGENTS.md", "CLAUDE.md"),
        help="native root adapter(s) to validate",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root, tuple(args.context_files))
    if errors:
        print("ROOT CONTEXT INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"ROOT CONTEXT OK: {args.root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
