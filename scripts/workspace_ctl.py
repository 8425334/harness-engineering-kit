#!/usr/bin/env python3
"""Workspace federation CLI: discover, verify, context, exec, guard and friends.

The Python implementation is the single source of logic; the Node CLI wrapper in
``bin/harness-engineering-kit.js`` only forwards arguments here.

Exit codes follow the existing convention: ``0`` pass, ``2`` blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from workspace import (
    IDENTITY_REL,
    MAX_INPUT_BYTES,
    discover,
    graph,
    load_identity,
    parse_identity,
    resolve_contract_version,
    version_satisfies,
    verify,
)
from workspace_guard import (
    BLOCKED,
    Diagnostic,
    git_toplevel,
    guard as run_guard,
    has_blocked,
    locate_harness_root,
)

PROJECTION_CACHE_REL = ".hek/state/workspace-projection.json"


class UsageError(ValueError):
    pass


def _roots(values: list[Path] | None) -> list[Path]:
    return [Path(value) for value in values] if values else [Path.cwd()]


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _write_cache(projection) -> None:
    """Persist the projection next to the current unit; cache only, never truth."""
    harness = locate_harness_root(Path.cwd())
    if harness is None:
        return
    path = harness / PROJECTION_CACHE_REL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(projection.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def _summarize_projection(projection) -> None:
    print(f"WORKSPACE {projection.workspace_id or '(none)'} digest={projection.digest}")
    print(f"Units: {len(projection.units)}")
    for unit in projection.units:
        print(f"  - {unit.unit_id} ({unit.unit_kind}) kit={unit.kit_version} path={unit.path}")
    print(f"Contracts: {len(projection.contracts)}")
    for contract in projection.contracts:
        consumers = ", ".join(contract["consumers"]) or "-"
        print(f"  - {contract['contract']} provider={contract['provider']} consumers={consumers}")
    _print_diagnostics(projection.diagnostics)


def _print_diagnostics(diagnostics) -> None:
    if not diagnostics:
        print("Diagnostics: none")
        return
    print(f"Diagnostics: {len(diagnostics)}")
    for item in diagnostics:
        suffix = f" [{item.unit_id}]" if item.unit_id else ""
        print(f"  - {item.level}: {item.code}{suffix}: {item.message}")


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------


def cmd_discover(args: argparse.Namespace) -> int:
    projection = discover(_roots(args.root), args.depth)
    if args.refresh:
        _write_cache(projection)
    else:
        _write_cache(projection)
    if args.as_json:
        _print_json(projection.as_dict())
    else:
        _summarize_projection(projection)
    return 2 if has_blocked(projection.diagnostics) else 0


def cmd_verify(args: argparse.Namespace) -> int:
    code, projection = verify(_roots(args.root), args.depth)
    payload = projection.as_dict()
    payload["status"] = "blocked" if code else "pass"
    if args.as_json:
        _print_json(payload)
    else:
        print("WORKSPACE VERIFY " + ("BLOCKED" if code else "PASS"))
        _summarize_projection(projection)
    return code


def cmd_context(args: argparse.Namespace) -> int:
    target = Path(args.path)
    target_toplevel = git_toplevel(target)
    target_harness = locate_harness_root(target) or target_toplevel
    session = Path.cwd()
    session_toplevel = git_toplevel(session) or session
    payload: dict[str, object] = {
        "schema_version": 1,
        "kind": "workspace-context",
        "target": str(target),
        "unit_id": None,
        "cross_unit": bool(target_toplevel and session_toplevel and target_toplevel != session_toplevel),
        "harness_root": str(target_harness) if target_harness else None,
        "input_bytes": 0,
        "modules": [],
        "load_order": [],
        "diagnostics": [],
    }
    diagnostics: list[Diagnostic] = []

    if target_harness and (target_harness / IDENTITY_REL).is_file():
        try:
            identity = load_identity(target_harness)
            payload["unit_id"] = identity.get("unit_id")
        except ValueError as exc:
            diagnostics.append(Diagnostic(BLOCKED, "identity.schema", str(exc)))

    if payload["cross_unit"]:
        diagnostics.append(
            Diagnostic(
                BLOCKED,
                "boundary.cross-repo",
                "target belongs to another unit; open a session in that unit or file a workspace change",
            )
        )
    elif target_harness is not None:
        try:
            import resolve_context as resolve_context_module

            resolved = resolve_context_module.resolve_context(target_harness, [str(target)], args.keyword)
            payload["modules"] = resolved["modules"]
            payload["load_order"] = resolved["load_order"]
            total = 0
            for relative in resolved["load_order"]:
                candidate = Path(relative)
                path = candidate if candidate.is_absolute() else target_harness / candidate
                if path.is_file():
                    total += path.stat().st_size
            payload["input_bytes"] = total
            if total > MAX_INPUT_BYTES:
                diagnostics.append(
                    Diagnostic(
                        BLOCKED,
                        "context.budget",
                        f"input_bytes {total} exceeds MAX_INPUT_BYTES {MAX_INPUT_BYTES}",
                    )
                )
        except Exception as exc:  # noqa: BLE001 - surfaced as a blocked diagnostic
            diagnostics.append(Diagnostic(BLOCKED, "context.missing", str(exc)))
    else:
        diagnostics.append(Diagnostic(BLOCKED, "harness.mismatch", f"no harness root above {target}"))

    payload["diagnostics"] = [item.as_dict() for item in diagnostics]
    payload["status"] = "blocked" if has_blocked(diagnostics) else "pass"
    if args.as_json:
        _print_json(payload)
    else:
        print(f"CONTEXT {'BLOCKED' if has_blocked(diagnostics) else 'RESOLVED'}")
        print(f"Target: {target}")
        print(f"Unit: {payload['unit_id']} | cross_unit={payload['cross_unit']} | input_bytes={payload['input_bytes']}")
        for item in payload["load_order"]:
            print(f"  - {item}")
        _print_diagnostics(diagnostics)
    return 2 if has_blocked(diagnostics) else 0


def _load_unit(unit_id: str, roots: list[Path], depth: int):
    projection = discover(roots, depth)
    for unit in projection.units:
        if unit.unit_id == unit_id:
            return projection, unit
    return projection, None


def cmd_exec(args: argparse.Namespace) -> int:
    rest = list(args.rest or [])
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not args.unit or not rest:
        raise UsageError("usage: workspace exec <unit> -- <cmd...>")
    roots = _roots(args.root)
    projection, unit = _load_unit(args.unit, roots, args.depth)
    # A blocked projection means the structure itself is unsafe (nested unit,
    # mixed workspace, kit version mismatch, missing member). Launching a session
    # anyway would hand the agent a repository the gates have already rejected.
    if has_blocked(projection.diagnostics):
        blocked = [item for item in projection.diagnostics if item.level == BLOCKED]
        print("WORKSPACE EXEC BLOCKED", file=sys.stderr)
        for item in blocked:
            print(f"- {item.code}: {item.message}", file=sys.stderr)
        return 2
    if unit is None:
        print(f"WORKSPACE EXEC BLOCKED: unknown unit {args.unit}", file=sys.stderr)
        return 2
    environment = dict(os.environ)
    environment["HEK_UNIT"] = unit.unit_id
    environment["HEK_WORKSPACE"] = unit.workspace_id
    environment["HEK_SESSION_ROOT"] = str(unit.root)
    completed = subprocess.run(rest, cwd=str(unit.root), env=environment)
    return completed.returncode


STDIN_PATH_KEYS = ("file_path", "filePath", "path", "target", "notebook_path", "notebookPath")


def hook_target(payload: object) -> Path | None:
    """Extract the write target from a host-agent hook payload.

    Hook runtimes differ in shape, so the common spellings are accepted and the
    nested ``tool_input`` object is searched as well. No path means "cannot
    verify", which is reported as information rather than as a violation: a
    payload this process does not understand must not block every write.
    """
    if not isinstance(payload, dict):
        return None
    for key in STDIN_PATH_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value)
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in STDIN_PATH_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return Path(value)
    return None


def cmd_guard(args: argparse.Namespace) -> int:
    session_root = (
        args.session_root
        or os.environ.get("HEK_SESSION_ROOT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or Path.cwd()
    )
    target = args.path
    if getattr(args, "stdin", False):
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            payload = None
        target = hook_target(payload)
        if target is None:
            result = {
                "schema_version": 1,
                "kind": "workspace-guard",
                "session_root": str(session_root),
                "status": "pass",
                "diagnostics": [
                    {
                        "level": "info",
                        "code": "harness.mismatch",
                        "message": "hook payload carried no recognizable target path; nothing was verified",
                    }
                ],
            }
            if args.as_json:
                _print_json(result)
            else:
                print("WORKSPACE GUARD PASS (no target in hook payload)")
            return 0
    if target is None:
        raise UsageError("workspace guard requires --path <path> or --stdin")
    diagnostics = run_guard(target, session_root)
    payload = {
        "schema_version": 1,
        "kind": "workspace-guard",
        "path": str(target),
        "session_root": str(session_root),
        "status": "blocked" if has_blocked(diagnostics) else "pass",
        "diagnostics": [item.as_dict() for item in diagnostics],
    }
    if args.as_json:
        _print_json(payload)
    else:
        print("WORKSPACE GUARD " + payload["status"].upper())
        _print_diagnostics(diagnostics)
    return 2 if has_blocked(diagnostics) else 0


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compat_entry(consumer, contract: str, projection) -> tuple[dict, list[dict[str, str]]]:
    """Evidence for one consumed contract, including the declared version range."""
    entry = next((item for item in consumer.consumes if item["contract"] == contract), None)
    findings: list[dict[str, str]] = []
    if entry is None:
        findings.append(
            {
                "level": "blocked",
                "code": "contract.orphan",
                "message": f"{contract} is not consumed by {consumer.unit_id}",
            }
        )
    provider = next((item for item in projection.contracts if item["contract"] == contract), None)
    snapshot_rel = (entry or {}).get("snapshot")
    snapshot_path = consumer.root / snapshot_rel if snapshot_rel else None
    snapshot_digest = _sha256(snapshot_path) if snapshot_path else None
    provider_digest = None
    published = provider["version"] if provider else None
    declared = str((entry or {}).get("version", ""))
    if provider is not None:
        provider_unit = next(unit for unit in projection.units if unit.unit_id == provider["provider"])
        provider_digest = _sha256(provider_unit.root / str(provider["artifact"]))
    if snapshot_digest and provider_digest and snapshot_digest != provider_digest:
        findings.append(
            {
                "level": "blocked",
                "code": "contract.compat",
                "message": f"{contract} artifact differs from the consumer snapshot",
            }
        )
    # Invariant I13: the version the consumer declares it accepts must actually
    # accept the version the provider published. Comparing bytes alone would let
    # a consumer pass CI while its declared range excludes the provider release.
    if provider is not None and published is not None and declared:
        satisfied = version_satisfies(str(published), declared)
        if satisfied is False:
            findings.append(
                {
                    "level": "blocked",
                    "code": "contract.version",
                    "message": (
                        f"{contract}: declared range {declared} does not accept the published "
                        f"version {published}"
                    ),
                }
            )
        elif satisfied is None:
            findings.append(
                {
                    "level": "warning",
                    "code": "contract.version",
                    "message": f"{contract}: declared range {declared} is not decidable locally",
                }
            )
    if provider is None:
        findings.append(
            {
                "level": "warning",
                "code": "contract.orphan",
                "message": f"{contract} has no visible provider; compat cannot be verified locally",
            }
        )
    return {
        "unit_id": consumer.unit_id,
        "contract": contract,
        "provider": provider["provider"] if provider else None,
        "provider_version": published,
        "declared_version": declared or None,
        "artifact": provider["artifact"] if provider else None,
        "artifact_sha256": provider_digest,
        "snapshot": snapshot_rel,
        "snapshot_sha256": snapshot_digest,
        "verdict": "fail" if any(item["level"] == BLOCKED for item in findings) else "pass",
        "findings": findings,
    }, findings


def cmd_compat(args: argparse.Namespace) -> int:
    if not args.contract and not args.all_contracts:
        raise UsageError("workspace compat requires --contract <id> or --all")
    roots = _roots(args.root)
    projection = discover(roots, args.depth)
    cwd = Path.cwd().resolve()
    consumer = next(
        (unit for unit in projection.units if unit.root == cwd or cwd.is_relative_to(unit.root)),
        None,
    )
    if consumer is None:
        harness = locate_harness_root(cwd)
        consumer = next((unit for unit in projection.units if unit.root == harness), None)
    if consumer is None:
        print("WORKSPACE COMPAT BLOCKED: current directory is not a workspace unit", file=sys.stderr)
        return 2

    contracts = [args.contract] if args.contract else [str(item["contract"]) for item in consumer.consumes]
    if not contracts:
        print("WORKSPACE COMPAT BLOCKED: this unit consumes no contract", file=sys.stderr)
        return 2
    evidence = []
    failed = False
    for contract in contracts:
        entry, findings = _compat_entry(consumer, contract, projection)
        evidence.append(entry)
        failed = failed or entry["verdict"] == "fail"

    payload = {
        "schema_version": 1,
        "kind": "workspace-compat-evidence",
        "unit_id": consumer.unit_id,
        "verdict": "fail" if failed else "pass",
        "contracts": evidence,
    }
    evidence_dir = consumer.root / ".hek/state"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for entry in evidence:
        (evidence_dir / f"compat-{entry['contract']}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": "workspace-compat-evidence",
                    **{key: value for key, value in entry.items()},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.as_json:
        _print_json(payload)
    else:
        print(f"WORKSPACE COMPAT {'FAIL' if failed else 'PASS'}: {consumer.unit_id}")
        for entry in evidence:
            print(f"  - {entry['contract']}: {entry['verdict']}")
            for finding in entry["findings"]:
                print(f"      {finding['level']}: {finding['code']}: {finding['message']}")
    return 2 if failed else 0


def cmd_graph(args: argparse.Namespace) -> int:
    projection = discover(_roots(args.root), args.depth)
    adjacency = graph(projection)
    if args.as_json:
        _print_json(adjacency)
    else:
        for unit_id, providers in adjacency.items():
            print(f"{unit_id} -> {', '.join(providers) if providers else '(none)'}")
    return 2 if has_blocked(projection.diagnostics) else 0


def _policy_command(unit_root: Path, name: str) -> str | None:
    path = unit_root / ".hek/project/agent-policy.yaml"
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    import re

    section = re.search(r"^commands:\s*$([\s\S]*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*$|\Z)", content, re.MULTILINE)
    if not section:
        return None
    match = re.search(rf"^[ \t]+{re.escape(name)}:\s*(.+?)\s*$", section.group(1), re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip("'\"")


def cmd_run(args: argparse.Namespace) -> int:
    if not args.unit or not args.stage:
        raise UsageError("usage: workspace run <unit>|all <fast_test|test|build|fitness>")
    projection = discover(_roots(args.root), args.depth)
    if has_blocked(projection.diagnostics):
        print("WORKSPACE RUN BLOCKED: nested or cross-repository structures cannot run aggregated", file=sys.stderr)
        return 2
    targets = projection.units if args.unit == "all" else [unit for unit in projection.units if unit.unit_id == args.unit]
    if not targets:
        print(f"WORKSPACE RUN BLOCKED: unknown unit {args.unit}", file=sys.stderr)
        return 2
    failures = 0
    for unit in targets:
        command = _policy_command(unit.root, args.stage)
        if not command:
            print(f"[{unit.unit_id}] no {args.stage} command declared")
            failures += 1
            continue
        print(f"[{unit.unit_id}] {command}")
        completed = subprocess.run(command, cwd=str(unit.root), shell=True)
        if completed.returncode:
            failures += 1
    return 2 if failures else 0


def cmd_pin(args: argparse.Namespace) -> int:
    roots = _roots(args.root)
    projection = discover(roots, args.depth)
    versions = sorted({unit.kit_version for unit in projection.units if unit.kit_version})
    if len(versions) > 1:
        print(f"WORKSPACE PIN BLOCKED: .hek/VERSION differs: {', '.join(versions)}", file=sys.stderr)
        return 2
    requested = args.version or (versions[0] if versions else None)
    payload = {
        "schema_version": 1,
        "kind": "workspace-kit-pin",
        "version": requested,
        "units": [{"unit_id": unit.unit_id, "kit_version": unit.kit_version} for unit in projection.units],
    }
    harness = locate_harness_root(Path.cwd())
    if harness is not None:
        state = harness / ".hek/state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "kit-pin.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.as_json:
        _print_json(payload)
    else:
        print(f"WORKSPACE PIN OK: {requested}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Scale-out report: which unit is not onboarded, which consumer lags."""
    roots = _roots(args.root)
    projection = discover(roots, args.depth)
    contracts = {item["contract"]: item for item in projection.contracts}

    not_onboarded = [
        {"unit_id": item.unit_id, "code": item.code, "message": item.message}
        for item in projection.diagnostics
        if item.code in {"identity.missing", "unit.no-harness", "identity.schema", "identity.untracked"}
    ]
    units = [
        {
            "unit_id": unit.unit_id,
            "kit_version": unit.kit_version,
            "harness_root": unit.harness_rel,
            "identity_tracked": unit.tracked,
            "unit_kind": unit.unit_kind,
        }
        for unit in projection.units
    ]
    consumers: list[dict[str, object]] = []
    for unit in projection.units:
        for consume in unit.consumes:
            contract = str(consume["contract"])
            provider = contracts.get(contract)
            declared = str(consume.get("version", ""))
            actual = provider["version"] if provider else None
            if provider is None:
                state, reason = "unresolved", "provider is not visible in this checkout"
            elif actual is None:
                state, reason = "unknown", "provider version source is not readable"
            else:
                satisfied = version_satisfies(str(actual), declared)
                if satisfied is True:
                    state, reason = "ok", "declared range accepts the published version"
                elif satisfied is False:
                    state, reason = "behind", "declared range does not accept the published version"
                else:
                    state, reason = "unknown", "range is not decidable locally"
            consumers.append(
                {
                    "unit_id": unit.unit_id,
                    "contract": contract,
                    "provider": provider["provider"] if provider else None,
                    "declared": declared,
                    "published": actual,
                    "state": state,
                    "reason": reason,
                }
            )

    payload = {
        "schema_version": 1,
        "kind": "workspace-status",
        "workspace_id": projection.workspace_id,
        "digest": projection.digest,
        "status": "blocked" if has_blocked(projection.diagnostics) else "pass",
        "units": units,
        "not_onboarded": not_onboarded,
        "consumers": consumers,
        "diagnostics": [item.as_dict() for item in projection.diagnostics],
    }
    if args.as_json:
        _print_json(payload)
    else:
        print(f"WORKSPACE STATUS {payload['status'].upper()}: {projection.workspace_id or '(none)'}")
        print(f"Units: {len(units)}")
        for unit in units:
            print(f"  - {unit['unit_id']} kit={unit['kit_version']} harness={unit['harness_root'] or '-'}")
        if not_onboarded:
            print(f"Not onboarded: {len(not_onboarded)}")
            for item in not_onboarded:
                print(f"  - {item['code']}: {item['message']}")
        lagging = [item for item in consumers if item["state"] != "ok"]
        print(f"Consumers: {len(consumers)} ({len(lagging)} needing attention)")
        for item in lagging:
            print(
                f"  - {item['unit_id']} {item['contract']}: {item['state']} "
                f"(declared {item['declared']}, published {item['published']})"
            )
    return 2 if has_blocked(projection.diagnostics) else 0


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------


