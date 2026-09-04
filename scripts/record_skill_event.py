#!/usr/bin/env python3
"""Record a non-transition Engineering event in both audit stores."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from methodology_common import append_event, read_json, utc_now


EVENTS = ("phase.started", "skill.fallback", "human.intervention")
PHASES = ("EXPLORE", "SPEC", "DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("event", choices=EVENTS)
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Cannot read change record: {exc}")
        return 2
    if args.event in {"skill.fallback", "human.intervention"} and not args.reason:
        print(f"BLOCKED: {args.event} requires --reason")
        return 2
    payload = {
        "event": args.event,
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "phase": args.phase,
        "actor": args.actor,
        "reason": args.reason,
        "at": utc_now(),
    }
    append_event(change_dir, payload)
    print(f"EVENT RECORDED: {args.event}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
