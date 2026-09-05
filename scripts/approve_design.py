#!/usr/bin/env python3
"""Bind an external approval reference to the complete change contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_phase import check
from methodology_common import append_event, contract_files, read_json, relative_digests, sha256, utc_now, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--source", required=True, help="Approval system or channel")
    parser.add_argument("--approval-id", required=True, help="Stable ticket, review, or message identifier")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
    try:
        record = read_json(change_dir / "change.json")
    except (OSError, ValueError) as exc:
        print(f"APPROVAL BLOCKED: cannot read change record: {exc}")
        return 2
    approval_path = change_dir / "approval.json"
    if approval_path.is_file():
        # Re-approving after a contract edit would silently rebind the digests;
        # a revised design requires a new change or an explicit, audited removal.
        print("APPROVAL BLOCKED: approval.json already exists")
        print("- a revised contract requires a new change, or remove the stale approval record explicitly before re-approving")
        return 2
    errors = check(change_dir, "DESIGN")
    if errors:
        print("APPROVAL BLOCKED")
        for error in errors:
            print(f"- {error}")
        return 2
    files = contract_files(change_dir)
    approval = {
        "schema_version": 1,
        "status": "approved",
        "actor": args.actor,
        "at": utc_now(),
        "source": args.source,
        "approval_id": args.approval_id,
        "artifacts": relative_digests(change_dir, files),
    }
    write_json(approval_path, approval)
    append_event(change_dir, {
        "event": "design.approved",
        "change_id": record.get("change_id"),
        "skill": record.get("skill"),
        "mode": record.get("mode"),
        "trigger": record.get("trigger"),
        "actor": args.actor,
        "source": args.source,
        "approval_id": args.approval_id,
        "artifacts_sha256": sha256(approval_path),
        "at": approval["at"],
    })
    print(f"CONTRACT APPROVED: {change_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
