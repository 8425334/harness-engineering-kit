#!/usr/bin/env python3
"""Diagnose and self-repair a Harness installation and its runtime environment.

The engine covers the three failure classes an Agent can hit mid-conversation:

* the project-local ``engineering`` Skill is missing, stale, or undiscoverable;
* the Python runtime or the installed control scripts are unusable;
* the installed Harness control plane is incomplete or drifted from the Kit.

Diagnosis is read-only. ``--apply`` restores only canonical Kit resources,
never rewrites a project-owned fact that already exists, never installs an
interpreter or a package, and never writes outside the project root. When a
failure needs host-level action the engine reports the exact remedy instead of
guessing.
"""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from .onboard import (
        AGENT_TARGETS,
        OPENSPEC_SKILL_ROOTS,
        PROJECT_FACT_TARGETS,
        REQUIRED_OPENSPEC_SKILLS,
        SKILL_ROOTS,
        Action,
        agent_target,
        apply_actions,
        detect_status,
        load_receipt,
        project_root,
        sha256,
        source_actions,
    )
    from .versioning import classify_versions, read_version
except ImportError:  # pragma: no cover - direct script execution
    from onboard import (
        AGENT_TARGETS,
        OPENSPEC_SKILL_ROOTS,
        PROJECT_FACT_TARGETS,
        REQUIRED_OPENSPEC_SKILLS,
        SKILL_ROOTS,
        Action,
        agent_target,
        apply_actions,
        detect_status,
        load_receipt,
        project_root,
        sha256,
        source_actions,
    )
    from versioning import classify_versions, read_version


REPAIR_RECEIPT = "docs/methodology/repair.json"
PLATFORMS = ("claude", "codex", "opencode", "cursor", "gemini", "trae")
# Read-only observation targets: Harness installs the Skill project-locally, but
# a stale user-level duplicate can shadow it inside an Agent that also scans the
# user root. Repair never writes there.
USER_SKILL_ROOTS = {
    "claude": Path.home() / ".claude/skills",
    "codex": Path.home() / ".codex/skills",
    "opencode": Path.home() / ".config/opencode/skills",
    "cursor": Path.home() / ".cursor/skills",
    "gemini": Path.home() / ".gemini/skills",
    "trae": Path.home() / ".trae/skills",
}
MIN_PYTHON = (3, 9)
MIN_NODE = 18
MAX_EXAMPLES = 12
BLOCKING_SEVERITIES = ("repairable", "manual")


# ---------------------------------------------------------------------------
# Small probes: environment, digests, and source discovery.
# ---------------------------------------------------------------------------

