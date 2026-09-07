#!/usr/bin/env python3
"""Validate Engineering execution evidence against OpenSpec task progress."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from methodology_common import meaningful, read_json


TASK_LINE = re.compile(r"^- \[([ xX])\] ([0-9]+(?:\.[0-9]+)+)\s+(.+)$", re.MULTILINE)
ISOLATION_MODES = {"worktree", "disjoint-write-scope", "single-workspace"}


def meaningful_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "{{" not in value and "}}" not in value


def parse_timestamp(value: Any) -> datetime | None:
    if not meaningful_value(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def valid_relative_path(value: Any) -> bool:
    if not meaningful_value(value) or "\\" in str(value):
        return False
    path = PurePosixPath(str(value))
    return not path.is_absolute() and ".." not in path.parts and not any(char in str(value) for char in "*?[")


def validate_commands(commands: Any, label: str, errors: list[str]) -> None:
    if not isinstance(commands, list) or not commands:
        errors.append(f"{label} requires at least one command result")
        return
    for item in commands:
        if (
            not isinstance(item, dict)
            or not meaningful_value(item.get("command"))
            or not isinstance(item.get("exit_code"), int)
            or isinstance(item.get("exit_code"), bool)
            or item.get("exit_code") != 0
            or not meaningful_value(item.get("evidence"))
        ):
            errors.append(f"every {label} command requires command, integer exit_code=0, and evidence")


def task_status(change_dir: Path) -> tuple[dict[str, bool], list[str]]:
    path = change_dir / "tasks.md"
    if not meaningful(path):
        return {}, ["missing or placeholder artifact: tasks.md"]
    try:
        matches = TASK_LINE.findall(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        return {}, [f"tasks.md is not readable UTF-8: {exc}"]
    if not matches:
        return {}, ["tasks.md must contain OpenSpec checkbox tasks such as `- [ ] 1.1 Description`"]
    tasks: dict[str, bool] = {}
    errors: list[str] = []
    for mark, task_id, _title in matches:
        if task_id in tasks:
            errors.append(f"duplicate OpenSpec task id: {task_id}")
        tasks[task_id] = mark.lower() == "x"
    return tasks, errors


def validate_execution(change_dir: Path, record: dict[str, Any], review: dict[str, Any] | None = None) -> list[str]:
    tasks, errors = task_status(change_dir)
    try:
        evidence = read_json(change_dir / "execution-evidence.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return errors + ["execution-evidence.json must be a valid JSON object"]
    if evidence.get("schema_version") != 1:
        errors.append("execution-evidence.json schema_version must be 1")
    strategy = evidence.get("strategy")
    capability = evidence.get("capability") if isinstance(evidence.get("capability"), dict) else {}
    isolation = capability.get("isolation")
    max_concurrency = capability.get("max_concurrency")
    if strategy not in {"parallel", "sequential"}:
        errors.append("execution strategy must be parallel or sequential")
    if isolation not in ISOLATION_MODES:
        errors.append(f"execution isolation must be one of {sorted(ISOLATION_MODES)}")
    if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or max_concurrency < 1:
        errors.append("execution max_concurrency must be a positive integer")
    if strategy == "parallel" and (capability.get("agent_parallelism") is not True or max_concurrency < 2):
        errors.append("parallel execution requires agent_parallelism=true and max_concurrency>=2")
    if strategy == "sequential" and (max_concurrency != 1 or not meaningful_value(evidence.get("fallback_reason"))):
        errors.append("sequential execution requires max_concurrency=1 and fallback_reason")
    started_at = parse_timestamp(evidence.get("started_at"))
    completed_at = parse_timestamp(evidence.get("completed_at"))
    if started_at is None or completed_at is None or started_at > completed_at:
        errors.append("execution evidence requires ordered timezone-aware started_at/completed_at")
    if not meaningful_value(evidence.get("coordinator")):
        errors.append("execution coordinator is required")

    runs = evidence.get("task_runs")
    if not isinstance(runs, list):
        errors.append("execution task_runs must be an array")
        runs = []
    run_ids: set[str] = set()
    changed_files: set[str] = set()
    for index, run in enumerate(runs):
        label = f"execution task_runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{label} must be an object")
            continue
        task_id = run.get("task_id")
        if task_id not in tasks:
            errors.append(f"{label} references unknown OpenSpec task: {task_id}")
            continue
        if task_id in run_ids:
            errors.append(f"duplicate execution run for task: {task_id}")
        run_ids.add(str(task_id))
        if run.get("status") != "completed":
            errors.append(f"execution run {task_id} status must be completed")
        for field in ("actor", "workspace", "result_ref"):
            if not meaningful_value(run.get(field)):
                errors.append(f"execution run {task_id} requires {field}")
        if run.get("isolation") != isolation:
            errors.append(f"execution run {task_id} isolation must match the declared capability")
        run_start = parse_timestamp(run.get("started_at"))
        run_end = parse_timestamp(run.get("completed_at"))
        if run_start is None or run_end is None or run_start > run_end:
            errors.append(f"execution run {task_id} requires ordered timezone-aware timestamps")
        files = run.get("changed_files")
        if not isinstance(files, list) or not all(valid_relative_path(path) for path in files):
            errors.append(f"execution run {task_id} changed_files must be project-relative paths")
        else:
            changed_files.update(str(path) for path in files)
        validate_commands(run.get("commands"), f"execution run {task_id}", errors)
    completed = {task_id for task_id, done in tasks.items() if done}
    if completed != set(tasks):
        errors.append("all OpenSpec tasks must be checked before Engineering review")
    if run_ids != completed:
        errors.append("execution task runs must cover every and only checked OpenSpec task")

    integration = evidence.get("integration")
    if not isinstance(integration, dict):
        errors.append("execution integration must be an object")
    else:
        if integration.get("status") != "passed" or integration.get("actor") != evidence.get("coordinator"):
            errors.append("execution integration requires status=passed and the coordinator actor")
        order = integration.get("order")
        if not isinstance(order, list) or set(order) != run_ids or len(order) != len(run_ids):
            errors.append("execution integration order must contain every completed OpenSpec task exactly once")
        files = integration.get("changed_files")
        if not isinstance(files, list) or not all(valid_relative_path(path) for path in files):
            errors.append("execution integration changed_files must be project-relative paths")
        else:
            changed_files.update(str(path) for path in files)
        validate_commands(integration.get("commands"), "execution integration", errors)
    project_root = Path(str(record.get("project_root", ""))).resolve()
    for changed in changed_files:
        try:
            (project_root / changed).resolve().relative_to(project_root)
        except (OSError, ValueError):
            errors.append(f"execution changed file escapes project root: {changed}")
    if review is not None and isinstance(review.get("files"), dict) and changed_files != set(review["files"]):
        errors.append("execution changed_files must exactly match review-evidence.json files")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    try:
        record = read_json(change_dir / "governance.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        errors = ["governance.json must be a valid JSON object"]
    else:
        errors = validate_execution(change_dir, record)
    payload = {"change_dir": str(change_dir), "status": "PASS" if not errors else "BLOCKED", "errors": errors}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"EXECUTION {payload['status']}")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
