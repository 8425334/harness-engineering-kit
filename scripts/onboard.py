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
from functools import cmp_to_key
from pathlib import Path

try:
    from .versioning import classify_versions, compare_versions, parse_version, read_version
except ImportError:
    from versioning import classify_versions, compare_versions, parse_version, read_version


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
    "docs/sdd",
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

JAVA_SCANNER = "templates/fitness/JavaParameterScanner.java.template"

# Kit-development scripts that must not be installed into target projects:
# they validate the kit's own checkout and would fail in the installed layout.
KIT_DEV_ONLY_SCRIPTS = frozenset({"smoke_test_skills.py"})
RELEASE_MIGRATIONS = "migrations/releases.json"


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
    legacy = any((root / marker).exists() for marker in LEGACY_MARKERS)
    if legacy:
        return "legacy"
    canonical = (
        (root / "docs/methodology/VERSION").is_file()
        and (root / "docs/methodology/agent-policy.yaml").is_file()
        and (root / ".agents/skills/engineering/SKILL.md").is_file()
    )
    if canonical:
        return "current"
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
        if relative.name in KIT_DEV_ONLY_SCRIPTS:
            continue
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
        )
    )
    version_file = source / "VERSION"
    if version_file.is_file():
        actions.append(Action("sync", "VERSION", "docs/methodology/VERSION", "installed methodology version"))

    # agent-policy.yaml references the production policy at every tier, so the
    # production control scaffold must be installed at every tier as well.
    for relative in sorted((source / "templates/production").glob("*.template")):
        target = {
            "README.md.template": "docs/methodology/production/README.md",
            "policy.yaml.template": "docs/methodology/production/policy.yaml",
            "change-record.json.template": "docs/methodology/production/change-record.template.json",
        }.get(relative.name)
        if target:
            actions.append(Action("create", str(relative.relative_to(source)), target, "production control"))

    if tier >= 2:
        for relative in sorted((source / "templates/fitness").glob("*.py.template")):
            actions.append(Action("create", str(relative.relative_to(source)), f"docs/fitness/scripts/{relative.stem}", "optional Fitness control"))
        actions.append(Action("create", JAVA_SCANNER, "docs/fitness/scripts/JavaParameterScanner.java", "Java Fitness scanner"))
        actions.append(Action("create-empty", None, "docs/fitness/verification-ledger.md", "Fitness verification ledger"))
        fitness_readme = source / "templates/fitness/README.md"
        if fitness_readme.is_file():
            actions.append(Action("create", str(fitness_readme.relative_to(source)), "docs/fitness/README.md", "optional Fitness control"))
        for relative in sorted((source / "templates/fitness/rules").glob("*.md.template")):
            actions.append(Action("create", str(relative.relative_to(source)), f"docs/fitness/{relative.stem}", "optional Fitness rule"))
        lessons_readme = source / "templates/lessons/README.md.template"
        if lessons_readme.is_file():
            actions.append(Action("create", str(lessons_readme.relative_to(source)), "docs/methodology/lessons/README.md", "lesson memory"))

    for platform in (".claude/skills", ".agents/skills"):
        actions.append(Action("sync-tree", "templates/engineering", f"{platform}/engineering", "project-local Skill discovery"))

    if status == "legacy":
        actions.append(Action("report", None, "legacy architecture", "preserve legacy files; route future work to engineering Skill"))
    if (root / "docs/sdd").exists():
        actions.append(Action("report", None, "docs/sdd", "legacy SDD workspace requires manual migration to openspec/changes; no files are deleted automatically"))
    return actions


def release_migrations(
    source: Path,
    installed_version: str | None,
    target_version: str | None,
    version_relation: str,
) -> list[dict[str, object]]:
    if version_relation != "upgrade" or not installed_version or not target_version:
        return []
    manifest = source / RELEASE_MIGRATIONS
    if not manifest.is_file() or not target_version:
        return []
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("releases"), list):
        return []
    try:
        installed = parse_version(installed_version)
        target = parse_version(target_version)
    except ValueError:
        return []
    selected: list[dict[str, object]] = []
    for release in payload["releases"]:
        if not isinstance(release, dict) or not isinstance(release.get("version"), str):
            continue
        try:
            release_version = parse_version(release["version"])
        except ValueError:
            continue
        if compare_versions(installed, release_version) < 0 and compare_versions(release_version, target) <= 0:
            selected.append(release)
    selected.sort(
        key=cmp_to_key(
            lambda left, right: compare_versions(
                parse_version(str(left["version"])),
                parse_version(str(right["version"])),
            )
        )
    )
    return selected


