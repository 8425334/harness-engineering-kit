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


def validate(record: dict[str, Any]) -> list[str]:
    errors = [f"missing top-level field: {key}" for key in sorted(REQUIRED - set(record))]
    if record.get("environment") != "production":
        errors.append("environment must be production")
    if record.get("profile") not in {"standard", "regulated"}:
        errors.append("production changes require standard or regulated profile")
    if record.get("risk") not in {"low", "medium", "high", "critical"}:
        errors.append("risk must be low, medium, high, or critical")

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
    ]
    errors.extend(f"missing or placeholder: {name}" for name, item in required_values if not meaningful(item))

    state = record.get("state")
    if state in READY_STATES and not record.get("technical_done"):
        errors.append("technical_done must be true before release readiness")
    if state in READY_STATES and not record.get("operational_done"):
        errors.append("operational_done must be true before release readiness")
    if record.get("risk") in HIGH_RISK:
        for field in ("threat_model", "audit"):  # optional fields become mandatory for high-risk records
            if not meaningful(value(record, "evidence", field)):
                errors.append(f"high-risk change requires evidence.{field}")
    if state == "DEPLOYED" and value(record, "observability", "observation_window_minutes") in (None, 0):
        errors.append("DEPLOYED requires a positive observation window")

    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/methodology/production/changes/change.json")
    if not path.is_file():
        print(f"MISSING: {path}")
        return 2
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID JSON: {exc}")
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
