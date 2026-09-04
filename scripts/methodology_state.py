#!/usr/bin/env python3
"""Advance the canonical Engineering lifecycle with automatic gate events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_phase import check
from methodology_common import append_event, append_failure_event, read_json, utc_now, write_json


TRANSITIONS = {
    "INTAKE": {"EXPLORED"},
    "EXPLORED": {"CONTRACT_READY"},
    "CONTRACT_READY": {"DESIGN_READY", "CONTRACT_CHANGED"},
    "DESIGN_READY": {"APPROVED", "CONTRACT_CHANGED"},
    "APPROVED": {"IMPLEMENTING", "CONTRACT_CHANGED", "DRIFT_DETECTED"},
    "IMPLEMENTING": {"VERIFYING", "CONTRACT_CHANGED", "DRIFT_DETECTED"},
    "VERIFYING": {"VERIFIED", "REMEDIATING", "CONTRACT_CHANGED", "DRIFT_DETECTED"},
    "REMEDIATING": {"IMPLEMENTING"},
    "VERIFIED": {"SYNCED", "REMEDIATING", "CONTRACT_CHANGED", "DRIFT_DETECTED"},
    "SYNCED": {"ARCHIVED", "CONTRACT_CHANGED", "DRIFT_DETECTED"},
    "DRIFT_DETECTED": {"EXPLORED"},
    "CONTRACT_CHANGED": {"CONTRACT_READY"},
}
GATE_FOR_STATE = {
    "EXPLORED": "EXPLORE",
    "CONTRACT_READY": "SPEC",
    "DESIGN_READY": "DESIGN",
    "APPROVED": "EXECUTE",
    "IMPLEMENTING": "EXECUTE",
    "VERIFYING": "EXECUTE",
    "VERIFIED": "REVIEW",
    "SYNCED": "SYNC",
    "ARCHIVED": "ARCHIVE",
}


def event(record: dict[str, object], event_name: str, actor: str, **extra: object) -> dict[str, object]:
    return {
        "event": event_name,
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "actor": actor,
        "at": utc_now(),
        **extra,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("next_state", choices=sorted({item for values in TRANSITIONS.values() for item in values}))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--reason")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    record_path = change_dir / "change.json"
    try:
        record = read_json(record_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Cannot read change record: {exc}")
        return 2
    current = record.get("state")
    if args.next_state not in TRANSITIONS.get(str(current), set()):
        print(f"INVALID TRANSITION: {current} -> {args.next_state}")
        return 2
    if args.next_state in {"DRIFT_DETECTED", "CONTRACT_CHANGED", "REMEDIATING"} and not args.reason:
        print("BLOCKED: exceptional transitions require --reason")
        return 2
    gate = GATE_FOR_STATE.get(args.next_state)
    if gate:
        errors = check(change_dir, gate)
        if errors:
            append_failure_event(change_dir, {
                "schema_version": 1,
                "event_id": f"failure-gate-{utc_now().replace(':', '').replace('+00:00', 'z')}-{gate.lower()}",
                "change_id": record.get("change_id"),
                "source": "phase",
                "category": "fitness" if gate in {"EXECUTE", "REVIEW"} else "other",
                "rule": f"phase-{gate.lower()}",
                "message": "; ".join(errors),
                "paths": [],
                "evidence": [],
                "signature": f"phase-{gate.lower()}",
                "severity": "medium",
                "actor": args.actor,
                "at": utc_now(),
            })
            append_event(change_dir, event(record, "phase.blocked", args.actor, phase=gate, target_state=args.next_state, errors=errors))
            print(f"BLOCKED: {args.next_state} requires {gate} evidence")
            for error in errors:
                print(f"- {error}")
            return 2
        append_event(change_dir, event(record, "phase.completed", args.actor, phase=gate, target_state=args.next_state), update_record=False)
    transition = event(
        record,
        "methodology.transition",
        args.actor,
        **{"from": current, "to": args.next_state, "evidence": args.evidence, "reason": args.reason},
    )
    record["state"] = args.next_state
    record["updated_at"] = transition["at"]
    record.setdefault("events", []).append(transition)
    write_json(record_path, record)
    append_event(change_dir, transition, update_record=False)
    print(f"STATE UPDATED: {current} -> {args.next_state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
