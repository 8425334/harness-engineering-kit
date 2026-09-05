#!/usr/bin/env python3
"""Retrieve active project lessons for a target task or path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lessons_common import lesson_matches, load_lessons


def retrieve(project_root: Path, keywords: list[str], rules: list[str], paths: list[str], scope: str | None) -> dict[str, object]:
    lessons, errors = load_lessons(project_root, active_only=True)
    matched = [lesson for lesson in lessons if lesson_matches(lesson, keywords, rules, paths, scope)]
    for lesson in matched:
        lesson.pop("_path", None)
    return {"project_root": str(project_root), "keywords": keywords, "rules": rules, "paths": paths, "scope": scope, "lessons": matched, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--rule", action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--scope")
    parser.add_argument("--json", action="store_true", help="deprecated: output is always JSON")
    args = parser.parse_args()
    result = retrieve(args.project_root.resolve(), args.keyword, args.rule, args.path, args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
