#!/usr/bin/env python3
"""Plan, apply, and verify Harness onboarding from an Agent conversation.

The command is intentionally read-only unless ``--apply`` is supplied.  This
lets an Agent inspect a project, present a concrete change list, obtain the
user's confirmation, and then perform an idempotent fresh install or upgrade.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT_FILES = {
    "templates/AGENTS.md.template": "AGENTS.md",
    "templates/CLAUDE.md.template": "CLAUDE.md",
    "templates/agent-policy.yaml.template": "docs/methodology/agent-policy.yaml",
    "templates/methodology-profile.yaml.template": "docs/methodology/profile.yaml",
    "templates/ai.json.template": "ai.json",
    "templates/path-document.md.template": "AI.md",
    "templates/openspec-config.yaml.template": "openspec/config.yaml",
    "templates/openspec-readme.md.template": "openspec/README.md",
}

LEGACY_MARKERS = (
    ".cursor/skills",
    ".codex/skills/ramer",
    ".codex/skills/fe-engineering",
    ".codex/skills/multi-agent",
    ".claude/skills/ramer",
    ".claude/skills/fe-engineering",
    ".claude/skills/multi-agent",
    "docs/methodology/core/ramer-agent.md",
    "docs/methodology/core/ramer-cycle.md",
)


@dataclass(frozen=True)
class Action:
    kind: str
    source: str | None
    target: str
    reason: str


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_root(value: Path | None) -> Path:
    if value:
        return value.resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd().resolve()


def detect_status(root: Path) -> str:
    canonical = (
        (root / "docs/methodology/VERSION").is_file()
        and (root / "docs/methodology/agent-policy.yaml").is_file()
        and (root / ".agents/skills/engineering/SKILL.md").is_file()
    )
    legacy = any((root / marker).exists() for marker in LEGACY_MARKERS)
    if canonical:
        return "current"
    if legacy:
        return "legacy"
    if any((root / target).exists() for target in ROOT_FILES.values()):
        return "partial"
    return "fresh"


def source_actions(source: Path, root: Path, tier: int, status: str) -> list[Action]:
    actions: list[Action] = []
    for relative, target in ROOT_FILES.items():
        destination = root / target
        if destination.is_file():
            actions.append(Action("preserve", relative, target, "existing project configuration"))
        else:
            actions.append(Action("create", relative, target, "required Harness entrypoint"))

    for relative in sorted((source / "core").glob("*.md")):
        actions.append(Action("sync", str(relative.relative_to(source)), f"docs/methodology/core/{relative.name}", "canonical methodology"))
    for relative in sorted((source / "scripts").glob("*.py")):
        actions.append(Action("sync", str(relative.relative_to(source)), f"docs/methodology/scripts/{relative.name}", "canonical control script"))
    for relative in sorted((source / "templates/workflow").glob("*.template")):
        actions.append(Action("sync", str(relative.relative_to(source)), f"docs/methodology/change-templates/{relative.name}", "change evidence template"))
    actions.extend(
        Action("mkdir", None, target, "Harness workspace directory")
        for target in (
            "docs/methodology/production/changes",
            "docs/methodology/production/audit",
            "docs/methodology/lessons",
            "openspec/changes",
            "openspec/specs",
            "docs/superpowers/plans",
            "docs/superpowers/specs",
        )
    )
    version_file = source / "VERSION"
    if version_file.is_file():
        actions.append(Action("sync", "VERSION", "docs/methodology/VERSION", "installed methodology version"))

    if tier >= 2:
        for relative in sorted((source / "templates/fitness").glob("*.py.template")):
            actions.append(Action("create", str(relative.relative_to(source)), f"docs/fitness/scripts/{relative.stem}", "optional Fitness control"))
        fitness_readme = source / "templates/fitness/README.md"
        if fitness_readme.is_file():
            actions.append(Action("create", str(fitness_readme.relative_to(source)), "docs/fitness/README.md", "optional Fitness control"))
        for relative in sorted((source / "templates/fitness/rules").glob("*.md.template")):
            actions.append(Action("create", str(relative.relative_to(source)), f"docs/fitness/{relative.stem}", "optional Fitness rule"))
        for relative in sorted((source / "templates/production").glob("*.template")):
            target = {
                "README.md.template": "docs/methodology/production/README.md",
                "policy.yaml.template": "docs/methodology/production/policy.yaml",
                "change-record.json.template": "docs/methodology/production/change-record.template.json",
            }.get(relative.name)
            if target:
                actions.append(Action("create", str(relative.relative_to(source)), target, "production control"))
        lessons_readme = source / "templates/lessons/README.md.template"
        if lessons_readme.is_file():
            actions.append(Action("create", str(lessons_readme.relative_to(source)), "docs/methodology/lessons/README.md", "lesson memory"))

    for platform in (".claude/skills", ".agents/skills"):
        actions.append(Action("sync-tree", "templates/engineering", f"{platform}/engineering", "project-local Skill discovery"))

    if status == "legacy":
        actions.append(Action("report", None, "legacy architecture", "preserve legacy files; route future work to engineering Skill"))
    return actions


def render_plan(root: Path, source: Path, tier: int, status: str, actions: list[Action]) -> dict[str, object]:
    legacy_markers = [marker for marker in LEGACY_MARKERS if (root / marker).exists()]
    return {
        "schema_version": 1,
        "status": status,
        "project_root": str(root),
        "source_root": str(source),
        "source_version": (source / "VERSION").read_text(encoding="utf-8").strip() if (source / "VERSION").is_file() else "unknown",
        "tier": tier,
        "read_only": True,
        "legacy_files_preserved": True,
        "legacy_markers": legacy_markers,
        "actions": [action.__dict__ for action in actions],
    }


def copy_file(source: Path, target: Path, overwrite: bool) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and not overwrite:
        return "preserved"
    shutil.copy2(source, target)
    return "updated" if target.exists() else "created"


def apply_actions(root: Path, source: Path, actions: list[Action]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for action in actions:
        if action.kind == "preserve" or action.kind == "report":
            results.append({"target": action.target, "result": action.kind})
            continue
        if action.kind == "mkdir":
            (root / action.target).mkdir(parents=True, exist_ok=True)
            results.append({"target": action.target, "result": "ready"})
            continue
        if action.kind == "sync-tree":
            source_dir = source / "templates/engineering"
            target_dir = root / action.target
            target_dir.mkdir(parents=True, exist_ok=True)
            for item in source_dir.rglob("*"):
                if item.is_file():
                    destination = target_dir / item.relative_to(source_dir)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, destination)
            results.append({"target": action.target, "result": "updated"})
            continue
        if not action.source:
            continue
        source_file = source / action.source
        target = root / action.target
        overwrite = action.kind == "sync"
        result = copy_file(source_file, target, overwrite)
        results.append({"target": action.target, "result": result, "sha256": sha256(target)})
    return results


def run_check(root: Path, source: Path) -> tuple[int, list[str]]:
    checks = [
        ("check_root_context.py", ["check_root_context.py", str(root)]),
        ("check_context_docs.py", ["check_context_docs.py", str(root)]),
        ("check_agent_policy.py", ["check_agent_policy.py", str(root / "docs/methodology/agent-policy.yaml")]),
        ("check_profile.py", ["check_profile.py", str(root / "docs/methodology/profile.yaml")]),
        ("resolve_context.py", ["resolve_context.py", "--root", str(root), "."]),
        ("check_fitness_protection.py", ["check_fitness_protection.py", "--root", str(root)]),
        ("verify_skill.py (claude)", ["verify_skill.py", "engineering", "--project-root", str(root), "--platform", "claude", "--source-root", str(source)]),
        ("verify_skill.py (codex)", ["verify_skill.py", "engineering", "--project-root", str(root), "--platform", "codex", "--source-root", str(source)]),
    ]
    failures: list[str] = []
    for name, command in checks:
        script = source / "scripts" / command[0]
        if not script.is_file():
            failures.append(f"{name}: source script missing")
            continue
        completed = subprocess.run([sys.executable, str(script), *command[1:]], cwd=root, text=True, capture_output=True)
        if completed.returncode:
            failures.append(f"{name}: {completed.stdout.strip() or completed.stderr.strip()}")
    return (2 if failures else 0), failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--source-root", "--source", dest="source_root", type=Path, help="Harness kit checkout; defaults to this script's repository")
    parser.add_argument("--tier", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--name", help=argparse.SUPPRESS)
    parser.add_argument("--stack", help=argparse.SUPPRESS)
    parser.add_argument("--plan", action="store_true", help="print a read-only plan (default)")
    parser.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--apply", action="store_true", help="apply the displayed plan after user confirmation")
    parser.add_argument("--check", action="store_true", help="run deterministic checks after onboarding")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    root = project_root(args.project_root)
    source = (args.source_root or Path(__file__).resolve().parents[1]).resolve()
    if not (source / "templates").is_dir() or not (source / "scripts").is_dir():
        print(f"HARNESS ONBOARDING ERROR: invalid kit source: {source}", file=sys.stderr)
        return 2
    if args.apply and not (root / ".git").exists():
        print(f"HARNESS ONBOARDING ERROR: target is not a Git repository: {root}", file=sys.stderr)
        return 2
    status = detect_status(root)
    effective_tier = min(args.tier, 2)
    actions = source_actions(source, root, effective_tier, status)
    plan = render_plan(root, source, effective_tier, status, actions)

    if args.apply:
        plan["read_only"] = False
        plan["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        plan["results"] = apply_actions(root, source, actions)
        (root / "docs/methodology").mkdir(parents=True, exist_ok=True)
        (root / "docs/methodology/onboarding.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.check:
        code, failures = run_check(root, source)
        plan["check"] = {"status": "passed" if not failures else "failed", "failures": failures}
        receipt = root / "docs/methodology/onboarding.json"
        if receipt.is_file():
            try:
                saved = json.loads(receipt.read_text(encoding="utf-8"))
                saved["check"] = plan["check"]
                receipt.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass
        if failures:
            if args.as_json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print("ONBOARDING CHECK FAILED")
                for failure in failures:
                    print(f"- {failure}")
            return code
    if args.as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"HARNESS ONBOARDING PLAN: {status} project at {root}")
        for action in actions:
            print(f"- {action.kind:9} {action.target} ({action.reason})")
        if args.apply:
            print("HARNESS ONBOARDING APPLIED")
        else:
            print("Read-only plan. Ask the user for confirmation, then rerun with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
