#!/usr/bin/env python3
"""Shared contract for OpenSpec-owned changes with Harness governance."""

from __future__ import annotations

from typing import Any


LIFECYCLE_OWNER = "openspec"
GOVERNANCE_PROVIDER = "harness-engineering"
REQUIRED_WORKFLOWS = ["explore", "propose", "apply", "verify", "sync", "archive"]


def orchestration_contract(change_id: str) -> dict[str, Any]:
    """Return the exact OpenSpec lifecycle and Harness governance relationship."""
    return {
        "change_id": change_id,
        "lifecycle_owner": LIFECYCLE_OWNER,
        "governance_provider": GOVERNANCE_PROVIDER,
        "workflows": list(REQUIRED_WORKFLOWS),
        "governance": ["context", "requirement-reflection", "approval", "execution-evidence", "fitness", "production"],
    }


def validate_orchestration(record: dict[str, Any]) -> list[str]:
    change_id = record.get("change_id")
    if not isinstance(change_id, str) or not change_id:
        return ["governance.json orchestration cannot be validated without change_id"]
    actual = record.get("orchestration")
    expected = orchestration_contract(change_id)
    if actual != expected:
        return [
            "governance.json orchestration must declare OpenSpec as lifecycle owner "
            "and Harness Engineering as governance provider"
        ]
    return []
