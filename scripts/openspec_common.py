#!/usr/bin/env python3
"""Canonical parent-child contract for Harness-managed OpenSpec changes."""

from __future__ import annotations

from typing import Any


PARENT_ID = "harness-engineering"
CHILD_ID = "openspec"
DISPATCHER = "docs/methodology/scripts/dispatch_openspec.py"
ALLOWED_ACTIONS = ["status", "instructions", "validate", "show", "templates"]
DENIED_OWNERSHIP = [
    "change-creation",
    "lifecycle-state",
    "approval",
    "implementation",
    "sync",
    "archive",
]


def orchestration_contract(change_id: str) -> dict[str, Any]:
    """Return the exact machine-readable Harness -> OpenSpec relationship."""
    return {
        "parent": PARENT_ID,
        "change_id": change_id,
        "children": {
            CHILD_ID: {
                "role": "specification-authoring-and-validation",
                "dispatcher": DISPATCHER,
                "allowed_actions": list(ALLOWED_ACTIONS),
                "denied_ownership": list(DENIED_OWNERSHIP),
            }
        },
    }


def validate_orchestration(record: dict[str, Any]) -> list[str]:
    change_id = record.get("change_id")
    if not isinstance(change_id, str) or not change_id:
        return ["change.json orchestration cannot be validated without change_id"]
    actual = record.get("orchestration")
    expected = orchestration_contract(change_id)
    if actual != expected:
        return [
            "change.json orchestration must declare the canonical Harness parent and "
            "OpenSpec child dispatcher contract"
        ]
    return []
