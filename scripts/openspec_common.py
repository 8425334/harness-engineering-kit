#!/usr/bin/env python3
"""Shared contract for OpenSpec-owned changes with Harness governance."""

from __future__ import annotations

import os
import shutil
from typing import Any


LIFECYCLE_OWNER = "openspec"
GOVERNANCE_PROVIDER = "harness-engineering"
REQUIRED_WORKFLOWS = ["explore", "propose", "apply", "verify", "sync", "archive"]

#: Workspace federation adds one optional ``workspace`` section to
#: ``governance.json``. It references unit-local changes and specs; it never
#: carries spec content, which would create a second authority.
WORKSPACE_ROLES = ("provider", "consumer", "independent")
WORKSPACE_KEYS = (
    "workspace_id",
    "unit_id",
    "role",
    "change_id",
    "derived_from",
    "related_changes",
    "contracts",
)
WORKSPACE_REQUIRED_KEYS = ("workspace_id", "unit_id", "role")
RELATED_CHANGE_KEYS = ("unit", "change_id", "specs")
RELATED_CHANGE_REQUIRED_KEYS = ("unit", "change_id", "specs")
SPEC_REFERENCE_KEYS = ("unit", "path")
CONTRACT_KEYS = ("contract", "provider", "from_version", "to_version", "breaking", "deprecated_until", "verification")
CONTRACT_REQUIRED_KEYS = ("contract", "provider", "from_version", "to_version", "breaking")


def workspace_contract() -> dict[str, object]:
    """Return the canonical field contract of ``governance.json.workspace``.

    ``orchestration_contract`` is deliberately untouched: it is compared with a
    strict equality check, so adding keys there would invalidate every existing
    change. This contract is additive and only consulted when the optional
    ``workspace`` key is present.
    """
    return {
        "keys": list(WORKSPACE_KEYS),
        "required_keys": list(WORKSPACE_REQUIRED_KEYS),
        "roles": list(WORKSPACE_ROLES),
        "related_change_keys": list(RELATED_CHANGE_KEYS),
        "related_change_required_keys": list(RELATED_CHANGE_REQUIRED_KEYS),
        "spec_reference_keys": list(SPEC_REFERENCE_KEYS),
        "contract_keys": list(CONTRACT_KEYS),
        "contract_required_keys": list(CONTRACT_REQUIRED_KEYS),
    }


def openspec_executable() -> str:
    """Resolve the OpenSpec CLI for subprocess use.

    Windows resolves a command without an extension by appending only ``.exe``,
    so the bare name ``openspec`` never reaches the ``.cmd`` shim that npm
    installs. ``shutil.which`` honours ``PATHEXT`` and returns the real launcher.
    """
    return shutil.which("openspec") or "openspec"


def openspec_environment(home: str | None = None) -> dict[str, str]:
    """Environment for an OpenSpec CLI invocation, optionally fully isolated.

    The CLI keeps its global config under ``HOME``/``USERPROFILE`` on POSIX and
    under ``APPDATA``/``LOCALAPPDATA`` on Windows, and honours a pre-set
    ``XDG_CONFIG_HOME`` wherever it runs. Redirecting only the home variables
    still let ``config set`` rewrite the developer's own config on Windows, so
    every global location has to move together.
    """
    environment = dict(os.environ)
    environment["OPENSPEC_TELEMETRY"] = "0"
    if home is None:
        return environment
    environment["HOME"] = home
    environment["USERPROFILE"] = home
    environment["APPDATA"] = home
    environment["LOCALAPPDATA"] = home
    environment["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    return environment


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
