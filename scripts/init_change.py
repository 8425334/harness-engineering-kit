#!/usr/bin/env python3
"""Create a canonical, auditable Engineering change workspace."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from check_agent_policy import validate as validate_agent_policy
from check_context_docs import validate_project as validate_context_docs
from check_profile import read_project_profile
from methodology_common import append_event, utc_now, write_json


CANONICAL_POLICY_LOCATION = ("docs", "methodology", "agent-policy.yaml")


def project_root_from_policy(policy_path: Path) -> Path:
    """Derive the project root from the canonical policy location.

    The root is only knowable when the policy sits at
    ``<project root>/docs/methodology/agent-policy.yaml``; anything else is a
    caller error instead of a guessed (and crash-prone) ``parents[2]``.
    """
    if policy_path.parts[-3:] != CANONICAL_POLICY_LOCATION:
        raise ValueError("agent policy must be located at <project root>/docs/methodology/agent-policy.yaml")
    return policy_path.parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--mode", choices=("backend", "frontend", "fullstack"), required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--capability")
    parser.add_argument("--trigger", choices=("native-selection", "explicit-selection", "manual-fallback"), required=True)
    parser.add_argument("--fallback-reason")
    parser.add_argument("--delivery-scope", choices=("technical", "production"), default="technical")
    parser.add_argument("--production-record")
    parser.add_argument("--profile-path", type=Path, default=Path("docs/methodology/profile.yaml"))
    parser.add_argument("--policy-path", type=Path, default=Path("docs/methodology/agent-policy.yaml"))
    parser.add_argument("--root", type=Path, default=Path("openspec/changes"))
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", args.change_id):
        print("INVALID: change_id must be a 2-63 character lowercase slug")
        return 2
    if args.delivery_scope == "production" and not args.production_record:
        print("INVALID: production delivery requires --production-record")
        return 2
    if args.trigger == "manual-fallback" and not args.fallback_reason:
        print("INVALID: manual-fallback requires --fallback-reason")
        return 2
    profile_path = args.profile_path.resolve()
    policy_path = args.policy_path.resolve()
    policy_errors = validate_agent_policy(policy_path)
    if policy_errors:
        print(f"INVALID POLICY: {'; '.join(policy_errors)}")
        return 2
    if profile_path.parent != policy_path.parent:
        print("INVALID: profile and agent policy must share docs/methodology")
        return 2
    try:
        project_root = project_root_from_policy(policy_path)
    except ValueError as exc:
        print(f"INVALID: {exc}")
        return 2
    context_errors, _ = validate_context_docs(project_root)
    if context_errors:
        print(f"INVALID CONTEXT DOCS: {'; '.join(context_errors)}")
        return 2
    try:
        profile, risk = read_project_profile(profile_path)
    except (OSError, ValueError) as exc:
        print(f"INVALID PROFILE: {exc}")
        return 2
    change_root = args.root.resolve()
    try:
        change_root.relative_to(project_root)
    except ValueError:
        print(f"INVALID: --root must stay inside the project root: {project_root}")
        return 2
    (project_root / "docs" / "methodology" / "lessons").mkdir(parents=True, exist_ok=True)
    if args.production_record:
        production_record = (Path.cwd() / args.production_record).resolve()
        allowed_production_dir = (project_root / "docs/methodology/production/changes").resolve()
        try:
            production_record.relative_to(allowed_production_dir)
        except ValueError:
            print(f"INVALID: production record must be under {allowed_production_dir}")
            return 2
        if not production_record.is_file():
            print(f"INVALID: production record does not exist: {production_record}")
            return 2
    else:
        production_record = None
    change_dir = args.root.resolve() / args.change_id
    if change_dir.exists():
        print(f"EXISTS: {change_dir}")
        return 2
    capability = args.capability or args.change_id
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", capability):
        print("INVALID: capability must be a 2-63 character lowercase slug")
        return 2
    (change_dir / "specs" / capability).mkdir(parents=True)
    (change_dir / "evidence").mkdir()
    timestamp = utc_now()
    record = {
        "schema_version": 2,
        "change_id": args.change_id,
        "title": args.title,
        "profile": profile,
        "risk": risk,
        "skill": "engineering",
        "mode": args.mode,
        "trigger": args.trigger,
        "delivery_scope": args.delivery_scope,
        "production_record": str(production_record) if production_record else None,
        "project_root": str(project_root),
        "state": "INTAKE",
        "owner": args.owner,
        "created_at": timestamp,
        "updated_at": timestamp,
        "events": [],
    }
    write_json(change_dir / "change.json", record)
    event = {
        "event": "skill.fallback" if args.trigger == "manual-fallback" else "skill.triggered",
        "change_id": args.change_id,
        "skill": "engineering",
        "mode": args.mode,
        "trigger": args.trigger,
        "phase": "EXPLORE",
        "actor": args.owner,
        "reason": args.fallback_reason,
        "at": timestamp,
    }
    append_event(change_dir, event)
    print(f"CHANGE CREATED: {change_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
