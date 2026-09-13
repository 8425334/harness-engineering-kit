#!/usr/bin/env python3
"""Keep native root instruction adapters minimal and authoritative."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import layout


# An adapter is a router, not a manual: it names the policy, the control plane and
# the methodology entry point, and leaves the rest to .hek/. Bare document names
# stay valid under any layout because they remain substrings of the full path.
REQUIRED_TERMS = (
    "agent-policy.yaml",
    "engineering",
    layout.relative("fitness"),
    layout.relative("core"),
    "human approval",
)

#: Phrases the adapter must carry. Matched against whitespace-normalised content
#: so a template may wrap its lines wherever it reads best.
REQUIRED_PHRASES = (
    "Automatically select and load the `engineering` Skill",
    "Do not require the user to type `/engineering`",
    "cannot weaken",
    "native",
)
MAX_LINES = 34


def normalize(content: str) -> str:
    """Collapse whitespace so phrase checks survive line wrapping."""
    return re.sub(r"\s+", " ", content)


def validate(root: Path, context_files: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")) -> list[str]:
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
        flat = normalize(content)
        for term in REQUIRED_TERMS:
            if term not in content:
                errors.append(f"{name} missing required route/reference: {term}")
        for phrase in REQUIRED_PHRASES:
            if phrase not in flat:
                errors.append(f"{name} missing required statement: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--context-file",
        dest="context_files",
        nargs="+",
        default=("AGENTS.md", "CLAUDE.md", "GEMINI.md"),
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
