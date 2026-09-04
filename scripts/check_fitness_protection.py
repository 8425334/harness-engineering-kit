#!/usr/bin/env python3
"""Protect project Fitness controls from unapproved repository changes."""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping


PROTECTED_PREFIX = "docs/fitness/"
APPROVAL_FIELDS = (
    "FITNESS_CHANGE_APPROVED_BY",
    "FITNESS_CHANGE_APPROVAL_SOURCE",
    "FITNESS_CHANGE_APPROVAL_ID",
    "FITNESS_CHANGE_APPROVAL_DIGEST",
)


class FitnessProtectionError(ValueError):
    """Raised when Fitness changes cannot be inspected safely."""


def git(project_root: Path, arguments: list[str], *, text: bool = False) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=project_root,
        capture_output=True,
        text=text,
        check=False,
    )


def require_git_repository(project_root: Path) -> None:
    result = git(project_root, ["rev-parse", "--is-inside-work-tree"], text=True)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise FitnessProtectionError("project root must be inside a Git work tree")


def resolve_base(project_root: Path, requested: str | None) -> tuple[str | None, str]:
    candidate = requested or os.environ.get("FITNESS_BASE_REF") or "HEAD"
    result = git(project_root, ["rev-parse", "--verify", f"{candidate}^{{commit}}"], text=True)
    if result.returncode == 0:
        return candidate, result.stdout.strip()
    if requested or os.environ.get("FITNESS_BASE_REF") or candidate != "HEAD":
        raise FitnessProtectionError(f"Fitness comparison base is not a commit: {candidate}")
    return None, "UNBORN"


def parse_name_status(payload: bytes) -> dict[str, str]:
    fields = payload.split(b"\0")
    changes: dict[str, str] = {}
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index].decode("utf-8", errors="strict")
        if index + 1 >= len(fields) or not fields[index + 1]:
            raise FitnessProtectionError("Git returned an incomplete Fitness change record")
        path = fields[index + 1].decode("utf-8", errors="strict")
        changes[path] = status[:1]
        index += 2
    return changes


def collect_changes(project_root: Path, base_ref: str | None) -> dict[str, str]:
    changes: dict[str, str] = {}
    if base_ref:
        tracked = git(project_root, ["diff", "--name-status", "-z", "--no-renames", base_ref, "--", "docs/fitness"])
        if tracked.returncode != 0:
            raise FitnessProtectionError(tracked.stderr.decode("utf-8", errors="replace").strip() or "cannot inspect Fitness changes")
        changes.update(parse_name_status(tracked.stdout))

    untracked = git(project_root, ["ls-files", "-z", "--others", "--exclude-standard", "--", "docs/fitness"])
    if untracked.returncode != 0:
        raise FitnessProtectionError(untracked.stderr.decode("utf-8", errors="replace").strip() or "cannot inspect untracked Fitness files")
    for raw_path in untracked.stdout.split(b"\0"):
        if raw_path:
            changes[raw_path.decode("utf-8", errors="strict")] = "A"

    invalid = [path for path in changes if not path.startswith(PROTECTED_PREFIX)]
    if invalid:
        raise FitnessProtectionError(f"Git returned paths outside {PROTECTED_PREFIX}: {invalid}")
    return dict(sorted(changes.items()))


def baseline_has_fitness(project_root: Path, base_ref: str | None) -> bool:
    if not base_ref:
        return False
    result = git(project_root, ["ls-tree", "-r", "--name-only", "-z", base_ref, "--", "docs/fitness"])
    if result.returncode != 0:
        raise FitnessProtectionError(result.stderr.decode("utf-8", errors="replace").strip() or "cannot inspect baseline Fitness files")
    return bool(result.stdout.strip(b"\0"))


def post_change_digest(project_root: Path, status: str, relative: str) -> str:
    path = project_root / relative
    if status == "D" or not path.exists():
        return "DELETED"
    if path.is_symlink():
        return "SYMLINK:" + os.readlink(path)
    if not path.is_file():
        raise FitnessProtectionError(f"protected change is not a regular file: {relative}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change_digest(project_root: Path, base_commit: str, changes: Mapping[str, str]) -> tuple[str, list[dict[str, str]]]:
    records = [
        {"status": status, "path": path, "content": post_change_digest(project_root, status, path)}
        for path, status in sorted(changes.items())
    ]
    payload = {"schema_version": 1, "base_commit": base_commit, "changes": records}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), records


