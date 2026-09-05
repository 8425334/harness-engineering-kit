#!/usr/bin/env python3
"""Validate an approval-bound task DAG and its execution evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from methodology_common import meaningful, read_json


TASK_ID = re.compile(r"T[1-9][0-9]*")
TASK_LINE = re.compile(r"^- \[([ xX])\] (T[1-9][0-9]*)\b", re.MULTILINE)
TASK_KINDS = {"implementation", "test", "documentation", "verification", "integration"}
ISOLATION_MODES = {"worktree", "disjoint-write-scope", "single-workspace"}


def meaningful_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and "{{" not in value and "}}" not in value
    if isinstance(value, list):
        return bool(value) and all(meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(meaningful_value(key) and meaningful_value(item) for key, item in value.items())
    return value is not None


def is_exit_code(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not meaningful_value(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def valid_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not meaningful_value(value) or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and value != "."
        and ".." not in path.parts
        and (not path.parts or path.parts[0] != ".git")
        and not any(char in value for char in "*?[")
    )


def contained_file(root: Path, relative: str) -> bool:
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return candidate.is_file()


def scopes_overlap(left: str, right: str) -> bool:
    left_path = PurePosixPath(left)
    right_path = PurePosixPath(right)
    return left_path == right_path or left_path in right_path.parents or right_path in left_path.parents


def path_in_scopes(path: str, scopes: list[str]) -> bool:
    candidate = PurePosixPath(path)
    return any(candidate == PurePosixPath(scope) or PurePosixPath(scope) in candidate.parents for scope in scopes)


def string_list(value: Any) -> list[str]:
    return value if isinstance(value, list) and all(isinstance(item, str) for item in value) else []


def dependencies(task_map: dict[str, dict[str, Any]], task_id: str) -> set[str]:
    result: set[str] = set()
    pending = list(string_list(task_map[task_id].get("depends_on")))
    while pending:
        dependency = pending.pop()
        if dependency in result or dependency not in task_map:
            continue
        result.add(dependency)
        pending.extend(string_list(task_map[dependency].get("depends_on")))
    return result


def execution_waves(plan: dict[str, Any], completed: set[str] | None = None) -> list[list[str]]:
    """Return deterministic topological waves for coordinator scheduling.

    ``completed`` is used when an Apply run resumes. The approved graph is
    unchanged; only already recorded task runs are removed from the schedule.
    """
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(item, dict) for item in tasks):
        return []
    ids = [item.get("id") for item in tasks]
    if not all(isinstance(task_id, str) and TASK_ID.fullmatch(task_id) for task_id in ids) or len(ids) != len(set(ids)):
        return []
    if any(not isinstance(item.get("depends_on"), list) for item in tasks):
        return []
    task_map = {str(item["id"]): item for item in tasks}
    completed_ids = set(completed or ())
    if not completed_ids.issubset(task_map):
        return []
    remaining = [task_id for task_id in task_map if task_id not in completed_ids]
    waves: list[list[str]] = []
    while remaining:
        ready = [
            task_id
            for task_id in remaining
            if set(string_list(task_map[task_id].get("depends_on"))) <= completed_ids
        ]
        if not ready:
            return []
        # A coordinator-only task is a barrier and gets its own wave. Otherwise
        # all ready parallel tasks can be dispatched together; non-parallel work
        # is serialized to preserve its declared isolation requirement.
        parallel = [task_id for task_id in ready if task_map[task_id].get("parallelizable") is True]
        wave = parallel or [ready[0]]
        waves.append(wave)
        completed_ids.update(wave)
        remaining = [task_id for task_id in remaining if task_id not in completed_ids]
    return waves


def validate_commands(commands: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(commands, list) or not commands:
        errors.append(f"{label} requires at least one command result")
        return []
    actual: list[str] = []
    for item in commands:
        if (
            not isinstance(item, dict)
            or not meaningful_value(item.get("command"))
            or not is_exit_code(item.get("exit_code"))
            or item.get("exit_code") != 0
            or not meaningful_value(item.get("evidence"))
        ):
            errors.append(f"every {label} command requires command, integer exit_code=0, and evidence")
            continue
        actual.append(str(item["command"]))
    return actual


def task_markdown_status(change_dir: Path, task_ids: list[str], errors: list[str]) -> set[str]:
    path = change_dir / "tasks.md"
    if not meaningful(path):
        errors.append("missing or placeholder artifact: tasks.md")
        return set()
    try:
        matches = TASK_LINE.findall(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        errors.append(f"tasks.md is not readable UTF-8: {exc}")
        return set()
    markdown_ids = [task_id for _, task_id in matches]
    if markdown_ids != task_ids:
        errors.append("tasks.md checkbox ids and order must exactly match task-plan.json tasks")
    return {task_id for mark, task_id in matches if mark.lower() == "x"}


def validate_plan(change_dir: Path, status_mode: str = "planning") -> tuple[dict[str, Any] | None, list[str]]:
    if status_mode not in {"planning", "runtime"}:
        raise ValueError("status_mode must be planning or runtime")
    errors: list[str] = []
    try:
        plan = read_json(change_dir / "task-plan.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, ["task-plan.json must be a valid JSON object"]
    if plan.get("schema_version") != 1:
        errors.append("task-plan.json schema_version must be 1")
    if plan.get("strategy") != "parallel-when-supported":
        errors.append("task-plan.json strategy must be parallel-when-supported")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("task-plan.json tasks must be a non-empty array")
        return plan, errors
    task_ids: list[str] = []
    task_map: dict[str, dict[str, Any]] = {}
    for index, task in enumerate(tasks):
        label = f"task-plan.json tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ("id", "title", "kind", "depends_on", "write_scope", "contract_refs", "acceptance", "verification", "parallelizable"):
            if field not in task:
                errors.append(f"{label} missing {field}")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            errors.append(f"{label} id must match T<number>")
            continue
        if task_id in task_map:
            errors.append(f"duplicate task id: {task_id}")
            continue
        task_ids.append(task_id)
        task_map[task_id] = task
        if not meaningful_value(task.get("title")):
            errors.append(f"task {task_id} title is required")
        if task.get("kind") not in TASK_KINDS:
            errors.append(f"task {task_id} kind must be one of {sorted(TASK_KINDS)}")
        if not isinstance(task.get("parallelizable"), bool):
            errors.append(f"task {task_id} parallelizable must be boolean")
        for field in ("depends_on", "write_scope", "contract_refs", "acceptance", "verification"):
            value = task.get(field)
            if not isinstance(value, list):
                errors.append(f"task {task_id} {field} must be an array")
        for field in ("contract_refs", "acceptance", "verification"):
            value = task.get(field)
            if isinstance(value, list) and (
                not value or not all(isinstance(item, str) and meaningful_value(item) for item in value)
            ):
                errors.append(f"task {task_id} {field} must be a non-empty string array")
        scopes = task.get("write_scope")
        if isinstance(scopes, list):
            if task.get("kind") != "verification" and not scopes:
                errors.append(f"task {task_id} write_scope must not be empty for {task.get('kind')} work")
            if not all(valid_relative_path(item) for item in scopes):
                errors.append(f"task {task_id} write_scope must contain explicit project-relative paths without globs")
            if len(scopes) != len(set(scopes)):
                errors.append(f"task {task_id} write_scope contains duplicates")
        refs = task.get("contract_refs")
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, str):
                    continue
                relative = ref.split("#", 1)[0]
                if not valid_relative_path(relative) or not contained_file(change_dir, relative):
                    errors.append(f"task {task_id} contract ref is missing or escapes the change workspace: {ref}")

    if len(task_ids) != len(tasks):
        task_markdown_status(change_dir, task_ids, errors)
        return plan, errors

    for task_id, task in task_map.items():
        deps = task.get("depends_on")
        if not isinstance(deps, list):
            continue
        if not all(isinstance(item, str) for item in deps) or len(deps) != len(set(deps)):
            errors.append(f"task {task_id} depends_on must contain unique task ids")
            continue
        for dependency in deps:
            if dependency == task_id:
                errors.append(f"task {task_id} cannot depend on itself")
            elif dependency not in task_map:
                errors.append(f"task {task_id} has unknown dependency: {dependency}")

    waves = execution_waves(plan)
    if not waves:
        errors.append("task-plan.json dependencies must form an acyclic graph")
    order_index = {task_id: index for index, task_id in enumerate(task_ids)}
    for task_id, task in task_map.items():
        for dependency in string_list(task.get("depends_on")):
            if dependency in order_index and order_index[dependency] >= order_index[task_id]:
                errors.append("task-plan.json tasks must be listed in topological dependency order")
                break

    for left_index, left_id in enumerate(task_ids):
        left = task_map[left_id]
        if left.get("parallelizable") is not True:
            continue
        left_dependencies = dependencies(task_map, left_id)
        for right_id in task_ids[left_index + 1:]:
            right = task_map[right_id]
            if right.get("parallelizable") is not True:
                continue
            if right_id in left_dependencies or left_id in dependencies(task_map, right_id):
                continue
            if any(
                scopes_overlap(left_scope, right_scope)
                for left_scope in string_list(left.get("write_scope"))
                for right_scope in string_list(right.get("write_scope"))
            ):
                errors.append(f"parallel tasks {left_id} and {right_id} have overlapping write_scope without a dependency")

    integration = plan.get("integration")
    if not isinstance(integration, dict):
        errors.append("task-plan.json integration must be an object")
    else:
        if integration.get("owner") != "coordinator":
            errors.append("task-plan.json integration owner must be coordinator")
        merge_order = integration.get("merge_order")
        if merge_order != task_ids:
            errors.append("task-plan.json integration.merge_order must exactly match the topological task order")
        final_verification = integration.get("final_verification")
        if (
            not isinstance(final_verification, list)
            or not final_verification
            or not all(isinstance(item, str) and meaningful_value(item) for item in final_verification)
        ):
            errors.append("task-plan.json integration.final_verification must be a non-empty command array")

    impact_path = change_dir / "context-impact.json"
    if impact_path.is_file():
        try:
            impact = read_json(impact_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            pass  # check_phase reports the authoritative context-impact error
        else:
            analyzed = impact.get("analyzed_paths")
            all_scopes = [scope for task in tasks for scope in string_list(task.get("write_scope"))]
            if isinstance(analyzed, list) and all(isinstance(path, str) for path in analyzed):
                for path in analyzed:
                    if valid_relative_path(path) and not path_in_scopes(path, all_scopes):
                        errors.append(f"context-impact.json analyzed path has no task owner: {path}")
                for scope in all_scopes:
                    if valid_relative_path(scope) and not any(
                        path_in_scopes(path, [scope]) or path_in_scopes(scope, [path])
                        for path in analyzed
                        if valid_relative_path(path)
                    ):
                        errors.append(f"task write_scope is absent from context-impact.json analyzed_paths: {scope}")

    completed = task_markdown_status(change_dir, task_ids, errors)
    if status_mode == "planning" and completed:
        errors.append("tasks.md must start with every checkbox unchecked before Approval")
    return plan, errors


def transition_time(record: dict[str, Any], state: str) -> datetime | None:
    values = [
        parse_timestamp(event.get("at"))
        for event in record.get("events", [])
        if isinstance(event, dict) and event.get("event") == "methodology.transition" and event.get("to") == state
    ]
    timestamps = [value for value in values if value is not None]
    return max(timestamps) if timestamps else None


def validate_execution(
    change_dir: Path,
    record: dict[str, Any],
    review: dict[str, Any] | None = None,
) -> list[str]:
    plan, errors = validate_plan(change_dir, status_mode="runtime")
    if not plan or errors:
        return errors
    try:
        evidence = read_json(change_dir / "execution-evidence.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return errors + ["execution-evidence.json must be a valid JSON object"]
    if evidence.get("schema_version") != 1:
        errors.append("execution-evidence.json schema_version must be 1")
    strategy = evidence.get("strategy")
    if strategy not in {"parallel", "sequential"}:
        errors.append("execution-evidence.json strategy must be parallel or sequential")
    if not meaningful_value(evidence.get("coordinator")):
        errors.append("execution-evidence.json coordinator is required")
    capability = evidence.get("capability")
    if not isinstance(capability, dict):
        errors.append("execution-evidence.json capability must be an object")
        capability = {}
    agent_parallelism = capability.get("agent_parallelism")
    max_concurrency = capability.get("max_concurrency")
    isolation = capability.get("isolation")
    if not isinstance(agent_parallelism, bool):
        errors.append("execution capability agent_parallelism must be boolean")
    if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or max_concurrency < 1:
        errors.append("execution capability max_concurrency must be a positive integer")
    if isolation not in ISOLATION_MODES:
        errors.append(f"execution capability isolation must be one of {sorted(ISOLATION_MODES)}")
    if strategy == "parallel":
        if agent_parallelism is not True or not isinstance(max_concurrency, int) or max_concurrency < 2:
            errors.append("parallel execution requires agent_parallelism=true and max_concurrency>=2")
        if isolation not in {"worktree", "disjoint-write-scope"}:
            errors.append("parallel execution requires worktree or disjoint-write-scope isolation")
        if evidence.get("fallback_reason") not in (None, ""):
            errors.append("parallel execution must not declare fallback_reason")
    elif strategy == "sequential":
        if max_concurrency != 1:
            errors.append("sequential execution requires max_concurrency=1")
        if not meaningful_value(evidence.get("fallback_reason")):
            errors.append("sequential execution requires a fallback_reason")

    started_at = parse_timestamp(evidence.get("started_at"))
    completed_at = parse_timestamp(evidence.get("completed_at"))
    if started_at is None or completed_at is None or started_at > completed_at:
        errors.append("execution evidence requires ordered timezone-aware started_at/completed_at")
    implementing_at = transition_time(record, "IMPLEMENTING")
    verifying_at = transition_time(record, "VERIFYING")
    if started_at and implementing_at and started_at < implementing_at:
        errors.append("execution must start after the latest transition to IMPLEMENTING")
    if completed_at and verifying_at and completed_at > verifying_at:
        errors.append("execution must complete before the latest transition to VERIFYING")

    tasks = plan.get("tasks", [])
    task_map = {task["id"]: task for task in tasks if isinstance(task, dict) and "id" in task}
    runs = evidence.get("task_runs")
    if not isinstance(runs, list):
        errors.append("execution-evidence.json task_runs must be an array")
        runs = []
    run_map: dict[str, dict[str, Any]] = {}
    changed_owners: dict[str, str] = {}
    run_times: dict[str, tuple[datetime, datetime]] = {}
    for index, run in enumerate(runs):
        label = f"execution task_runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{label} must be an object")
            continue
        task_id = run.get("task_id")
        if not isinstance(task_id, str) or task_id not in task_map:
            errors.append(f"{label} references unknown task: {task_id}")
            continue
        if task_id in run_map:
            errors.append(f"duplicate execution run for task: {task_id}")
            continue
        run_map[str(task_id)] = run
        for field in ("actor", "workspace", "result_ref"):
            if not meaningful_value(run.get(field)):
                errors.append(f"execution run {task_id} requires {field}")
        if run.get("status") != "completed":
            errors.append(f"execution run {task_id} status must be completed")
        run_isolation = run.get("isolation")
        if run_isolation not in ISOLATION_MODES:
            errors.append(f"execution run {task_id} has invalid isolation")
        elif run_isolation != isolation:
            errors.append(f"execution run {task_id} isolation must match the declared capability")
        if strategy == "parallel" and run_isolation not in {"worktree", "disjoint-write-scope"}:
            errors.append(f"parallel execution run {task_id} lacks safe isolation")
        run_start = parse_timestamp(run.get("started_at"))
        run_complete = parse_timestamp(run.get("completed_at"))
        if run_start is None or run_complete is None or run_start > run_complete:
            errors.append(f"execution run {task_id} requires ordered timezone-aware timestamps")
        else:
            run_times[str(task_id)] = (run_start, run_complete)
            if (started_at and run_start < started_at) or (completed_at and run_complete > completed_at):
                errors.append(f"execution run {task_id} falls outside the execution time window")
        changed_files = run.get("changed_files")
        if not isinstance(changed_files, list) or not all(valid_relative_path(item) for item in changed_files):
            errors.append(f"execution run {task_id} changed_files must be project-relative paths")
            changed_files = []
        elif len(changed_files) != len(set(changed_files)):
            errors.append(f"execution run {task_id} changed_files contains duplicates")
        if task_map[str(task_id)].get("kind") != "verification" and not changed_files:
            errors.append(f"execution run {task_id} must own at least one changed file")
        for changed in changed_files:
            if not path_in_scopes(changed, task_map[str(task_id)].get("write_scope", [])):
                errors.append(f"execution run {task_id} changed file outside write_scope: {changed}")
            previous = changed_owners.get(changed)
            if previous and previous != task_id:
                errors.append(f"changed file has multiple task owners: {changed} ({previous}, {task_id})")
            changed_owners[changed] = str(task_id)
        actual_commands = validate_commands(run.get("commands"), f"execution run {task_id}", errors)
        expected_commands = task_map[str(task_id)].get("verification", [])
        if not set(expected_commands).issubset(actual_commands):
            errors.append(f"execution run {task_id} did not run every planned verification command")

    if set(run_map) != set(task_map):
        errors.append("execution task_runs must cover every and only task-plan.json task")
    markdown_completed = task_markdown_status(change_dir, list(task_map), errors)
    if markdown_completed != set(run_map):
        errors.append("tasks.md checked tasks must exactly match completed execution task runs")
    for task_id, task in task_map.items():
        if task_id not in run_times:
            continue
        for dependency in task.get("depends_on", []):
            if dependency in run_times and run_times[task_id][0] < run_times[dependency][1]:
                errors.append(f"execution run {task_id} started before dependency {dependency} completed")

    if strategy == "parallel":
        overlapping = False
        observed_concurrency = 0
        run_ids = list(run_times)
        for point, _ in run_times.values():
            observed_concurrency = max(
                observed_concurrency,
                sum(start <= point < end for start, end in run_times.values()),
            )
        for index, left_id in enumerate(run_ids):
            for right_id in run_ids[index + 1:]:
                left_start, left_end = run_times[left_id]
                right_start, right_end = run_times[right_id]
                if left_start < right_end and right_start < left_end:
                    if task_map[left_id].get("parallelizable") is not True or task_map[right_id].get("parallelizable") is not True:
                        errors.append(f"non-parallel task overlapped another run: {left_id}, {right_id}")
                    if isolation == "worktree" and run_map[left_id].get("workspace") == run_map[right_id].get("workspace"):
                        errors.append(f"overlapping worktree runs share a workspace: {left_id}, {right_id}")
                    if run_map[left_id].get("actor") != run_map[right_id].get("actor"):
                        overlapping = True
        if not overlapping:
            errors.append("parallel strategy requires overlapping runs by different actors")
        if isinstance(max_concurrency, int) and observed_concurrency > max_concurrency:
            errors.append("observed task concurrency exceeds capability.max_concurrency")

    integration = evidence.get("integration")
    integration_changed: list[str] = []
    if not isinstance(integration, dict):
        errors.append("execution-evidence.json integration must be an object")
    else:
        if integration.get("status") != "passed" or not meaningful_value(integration.get("actor")):
            errors.append("execution integration requires actor and status=passed")
        expected_order = plan.get("integration", {}).get("merge_order")
        if integration.get("order") != expected_order:
            errors.append("execution integration order must match the approved merge_order")
        conflicts = integration.get("conflicts")
        if not isinstance(conflicts, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("paths"), list)
            or not item.get("paths")
            or not all(valid_relative_path(path) for path in item.get("paths", []))
            or not isinstance(item.get("resolution"), str)
            or not meaningful_value(item.get("resolution"))
            for item in conflicts
        ):
            errors.append("execution integration conflicts must contain paths and resolution")
        integration_changed = integration.get("changed_files")
        if not isinstance(integration_changed, list) or not all(valid_relative_path(item) for item in integration_changed):
            errors.append("execution integration changed_files must be project-relative paths")
            integration_changed = []
        all_scopes = [scope for task in tasks for scope in string_list(task.get("write_scope"))]
        for changed in integration_changed:
            if not path_in_scopes(changed, all_scopes):
                errors.append(f"execution integration changed file outside approved write scopes: {changed}")
        actual_commands = validate_commands(integration.get("commands"), "execution integration", errors)
        expected_commands = plan.get("integration", {}).get("final_verification", [])
        if not set(expected_commands).issubset(actual_commands):
            errors.append("execution integration did not run every approved final verification command")
        if integration.get("actor") != evidence.get("coordinator"):
            errors.append("execution integration actor must be the coordinator")

    project_root = Path(str(record.get("project_root", "")))
    if project_root.is_absolute() and project_root.is_dir():
        for changed in set(changed_owners) | set(integration_changed):
            try:
                (project_root / changed).resolve().relative_to(project_root.resolve())
            except (OSError, ValueError):
                errors.append(f"execution changed file escapes project root: {changed}")

    if review is not None and isinstance(review.get("files"), dict):
        executed_files = set(changed_owners) | set(integration_changed)
        if executed_files != set(review["files"]):
            errors.append("execution changed_files must exactly match review-evidence.json files")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--phase", choices=("DESIGN", "REVIEW"), default="DESIGN")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    plan, errors = validate_plan(change_dir, status_mode="planning" if args.phase == "DESIGN" else "runtime")
    if args.phase == "REVIEW" and plan:
        try:
            record = read_json(change_dir / "change.json")
            review = read_json(change_dir / "review-evidence.json")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            errors.append("REVIEW requires valid change.json and review-evidence.json")
        else:
            errors = validate_execution(change_dir, record, review)
    payload = {
        "change_dir": str(change_dir),
        "phase": args.phase,
        "status": "PASS" if not errors else "BLOCKED",
        "waves": execution_waves(plan or {}),
        "errors": errors,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"TASK PLAN {payload['status']}: {args.phase}")
        if payload["waves"]:
            print("WAVES: " + " -> ".join("[" + ", ".join(wave) + "]" for wave in payload["waves"]))
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
