#!/usr/bin/env python3
"""Fail-closed ownership guard for the canonical change workspace.

In a Harness-instrumented repository every live directory under
``openspec/changes/`` must be owned by the Engineering lifecycle: it must carry
a canonical ``change.json`` (schema_version 3) whose ``change_id`` equals the
directory name.  A directory holding only OpenSpec artifacts (proposal/design/
specs/tasks) with no ``change.json`` is *unmanaged* and is not a valid active
change; gates must fail until it is registered with ``init_change.py``
(trigger=manual-fallback) or removed/archived.

Entry points (single script, three modes):

  (default / scan)   Deterministic repo-level check.  exit 0 (pass) / 2 (blocked).
  --install-hook     Idempotently install the Claude Code PreToolUse hook that
                     enforces the Harness -> OpenSpec dispatch boundary.
  --hook-check       Run from the PreToolUse hook: read the tool-use event JSON
                     on stdin and exit 0 (allow) / 2 (block).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

from openspec_common import validate_orchestration


CHANGES_REL = "openspec/changes"
ARCHIVE_NAME = "archive"

# OpenSpec CLI verbs that drive the *standalone* change lifecycle.  In an
# instrumented repo those transitions belong to the Engineering lifecycle, so
# the hook blocks them (config steerage already says so; this is the
# deterministic backstop for the lane that never enters a Harness gate).
OPENSPEC_LIFECYCLE_VERBS = {
    "propose", "new", "apply", "archive", "sync", "bulk-archive", "continue", "ff", "verify",
}
OPENSPEC_CHANGE_READS = {"status", "instructions", "validate", "show"}

# Harness control scripts are allowed to create/advance change dirs; they are
# how a change becomes and stays registered.  Never treat them as a bypass.
HARNESS_SCRIPT_NAMES = {
    "init_change.py",
    "methodology_state.py",
    "change_state.py",
    "approve_design.py",
    "approve_lesson.py",
    "create_lesson_candidate.py",
    "preflight_lessons.py",
    "record_failure.py",
    "record_skill_event.py",
    "resolve_context.py",
    "retrieve_lessons.py",
    "check_phase.py",
    "check_change_workspace.py",
    "check_task_plan.py",
    "dispatch_openspec.py",
    "record_task_completion.py",
    "skill_metrics.py",
}

HOOK_COMMAND = (
    "python3 ${CLAUDE_PROJECT_DIR}/docs/methodology/scripts/check_change_workspace.py "
    "--hook-check --root ${CLAUDE_PROJECT_DIR}"
)


def change_is_registered(change_dir: Path) -> tuple[bool, str]:
    """Return (True, "") when ``change_dir`` carries a canonical change.json.

    A registered change owns ``change.json`` with schema_version 3, the
    canonical parent-child contract, and a matching change_id.
    """
    record_path = change_dir / "change.json"
    if not record_path.is_file():
        return False, "missing canonical change.json"
    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "change.json is not readable JSON"
    if not isinstance(data, dict):
        return False, "change.json must be a JSON object"
    if data.get("schema_version") != 3:
        return False, f"change.json schema_version must be 3 (got {data.get('schema_version')!r})"
    if str(data.get("change_id", "")) != change_dir.name:
        return False, f"change.json change_id must match the change directory name: {change_dir.name}"
    orchestration_errors = validate_orchestration(data)
    if orchestration_errors:
        return False, orchestration_errors[0]
    return True, ""


def live_change_dirs(changes_root: Path) -> list[Path]:
    """Immediate children of the changes root that are active change workspaces.

    ``archive`` (OpenSpec/legacy archive subtree), dot-entries, and non-dirs are
    not active changes and are ignored.
    """
    if not changes_root.is_dir():
        return []
    result: list[Path] = []
    for child in sorted(changes_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name == ARCHIVE_NAME or child.name.startswith("."):
            continue
        result.append(child)
    return result


def check_workspace(project_root: Path | str) -> list[str]:
    """Return deterministic errors for unmanaged live change directories.

    An absent ``openspec/changes`` root is fine (nothing to manage).  Errors are
    sorted and reference each offending directory with a remediation hint.
    """
    root = Path(project_root).resolve()
    changes_root = root / CHANGES_REL
    if not changes_root.is_dir():
        return []
    errors: list[str] = []
    for change_dir in live_change_dirs(changes_root):
        registered, problem = change_is_registered(change_dir)
        if not registered:
            relative = change_dir.relative_to(root)
            errors.append(
                f"{relative}: {problem} (register with `init_change.py` trigger=manual-fallback, "
                "or archive/remove the directory; see docs/methodology/core/sdd-workflow.md)"
            )
    return errors


def _openspec_block(project_root: Path, command: str) -> list[str]:
    """Require change-scoped OpenSpec operations to cross the dispatcher.

    A ``python3 .../init_change.py`` or other Harness script invocation is never
    an OpenSpec lane and always passes. Real ``openspec`` invocations that own
    lifecycle actions or bypass change-scoped dispatch are blocked.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if any(os.path.basename(token) in HARNESS_SCRIPT_NAMES for token in tokens):
        return []
    for index, token in enumerate(tokens):
        if os.path.basename(token) != "openspec":
            continue
        subcommand = next((t for t in tokens[index + 1 :] if not t.startswith("-")), None)
        if subcommand is None:
            return []
        if subcommand not in OPENSPEC_LIFECYCLE_VERBS | OPENSPEC_CHANGE_READS:
            return []
        remaining = tokens[index + 1 :]
        if subcommand == "new":
            # `openspec new change ...` creates a change; `new` for other item
            # kinds (spec, initiative, ...) is not a lifecycle transition.
            if "change" not in remaining:
                return []
            return [
                "standalone OpenSpec change creation is disabled in an instrumented repo; "
                "create the change with `init_change.py` (the Engineering lifecycle owns openspec/changes)"
            ]
        if subcommand in OPENSPEC_CHANGE_READS:
            return [
                f"direct `openspec {subcommand}` is disabled for managed changes; "
                "invoke the allowlisted child capability through `dispatch_openspec.py`"
            ]
        return [
            f"standalone `openspec {subcommand}` is disabled in an instrumented repo; "
            "Harness owns creation, lifecycle state, approval, implementation, sync, and archive"
        ]
    return []