def is_python_syntax_repair(project_root: Path, base_ref: str | None, changes: Mapping[str, str]) -> bool:
    if not base_ref or not changes:
        return False
    for relative, status in changes.items():
        if status != "M" or not relative.endswith(".py"):
            return False
        baseline = git(project_root, ["show", f"{base_ref}:{relative}"])
        if baseline.returncode != 0:
            return False
        try:
            baseline_text = baseline.stdout.decode("utf-8")
            ast.parse(baseline_text, filename=f"{base_ref}:{relative}")
        except SyntaxError as syntax_error:
            error_line = syntax_error.lineno or 1
        except UnicodeError:
            return False
        else:
            return False
        try:
            current_text = (project_root / relative).read_text(encoding="utf-8")
            ast.parse(current_text, filename=relative)
        except (OSError, SyntaxError, UnicodeError):
            return False
        matcher = difflib.SequenceMatcher(a=baseline_text.splitlines(), b=current_text.splitlines(), autojunk=False)
        changed_lines = 0
        for tag, baseline_start, baseline_end, current_start, current_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            changed_lines += max(baseline_end - baseline_start, current_end - current_start)
            affected = range(baseline_start + 1, max(baseline_end, baseline_start + 1) + 1)
            if any(abs(line - error_line) > 2 for line in affected):
                return False
        if changed_lines > 8:
            return False
    return True


def approval_matches(environment: Mapping[str, str], digest: str) -> bool:
    return all(environment.get(field, "").strip() for field in APPROVAL_FIELDS[:-1]) and environment.get(APPROVAL_FIELDS[-1], "").strip() == digest


def check(project_root: Path, base: str | None = None, environment: Mapping[str, str] | None = None) -> dict[str, object]:
    project_root = project_root.resolve()
    require_git_repository(project_root)
    base_ref, base_commit = resolve_base(project_root, base)
    changes = collect_changes(project_root, base_ref)
    if not changes:
        return {"status": "PASS", "reason": "unchanged", "base_commit": base_commit, "changes": []}

    digest, records = change_digest(project_root, base_commit, changes)
    if not baseline_has_fitness(project_root, base_ref) and all(status == "A" for status in changes.values()):
        return {"status": "PASS", "reason": "initial-bootstrap", "base_commit": base_commit, "digest": digest, "changes": records}
    if is_python_syntax_repair(project_root, base_ref, changes):
        return {"status": "PASS", "reason": "python-syntax-repair", "base_commit": base_commit, "digest": digest, "changes": records}

    approval_environment = environment if environment is not None else os.environ
    if approval_matches(approval_environment, digest):
        return {
            "status": "PASS",
            "reason": "human-approved",
            "base_commit": base_commit,
            "digest": digest,
            "approval": {
                "actor": approval_environment["FITNESS_CHANGE_APPROVED_BY"],
                "source": approval_environment["FITNESS_CHANGE_APPROVAL_SOURCE"],
                "approval_id": approval_environment["FITNESS_CHANGE_APPROVAL_ID"],
            },
            "changes": records,
        }
    return {"status": "BLOCKED", "reason": "human-approval-required", "base_commit": base_commit, "digest": digest, "changes": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root; defaults to the current directory.")
    parser.add_argument("--base", help="Git commit/ref to compare; defaults to FITNESS_BASE_REF or HEAD.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        result = check(args.root, args.base)
    except (FitnessProtectionError, OSError, UnicodeError) as exc:
        print(f"FITNESS PROTECTION FAILED: {exc}")
        return 2

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["status"] == "PASS":
        print(f"FITNESS PROTECTION OK: {result['reason']}")
    else:
        print("FITNESS PROTECTION BLOCKED: human approval is required for every docs/fitness change")
        print(f"Approval digest: {result['digest']}")
        print("Protected CI or a human operator must set:")
        for field in APPROVAL_FIELDS:
            suffix = f"={result['digest']}" if field == "FITNESS_CHANGE_APPROVAL_DIGEST" else "=<value>"
            print(f"- {field}{suffix}")
        for change in result["changes"]:
            print(f"- {change['status']} {change['path']}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
