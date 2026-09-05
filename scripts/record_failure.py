#!/usr/bin/env python3
"""Record a structured failure for later lesson extraction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lessons_common import FAILURE_CATEGORIES, FAILURE_SOURCES, validate_failure_event
from methodology_common import append_event, append_failure_event, read_json, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--source", required=True, choices=sorted(FAILURE_SOURCES))
    parser.add_argument("--category", required=True, choices=sorted(FAILURE_CATEGORIES))
    parser.add_argument("--rule", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--signature")
    parser.add_argument("--severity", choices=("low", "medium", "high", "critical"), default="medium")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Cannot read change record: {exc}")
        return 2
    timestamp = utc_now()
    event = {
        "schema_version": 1,
        "event_id": f"failure-{timestamp.replace('+00:00', 'Z').replace(':', '')}-{args.rule}",
        "change_id": record.get("change_id"),
        "source": args.source,
        "category": args.category,
        "rule": args.rule,
        "message": args.message,
        "paths": args.path,
        "evidence": args.evidence,
        "signature": args.signature or args.rule,
        "severity": args.severity,
        "actor": args.actor,
        "at": timestamp,
    }
    errors = validate_failure_event(event)
    if errors:
        print("FAILURE RECORD BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 2
    append_failure_event(change_dir, event)
    append_event(change_dir, {
        "event": "failure.detected",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "source": args.source,
        "category": args.category,
        "rule": args.rule,
        "signature": event["signature"],
        "actor": args.actor,
        "at": event["at"],
    })
    print(f"FAILURE RECORDED: {event['event_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
