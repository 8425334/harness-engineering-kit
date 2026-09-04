#!/usr/bin/env python3
"""Create an approval-pending lesson candidate from recorded failures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lessons_common import load_failure_events, sha256, validate_slug, write_json_file
from methodology_common import append_event, read_json, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("lesson_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--root-cause", required=True)
    parser.add_argument("--prevention", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--rule", action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--owner", required=True)
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    errors = validate_slug(args.lesson_id)
    if errors:
        print("LESSON CANDIDATE BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 2
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Cannot read change record: {exc}")
        return 2
    events, event_errors = load_failure_events(change_dir)
    if event_errors:
        print("LESSON CANDIDATE BLOCKED")
        for error in event_errors:
            print(f"- {error}")
        return 2
    if not events:
        print("LESSON CANDIDATE BLOCKED: no failure events recorded")
        return 2
    candidate_path = change_dir / "lesson-candidate.json"
    if candidate_path.exists():
        print(f"EXISTS: {candidate_path}")
        return 2
    failure_path = change_dir / "evidence" / "failure-events.jsonl"
    candidate = {
        "schema_version": 1,
        "lesson_id": args.lesson_id,
        "title": args.title,
        "pattern": args.pattern,
        "root_cause": args.root_cause,
        "prevention": args.prevention,
        "verification": args.verification,
        "scope": args.scope,
        "keywords": args.keyword or [args.scope],
        "rules": args.rule,
        "paths": args.path,
        "source_changes": [record.get("change_id")],
        "source_events": [event.get("event_id") for event in events],
        "failure_events_digest": sha256(failure_path),
        "status": "candidate",
        "owner": args.owner,
        "created_at": utc_now(),
    }
    write_json_file(candidate_path, candidate)
    append_event(change_dir, {
        "event": "lesson.candidate.created",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "lesson_id": args.lesson_id,
        "source_events": candidate["source_events"],
        "actor": args.owner,
        "at": candidate["created_at"],
    })
    print(f"LESSON CANDIDATE CREATED: {candidate_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
