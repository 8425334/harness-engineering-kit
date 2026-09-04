#!/usr/bin/env python3
"""Record the lesson retrieval and acknowledgement for a change Explore gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lessons_common import write_json_file
from methodology_common import append_event, read_json, utc_now
from retrieve_lessons import retrieve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--keyword", action="append", default=[])
    parser.add_argument("--rule", action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--scope")
    parser.add_argument("--action", action="append", default=[])
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"LESSON PREFLIGHT BLOCKED: {exc}")
        return 2
    project_root = Path(str(record.get("project_root", ""))).resolve()
    result = retrieve(project_root, args.keyword, args.rule, args.path, args.scope)
    if result["errors"]:
        print("LESSON PREFLIGHT BLOCKED")
        for error in result["errors"]:
            print(f"- {error}")
        return 2
    at = utc_now()
    evidence = {
        "schema_version": 1,
        "status": "passed",
        "actor": args.actor,
        "at": at,
        "keywords": args.keyword,
        "rules": args.rule,
        "paths": args.path,
        "scope": args.scope,
        "matched_lessons": [lesson["lesson_id"] for lesson in result["lessons"]],
        "actions": args.action or (["Reviewed matched lessons before implementation."] if result["lessons"] else ["No active matching lessons."]),
    }
    write_json_file(change_dir / "evidence" / "lesson-preflight.json", evidence)
    append_event(change_dir, {
        "event": "lesson.preflight.completed",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "matched_lessons": evidence["matched_lessons"],
        "actor": args.actor,
        "at": at,
    })
    print(f"LESSON PREFLIGHT PASSED: {len(evidence['matched_lessons'])} lesson(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