def validate_release_manifest(source: Path) -> list[str]:
    manifest = source / RELEASE_MIGRATIONS
    if not manifest.is_file():
        return [f"missing required source asset: {RELEASE_MIGRATIONS}"]
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [f"invalid release migration manifest: {RELEASE_MIGRATIONS}"]
    releases = payload.get("releases") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(releases, list):
        return [f"invalid release migration manifest: {RELEASE_MIGRATIONS}"]
    errors: list[str] = []
    seen_versions = []
    for release in releases:
        if not isinstance(release, dict) or not isinstance(release.get("version"), str):
            errors.append(f"invalid release migration entry: {RELEASE_MIGRATIONS}")
            continue
        version = release["version"]
        try:
            parsed = parse_version(version)
        except ValueError:
            errors.append(f"invalid release version: {version}")
            continue
        if any(compare_versions(parsed, previous) == 0 for previous in seen_versions):
            errors.append(f"duplicate release version: {version}")
            continue
        seen_versions.append(parsed)
    return errors


def render_plan(
    root: Path,
    source: Path,
    tier: int,
    status: str,
    actions: list[Action],
    installed_version: str | None = None,
    target_version: str | None = None,
) -> dict[str, object]:
    legacy_markers = [marker for marker in LEGACY_MARKERS if (root / marker).exists()]
    installed_version = installed_version if installed_version is not None else read_version(root / "docs/methodology/VERSION")
    target_version = target_version if target_version is not None else read_version(source / "VERSION")
    version_relation = classify_versions(installed_version, target_version)
    if installed_version is None and status != "fresh":
        version_relation = "unversioned"
    return {
        "schema_version": 1,
        "status": status,
        "project_root": str(root),
        "source_root": str(source),
        "source_version": target_version or "unknown",
        "installed_version": installed_version or "unknown",
        "version_relation": version_relation,
        "version_transition": {
            "from": installed_version,
            "to": target_version,
            "relation": version_relation,
        },
        "migration_manifest_errors": validate_release_manifest(source),
        "release_migrations": release_migrations(source, installed_version, target_version, version_relation),
        "tier": tier,
        "read_only": True,
        "legacy_files_preserved": True,
        "legacy_markers": legacy_markers,
        "actions": [action.__dict__ for action in actions],
    }


def copy_file(source: Path, target: Path, overwrite: bool) -> str:
    existed = target.is_file()
    if existed and not overwrite:
        return "preserved"
    if existed and sha256(source) == sha256(target):
        return "unchanged"
    shutil.copy2(source, target)
    return "updated" if existed else "created"


def validate_action_sources(source: Path, actions: list[Action]) -> list[str]:
    errors: list[str] = []
    for directory in ("core", "scripts", "templates/engineering", "templates/workflow"):
        if not (source / directory).is_dir():
            errors.append(f"missing required source directory: {directory}")
    required = list(ROOT_FILES)
    required.append("VERSION")
    required.extend(path.relative_to(source).as_posix() for path in (source / "core").glob("*.md"))
    required.extend(
        path.relative_to(source).as_posix()
        for path in (source / "scripts").glob("*.py")
        if path.name not in KIT_DEV_ONLY_SCRIPTS
    )
    required.extend(path.relative_to(source).as_posix() for path in (source / "templates/workflow").glob("*.template"))
    required.extend(path.relative_to(source).as_posix() for path in (source / "templates/production").glob("*.template"))
    if any(action.target == "docs/fitness/README.md" for action in actions):
        required.extend(path.relative_to(source).as_posix() for path in (source / "templates/fitness").glob("*.py.template"))
        required.extend(path.relative_to(source).as_posix() for path in (source / "templates/fitness").glob("*.template"))
        required.extend(path.relative_to(source).as_posix() for path in (source / "templates/fitness/rules").glob("*.md.template"))
        required.append("templates/lessons/README.md.template")
    for relative in sorted(set(required)):
        if not (source / relative).is_file():
            errors.append(f"missing required source asset: {relative}")
    errors.extend(validate_release_manifest(source))
    for action in actions:
        if action.kind == "sync-tree":
            if not (source / "templates/engineering").is_dir():
                errors.append("missing source directory: templates/engineering")
        elif action.source and not (source / action.source).is_file():
            errors.append(f"missing source file: {action.source}")
    return errors


