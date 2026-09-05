#!/usr/bin/env python3
"""Fail-closed validation for a production change record."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED = {
    "schema_version", "change_id", "title", "environment", "profile", "risk",
    "owner", "service", "state", "technical_done", "operational_done",
    "evidence", "observability", "rollout", "rollback", "approvals", "audit_log",
}
READY_STATES = {"RELEASE_READY", "DEPLOYED", "OBSERVING", "CLOSED"}
HIGH_RISK = {"high", "critical"}
RECORD_STATES = {
    "INTAKE", "CLASSIFIED", "CONTEXT_READY", "CONTRACT_READY", "PLAN_APPROVED",
    "IMPLEMENTING", "VERIFYING", "REVIEW_REQUIRED", "REMEDIATING", "RELEASE_READY",
    "DEPLOYED", "OBSERVING", "ROLLED_BACK", "CLOSED",
}


def value(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def meaningful(item: Any) -> bool:
    if not item or not isinstance(item, (str, int, float, list, dict)):
        return False
    if isinstance(item, str):
        return bool(item.strip()) and "{{" not in item
    if isinstance(item, list):
        return bool(item) and all(meaningful(entry) for entry in item)
    return True


def is_int(item: Any) -> bool:
    """True only for real integers; JSON booleans are not rollout counts."""
    return isinstance(item, int) and not isinstance(item, bool)


def rollout_cycles(events: Any) -> list[list[str | None]]:
    """Split rollout progress into cycles, reset by every rollback.

    A rollback invalidates the stages deployed before it, so the next
    deployment must restart from the first declared stage.  The last cycle is
    the currently active one.
    """
    cycles: list[list[str | None]] = [[]]
    if not isinstance(events, list):
        return cycles
    for item in events:
        if not isinstance(item, dict):
            continue
        if item.get("to") == "ROLLED_BACK":
            cycles.append([])
        elif item.get("to") == "DEPLOYED":
            cycles[-1].append(item.get("rollout_stage"))
    return cycles


def validate(record: dict[str, Any]) -> list[str]:
    errors = [f"missing top-level field: {key}" for key in sorted(REQUIRED - set(record))]
    if record.get("environment") != "production":
        errors.append("environment must be production")
    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if record.get("profile") not in {"standard", "regulated"}:
        errors.append("production changes require standard or regulated profile")
    if record.get("risk") not in {"low", "medium", "high", "critical"}:
        errors.append("risk must be low, medium, high, or critical")
    if record.get("state") not in RECORD_STATES:
        errors.append(f"state must be one of {sorted(RECORD_STATES)}")
    for field in ("technical_done", "operational_done"):
        if not isinstance(record.get(field), bool):
            errors.append(f"{field} must be a JSON boolean")

    required_values = [
        ("change_id", record.get("change_id")), ("title", record.get("title")),
        ("owner", record.get("owner")), ("service", record.get("service")),
        ("evidence.spec", value(record, "evidence", "spec")),
        ("evidence.tests", value(record, "evidence", "tests")),
        ("evidence.gates", value(record, "evidence", "gates")),
        ("evidence.review", value(record, "evidence", "review")),
        ("observability.dashboard", value(record, "observability", "dashboard")),
        ("observability.alerts", value(record, "observability", "alerts")),
        ("observability.baseline", value(record, "observability", "baseline")),
        ("observability.correlation", value(record, "observability", "correlation")),
        ("rollout.strategy", value(record, "rollout", "strategy")),
        ("rollout.stages", value(record, "rollout", "stages")),
        ("rollout.stop_conditions", value(record, "rollout", "stop_conditions")),
        ("rollout.operator", value(record, "rollout", "operator")),
        ("rollback.strategy", value(record, "rollback", "strategy")),
        ("rollback.runbook", value(record, "rollback", "runbook")),
        ("rollback.owner", value(record, "rollback", "owner")),
        ("rollback.tested_at", value(record, "rollback", "tested_at")),
        ("rollback.data_plan", value(record, "rollback", "data_plan")),
        ("approvals.reviewer", value(record, "approvals", "reviewer")),
        ("approvals.approved_at", value(record, "approvals", "approved_at")),
        ("audit_log", record.get("audit_log")),
    ]
    errors.extend(f"missing or placeholder: {name}" for name, item in required_values if not meaningful(item))

    stages = value(record, "rollout", "stages")
    if not isinstance(stages, list) or not stages or not all(isinstance(stage, str) and stage.strip() for stage in stages):
        errors.append("rollout.stages must be a non-empty array of stage names")
    elif len(set(stages)) != len(stages):
        errors.append("rollout.stages must not contain duplicate stages")

    audit_log = record.get("audit_log")
    if isinstance(audit_log, str) and audit_log.strip() and "{{" not in audit_log:
        configured = Path(audit_log)
        if configured.is_absolute() or ".." in configured.parts:
            errors.append("audit_log must be a project-relative path without ..")

    state = record.get("state")
    if state in READY_STATES:
        if record.get("technical_done") is not True:
            errors.append("technical_done must be true before release readiness")
        if record.get("operational_done") is not True:
            errors.append("operational_done must be true before release readiness")
    if record.get("risk") in HIGH_RISK:
        for field in ("threat_model", "audit"):  # optional fields become mandatory for high-risk records
            if not meaningful(value(record, "evidence", field)):
                errors.append(f"high-risk change requires evidence.{field}")
    if state == "DEPLOYED":
        window = value(record, "observability", "observation_window_minutes")
        if not is_int(window) or window <= 0:
            errors.append("DEPLOYED requires observation_window_minutes to be a positive integer")

    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/methodology/production/changes/change.json")
    if not path.is_file():
        print(f"MISSING: {path}")
        return 2
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"INVALID JSON: {exc}")
        return 2
    if not isinstance(record, dict):
        print("INVALID JSON: record must be a JSON object")
        return 2
    errors = validate(record)
    if errors:
        print("PRODUCTION RECORD INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"PRODUCTION RECORD OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
