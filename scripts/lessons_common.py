"""Shared validation and matching helpers for project lessons."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from methodology_common import read_json, utc_now, write_json


LESSON_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")
LESSON_STATUSES = {"candidate", "active", "retired"}
FAILURE_SOURCES = {"fitness", "phase", "test", "diff", "production", "manual"}
FAILURE_CATEGORIES = {"context", "contract", "implementation", "test", "fitness", "drift", "production", "other"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_slug(value: Any, field: str = "lesson_id") -> list[str]:
    if not isinstance(value, str) or not LESSON_ID_PATTERN.fullmatch(value):
        return [f"{field} must be a 2-63 character lowercase slug"]
    return []


def load_failure_events(change_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = change_dir / "evidence" / "failure-events.jsonl"
    if not path.is_file():
        return [], []
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"failure-events.jsonl line {line_number} is invalid JSON")
            continue
        if not isinstance(item, dict):
            errors.append(f"failure-events.jsonl line {line_number} must be an object")
            continue
        events.append(item)
    return events, errors


def validate_failure_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("schema_version", "event_id", "change_id", "source", "category", "rule", "message", "actor", "at"):
        if not meaningful_value(event.get(field)):
            errors.append(f"failure event missing {field}")
    if event.get("schema_version") != 1:
        errors.append("failure event schema_version must be 1")
    if event.get("source") not in FAILURE_SOURCES:
        errors.append(f"failure event source must be one of {sorted(FAILURE_SOURCES)}")
    if event.get("category") not in FAILURE_CATEGORIES:
        errors.append(f"failure event category must be one of {sorted(FAILURE_CATEGORIES)}")
    if not isinstance(event.get("paths", []), list):
        errors.append("failure event paths must be an array")
    if not isinstance(event.get("evidence", []), list):
        errors.append("failure event evidence must be an array")
    return errors


def meaningful_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and "{{" not in value and "}}" not in value
    return value is not None


def validate_lesson(lesson: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("schema_version", "lesson_id", "title", "pattern", "root_cause", "prevention", "verification", "scope", "keywords", "status"):
        if not meaningful_value(lesson.get(field)):
            errors.append(f"lesson missing {field}")
    if lesson.get("schema_version") != 1:
        errors.append("lesson schema_version must be 1")
    errors.extend(validate_slug(lesson.get("lesson_id")))
    if lesson.get("status") not in LESSON_STATUSES:
        errors.append(f"lesson status must be one of {sorted(LESSON_STATUSES)}")
    errors.extend(_require_string_array(lesson, "keywords", non_empty=True))
    for field in ("source_changes", "source_events", "rules", "paths"):
        errors.extend(_require_string_array(lesson, field))
    if "approved" in lesson and not isinstance(lesson["approved"], dict):
        errors.append("lesson approved must be an object")
    return errors


def _require_string_array(lesson: dict[str, Any], field: str, *, non_empty: bool = False) -> list[str]:
    """Validate that ``field`` is an array of non-placeholder strings."""
    value = lesson.get(field, [])
    if not isinstance(value, list) or (non_empty and not value):
        return [f"lesson {field} must be a{' non-empty' if non_empty else ''} array"]
    if not all(isinstance(item, str) and meaningful_value(item) for item in value):
        return [f"lesson {field} must contain only non-placeholder strings"]
    return []


def lessons_dir(project_root: Path) -> Path:
    return project_root / "docs" / "methodology" / "lessons"


def load_lessons(project_root: Path, *, active_only: bool = True) -> tuple[list[dict[str, Any]], list[str]]:
    directory = lessons_dir(project_root)
    if not directory.is_dir():
        return [], [f"lessons directory is missing: {directory}"]
    lessons: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            lesson = read_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            errors.append(f"lesson is not a valid JSON object: {path.name}")
            continue
        lesson_errors = validate_lesson(lesson)
        if lesson_errors:
            errors.extend(f"{path.name}: {error}" for error in lesson_errors)
            continue
        if active_only and lesson.get("status") != "active":
            # Retired (or otherwise non-active) lessons stay on disk for audit;
            # retrieval and preflight simply skip them instead of failing.
            continue
        lesson["_path"] = str(path)
        lessons.append(lesson)
    return lessons, errors


def lesson_matches(lesson: dict[str, Any], keywords: list[str], rules: list[str], paths: list[str], scope: str | None) -> bool:
    normalized_keywords = [item.lower() for item in keywords if item.strip()]
    haystack = " ".join(str(lesson.get(field, "")) for field in ("lesson_id", "title", "pattern", "root_cause", "prevention", "verification", "scope", "keywords")).lower()
    if normalized_keywords and not all(keyword in haystack for keyword in normalized_keywords):
        return False
    lesson_rules = {str(item) for item in lesson.get("rules", [])}
    if rules and not lesson_rules.intersection(rules):
        return False
    if scope and scope not in {str(lesson.get("scope")), *[str(item) for item in lesson.get("scopes", [])]}:
        return False
    if paths:
        lesson_paths = [str(item) for item in lesson.get("paths", [])]
        if lesson_paths and not any(path == pattern or path.startswith(pattern.rstrip("/") + "/") for path in paths for pattern in lesson_paths):
            return False
    return True


def now() -> str:
    return utc_now()


def write_json_file(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, value)
