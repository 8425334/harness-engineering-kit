#!/usr/bin/env python3
"""Bind an external approval reference to the complete change contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_phase import check
from methodology_common import contract_files, relative_digests, utc_now, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--source", required=True, help="Approval system or channel")
    parser.add_argument("--approval-id", required=True, help="Stable ticket, review, or message identifier")
    args = parser.parse_args()
    change_dir = args.change_dir.resolve()
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
    write_json(change_dir / "approval.json", approval)
    print(f"CONTRACT APPROVED: {change_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
