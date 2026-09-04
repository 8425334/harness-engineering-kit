#!/usr/bin/env python3
"""Aggregate structured Engineering lifecycle metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_events(root: Path) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    invalid = 0
    for event_file in root.glob("*/evidence/events.jsonl"):
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
    for event_file in root.glob("*/evidence/failure-events.jsonl"):
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("openspec/changes"))
    args = parser.parse_args()
    events, invalid = parse_events(args.root)
    failures, invalid_failures = parse_failure_events(args.root)
    invalid += invalid_failures
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
        "lesson_candidates": sum(1 for path in args.root.glob("*/lesson-candidate.json") if path.is_file()),
        "lesson_promotions": event_counts["lesson.promoted"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