def apply_actions(root: Path, source: Path, actions: list[Action]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    snapshots: dict[Path, tuple[bytes, int]] = {}
    created_files: list[Path] = []
    created_dirs: list[Path] = []

    def ensure_dir(directory: Path) -> None:
        missing: list[Path] = []
        current = directory
        while not current.exists():
            missing.append(current)
            if current.parent == current:
                break
            current = current.parent
        directory.mkdir(parents=True, exist_ok=True)
        # Record ancestors shallowest-first so rollback removes deepest-first.
        created_dirs.extend(reversed(missing))

    def snapshot(target: Path) -> None:
        if target in snapshots:
            return
        if target.is_file():
            snapshots[target] = (target.read_bytes(), target.stat().st_mode)
        elif not target.exists():
            created_files.append(target)

    try:
        for action in actions:
            if action.kind == "preserve" or action.kind == "report":
                results.append({"target": action.target, "result": action.kind})
                continue
            if action.kind == "mkdir":
                ensure_dir(root / action.target)
                results.append({"target": action.target, "result": "ready"})
                continue
            if action.kind == "create-empty":
                target = root / action.target
                if target.exists():
                    results.append({"target": action.target, "result": "preserved"})
                else:
                    ensure_dir(target.parent)
                    target.write_text("# Fitness Verification Ledger\n\n", encoding="utf-8")
                    created_files.append(target)
                    results.append({"target": action.target, "result": "created", "sha256": sha256(target)})
                continue
            if action.kind == "sync-tree":
                source_dir = source / "templates/engineering"
                target_dir = root / action.target
                existed = target_dir.is_dir()
                ensure_dir(target_dir)
                copied = 0
                changed = 0
                for item in source_dir.rglob("*"):
                    if item.is_file():
                        destination = target_dir / item.relative_to(source_dir)
                        ensure_dir(destination.parent)
                        snapshot(destination)
                        copied += 1
                        if not destination.exists() or sha256(item) != sha256(destination):
                            changed += 1
                        shutil.copy2(item, destination)
                result = "created" if not existed else ("unchanged" if changed == 0 else "updated")
                results.append({"target": action.target, "result": result, "files": copied})
                continue
            if not action.source:
                continue
            source_file = source / action.source
            target = root / action.target
            overwrite = action.kind == "sync"
            snapshot(target)
            ensure_dir(target.parent)
            result = copy_file(source_file, target, overwrite)
            results.append({"target": action.target, "result": result, "sha256": sha256(target)})
    except (OSError, shutil.Error):
        for target, (content, mode) in snapshots.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(mode)
        for target in reversed(created_files):
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
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


CHECK_SUMMARY = "Deterministic checks passed: root context, context docs, agent policy, profile, context resolution, fitness protection, engineering Skill (claude, codex)."


def print_apply_summary(plan: dict[str, object]) -> None:
    counts: dict[str, int] = {}
    for entry in plan.get("results") or []:  # type: ignore[union-attr]
        if isinstance(entry, dict):
            key = str(entry.get("result", "unknown"))
            counts[key] = counts.get(key, 0) + 1
    summary = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())) or "no actions"
    print(f"HARNESS ONBOARDING APPLIED: {summary}")
    print("Receipt: docs/methodology/onboarding.json")


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
    installed_version = read_version(root / "docs/methodology/VERSION")
    target_version = read_version(source / "VERSION")
    version_relation = classify_versions(installed_version, target_version)
    if installed_version is None and status != "fresh":
        version_relation = "unversioned"
    actions = source_actions(source, root, effective_tier, status)
    plan = render_plan(root, source, effective_tier, status, actions, installed_version, target_version)

    if args.apply and version_relation in {"downgrade", "invalid", "unknown-target", "unversioned"}:
        plan["errors"] = [f"unsupported version transition: {version_relation}"]
        if args.as_json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"HARNESS ONBOARDING BLOCKED: unsupported version transition: {version_relation}", file=sys.stderr)
        return 2

    if args.apply:
        source_errors = validate_action_sources(source, actions)
        if source_errors:
            if args.as_json:
                plan["errors"] = source_errors
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print("HARNESS ONBOARDING BLOCKED: source preflight failed", file=sys.stderr)
                for error in source_errors:
                    print(f"- {error}", file=sys.stderr)
            return 2
        plan["read_only"] = False
        plan["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        try:
            plan["results"] = apply_actions(root, source, actions)
        except (OSError, shutil.Error) as exc:
            plan["errors"] = [f"apply failed and rolled back: {exc}"]
            if args.as_json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print(f"HARNESS ONBOARDING FAILED AND ROLLED BACK: {exc}", file=sys.stderr)
            return 2
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
                if args.apply:
                    print_apply_summary(plan)
                print("ONBOARDING CHECK FAILED")
                for failure in failures:
                    print(f"- {failure}")
            return code
    if args.as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    elif args.apply:
        print_apply_summary(plan)
        if args.check:
            print("ONBOARDING CHECK PASSED")
            print(CHECK_SUMMARY)
    elif args.check:
        print(f"ONBOARDING CHECK PASSED: {root}")
        print(CHECK_SUMMARY)
    else:
        print(f"HARNESS ONBOARDING PLAN: {status} project at {root}")
        for action in actions:
            print(f"- {action.kind:9} {action.target} ({action.reason})")
        print("Read-only plan. Ask the user for confirmation, then rerun with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
