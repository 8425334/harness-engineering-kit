#!/usr/bin/env python3
"""Aggregate structured Engineering lifecycle metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def change_files(root: Path, relative: str) -> list[Path]:
    """Collect evidence files from active and archived change workspaces.

    Archived changes live under ``openspec/changes/archive/<id>/`` per
    archive-evidence.json.template (a ``<date>-<change-id>`` directory, with or
    without a separate date level) and must keep counting toward completion
    metrics.
    """
    return sorted({
        *root.glob(f"*/{relative}"),
        *root.glob(f"archive/*/{relative}"),
        *root.glob(f"archive/*/*/{relative}"),
    })


def parse_events(root: Path) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    invalid = 0
    for event_file in change_files(root, "evidence/events.jsonl"):
        for line in event_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if isinstance(item, dict):
                if all(item.get(field) for field in ("event", "change_id", "at")):
                    events.append(item)
                else:
                    invalid += 1
            else:
                invalid += 1
    return events, invalid


def parse_failure_events(root: Path) -> tuple[list[dict[str, Any]], int]:
    failures: list[dict[str, Any]] = []
    invalid = 0
    for event_file in change_files(root, "evidence/failure-events.jsonl"):
        for line in event_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if isinstance(item, dict) and item.get("event_id") and item.get("source"):
                failures.append(item)
            else:
                invalid += 1
    return failures, invalid


def parse_execution_records(root: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid = 0
    for evidence_file in change_files(root, "execution-evidence.json"):
        try:
            item = json.loads(evidence_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            invalid += 1
            continue
        if (
            isinstance(item, dict)
            and item.get("strategy") in {"parallel", "sequential"}
            and isinstance(item.get("task_runs"), list)
            and isinstance(item.get("capability"), dict)
        ):
            records.append(item)
        else:
            invalid += 1
    return records, invalid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("openspec/changes"))
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"CHANGES ROOT MISSING: {args.root}")
        return 2
    events, invalid = parse_events(args.root)
    failures, invalid_failures = parse_failure_events(args.root)
    executions, invalid_executions = parse_execution_records(args.root)
    invalid += invalid_failures + invalid_executions
    event_counts = Counter(str(item.get("event", "unknown")) for item in events)
    start_events = {"skill.triggered", "skill.fallback"}
    mode_counts = Counter(str(item.get("mode", "unknown")) for item in events if item.get("event") in start_events)
    changes = {str(item["change_id"]) for item in events if item.get("change_id")}
    triggered_changes = {str(item["change_id"]) for item in events if item.get("event") == "skill.triggered" and item.get("change_id")}
    started_changes = {str(item["change_id"]) for item in events if item.get("event") in start_events and item.get("change_id")}
    final_states = {
        str(item["change_id"]): str(item.get("to"))
        for item in events
        if item.get("event") == "methodology.transition" and item.get("change_id")
    }
    archived = sum(state == "ARCHIVED" for state in final_states.values())
    strategy_counts = Counter(str(item.get("strategy")) for item in executions)
    fallback_reasons = Counter(
        str(item.get("fallback_reason"))
        for item in executions
        if item.get("strategy") == "sequential" and item.get("fallback_reason")
    )
    total_task_runs = sum(len(item.get("task_runs", [])) for item in executions)
    declared_concurrency = [
        item.get("capability", {}).get("max_concurrency")
        for item in executions
        if isinstance(item.get("capability", {}).get("max_concurrency"), int)
        and not isinstance(item.get("capability", {}).get("max_concurrency"), bool)
    ]
    payload = {
        "changes": len(changes),
        "triggered": len(triggered_changes),
        "started": len(started_changes),
        "archived": archived,
        "completion_rate": round(archived / len(started_changes), 4) if started_changes else 0,
        "blocked_events": event_counts["phase.blocked"],
        "fallbacks": event_counts["skill.fallback"],
        "human_interventions": event_counts["human.intervention"],
        "invalid_events": invalid,
        "by_mode": dict(mode_counts),
        "failure_events": len(failures),
        "failures_by_source": dict(Counter(str(item.get("source")) for item in failures)),
        "lesson_candidates": sum(1 for path in change_files(args.root, "lesson-candidate.json")),
        "lesson_promotions": event_counts["lesson.promoted"],
        "execution_records": len(executions),
        "execution_by_strategy": dict(strategy_counts),
        "parallel_adoption_rate": round(strategy_counts["parallel"] / len(executions), 4) if executions else 0,
        "sequential_fallback_reasons": dict(fallback_reasons),
        "task_runs": total_task_runs,
        "average_task_runs": round(total_task_runs / len(executions), 4) if executions else 0,
        "max_declared_concurrency": max(declared_concurrency, default=0),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
