#!/usr/bin/env python3
"""Validate the compact root context index and its detailed AI.md targets."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


MAX_INDEX_BYTES = 4096
MAX_DETAIL_BYTES = 32768
MAX_DETAIL_LINES = 400
MAX_MODULES = 50
TOP_LEVEL_KEYS = {"schema_version", "kind", "project", "summary", "modules", "entrypoints"}
MODULE_KEYS = {"path", "summary", "context", "read_when"}
ENTRYPOINT_KEYS = {"policy", "lifecycle"}
DETAIL_HEADINGS = ("## Responsibilities", "## Boundaries", "## Local Verification", "## Navigation")
EXCLUDED_DIRECTORIES = {".git", ".claude", ".agents", "node_modules", "target", "build", "dist", "archive", "changes", ".venv", "venv"}
AI_JSON_SIGNALS = {"project-summary", "module-topology", "context-route", "entrypoint"}
AI_MD_SIGNALS = {"responsibility", "boundary", "invariant", "dependency", "contract", "local-verification"}
CONTEXT_SIGNALS = {"none", *AI_JSON_SIGNALS, *AI_MD_SIGNALS}
IMPACT_KEYS = {"schema_version", "analyzed_paths", "signals", "ai_json", "ai_md"}
DECISION_KEYS = {"required", "paths", "reason"}


def useful_string(value: Any, maximum: int | None = None) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "{{" not in value and "}}" not in value and (maximum is None or len(value) <= maximum)


def project_path(project_root: Path, value: Any, *, file_required: bool = False, directory_required: bool = False) -> tuple[Path | None, str | None]:
    if not useful_string(value):
        return None, "path must be a non-placeholder string"
    try:
        configured = Path(str(value))
    except (OSError, ValueError) as exc:
        return None, f"path is invalid: {exc}"
    if configured.is_absolute():
        return None, "path must be project-relative"
    try:
        resolved = (project_root / configured).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return None, f"path cannot be resolved: {exc}"
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return None, "path escapes project root"
    if file_required and not resolved.is_file():
        return None, "file does not exist"
    if directory_required and not resolved.is_dir():
        return None, "directory does not exist"
    return resolved, None


def validate_detail(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{path} is not readable UTF-8: {exc}"]
    if len(content.encode("utf-8")) > MAX_DETAIL_BYTES:
        errors.append(f"{path} exceeds {MAX_DETAIL_BYTES} bytes")
    if len(content.splitlines()) > MAX_DETAIL_LINES:
        errors.append(f"{path} exceeds {MAX_DETAIL_LINES} lines")
    if "{{" in content or "}}" in content:
        errors.append(f"{path} contains unfilled placeholders")
    if "cannot override or weaken" not in content:
        errors.append(f"{path} must state that it cannot override higher-level policy")
    for heading in DETAIL_HEADINGS:
        if heading not in content:
            errors.append(f"{path} missing heading: {heading}")
    return errors


def find_ai_docs(project_root: Path) -> tuple[set[Path], list[str]]:
    documents: set[Path] = set()
    errors: list[str] = []
    for path in project_root.rglob("AI.md"):
        relative = path.relative_to(project_root)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(project_root.resolve())
        except ValueError:
            errors.append(f"AI.md resolves outside project root: {relative}")
            continue
        except (OSError, RuntimeError) as exc:
            errors.append(f"AI.md cannot be resolved: {relative}: {exc}")
            continue
        documents.add(resolved)
    return documents, errors


def planned_file_path(project_root: Path, value: Any) -> str | None:
    if not useful_string(value, 240):
        return "must be a non-placeholder project-relative file up to 240 characters"
    try:
        configured = Path(str(value))
    except (OSError, ValueError) as exc:
        return f"path is invalid: {exc}"
    if configured.is_absolute() or str(value).endswith("/") or configured.name in {"", ".", ".."}:
        return "must identify a project-relative file, not a directory"
    if "\\" in str(value) or configured.as_posix() != str(value) or any(part in {"", ".", ".."} for part in configured.parts):
        return "must use a normalized POSIX project-relative path"
    resolved, path_error = project_path(project_root, value)
    if path_error:
        return path_error
    if resolved and resolved.exists() and not resolved.is_file():
        return "resolves to a directory"
    return None


def validate_project(project_root: Path) -> tuple[list[str], set[str]]:
    project_root = project_root.resolve()
    index_path = project_root / "ai.json"
    errors: list[str] = []
    contexts: set[str] = set()
    if not index_path.is_file():
        return ["missing root context index: ai.json"], contexts
    if index_path.stat().st_size > MAX_INDEX_BYTES:
        errors.append(f"ai.json exceeds {MAX_INDEX_BYTES} bytes")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"ai.json is invalid JSON: {exc}"], contexts
    if not isinstance(index, dict):
        return ["ai.json must be a JSON object"], contexts
    if set(index) != TOP_LEVEL_KEYS:
        errors.append(f"ai.json keys must be exactly {sorted(TOP_LEVEL_KEYS)}")
    if index.get("schema_version") != 1 or index.get("kind") != "context-index":
        errors.append("ai.json requires schema_version=1 and kind=context-index")
    if not useful_string(index.get("project"), 80):
        errors.append("ai.json project must be a non-placeholder string up to 80 characters")
    if not useful_string(index.get("summary"), 240):
        errors.append("ai.json summary must be a non-placeholder string up to 240 characters")

    modules = index.get("modules")
    if not isinstance(modules, list) or not modules or len(modules) > MAX_MODULES:
        errors.append(f"ai.json modules must contain 1-{MAX_MODULES} entries")
        modules = []
    module_paths: set[str] = set()
    for position, module in enumerate(modules):
        label = f"ai.json modules[{position}]"
        if not isinstance(module, dict) or set(module) != MODULE_KEYS:
            errors.append(f"{label} keys must be exactly {sorted(MODULE_KEYS)}")
            continue
        module_path = module.get("path")
        context = module.get("context")
        if not useful_string(module_path, 160) or str(module_path) in module_paths:
            errors.append(f"{label}.path must be unique and up to 160 characters")
            continue
        configured_module = Path(str(module_path))
        if str(module_path) != "." and (
            "\\" in str(module_path)
            or configured_module.as_posix() != str(module_path)
            or str(module_path).endswith("/")
            or any(part in {"", ".", ".."} for part in configured_module.parts)
        ):
            errors.append(f"{label}.path must be a normalized POSIX project-relative directory")
            continue
        module_paths.add(str(module_path))
        _, path_error = project_path(project_root, module_path, directory_required=True)
        if path_error:
            errors.append(f"{label}.path {path_error}")
        if not useful_string(module.get("summary"), 160):
            errors.append(f"{label}.summary must be non-placeholder and up to 160 characters")
        read_when = module.get("read_when")
        if not isinstance(read_when, list) or not 1 <= len(read_when) <= 8 or not all(useful_string(item, 40) for item in read_when):
            errors.append(f"{label}.read_when requires 1-8 keywords up to 40 characters")
        elif len(set(read_when)) != len(read_when):
            errors.append(f"{label}.read_when keywords must be unique")
        expected_context = "AI.md" if module_path == "." else f"{str(module_path).rstrip('/')}/AI.md"
        if context != expected_context:
            errors.append(f"{label}.context must be {expected_context}")
            continue
        context_path, context_error = project_path(project_root, context, file_required=True)
        if context_error:
            errors.append(f"{label}.context {context_error}")
        elif context_path:
            contexts.add(str(Path(str(context))))
            errors.extend(validate_detail(context_path))
    if "." not in module_paths:
        errors.append("ai.json modules must include path '.' so every task resolves through root AI.md")

    entrypoints = index.get("entrypoints")
    if not isinstance(entrypoints, dict) or set(entrypoints) != ENTRYPOINT_KEYS:
        errors.append(f"ai.json entrypoints keys must be exactly {sorted(ENTRYPOINT_KEYS)}")
    else:
        for key, value in entrypoints.items():
            _, path_error = project_path(project_root, value, file_required=True)
            if path_error:
                errors.append(f"ai.json entrypoints.{key} {path_error}")

    indexed = {(project_root / path).resolve() for path in contexts}
    discovered, discovery_errors = find_ai_docs(project_root)
    errors.extend(discovery_errors)
    unindexed = discovered - indexed
    for path in sorted(unindexed):
        errors.append(f"AI.md is not indexed by root ai.json: {path.relative_to(project_root)}")
    return errors, contexts


def validate_context_impact(path: Path, project_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        impact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"context-impact.json is invalid: {exc}"]
    if not isinstance(impact, dict):
        return None, ["context-impact.json must be a JSON object"]
    if set(impact) != IMPACT_KEYS:
        errors.append(f"context-impact.json keys must be exactly {sorted(IMPACT_KEYS)}")
    if impact.get("schema_version") != 1:
        errors.append("context-impact.json schema_version must be 1")

    analyzed_paths = impact.get("analyzed_paths")
    if not isinstance(analyzed_paths, list) or not analyzed_paths or len(analyzed_paths) > 200 or not all(isinstance(item, str) for item in analyzed_paths):
        errors.append("context-impact.json analyzed_paths must contain 1-200 planned project-relative files")
        analyzed_paths = []
    elif len(set(analyzed_paths)) != len(analyzed_paths):
        errors.append("context-impact.json analyzed_paths must be unique")
    for planned in analyzed_paths:
        path_error = planned_file_path(project_root, planned)
        if path_error:
            errors.append(f"context-impact.json analyzed path {planned!r}: {path_error}")

    signals = impact.get("signals")
    if not isinstance(signals, list) or not signals or not all(isinstance(signal, str) for signal in signals) or len(set(signals)) != len(signals) or not all(signal in CONTEXT_SIGNALS for signal in signals):
        errors.append(f"context-impact.json signals must be unique values from {sorted(CONTEXT_SIGNALS)}")
        signals = []
    if "none" in signals and len(signals) != 1:
        errors.append("context-impact.json signal none must be used alone")

    for document, required_signals in (("ai_json", AI_JSON_SIGNALS), ("ai_md", AI_MD_SIGNALS)):
        decision = impact.get(document)
        if not isinstance(decision, dict) or set(decision) != DECISION_KEYS:
            errors.append(f"context-impact.json {document} keys must be exactly {sorted(DECISION_KEYS)}")
            continue
        required = decision.get("required")
        paths = decision.get("paths")
        if not isinstance(required, bool):
            errors.append(f"context-impact.json {document}.required must be boolean")
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths) or len(set(paths)) != len(paths):
            errors.append(f"context-impact.json {document}.paths must be a unique array")
            paths = []
        if required is True and not paths:
            errors.append(f"context-impact.json {document}.paths is required when an update is required")
        if required is False and paths:
            errors.append(f"context-impact.json {document}.paths must be empty when no update is required")
        if not useful_string(decision.get("reason"), 240):
            errors.append(f"context-impact.json {document}.reason must explain the decision in up to 240 characters")
        relevant = bool(set(signals) & required_signals)
        if relevant and required is not True:
            errors.append(f"context-impact.json signals require {document} update")
        if required is True and not relevant:
            errors.append(f"context-impact.json {document}.required needs a matching impact signal")
        for planned in paths:
            path_error = planned_file_path(project_root, planned)
            if path_error:
                errors.append(f"context-impact.json {document} path {planned!r}: {path_error}")
            if planned not in analyzed_paths:
                errors.append(f"context-impact.json {document} path must also appear in analyzed_paths: {planned}")
            if document == "ai_json" and planned != "ai.json":
                errors.append("context-impact.json ai_json path must be root ai.json")
            if document == "ai_md" and not (planned == "AI.md" or str(planned).endswith("/AI.md")):
                errors.append(f"context-impact.json ai_md path must end with AI.md: {planned}")
    return impact, errors


def main() -> int:
    project_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    errors, contexts = validate_project(project_root)
    if errors:
        print("CONTEXT DOCS INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"CONTEXT DOCS OK: ai.json -> {len(contexts)} AI.md document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