def _common(parser: argparse.ArgumentParser, *, depth: bool = True) -> None:
    parser.add_argument("--root", action="append", type=Path, default=[], help="Workspace root; repeatable")
    if depth:
        parser.add_argument("--depth", type=int, default=1, help="Directory levels below each root to scan")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Machine-readable output")


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hek workspace", description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    discover_parser = subparsers.add_parser("discover", help="Aggregate the workspace projection")
    _common(discover_parser)
    discover_parser.add_argument("--refresh", action="store_true", help="Force a cache rebuild")
    discover_parser.set_defaults(handler=cmd_discover)

    verify_parser = subparsers.add_parser("verify", help="Validate the federation invariants")
    _common(verify_parser)
    verify_parser.set_defaults(handler=cmd_verify)

    context_parser = subparsers.add_parser("context", help="Resolve the context for a target path")
    context_parser.add_argument("path", help="Task path")
    context_parser.add_argument("--keyword", action="append", default=[], help="Exact read_when keyword")
    context_parser.add_argument("--json", action="store_true", dest="as_json")
    context_parser.set_defaults(handler=cmd_context)

    exec_parser = subparsers.add_parser("exec", help="Run a command inside a unit")
    _common(exec_parser)
    exec_parser.add_argument("unit")
    exec_parser.add_argument("rest", nargs=argparse.REMAINDER)
    exec_parser.set_defaults(handler=cmd_exec)

    guard_parser = subparsers.add_parser("guard", help="Pre-write boundary guard")
    guard_parser.add_argument("--path", type=Path)
    guard_parser.add_argument("--session-root", type=Path)
    guard_parser.add_argument("--stdin", action="store_true", help="Read the host-agent hook payload from stdin")
    guard_parser.add_argument("--json", action="store_true", dest="as_json")
    guard_parser.set_defaults(handler=cmd_guard)

    compat_parser = subparsers.add_parser("compat", help="Consumer-side contract compatibility")
    _common(compat_parser)
    compat_parser.add_argument("--contract", help="One consumed contract id; repeat the command for others")
    compat_parser.add_argument("--all", action="store_true", dest="all_contracts", help="Check every consumed contract")
    compat_parser.set_defaults(handler=cmd_compat)

    graph_parser = subparsers.add_parser("graph", help="Print the contract graph")
    _common(graph_parser)
    graph_parser.set_defaults(handler=cmd_graph)

    run_parser = subparsers.add_parser("run", help="Aggregated checkout-local command run")
    _common(run_parser)
    run_parser.add_argument("unit", help="A unit id or 'all'")
    run_parser.add_argument("stage", choices=("fast_test", "test", "build", "fitness"))
    run_parser.set_defaults(handler=cmd_run)

    pin_parser = subparsers.add_parser("pin", help="Record and verify the kit version pin")
    _common(pin_parser)
    pin_parser.add_argument("--version")
    pin_parser.set_defaults(handler=cmd_pin)

    status_parser = subparsers.add_parser("status", help="Report onboarding and consumer-version lag")
    _common(status_parser)
    status_parser.set_defaults(handler=cmd_status)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    try:
        parsed = _parse(arguments)
    except SystemExit as exc:  # argparse already printed usage
        return int(exc.code or 2)
    if not getattr(parsed, "handler", None):
        print("usage: hek workspace <discover|verify|context|exec|guard|compat|graph|run|pin|status>", file=sys.stderr)
        return 2
    try:
        return parsed.handler(parsed)
    except UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"WORKSPACE COMMAND FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
