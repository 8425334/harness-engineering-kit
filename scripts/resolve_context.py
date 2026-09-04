#!/usr/bin/env python3
"""Resolve the deterministic trusted-context load order for task paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from check_context_docs import validate_project


class ContextResolutionError(ValueError):
    """Raised when the trusted context chain cannot be resolved safely."""


def relative_target(project_root: Path, value: str) -> str:
    configured = Path(value)
    candidate = configured if configured.is_absolute() else project_root / configured
    try:
        resolved = candidate.resolve()
        relative = resolved.relative_to(project_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContextResolutionError(f"target escapes or cannot be resolved from project root: {value}: {exc}") from exc
    return relative.as_posix() if relative.parts else "."


def path_contains(parent: str, child: str) -> bool:
    if parent == ".":
        return True
    parent_parts = Path(parent).parts
    child_parts = Path(child).parts
    return len(parent_parts) <= len(child_parts) and child_parts[:len(parent_parts)] == parent_parts


def resolve_context(project_root: Path, targets: list[str], keywords: list[str] | None = None) -> dict[str, Any]:
    project_root = project_root.resolve()
    validation_errors, _ = validate_project(project_root)
    if validation_errors:
        raise ContextResolutionError("invalid context documents: " + "; ".join(validation_errors))

    profile = project_root / "docs/methodology/profile.yaml"
    if not profile.is_file():
        raise ContextResolutionError("trusted context chain is missing docs/methodology/profile.yaml")

    index = json.loads((project_root / "ai.json").read_text(encoding="utf-8"))
    modules = index["modules"]
    modules_by_path = {str(module["path"]): module for module in modules}
    if "." not in modules_by_path:
        raise ContextResolutionError("ai.json must index the root AI.md with modules[].path='.'")

    normalized_targets = [relative_target(project_root, target) for target in targets]
    normalized_keywords = list(dict.fromkeys(keyword.strip().casefold() for keyword in keywords or [] if keyword.strip()))
    selected_paths: set[str] = {"."}
    reasons: dict[str, set[str]] = {".": {"root"}}

    for target in normalized_targets:
        for module_path in modules_by_path:
            if path_contains(module_path, target):
                selected_paths.add(module_path)
                reasons.setdefault(module_path, set()).add(f"path:{target}")

    unmatched_keywords: list[str] = []
    for keyword in normalized_keywords:
        matched_paths = [
            module_path
            for module_path, module in modules_by_path.items()
            if keyword in {str(item).casefold() for item in module["read_when"]}
        ]
        if not matched_paths:
            unmatched_keywords.append(keyword)
            continue
        for matched_path in matched_paths:
            selected_paths.add(matched_path)
            reasons.setdefault(matched_path, set()).add(f"keyword:{keyword}")
            for ancestor_path in modules_by_path:
                if path_contains(ancestor_path, matched_path):
                    selected_paths.add(ancestor_path)
                    reasons.setdefault(ancestor_path, set()).add(f"ancestor-of:{matched_path}")

    if unmatched_keywords:
        raise ContextResolutionError(f"read_when keywords have no indexed route: {', '.join(unmatched_keywords)}")

    position = {str(module["path"]): index for index, module in enumerate(modules)}
    ordered_paths = sorted(selected_paths, key=lambda path: (0 if path == "." else len(Path(path).parts), position[path]))
    selected_modules = [
        {
            "path": module_path,
            "context": str(modules_by_path[module_path]["context"]),
            "reasons": sorted(reasons[module_path]),
        }
        for module_path in ordered_paths
    ]
    load_order = [
        str(index["entrypoints"]["policy"]),
        "docs/methodology/profile.yaml",
        "ai.json",
        *(str(module["context"]) for module in selected_modules),
    ]
    return {
        "schema_version": 1,
        "project_root": str(project_root),
        "targets": normalized_targets,
        "keywords": normalized_keywords,
        "modules": selected_modules,
        "load_order": list(dict.fromkeys(load_order)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="Project-relative or absolute task paths.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root; defaults to the current directory.")
    parser.add_argument("--keyword", action="append", default=[], help="Exact read_when keyword; repeat as needed.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print the resolution contract as JSON.")
    args = parser.parse_args()
    try:
        result = resolve_context(args.root, args.targets, args.keyword)
    except (ContextResolutionError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"CONTEXT RESOLUTION FAILED: {exc}")
        return 2

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("CONTEXT RESOLVED")
        print(f"Targets: {', '.join(result['targets'])}")
        if result["keywords"]:
            print(f"Keywords: {', '.join(result['keywords'])}")
        print("Load order:")
        for path in result["load_order"]:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
