#!/usr/bin/env python3
"""Promote an approved lesson candidate into the project lesson memory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lessons_common import load_failure_events, validate_lesson, validate_slug, write_json_file
from methodology_common import append_event, read_json, sha256, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--approval-id", required=True)
    args = parser.parse_args()
    candidate_path = args.candidate.resolve()
    change_dir = candidate_path.parent
    try:
        candidate = read_json(candidate_path)
        record = read_json(change_dir / "change.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"LESSON APPROVAL BLOCKED: {exc}")
        return 2
    errors = validate_lesson({**candidate, "status": "active"})
    errors.extend(validate_slug(candidate.get("lesson_id")))
    events, event_errors = load_failure_events(change_dir)
    errors.extend(event_errors)
    failure_path = change_dir / "evidence" / "failure-events.jsonl"
    if failure_path.is_file() and candidate.get("failure_events_digest") != sha256(failure_path):
        errors.append("lesson candidate failure_events_digest does not match current failure evidence")
    event_ids = {event.get("event_id") for event in events}
    missing_events = [item for item in candidate.get("source_events", []) if item not in event_ids]
    if missing_events:
        errors.append(f"lesson candidate references missing failure events: {missing_events}")
    project_root = Path(str(record.get("project_root", ""))).resolve()
    lessons_dir = project_root / "docs" / "methodology" / "lessons"
    destination = lessons_dir / f"{candidate.get('lesson_id')}.json"
    if destination.exists():
        errors.append(f"lesson already exists: {destination}")
    if errors:
        print("LESSON APPROVAL BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 2
    approved_at = utc_now()
    lesson = dict(candidate)
    lesson.update({
        "status": "active",
        "approved": {
            "actor": args.actor,
            "source": args.source,
            "approval_id": args.approval_id,
            "candidate_sha256": sha256(candidate_path),
            "at": approved_at,
        },
        "activated_at": approved_at,
    })
    write_json_file(destination, lesson)
    write_json_file(change_dir / "lesson-approval.json", {
        "schema_version": 1,
        "status": "approved",
        "actor": args.actor,
        "source": args.source,
        "approval_id": args.approval_id,
        "candidate": str(candidate_path.relative_to(change_dir)),
        "lesson": str(destination.relative_to(project_root)),
        "candidate_sha256": sha256(candidate_path),
        "at": approved_at,
    })
    append_event(change_dir, {
        "event": "lesson.promoted",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "lesson_id": lesson["lesson_id"],
        "approval_id": args.approval_id,
        "actor": args.actor,
        "at": approved_at,
    })
    print(f"LESSON ACTIVE: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