def _file_block(project_root: Path, raw_path: str) -> list[str]:
    """Block writes into an unmanaged live change directory.

    Writes under ``openspec/changes/archive``, dot-entries, the changes root
    itself, or a registered change directory all pass.
    """
    path = Path(raw_path)
    if not path.is_absolute():
        path = project_root / path
    changes_root = (project_root / CHANGES_REL).resolve()
    try:
        relative = path.resolve().relative_to(changes_root)
    except (OSError, ValueError):
        return []
    if not relative.parts:
        return []
    first = relative.parts[0]
    if first == ARCHIVE_NAME or first.startswith("."):
        return []
    registered, problem = change_is_registered(changes_root / first)
    if registered:
        return []
    return [
        f"write to unmanaged change `{first}` blocked: {problem}. "
        "Register it with `init_change.py` (trigger=manual-fallback) before authoring artifacts."
    ]


def hook_decision(tool_name: str, tool_input: dict, project_root: Path | str) -> list[str]:
    """Return blocking messages for one PreToolUse event (empty == allow)."""
    root = Path(project_root).resolve()
    if tool_name == "Bash":
        command = tool_input.get("command")
        return _openspec_block(root, str(command)) if command else []
    if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        raw = tool_input.get("file_path") or tool_input.get("path")
        return _file_block(root, str(raw)) if raw else []
    return []


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f"{path.name}.", suffix=".tmp", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def install_hook(project_root: Path | str) -> tuple[str, Path]:
    """Idempotently install the Claude Code PreToolUse guard into settings.json.

    Preserves every existing key and matcher; adds our matcher only when no
    existing hook already runs the guard command.  A settings file that cannot
    be parsed is backed up (``settings.json.guard-backup.json``) before the
    hooks-only configuration is written.
    """
    root = Path(project_root).resolve()
    settings = root / ".claude" / "settings.json"
    existing: dict | None = None
    backup: Path | None = None
    if settings.is_file():
        try:
            parsed = json.loads(settings.read_text(encoding="utf-8"))
            existing = parsed if isinstance(parsed, dict) else None
        except (OSError, UnicodeError, json.JSONDecodeError):
            backup = settings.with_name(settings.name + ".guard-backup.json")
            backup.write_bytes(settings.read_bytes())

    entry = {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash",
        "hooks": [{"type": "command", "command": HOOK_COMMAND}],
    }
    config = dict(existing or {})
    hooks = config.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool_use, list):
        pre_tool_use = [pre_tool_use]
        hooks["PreToolUse"] = pre_tool_use
    for item in pre_tool_use:
        if not isinstance(item, dict):
            continue
        if any(
            isinstance(hook, dict) and hook.get("command") == HOOK_COMMAND for hook in item.get("hooks", [])
        ):
            return ("unchanged" if backup is None else "unchanged-with-backup"), settings
    pre_tool_use.append(entry)
    _atomic_write_json(settings, config)
    if backup is not None:
        return "updated-with-backup", settings
    return ("created" if existing is None else "updated"), settings


def run_hook_check(project_root: Path | str) -> int:
    """Evaluate one PreToolUse event from stdin and return the exit code."""
    root = Path(project_root).resolve()
    try:
        event = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError):
        # Not a JSON tool-use event (e.g. non-PreToolUse invocations): allow.
        return 0
    tool_name = event.get("tool_name") if isinstance(event, dict) else None
    tool_input = event.get("tool_input") if isinstance(event, dict) else None
    if not isinstance(tool_input, dict):
        return 0
    reasons = hook_decision(str(tool_name or ""), tool_input, root)
    if not reasons:
        return 0
    for reason in reasons:
        print(f"WORKSPACE GUARD BLOCKED: {reason}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root; defaults to the current directory.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print the scan result as JSON.")
    parser.add_argument("--install-hook", action="store_true", help="Install the Claude Code PreToolUse guard hook.")
    parser.add_argument("--hook-check", action="store_true", help="Evaluate one PreToolUse event from stdin.")
    args = parser.parse_args()
    root = args.root.resolve()

    if args.install_hook:
        result, settings = install_hook(root)
        print(f"WORKSPACE GUARD HOOK {result.upper()}: {settings}")
        return 0
    if args.hook_check:
        return run_hook_check(root)

    errors = check_workspace(root)
    payload = {
        "schema_version": 1,
        "project_root": str(root),
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"WORKSPACE {payload['status']}: {root / CHANGES_REL}")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
