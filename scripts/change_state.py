#!/usr/bin/env python3
"""Apply a validated lifecycle transition and append an auditable event."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from check_production_readiness import validate


TRANSITIONS = {
    "INTAKE": {"CLASSIFIED"},
    "CLASSIFIED": {"CONTEXT_READY"},
    "CONTEXT_READY": {"CONTRACT_READY"},
    "CONTRACT_READY": {"PLAN_APPROVED"},
    "PLAN_APPROVED": {"IMPLEMENTING"},
    "IMPLEMENTING": {"VERIFYING"},
    "VERIFYING": {"REVIEW_REQUIRED", "REMEDIATING"},
    "REMEDIATING": {"VERIFYING"},
    "REVIEW_REQUIRED": {"RELEASE_READY", "REMEDIATING"},
    "RELEASE_READY": {"DEPLOYED", "ROLLED_BACK"},
    "DEPLOYED": {"DEPLOYED", "OBSERVING", "ROLLED_BACK"},
    "OBSERVING": {"CLOSED", "ROLLED_BACK"},
    "ROLLED_BACK": {"REMEDIATING", "CLOSED"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance a production change state.")
    parser.add_argument("record", type=Path)
    parser.add_argument("next_state", choices=sorted({state for states in TRANSITIONS.values() for state in states}))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--rollout-stage")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read record: {exc}")
        return 2
    current = record.get("state")
    record_errors = validate(record)
    if record_errors:
        print("BLOCKED: production record is incomplete")
        for error in record_errors:
            print(f"- {error}")
        return 2
    if args.next_state not in TRANSITIONS.get(current, set()):
        print(f"INVALID TRANSITION: {current} -> {args.next_state}")
        return 2
    if args.next_state in {"RELEASE_READY", "DEPLOYED"} and not (record.get("technical_done") and record.get("operational_done")):
        print("BLOCKED: technical_done and operational_done must both be true")
        return 2
    if args.next_state in {"RELEASE_READY", "DEPLOYED"}:
        candidate = dict(record)
        candidate["state"] = args.next_state
        errors = validate(candidate)
        if errors:
            print("BLOCKED: production readiness evidence is incomplete")
            for error in errors:
                print(f"- {error}")
            return 2
    if args.next_state in {"RELEASE_READY", "DEPLOYED", "OBSERVING", "ROLLED_BACK", "CLOSED"} and not args.evidence:
        print("BLOCKED: release, rollout, observation, rollback, and closure transitions require --evidence")
        return 2

    rollout_stage = None
    if args.next_state == "DEPLOYED":
        stages = record.get("rollout", {}).get("stages", []) if isinstance(record.get("rollout"), dict) else []
        completed = [item.get("rollout_stage") for item in record.get("events", []) if isinstance(item, dict) and item.get("to") == "DEPLOYED"]
        if not args.rollout_stage or args.rollout_stage not in stages:
            print("BLOCKED: DEPLOYED requires --rollout-stage from rollout.stages")
            return 2
        expected = stages[len(completed)] if len(completed) < len(stages) else None
        if args.rollout_stage != expected:
            print(f"BLOCKED: next rollout stage must be {expected}")
            return 2
        rollout_stage = args.rollout_stage
    if args.next_state == "OBSERVING":
        stages = record.get("rollout", {}).get("stages", []) if isinstance(record.get("rollout"), dict) else []
        completed = [item.get("rollout_stage") for item in record.get("events", []) if isinstance(item, dict) and item.get("to") == "DEPLOYED"]
        if completed != stages:
            print("BLOCKED: all rollout stages must complete in order before OBSERVING")
            return 2

    record_path = args.record.resolve()
    if record_path.parent.name != "changes" or record_path.parent.parent.name != "production":
        print("BLOCKED: production record must be under docs/methodology/production/changes")
        return 2
    project_root = record_path.parent.parent.parents[2]
    allowed_audit = (record_path.parent.parent / "audit").resolve()
    audit = Path(str(record.get("audit_log", "")))
    if not audit.is_absolute():
        audit = project_root / audit
    audit = audit.resolve()
    try:
        audit.relative_to(allowed_audit)
    except ValueError:
        print(f"BLOCKED: audit_log must stay under {allowed_audit}")
        return 2

    timestamp = datetime.now(timezone.utc).isoformat()
    record["state"] = args.next_state
    record.setdefault("events", []).append({
        "from": current, "to": args.next_state, "actor": args.actor,
        "at": timestamp, "evidence": args.evidence, "rollout_stage": rollout_stage,
    })
    args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if record.get("audit_log"):
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record["events"][-1], ensure_ascii=False) + "\n")
    print(f"STATE UPDATED: {current} -> {args.next_state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
