#!/usr/bin/env python3
"""Record one completed DAG task and synchronize its OpenSpec checkbox."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from check_task_plan import (
    parse_timestamp,
    path_in_scopes,
    string_list,
    task_markdown_status,
    valid_relative_path,
    validate_commands,
    validate_plan,
    execution_waves,
)
from methodology_common import append_event, file_lock, read_json, utc_now, write_json


CHECKBOX_LINE = re.compile(r"^(?P<prefix>- \[)[ xX](?P<suffix>\] (?P<id>T[1-9][0-9]*)\b.*)$", re.MULTILINE)


def meaningful_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "{{" not in value and "}}" not in value


def completed_run_ids(evidence: dict[str, Any]) -> set[str]:
    """Return task ids marked completed in raw evidence."""
    runs = evidence.get("task_runs")
    if not isinstance(runs, list):
        return set()
    return {
        str(run.get("task_id"))
        for run in runs
        if isinstance(run, dict) and run.get("status") == "completed" and isinstance(run.get("task_id"), str)
    }


def render_task_status(markdown: str, completed: set[str]) -> str:
    return CHECKBOX_LINE.sub(
        lambda match: f"{match.group('prefix')}{'x' if match.group('id') in completed else ' '}{match.group('suffix')}",
        markdown,
    )


def atomic_write_text(path: Path, content: str) -> None:
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f"{path.name}.", suffix=".tmp", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def validated_completed_run_ids(
    plan: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[set[str], list[str]]:
    """Return completed tasks only when every recorded run is valid."""
    runs = evidence.get("task_runs")
    if not isinstance(runs, list):
        return set(), ["execution-evidence.json task_runs must be an array"]
    task_map = {
        str(task["id"]): task
        for task in plan.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    completed: set[str] = set()
    errors: list[str] = []
    for index, run in enumerate(runs):
        label = f"execution task_runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{label} must be an object")
            continue
        task_id = run.get("task_id")
        if not isinstance(task_id, str) or task_id not in task_map:
            errors.append(f"{label} references unknown task: {task_id}")
            continue
        if task_id in completed:
            errors.append(f"duplicate execution run for task: {task_id}")
            continue
        if run.get("status") != "completed":
            errors.append(f"execution run {task_id} status must be completed")
            continue
        run_errors = validate_run(task_map[str(task_id)], run, evidence)
        errors.extend(f"{label}: {error}" for error in run_errors)
        if not run_errors:
            completed.add(str(task_id))
    for task_id in sorted(completed):
        dependencies = set(string_list(task_map[task_id].get("depends_on")))
        missing = dependencies - completed
        if missing:
            errors.append(f"execution run {task_id} has incomplete dependencies: {sorted(missing)}")
    return completed, errors


def sync_checkboxes(change_dir: Path, evidence: dict[str, Any] | None = None) -> list[str]:
    plan, errors = validate_plan(change_dir, status_mode="runtime")
    if not plan:
        return errors
    tasks = plan.get("tasks", [])
    task_ids = [str(task.get("id")) for task in tasks if isinstance(task, dict)]
    markdown_path = change_dir / "tasks.md"
    task_markdown_status(change_dir, task_ids, errors)
    if errors:
        return errors
    if evidence is None:
        try:
            evidence = read_json(change_dir / "execution-evidence.json")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return ["execution-evidence.json must be a valid JSON object"]
    completed, run_errors = validated_completed_run_ids(plan, evidence)
    if run_errors:
        return run_errors
    content = markdown_path.read_text(encoding="utf-8")
    atomic_write_text(markdown_path, render_task_status(content, completed))
    return []


def resume_execution(change_dir: Path, actor: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Reconcile task projection and return the next safe execution wave."""
    change_dir = change_dir.resolve()
    if not meaningful_value(actor):
        return None, ["execution resume requires a non-empty actor"]
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, ["change.json must be a valid JSON object"]
    if record.get("state") != "IMPLEMENTING":
        return None, [f"execution resume requires change state IMPLEMENTING (got {record.get('state')!r})"]
    plan, errors = validate_plan(change_dir, status_mode="runtime")
    if not plan or errors:
        return None, errors
    try:
        evidence = read_json(change_dir / "execution-evidence.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, ["execution-evidence.json must be a valid JSON object"]
    completed, errors = validated_completed_run_ids(plan, evidence)
    if errors:
        return None, errors
    errors = sync_checkboxes(change_dir, evidence)
    if errors:
        return None, errors
    task_ids = [str(task["id"]) for task in plan["tasks"]]
    pending = [task_id for task_id in task_ids if task_id not in completed]
    waves = execution_waves(plan, completed)
    payload = {
        "change_id": record.get("change_id"),
        "state": record.get("state"),
        "actor": actor,
        "completed_tasks": [task_id for task_id in task_ids if task_id in completed],
        "pending_tasks": pending,
        "ready_waves": waves,
        "status": "READY" if waves else ("INTEGRATION_PENDING" if not pending else "BLOCKED"),
    }
    append_event(change_dir, {
        "event": "execution.resumed",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "actor": actor,
        "completed_tasks": payload["completed_tasks"],
        "pending_tasks": pending,
        "ready_waves": waves,
        "at": utc_now(),
    })
    return payload, []


def validate_run(task: dict[str, Any], run: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    task_id = str(task.get("id"))
    errors: list[str] = []
    if run.get("task_id") != task_id:
        errors.append(f"run task_id must be {task_id}")
    if run.get("status") != "completed":
        errors.append("run status must be completed")
    for field in ("actor", "workspace", "result_ref"):
        if not meaningful_value(run.get(field)):
            errors.append(f"run requires {field}")
    isolation = evidence.get("capability", {}).get("isolation") if isinstance(evidence.get("capability"), dict) else None
    if run.get("isolation") != isolation:
        errors.append("run isolation must match execution capability")
    started_at = parse_timestamp(run.get("started_at"))
    completed_at = parse_timestamp(run.get("completed_at"))
    if started_at is None or completed_at is None or started_at > completed_at:
        errors.append("run requires ordered timezone-aware started_at/completed_at")
    changed = run.get("changed_files")
    if not isinstance(changed, list) or not all(valid_relative_path(path) for path in changed):
        errors.append("run changed_files must be project-relative paths")
        changed = []
    if task.get("kind") != "verification" and not changed:
        errors.append("non-verification task requires at least one changed file")
    for path in changed:
        if not path_in_scopes(path, string_list(task.get("write_scope"))):
            errors.append(f"run changed file outside task write_scope: {path}")
    actual = validate_commands(run.get("commands"), f"task completion {task_id}", errors)
    if not set(string_list(task.get("verification"))).issubset(actual):
        errors.append("run did not pass every planned verification command")
    return errors


def record_completion(change_dir: Path, task_id: str, run: dict[str, Any]) -> list[str]:
    change_dir = change_dir.resolve()
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return ["change.json must be a valid JSON object"]
    if record.get("state") != "IMPLEMENTING":
        return [f"task completion requires change state IMPLEMENTING (got {record.get('state')!r})"]
    plan, errors = validate_plan(change_dir, status_mode="runtime")
    if not plan or errors:
        return errors
    task_map = {str(task["id"]): task for task in plan["tasks"] if isinstance(task, dict) and "id" in task}
    if task_id not in task_map:
        return [f"unknown task id: {task_id}"]

    evidence_path = change_dir / "execution-evidence.json"
    try:
        with file_lock(evidence_path):
            evidence = read_json(evidence_path)
            runs = evidence.get("task_runs")
            if not isinstance(runs, list):
                return ["execution-evidence.json task_runs must be an array"]
            existing, existing_errors = validated_completed_run_ids(plan, evidence)
            if existing_errors:
                return existing_errors
            if task_id in existing:
                return [f"task already completed: {task_id}"]
            missing_dependencies = set(string_list(task_map[task_id].get("depends_on"))) - existing
            if missing_dependencies:
                return [f"task dependencies are not completed: {sorted(missing_dependencies)}"]
            errors = validate_run(task_map[task_id], run, evidence)
            if errors:
                return errors
            runs.append(run)
            order = {task: index for index, task in enumerate(task_map)}
            runs.sort(key=lambda item: order.get(str(item.get("task_id")), len(order)))
            write_json(evidence_path, evidence)
            sync_errors = sync_checkboxes(change_dir, evidence)
            if sync_errors:
                return ["task evidence was recorded but tasks.md synchronization failed", *sync_errors]
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"cannot record task completion: {exc}"]

    append_event(change_dir, {
        "event": "task.completed",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "actor": run.get("actor"),
        "task_id": task_id,
        "result_ref": run.get("result_ref"),
        "at": utc_now(),
    })
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    complete = subparsers.add_parser("complete", help="record evidence and tick one task")
    complete.add_argument("change_dir", type=Path)
    complete.add_argument("task_id")
    complete.add_argument("--run", type=Path, required=True, help="JSON file containing one completed task run")
    sync = subparsers.add_parser("sync", help="repair task checkboxes from execution evidence")
    sync.add_argument("change_dir", type=Path)
    resume = subparsers.add_parser("resume", help="reconcile progress and show the next ready task wave")
    resume.add_argument("change_dir", type=Path)
    resume.add_argument("--actor", required=True)
    resume.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if args.command == "sync":
        errors = sync_checkboxes(args.change_dir.resolve())
    elif args.command == "complete":
        try:
            run = read_json(args.run.resolve())
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors = [f"run evidence must be a valid JSON object: {exc}"]
        else:
            errors = record_completion(args.change_dir, args.task_id, run)
    else:
        payload, errors = resume_execution(args.change_dir, args.actor)
        if not errors:
            if args.as_json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"EXECUTION RESUMED: {payload['status']}")
                print("COMPLETED: " + (", ".join(payload["completed_tasks"]) or "none"))
                print("READY: " + (" -> ".join("[" + ", ".join(wave) + "]" for wave in payload["ready_waves"]) or "none"))
    if errors:
        print("TASK COMPLETION BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 2
    if args.command == "sync":
        print("TASK CHECKBOXES SYNCHRONIZED")
    else:
        print(f"TASK COMPLETED: {args.task_id} (evidence recorded; tasks.md checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