def _version_tuple(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def probe_python() -> dict[str, object]:
    candidates = [["python3"], ["python"], ["py", "-3"]] if os.name == "nt" else [["python3"], ["python"]]
    entrypoint: dict[str, object] | None = None
    for candidate in candidates:
        executable = shutil.which(candidate[0])
        if not executable:
            continue
        try:
            completed = subprocess.run(
                [executable, *candidate[1:], "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        version = _version_tuple(f"{completed.stdout}\n{completed.stderr}")
        if version and version >= MIN_PYTHON:
            entrypoint = {
                "command": " ".join(candidate),
                "path": executable,
                "version": ".".join(str(part) for part in version),
            }
            break
    running = ".".join(str(part) for part in sys.version_info[:3])
    return {
        "command": entrypoint["command"] if entrypoint else None,
        "path": entrypoint["path"] if entrypoint else None,
        "version": entrypoint["version"] if entrypoint else None,
        "running_executable": sys.executable,
        "running_version": running,
        "minimum": ".".join(str(part) for part in MIN_PYTHON),
        "ok": entrypoint is not None and sys.version_info >= MIN_PYTHON,
    }


def probe_node() -> dict[str, object]:
    executable = shutil.which("node")
    if not executable:
        return {"command": None, "version": None, "minimum": str(MIN_NODE), "ok": False}
    try:
        completed = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
    except OSError:
        return {"command": "node", "version": None, "minimum": str(MIN_NODE), "ok": False}
    version = _version_tuple(completed.stdout or completed.stderr)
    return {
        "command": "node",
        "version": ".".join(str(part) for part in version) if version else None,
        "minimum": str(MIN_NODE),
        "ok": bool(version and version[0] >= MIN_NODE),
    }


def probe_openspec() -> dict[str, object]:
    executable = shutil.which("openspec")
    if not executable:
        return {"command": None, "version": None, "ok": False}
    try:
        completed = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
    except OSError:
        return {"command": "openspec", "version": None, "ok": False}
    version = _version_tuple(completed.stdout or completed.stderr)
    return {
        "command": "openspec",
        "version": ".".join(str(part) for part in version) if version else None,
        "ok": completed.returncode == 0,
    }


def tree_digests(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        return {}
    return {
        item.relative_to(directory).as_posix(): sha256(item)
        for item in sorted(directory.rglob("*"))
        if item.is_file()
    }


def compiles(path: Path, cache_dir: Path) -> bool:
    try:
        py_compile.compile(
            str(path),
            cfile=str(cache_dir / f"{path.stem}.pyc"),
            doraise=True,
            optimize=0,
        )
    except (py_compile.PyCompileError, OSError, ValueError):
        return False
    return True


def looks_like_kit(candidate: Path) -> bool:
    return (
        (candidate / "VERSION").is_file()
        and (candidate / "scripts" / "onboard.py").is_file()
        and (candidate / "templates" / "engineering" / "SKILL.md").is_file()
    )


def resolve_source(explicit: Path | None, root: Path) -> tuple[Path | None, str | None]:
    candidate = explicit.expanduser() if explicit else None
    if candidate is None:
        receipt = load_receipt(root) or {}
        recorded = receipt.get("source_root")
        if isinstance(recorded, str) and recorded.strip():
            candidate = Path(recorded).expanduser()
    if candidate is None:
        return None, (
            "Harness kit source not found. Pass --source-root <kit checkout>; "
            "the engine never downloads or guesses a remote source."
        )
    resolved = candidate.resolve()
    if not looks_like_kit(resolved):
        return None, f"Not a Harness kit checkout: {resolved}"
    return resolved, None


def resolve_agent(root: Path, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    receipt = load_receipt(root) or {}
    recorded = receipt.get("agent")
    if isinstance(recorded, str) and recorded in AGENT_TARGETS:
        return recorded
    return None


def resolve_tier(root: Path, explicit: int | None) -> int:
    if explicit in (1, 2):
        return int(explicit)
    receipt = load_receipt(root) or {}
    recorded = receipt.get("tier")
    if recorded in (1, 2):
        return int(recorded)
    return 2


def scoped_platforms(root: Path, agent: str | None) -> tuple[str, ...]:
    """Platforms this run may write a Skill tree for.

    An explicit or receipt-recorded Agent is authoritative. Otherwise repair
    only refreshes Skill trees that already exist; it never invents six
    platform installs for a project whose Agent is unknown.
    """

    if agent is not None:
        platform = agent_target(agent)["skill_platform"]
        return (platform,) if platform else ()
    receipt = load_receipt(root) or {}
    recorded = receipt.get("agent")
    if isinstance(recorded, str) and recorded != "all" and recorded in AGENT_TARGETS:
        platform = agent_target(recorded)["skill_platform"]
        return (platform,) if platform else ()
    return tuple(platform for platform in PLATFORMS if (root / SKILL_ROOTS[platform] / "engineering").is_dir())


def platform_for_skill_target(target: str) -> str | None:
    for platform in PLATFORMS:
        if target == f"{SKILL_ROOTS[platform]}/engineering":
            return platform
    return None


def skill_state(root: Path, source: Path, target: str) -> str:
    return skill_tree_state(root / target, source)


def skill_tree_state(installed: Path, source: Path) -> str:
    if not (installed / "SKILL.md").is_file():
        return "missing"
    expected = tree_digests(source / "templates" / "engineering")
    actual = tree_digests(installed)
    return "ok" if all(actual.get(name) == digest for name, digest in expected.items()) else "stale"


# ---------------------------------------------------------------------------
# Diagnosis.
# ---------------------------------------------------------------------------

def record(
    groups: dict[str, dict[str, object]],
    identifier: str,
    area: str,
    severity: str,
    detail: str,
    remedy: str | None = None,
) -> None:
    entry = groups.get(identifier)
    if entry is None:
        entry = {
            "id": identifier,
            "area": area,
            "severity": severity,
            "detail": detail,
            "remedy": remedy,
            "count": 0,
            "examples": [],
        }
        groups[identifier] = entry
    entry["count"] = int(entry["count"]) + 1
    examples = entry["examples"]
    if isinstance(examples, list) and len(examples) < MAX_EXAMPLES:
        examples.append(detail)


def add_repair(repairs: dict[tuple[str, str], Action], action: Action) -> None:
    repairs.setdefault((action.kind, action.target), action)


def combined(target: str, count: int) -> str:
    return target if count <= 1 else f"{target} (+{count - 1} more)"


def diagnose(root: Path, source: Path, agent: str | None, tier: int) -> dict[str, object]:
    findings: dict[str, dict[str, object]] = {}
    repairs: dict[tuple[str, str], Action] = {}
    environment = {"python": probe_python(), "node": probe_node(), "openspec": probe_openspec()}

    python = environment["python"]
    if not python["ok"]:
        record(
            findings,
            "python-unusable",
            "python",
            "manual",
            f"no usable Python >= {python['minimum']} on PATH (running {python['running_version']} at {python['running_executable']})",
            remedy=(
                f"Install Python {python['minimum']}+ and make `python3` available, or set "
                "HARNESS_PYTHON to a working interpreter, then rerun `hek repair`."
            ),
        )
    if not environment["node"]["ok"]:
        record(
            findings,
            "node-unusable",
            "runtime",
            "informational",
            f"no Node.js >= {MIN_NODE} on PATH",
            remedy=f"Install Node.js {MIN_NODE}+ only if you need the `hek` CLI or the OpenSpec CLI.",
        )
    openspec = environment["openspec"]

    installed = (
        (root / "docs/methodology/VERSION").is_file()
        or (root / "docs/methodology/scripts").is_dir()
        or load_receipt(root) is not None
    )
    source_version = read_version(source / "VERSION")
    installed_version = read_version(root / "docs/methodology/VERSION")
    status = detect_status(root, agent)
    relation = classify_versions(installed_version, source_version)
    if installed_version is None and status != "fresh":
        relation = "unversioned"

    result: dict[str, object] = {
        "project_root": str(root),
        "source_root": str(source),
        "agent": agent or "all",
        "tier": tier,
        "detected_status": status,
        "installed_version": installed_version or "unknown",
        "source_version": source_version or "unknown",
        "version_relation": relation,
        "environment": environment,
        "blocked": relation == "downgrade",
    }

    if not installed:
        record(
            findings,
            "not-installed",
            "control-plane",
            "manual",
            "no Harness control plane detected in this project",
            remedy="Run `hek init` (or the onboarding playbook) to install Harness, then rerun `hek repair`.",
        )
        result["findings"] = ordered(findings)
        result["repairs"] = []
        return result

    if relation == "downgrade":
        record(
            findings,
            "version-downgrade",
            "version",
            "manual",
            f"installed {installed_version} is newer than kit {source_version}",
            remedy="Use the newer Kit checkout. Repair never downgrades an installation.",
        )
        result["findings"] = ordered(findings)
        result["repairs"] = []
        return result

    if relation == "invalid":
        record(
            findings,
            "version-invalid",
            "version",
            "repairable",
            f"docs/methodology/VERSION is not a semantic version: {installed_version!r}",
        )

    platforms = scoped_platforms(root, agent)
    if agent is None and not platforms and source_version:
        record(
            findings,
            "skill-scope-unknown",
            "skill",
            "informational",
            "no project-local engineering Skill found for any Agent platform",
            remedy="Pass --agent <claude|codex|opencode|cursor|gemini|trae-work> to select the Skill to restore.",
        )

    # docs/fitness/** is a protected control plane. Repair may only install its
    # canonical scaffold when no baseline exists; every later Fitness change
    # needs external human approval bound to the change digest.
    fitness_baseline = (root / "docs/fitness").is_dir()

    actions = source_actions(source, root, tier, status, agent)
    cache_dir = Path(tempfile.mkdtemp(prefix="hek-repair-compile-"))
    try:
        for action in actions:
            if action.kind == "sync":
                target = root / action.target
                source_file = source / str(action.source)
                if not target.is_file():
                    record(findings, "control-plane-missing", "control-plane", "repairable", action.target)
                    add_repair(repairs, action)
                elif not source_file.is_file() or sha256(source_file) != sha256(target):
                    record(findings, "control-plane-drift", "control-plane", "repairable", action.target)
                    add_repair(repairs, action)
                if (
                    action.target.startswith("docs/methodology/scripts/")
                    and action.target.endswith(".py")
                    and target.is_file()
                    and not compiles(target, cache_dir)
                ):
                    record(
                        findings,
                        "control-script-broken",
                        "python",
                        "repairable",
                        f"{action.target} fails to compile with {python['running_version']}",
                    )
                    add_repair(repairs, action)
            elif action.kind in ("create", "create-empty"):
                target = root / action.target
                if target.exists():
                    continue
                if action.target.startswith("docs/fitness/") and fitness_baseline:
                    record(
                        findings,
                        "fitness-change-requires-approval",
                        "fitness",
                        "manual",
                        action.target,
                        remedy=(
                            "docs/fitness/** is protected. Restore it only with external human approval "
                            "bound to the change digest; repair never rewrites an existing Fitness baseline."
                        ),
                    )
                    continue
                if action.kind == "create-empty":
                    record(findings, "fitness-ledger-missing", "control-plane", "repairable", action.target)
                elif action.target in PROJECT_FACT_TARGETS:
                    record(
                        findings,
                        "project-fact-missing",
                        "control-plane",
                        "repairable",
                        action.target,
                        remedy="The scaffold is restored with placeholders; fill real repository facts before the next check.",
                    )
                else:
                    record(findings, "tier-asset-missing", "control-plane", "repairable", action.target)
                add_repair(repairs, action)
            elif action.kind == "mkdir":
                if not (root / action.target).is_dir():
                    record(findings, "workspace-dir-missing", "control-plane", "repairable", action.target)
                    add_repair(repairs, action)
            elif action.kind == "sync-tree":
                platform = platform_for_skill_target(action.target)
                if platform is not None and platform not in platforms:
                    continue
                state = skill_state(root, source, action.target)
                if state == "missing":
                    record(findings, "skill-missing", "skill", "repairable", action.target)
                    add_repair(repairs, action)
                elif state == "stale":
                    record(findings, "skill-stale", "skill", "repairable", action.target)
                    add_repair(repairs, action)
            elif action.kind == "openspec-init":
                missing = missing_openspec_for(root, action.target)
                if not missing:
                    continue
                if openspec["ok"]:
                    record(findings, "openspec-skills-missing", "skill", "repairable", ", ".join(missing))
                    add_repair(repairs, action)
                else:
                    record(
                        findings,
                        "openspec-skills-missing",
                        "skill",
                        "manual",
                        ", ".join(missing),
                        remedy="Install the OpenSpec CLI (npm install -g openspec), then rerun `hek repair`.",
                    )
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)

    for platform in platforms:
        user_root = USER_SKILL_ROOTS.get(platform)
        if user_root is None or not (user_root / "engineering" / "SKILL.md").is_file():
            continue
        if skill_tree_state(user_root / "engineering", source) != "ok":
            record(
                findings,
                "skill-user-root-stale",
                "skill",
                "informational",
                f"{user_root}/engineering differs from the Kit source",
                remedy=(
                    "Harness installs the Skill project-locally. Remove or re-sync this user-level copy "
                    "(outside the project root) so a stale duplicate cannot shadow the current Skill."
                ),
            )

    result["findings"] = ordered(findings)
    result["repairs"] = [serialize(action) for action in repairs.values()]
    return result


def missing_openspec_for(root: Path, tools: str) -> list[str]:
    missing: list[str] = []
    for tool in tools.split(","):
        base = OPENSPEC_SKILL_ROOTS.get(tool)
        if not base:
            continue
        for skill in REQUIRED_OPENSPEC_SKILLS:
            if not (root / base / skill / "SKILL.md").is_file():
                missing.append(f"{base}/{skill}")
    return missing


def ordered(findings: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    severity_rank = {"repairable": 0, "manual": 1, "informational": 2}
    return sorted(
        findings.values(),
        key=lambda entry: (severity_rank.get(str(entry["severity"]), 9), str(entry["id"])),
    )


def serialize(action: Action) -> dict[str, object]:
    return {"kind": action.kind, "source": action.source, "target": action.target, "reason": action.reason}


def deserialize(payload: dict[str, object]) -> Action:
    return Action(
        kind=str(payload.get("kind")),
        source=str(payload["source"]) if payload.get("source") else None,
        target=str(payload.get("target")),
        reason=str(payload.get("reason") or "self-repair"),
    )


def apply_repairs(root: Path, source: Path, actions: list[Action]) -> list[dict[str, object]]:
    """Apply repairs one operation at a time so one failure cannot roll back all."""

    results: list[dict[str, object]] = []
    for action in actions:
        try:
            outcome = apply_actions(root, source, [action])
        except (OSError, shutil.Error) as exc:
            results.append(
                {"kind": action.kind, "target": action.target, "result": "failed", "error": str(exc)}
            )
            continue
        for entry in outcome:
            results.append({"kind": action.kind, **entry})
    return results


def blocking(findings: list[dict[str, object]]) -> bool:
    return any(str(finding.get("severity")) in BLOCKING_SEVERITIES for finding in findings)


def status_label(payload: dict[str, object], applied: bool) -> str:
    raw_findings = payload.get("findings")
    findings: list[dict[str, object]] = raw_findings if isinstance(raw_findings, list) else []
    if not findings:
        return "repaired" if applied else "healthy"
    if not blocking(findings):
        return "repaired-with-notes" if applied else "healthy-with-notes"
    if any(str(finding.get("severity")) == "repairable" for finding in findings):
        return "partially-repaired" if applied else "repairable"
    return "needs-attention"


def run(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    root = project_root(args.project_root)
    source, error = resolve_source(args.source_root, root)
    if error or source is None:
        return 2, {"schema_version": 1, "mode": "diagnose", "status": "error", "errors": [error]}
    agent = resolve_agent(root, args.agent)
    tier = resolve_tier(root, args.tier)
    payload = diagnose(root, source, agent, tier)
    payload["schema_version"] = 1
    payload["mode"] = "diagnose"
    payload["read_only"] = True
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    if not args.apply:
        payload["status"] = status_label(payload, applied=False)
        return (2 if blocking(payload["findings"]) else 0), payload

    if payload.get("blocked"):
        payload["mode"] = "apply"
        payload["status"] = "needs-attention"
        return 2, payload

    actions = [deserialize(entry) for entry in payload.get("repairs") or []]
    payload["mode"] = "apply"
    payload["read_only"] = False
    payload["results"] = apply_repairs(root, source, actions)
    if (root / "docs/methodology").is_dir():
        verification = diagnose(root, source, agent, tier)
        payload["verification"] = {
            "status": "passed" if not blocking(verification["findings"]) else "failed",
            "findings": verification["findings"],
        }
        payload["findings"] = verification["findings"]
    payload["status"] = status_label(payload, applied=True)
    if (root / "docs/methodology").is_dir():
        receipt = root / REPAIR_RECEIPT
        try:
            receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (OSError, UnicodeError):
            payload.setdefault("errors", []).append(f"could not write {REPAIR_RECEIPT}")  # type: ignore[union-attr]
    return (2 if blocking(payload["findings"]) else 0), payload


def print_summary(payload: dict[str, object]) -> None:
    environment = payload.get("environment")
    if isinstance(environment, dict):
        python = environment.get("python", {})
        node = environment.get("node", {})
        openspec = environment.get("openspec", {})
        print(
            "Environment: python={python} node={node} openspec={openspec}".format(
                python=(python or {}).get("version") or "missing",
                node=(node or {}).get("version") or "missing",
                openspec=(openspec or {}).get("version") or "missing",
            )
        )
    print(
        "HARNESS REPAIR: {status} | installed {installed} -> kit {source} ({relation})".format(
            status=payload.get("status"),
            installed=payload.get("installed_version"),
            source=payload.get("source_version"),
            relation=payload.get("version_relation"),
        )
    )
    findings = payload.get("findings") or []
    if isinstance(findings, list) and findings:
        print("Findings:")
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            examples = finding.get("examples") or []
            detail = combined(str(finding.get("detail")), int(finding.get("count") or 1))
            print(f"- [{finding.get('severity')}] {finding.get('id')}: {detail}")
            if finding.get("remedy"):
                print(f"  remedy: {finding['remedy']}")
            if isinstance(examples, list) and int(finding.get("count") or 1) > 1:
                for example in examples:
                    print(f"    - {example}")
    elif not payload.get("errors"):
        print("No findings. Harness is healthy.")
    for error in payload.get("errors") or []:
        print(f"- ERROR: {error}")
    results = payload.get("results")
    if isinstance(results, list) and results:
        print("Repair results:")
        for entry in results:
            if not isinstance(entry, dict):
                continue
            suffix = f" ({entry['error']})" if entry.get("error") else ""
            print(f"- {entry.get('kind')} {entry.get('target')}: {entry.get('result')}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--source-root", "--source", dest="source_root", type=Path, help="Harness kit checkout; defaults to the path recorded by onboarding")
    parser.add_argument("--agent", choices=tuple(AGENT_TARGETS), help="Agent whose project-local Skill is repaired; defaults to the onboarding receipt")
    parser.add_argument("--tier", type=int, choices=(1, 2), help="Canonical resource scope; defaults to the installed tier")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--diagnose", action="store_true", help="print the read-only repair plan (default)")
    mode.add_argument("--apply", action="store_true", help="apply the repair plan instead of printing it read-only")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    code, payload = run(args)
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_summary(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
