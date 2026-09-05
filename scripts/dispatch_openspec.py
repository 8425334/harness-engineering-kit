#!/usr/bin/env python3
"""Dispatch a strictly allowlisted OpenSpec child operation through Harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from methodology_common import append_event, read_json, utc_now
from openspec_common import ALLOWED_ACTIONS, validate_orchestration


ACTIVE_STATES = {
    "INTAKE", "EXPLORED", "CONTRACT_READY", "DESIGN_READY", "APPROVED",
    "IMPLEMENTING", "VERIFYING", "REMEDIATING", "VERIFIED", "SYNCED",
    "DRIFT_DETECTED", "CONTRACT_CHANGED",
}
AUTHORING_STATES = {
    "proposal": {"INTAKE", "EXPLORED", "DRIFT_DETECTED", "CONTRACT_CHANGED"},
    "specs": {"INTAKE", "EXPLORED", "DRIFT_DETECTED", "CONTRACT_CHANGED"},
    "design": {"CONTRACT_READY", "CONTRACT_CHANGED"},
    "tasks": {"CONTRACT_READY", "CONTRACT_CHANGED"},
    # These special instruction surfaces are read-only child input. They never
    # authorize OpenSpec to implement or archive the change.
    "apply": {"APPROVED", "IMPLEMENTING", "REMEDIATING"},
    "archive": {"VERIFIED", "SYNCED"},
}


@dataclass(frozen=True)
class DispatchRequest:
    action: str
    artifact: str | None = None


def authorize(record: dict[str, Any], request: DispatchRequest) -> list[str]:
    errors = validate_orchestration(record)
    state = record.get("state")
    if request.action not in ALLOWED_ACTIONS:
        errors.append(f"OpenSpec child action is not allowlisted: {request.action}")
    if state not in ACTIVE_STATES:
        errors.append(f"OpenSpec child cannot run in lifecycle state: {state!r}")
    if request.action == "instructions":
        allowed = AUTHORING_STATES.get(str(request.artifact))
        if allowed is None:
            errors.append("instructions artifact must be proposal, specs, design, tasks, apply, or archive")
        elif state not in allowed:
            errors.append(f"OpenSpec instructions {request.artifact} are not authorized in state {state}")
    elif request.artifact is not None:
        errors.append("--artifact is valid only with the instructions action")
    if request.action == "validate" and state in {"INTAKE", "ARCHIVED"}:
        errors.append(f"OpenSpec validation is not authorized in state {state}")
    return errors


def build_command(binary: str, change_id: str, request: DispatchRequest) -> list[str]:
    """Build fixed argv; callers cannot pass raw OpenSpec arguments."""
    if request.action == "status":
        return [binary, "status", "--change", change_id, "--json"]
    if request.action == "instructions":
        if request.artifact is None:
            raise ValueError("instructions requires an artifact")
        return [binary, "instructions", request.artifact, "--change", change_id, "--json"]
    if request.action == "validate":
        return [binary, "validate", change_id, "--type", "change", "--strict", "--json", "--no-interactive"]
    if request.action == "show":
        return [binary, "show", change_id, "--type", "change", "--json"]
    if request.action == "templates":
        return [binary, "templates", "--json"]
    raise ValueError(f"unsupported action: {request.action}")


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def dispatch(change_dir: Path, request: DispatchRequest, binary: str = "openspec") -> tuple[int, str, str]:
    change_dir = change_dir.resolve()
    record = read_json(change_dir / "change.json")
    project_root = Path(str(record.get("project_root", ""))).resolve()
    expected_dir = project_root / "openspec" / "changes" / str(record.get("change_id", ""))
    errors = []
    if change_dir != expected_dir:
        errors.append(f"change directory must be the canonical Harness workspace: {expected_dir}")
    errors.extend(authorize(record, request))
    if errors:
        return 2, "", "; ".join(errors)

    command = build_command(binary, str(record["change_id"]), request)
    started_at = utc_now()
    try:
        completed = subprocess.run(command, cwd=project_root, capture_output=True, text=True, check=False)
        stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
    except OSError as exc:
        stdout, stderr, returncode = "", str(exc), 127

    if returncode == 0:
        try:
            json.loads(stdout)
        except json.JSONDecodeError:
            stderr = (stderr + "\n" if stderr else "") + "OpenSpec child returned non-JSON output"
            returncode = 2
    append_event(change_dir, {
        "event": "openspec.dispatched" if returncode == 0 else "openspec.failed",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "actor": "engineering",
        "parent": "harness-engineering",
        "child": "openspec",
        "action": request.action,
        "artifact": request.artifact,
        "argv": command[1:],
        "exit_code": returncode,
        "stdout_sha256": digest_text(stdout),
        "stderr_sha256": digest_text(stderr),
        "started_at": started_at,
        "at": utc_now(),
    })
    return returncode, stdout, stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("action", choices=ALLOWED_ACTIONS)
    parser.add_argument("--artifact", choices=sorted(AUTHORING_STATES))
    args = parser.parse_args()
    try:
        code, stdout, stderr = dispatch(
            args.change_dir,
            DispatchRequest(args.action, args.artifact),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"OPENSPEC DISPATCH BLOCKED: {exc}", file=sys.stderr)
        return 2
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
