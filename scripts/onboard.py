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
import os
import shutil
import subprocess
import sys
import tempfile
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
    "templates/GEMINI.md.template": "GEMINI.md",
    "templates/agent-policy.yaml.template": "docs/methodology/agent-policy.yaml",
    "templates/methodology-profile.yaml.template": "docs/methodology/profile.yaml",
    "templates/ai.json.template": "ai.json",
    "templates/path-document.md.template": "AI.md",
    "templates/openspec-config.yaml.template": "openspec/config.yaml",
    "templates/openspec-readme.md.template": "openspec/README.md",
}

NATIVE_ROOT_FILES = {
    "templates/AGENTS.md.template": "AGENTS.md",
    "templates/CLAUDE.md.template": "CLAUDE.md",
    "templates/GEMINI.md.template": "GEMINI.md",
}

AGENT_TARGETS = {
    "claude": {"root_file": "CLAUDE.md", "skill_platform": "claude"},
    "codex": {"root_file": "AGENTS.md", "skill_platform": "codex"},
    "opencode": {"root_file": "AGENTS.md", "skill_platform": "opencode"},
    "cursor": {"root_file": "AGENTS.md", "skill_platform": "cursor"},
    "gemini": {"root_file": "GEMINI.md", "skill_platform": "gemini"},
    "workbuddy": {"root_file": "AGENTS.md", "skill_platform": None},
    "trae-work": {"root_file": "AGENTS.md", "skill_platform": "trae"},
}

SKILL_ROOTS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".opencode/skills",
    "cursor": ".cursor/skills",
    "gemini": ".gemini/skills",
    "trae": ".trae/skills",
}

OPENSPEC_TOOLS = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "cursor": "cursor",
    "gemini": "gemini",
    "trae-work": "trae",
}

OPENSPEC_SKILL_ROOTS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".opencode/skills",
    "cursor": ".cursor/skills",
    "gemini": ".gemini/skills",
    "trae": ".trae/skills",
}

REQUIRED_OPENSPEC_SKILLS = (
    "openspec-explore",
    "openspec-propose",
    "openspec-apply-change",
    "openspec-sync-specs",
    "openspec-archive-change",
    "openspec-update-change",
    "openspec-verify-change",
)

OPENSPEC_WORKFLOWS = ("propose", "explore", "apply", "update", "sync", "archive", "verify")

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

ONBOARDING_RECEIPT = "docs/methodology/onboarding.json"
UNINSTALL_RECEIPT = "docs/methodology/uninstall.json"

# Project-owned facts that an uninstall keeps when --keep-project-facts is set.
# They are the files onboarding fills from repository evidence and the user is
# most likely to want after the control plane is gone.
PROJECT_FACT_TARGETS = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "ai.json",
        "AI.md",
        "docs/methodology/agent-policy.yaml",
        "docs/methodology/profile.yaml",
        "openspec/config.yaml",
    }
)


@dataclass(frozen=True)
class Action:
    kind: str
    source: str | None
    target: str
    reason: str


@dataclass(frozen=True)
class Removal:
    kind: str
    target: str
    reason: str
    source: str | None = None
    expected_sha256: str | None = None
    expected_tree: dict[str, str] | None = None


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


def agent_target(agent: str | None) -> dict[str, str | None] | None:
    if agent is None:
        return None
    try:
        return AGENT_TARGETS[agent]
    except KeyError as exc:
        raise ValueError(f"unsupported agent: {agent}") from exc


def root_files_for(agent: str | None) -> dict[str, str]:
    if agent is None:
        return ROOT_FILES
    target = agent_target(agent)
    return {
        relative: destination
        for relative, destination in ROOT_FILES.items()
        if destination not in NATIVE_ROOT_FILES.values() or destination == target["root_file"]
    }


def skill_platforms_for(agent: str | None) -> tuple[str, ...]:
    if agent is None:
        return ("claude", "codex", "opencode", "cursor", "gemini", "trae")
    platform = agent_target(agent)["skill_platform"]
    return (platform,) if platform else ()


def openspec_tools_for(agent: str | None) -> tuple[str, ...]:
    if agent is None:
        return ("claude", "codex", "opencode", "cursor", "gemini", "trae")
    tool = OPENSPEC_TOOLS.get(agent)
    return (tool,) if tool else ()


def detect_status(root: Path, agent: str | None = None) -> str:
    legacy = any((root / marker).exists() for marker in LEGACY_MARKERS)
    if legacy:
        return "legacy"
    if agent is not None:
        target = agent_target(agent)
        root_ready = (root / str(target["root_file"])).is_file()
        skill_ready = not target["skill_platform"] or (
            root / SKILL_ROOTS[str(target["skill_platform"])] / "engineering/SKILL.md"
        ).is_file()
        canonical = (
            (root / "docs/methodology/VERSION").is_file()
            and (root / "docs/methodology/agent-policy.yaml").is_file()
            and root_ready
            and skill_ready
        )
        if canonical:
            return "current"
    if agent is None:
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


def source_actions(source: Path, root: Path, tier: int, status: str, agent: str | None = None) -> list[Action]:
    actions: list[Action] = []
    for relative, target in root_files_for(agent).items():
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
    for relative in sorted((source / "templates/openspec-schema").rglob("*")):
        if relative.is_file():
            target = Path("openspec/schemas/harness-engineering") / relative.relative_to(source / "templates/openspec-schema")
            actions.append(Action("sync", str(relative.relative_to(source)), target.as_posix(), "OpenSpec lifecycle schema"))
    for relative in sorted((source / "templates/compaction").glob("*")):
        if relative.is_file():
            target_name = relative.name.replace(".template", "")
            actions.append(Action("sync", str(relative.relative_to(source)), f"docs/methodology/compaction/{target_name}", "portable compaction recovery resource"))
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

    if tier >= 1:
        minimal_fitness = {"fitness.py.template", "check_sdd_quality.py.template"}
        for relative in sorted((source / "templates/fitness").glob("*.py.template")):
            if tier < 2 and relative.name not in minimal_fitness:
                continue
            actions.append(Action("create", str(relative.relative_to(source)), f"docs/fitness/scripts/{relative.stem}", "optional Fitness control"))
        sdd_rule = source / "templates/fitness/rules/sdd-quality.md.template"
        actions.append(Action("create", str(sdd_rule.relative_to(source)), "docs/fitness/sdd-quality.md", "required staged Fitness control"))
    if tier >= 2:
        actions.append(Action("create", JAVA_SCANNER, "docs/fitness/scripts/JavaParameterScanner.java", "Java Fitness scanner"))
        actions.append(Action("create-empty", None, "docs/fitness/verification-ledger.md", "Fitness verification ledger"))
        fitness_readme = source / "templates/fitness/README.md"
        if fitness_readme.is_file():
            actions.append(Action("create", str(fitness_readme.relative_to(source)), "docs/fitness/README.md", "optional Fitness control"))
        for relative in sorted((source / "templates/fitness/rules").glob("*.md.template")):
            if relative.name == "sdd-quality.md.template":
                continue
            actions.append(Action("create", str(relative.relative_to(source)), f"docs/fitness/{relative.stem}", "optional Fitness rule"))
        lessons_readme = source / "templates/lessons/README.md.template"
        if lessons_readme.is_file():
            actions.append(Action("create", str(lessons_readme.relative_to(source)), "docs/methodology/lessons/README.md", "lesson memory"))

    for platform in skill_platforms_for(agent):
        actions.append(Action("sync-tree", "templates/engineering", f"{SKILL_ROOTS[platform]}/engineering", "selected Agent Skill discovery"))
    tools = openspec_tools_for(agent)
    if tools:
        actions.append(Action("openspec-init", None, ",".join(tools), "generate native OpenSpec lifecycle Skills"))
    else:
        actions.append(Action("report", None, "OpenSpec native Skills", "selected Agent has no OpenSpec Skill adapter; use OpenSpec CLI operations directly"))

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
    agent: str | None = None,
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
        "agent": agent or "all",
        "native_root_file": agent_target(agent)["root_file"] if agent else "AGENTS.md + CLAUDE.md + GEMINI.md",
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


def ensure_safe_target(root: Path, target: Path) -> None:
    """Reject existing symlinks anywhere in a lexical installer target path."""
    root = Path(os.path.abspath(os.fspath(root)))
    target = Path(os.path.abspath(os.fspath(target)))
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise OSError(f"target escapes project root: {target}") from exc
    current = root
    for part in target.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise OSError(f"refusing to follow symlinked target path: {current}")


def validate_action_sources(source: Path, actions: list[Action], agent: str | None = None) -> list[str]:
    errors: list[str] = []
    for directory in ("core", "scripts", "templates/engineering", "templates/workflow", "templates/openspec-schema"):
        if not (source / directory).is_dir():
            errors.append(f"missing required source directory: {directory}")
    required = list(root_files_for(agent))
    required.append("VERSION")
    required.extend(path.relative_to(source).as_posix() for path in (source / "core").glob("*.md"))
    required.extend(
        path.relative_to(source).as_posix()
        for path in (source / "scripts").glob("*.py")
        if path.name not in KIT_DEV_ONLY_SCRIPTS
    )
    required.extend(path.relative_to(source).as_posix() for path in (source / "templates/workflow").glob("*.template"))
    required.extend(path.relative_to(source).as_posix() for path in (source / "templates/openspec-schema").rglob("*") if path.is_file())
    required.extend(path.relative_to(source).as_posix() for path in (source / "templates/compaction").glob("*"))
    required.extend(path.relative_to(source).as_posix() for path in (source / "templates/production").glob("*.template"))
    if any(action.target.startswith("docs/fitness/") for action in actions):
        required.extend(
            path.relative_to(source).as_posix()
            for path in (source / "templates/fitness").glob("*.py.template")
            if any(action.target == f"docs/fitness/scripts/{path.stem}" for action in actions)
        )
        required.append("templates/fitness/rules/sdd-quality.md.template")
    if any(action.target == "docs/fitness/README.md" for action in actions):
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
                target = root / action.target
                ensure_safe_target(root, target)
                ensure_dir(target)
                results.append({"target": action.target, "result": "ready"})
                continue
            if action.kind == "create-empty":
                target = root / action.target
                ensure_safe_target(root, target)
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
                ensure_safe_target(root, target_dir)
                existed = target_dir.is_dir()
                ensure_dir(target_dir)
                copied = 0
                changed = 0
                tree: dict[str, str] = {}
                for item in source_dir.rglob("*"):
                    if item.is_file():
                        destination = target_dir / item.relative_to(source_dir)
                        ensure_safe_target(root, destination)
                        ensure_dir(destination.parent)
                        snapshot(destination)
                        copied += 1
                        if not destination.exists() or sha256(item) != sha256(destination):
                            changed += 1
                        shutil.copy2(item, destination)
                        tree[item.relative_to(source_dir).as_posix()] = sha256(destination)
                result = "created" if not existed else ("unchanged" if changed == 0 else "updated")
                # Digest every installed file so a later uninstall can prove a
                # path is still the Kit's own content before deleting it.
                results.append({"target": action.target, "result": result, "files": copied, "tree": tree})
                continue
            if action.kind == "openspec-init":
                with tempfile.TemporaryDirectory(prefix="hek-openspec-home-") as isolated_home:
                    staging = Path(isolated_home) / "project"
                    environment = dict(os.environ)
                    environment["HOME"] = isolated_home
                    environment["USERPROFILE"] = isolated_home
                    environment["OPENSPEC_TELEMETRY"] = "0"
                    commands = (
                        ["openspec", "config", "set", "profile", "custom"],
                        ["openspec", "config", "set", "workflows", json.dumps(OPENSPEC_WORKFLOWS)],
                        ["openspec", "init", str(staging), "--tools", action.target, "--profile", "custom", "--no-animation"],
                    )
                    for command in commands:
                        completed = subprocess.run(command, text=True, capture_output=True, env=environment, check=False)
                        if completed.returncode:
                            raise OSError(completed.stderr.strip() or completed.stdout.strip() or "openspec init failed")
                    missing = [
                        f"{OPENSPEC_SKILL_ROOTS[tool]}/{skill}/SKILL.md"
                        for tool in action.target.split(",")
                        for skill in REQUIRED_OPENSPEC_SKILLS
                        if not (staging / OPENSPEC_SKILL_ROOTS[tool] / skill / "SKILL.md").is_file()
                    ]
                    if missing:
                        raise OSError("OpenSpec did not generate required Skills: " + ", ".join(missing))
                    copied = 0
                    changed = 0
                    directories: list[str] = []
                    trees: dict[str, dict[str, str]] = {}
                    for tool in action.target.split(","):
                        for skill in REQUIRED_OPENSPEC_SKILLS:
                            source_dir = staging / OPENSPEC_SKILL_ROOTS[tool] / skill
                            target_dir = root / OPENSPEC_SKILL_ROOTS[tool] / skill
                            ensure_safe_target(root, target_dir)
                            ensure_dir(target_dir)
                            directories.append(target_dir.relative_to(root).as_posix())
                            tree = trees.setdefault(target_dir.relative_to(root).as_posix(), {})
                            for item in source_dir.rglob("*"):
                                if not item.is_file():
                                    continue
                                destination = target_dir / item.relative_to(source_dir)
                                ensure_safe_target(root, destination)
                                ensure_dir(destination.parent)
                                snapshot(destination)
                                copied += 1
                                if not destination.exists() or sha256(item) != sha256(destination):
                                    changed += 1
                                shutil.copy2(item, destination)
                                tree[item.relative_to(source_dir).as_posix()] = sha256(destination)
                schema_check = subprocess.run(
                    ["openspec", "schema", "validate", "harness-engineering", "--json"],
                    cwd=root,
                    text=True,
                    capture_output=True,
                    env={**os.environ, "OPENSPEC_TELEMETRY": "0"},
                    check=False,
                )
                if schema_check.returncode:
                    raise OSError(schema_check.stderr.strip() or schema_check.stdout.strip() or "OpenSpec schema validation failed")
                try:
                    schema_payload = json.loads(schema_check.stdout)
                except json.JSONDecodeError as exc:
                    raise OSError("OpenSpec schema validation did not return JSON") from exc
                if schema_payload.get("valid") is not True:
                    raise OSError("OpenSpec harness-engineering schema is invalid")
                result = "unchanged" if changed == 0 else "generated"
                results.append(
                    {
                        "target": action.target,
                        "result": result,
                        "provider": "openspec",
                        "files": copied,
                        "directories": directories,
                        "trees": trees,
                    }
                )
                continue
            if not action.source:
                continue
            source_file = source / action.source
            target = root / action.target
            ensure_safe_target(root, target)
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


def load_receipt(root: Path) -> dict[str, object] | None:
    path = root / ONBOARDING_RECEIPT
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def receipt_entries(receipt: dict[str, object] | None) -> list[dict[str, object]]:
    if not isinstance(receipt, dict):
        return []
    entries = receipt.get("results")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def openspec_skill_directories(tools: str) -> list[str]:
    directories: list[str] = []
    for tool in tools.split(","):
        skill_root = OPENSPEC_SKILL_ROOTS.get(tool.strip())
        if not skill_root:
            continue
        directories.extend(f"{skill_root}/{skill}" for skill in REQUIRED_OPENSPEC_SKILLS)
    return directories


def source_tree_map(source: Path, relative: str) -> dict[str, str]:
    base = source / relative
    if not base.is_dir():
        return {}
    return {
        item.relative_to(base).as_posix(): sha256(item)
        for item in base.rglob("*")
        if item.is_file()
    }


def uninstall_removals(
    root: Path,
    source: Path,
    receipt: dict[str, object] | None,
    tier: int,
    agent: str | None,
    keep_project_facts: bool,
) -> list[Removal]:
    """Derive the removal plan from the install receipt, falling back to source facts.

    A path is only removed when the receipt proves Harness wrote it and, for
    regular files, its digest still matches the recorded install digest. Files
    the install preserved, and files edited after install, stay in place.
    """

    removals: list[Removal] = []
    seen: set[str] = set()

    def add(removal: Removal) -> None:
        if removal.target in seen:
            return
        if not (root / removal.target).exists():
            return
        seen.add(removal.target)
        removals.append(removal)

    entries = receipt_entries(receipt)
    if entries:
        for entry in entries:
            target = entry.get("target")
            result = entry.get("result")
            if not isinstance(target, str):
                continue
            if result in {"report", "preserved"}:
                continue
            if result == "ready":
                add(Removal("prune-dir", target, "Harness workspace directory"))
                continue
            if entry.get("provider") == "openspec":
                directories = entry.get("directories")
                if not isinstance(directories, list) or not directories:
                    directories = openspec_skill_directories(target)
                trees = entry.get("trees")
                trees = trees if isinstance(trees, dict) else {}
                for directory in directories:
                    if not isinstance(directory, str):
                        continue
                    expected = trees.get(directory)
                    add(
                        Removal(
                            "remove-tree",
                            directory,
                            "OpenSpec lifecycle Skill generated by Harness",
                            expected_tree=expected if isinstance(expected, dict) else None,
                        )
                    )
                continue
            if isinstance(entry.get("tree"), dict) or isinstance(entry.get("files"), int):
                expected = entry.get("tree")
                add(
                    Removal(
                        "remove-tree",
                        target,
                        "project-local Engineering Skill",
                        source="templates/engineering",
                        expected_tree=expected if isinstance(expected, dict) else None,
                    )
                )
                continue
            if isinstance(entry.get("sha256"), str):
                add(Removal("remove", target, "installed Harness control asset", expected_sha256=entry["sha256"]))
                continue
    else:
        # No receipt: infer from the current source and only delete files whose
        # bytes still match the Kit, which leaves filled project facts alone.
        for action in source_actions(source, root, tier, "fresh", agent):
            if action.kind == "report":
                continue
            if action.kind == "mkdir":
                add(Removal("prune-dir", action.target, action.reason))
            elif action.kind == "sync-tree":
                add(Removal("remove-tree", action.target, action.reason, source="templates/engineering"))
            elif action.kind == "openspec-init":
                for directory in openspec_skill_directories(action.target):
                    add(Removal("remove-tree", directory, "OpenSpec lifecycle Skill generated by Harness"))
            else:
                add(Removal("remove", action.target, action.reason, source=action.source))

    receipt_path = root / ONBOARDING_RECEIPT
    if receipt_path.is_file():
        add(Removal("remove", ONBOARDING_RECEIPT, "Harness onboarding receipt", expected_sha256=sha256(receipt_path)))

    if keep_project_facts:
        removals = [
            Removal("keep", removal.target, "project-owned fact kept by --keep-project-facts")
            if removal.target in PROJECT_FACT_TARGETS
            else removal
            for removal in removals
        ]
    return removals


def render_uninstall_plan(
    root: Path,
    source: Path,
    removals: list[Removal],
    receipt: dict[str, object] | None,
    tier: int,
    agent: str | None,
    keep_project_facts: bool,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "uninstall",
        "project_root": str(root),
        "source_root": str(source),
        "installed_version": read_version(root / "docs/methodology/VERSION") or "unknown",
        "source_version": read_version(source / "VERSION") or "unknown",
        "tier": tier,
        "agent": agent or "all",
        "keep_project_facts": keep_project_facts,
        "receipt_source": ONBOARDING_RECEIPT if receipt else "source-analysis",
        "read_only": True,
        "removals": [removal.__dict__ for removal in removals],
    }


def _remove_regular_file(root: Path, path: Path, target: str, expected_sha256: str | None) -> dict[str, object]:
    if not path.exists() and not path.is_symlink():
        return {"target": target, "result": "missing"}
    if path.is_symlink() or not path.is_file():
        return {"target": target, "result": "kept-unsafe"}
    if expected_sha256 and sha256(path) != expected_sha256:
        return {"target": target, "result": "kept-modified"}
    path.unlink()
    return {"target": target, "result": "removed"}


def walk_regular_files(base: Path) -> list[Path]:
    """List files under base without following symlinked directories."""
    files: list[Path] = []
    stack = [base]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                stack.append(entry)
            elif entry.is_file():
                files.append(entry)
    return files


def _remove_tree(
    root: Path,
    source: Path,
    path: Path,
    target: str,
    removal: Removal,
    removed_files: list[Path],
) -> dict[str, object]:
    if not path.exists():
        return {"target": target, "result": "missing"}
    if path.is_symlink() or not path.is_dir():
        return {"target": target, "result": "kept-unsafe"}
    expected = removal.expected_tree
    if expected is None and removal.source:
        expected = source_tree_map(source, removal.source)
    removed = 0
    preserved: list[str] = []
    for item in walk_regular_files(path):
        relative = item.relative_to(path).as_posix()
        digest = expected.get(relative) if expected else None
        if expected and (digest is None or sha256(item) != digest):
            preserved.append(relative)
            continue
        item.unlink()
        removed_files.append(item)
        removed += 1
    if removed == 0 and not preserved:
        return {"target": target, "result": "missing"}
    if preserved:
        return {"target": target, "result": "removed-unverified-tree", "files": removed, "preserved": sorted(preserved)}
    if expected is None:
        return {"target": target, "result": "removed-unverified-tree", "files": removed}
    return {"target": target, "result": "removed", "files": removed}


def _prune_directory(root: Path, path: Path, target: str) -> dict[str, object]:
    if not path.exists():
        return {"target": target, "result": "missing"}
    if path.is_symlink() or not path.is_dir():
        return {"target": target, "result": "kept-unsafe"}
    leftovers = [item.relative_to(root).as_posix() for item in walk_regular_files(path)]
    if leftovers:
        return {"target": target, "result": "kept-nonempty", "files": sorted(leftovers)[:20]}
    path.rmdir()
    return {"target": target, "result": "pruned"}


def apply_uninstall(root: Path, source: Path, removals: list[Removal]) -> list[dict[str, object]]:
    """Delete planned Harness assets, restoring everything if a delete fails."""
    results: list[dict[str, object]] = []
    backups: dict[Path, tuple[bytes, int]] = {}
    pruned_dirs: list[Path] = []
    removed_files: list[Path] = []

    if not removals:
        return results

    def backup(path: Path) -> None:
        if path not in backups and path.is_file() and not path.is_symlink():
            backups[path] = (path.read_bytes(), path.stat().st_mode)

    try:
        for removal in removals:
            target = root / removal.target
            if removal.kind == "keep":
                results.append({"target": removal.target, "result": "kept"})
                continue
            if removal.kind == "prune-dir":
                results.append(_prune_directory(root, target, removal.target))
                continue
            if removal.kind == "remove":
                ensure_safe_target(root, target)
                backup(target)
                entry = _remove_regular_file(root, target, removal.target, removal.expected_sha256)
                if entry["result"] == "removed":
                    removed_files.append(target)
                results.append(entry)
                continue
            if removal.kind == "remove-tree":
                ensure_safe_target(root, target)
                if target.is_dir() and not target.is_symlink():
                    for item in walk_regular_files(target):
                        backup(item)
                entry = _remove_tree(root, source, target, removal.target, removal, removed_files)
                if entry["result"].startswith("removed"):
                    removed_files.append(target)
                results.append(entry)
                continue
        # Remove directories that only existed to hold deleted Harness assets.
        candidates = {
            parent
            for removed in removed_files
            for parent in _ancestor_dirs(root, removed)
        }
        for candidate in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
            if candidate.exists() and not candidate.is_symlink() and candidate.is_dir() and not any(candidate.iterdir()):
                candidate.rmdir()
                pruned_dirs.append(candidate)
                results.append({"target": candidate.relative_to(root).as_posix(), "result": "pruned"})
    except (OSError, shutil.Error):
        for target, (content, mode) in backups.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(mode)
        for directory in reversed(pruned_dirs):
            directory.mkdir(parents=True, exist_ok=True)
        raise
    return results


def _ancestor_dirs(root: Path, target: Path) -> list[Path]:
    directories: list[Path] = []
    if target.is_dir() and not target.is_symlink():
        current = target
    else:
        current = target.parent
    while current != root and current != current.parent:
        if current.is_symlink() or not current.is_dir():
            break
        directories.append(current)
        current = current.parent
    return directories


def print_uninstall_summary(plan: dict[str, object]) -> None:
    counts: dict[str, int] = {}
    for entry in plan.get("results") or []:  # type: ignore[union-attr]
        if isinstance(entry, dict):
            key = str(entry.get("result", "unknown"))
            counts[key] = counts.get(key, 0) + 1
    summary = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())) or "no actions"
    print(f"HARNESS UNINSTALL APPLIED: {summary}")
    if any(key.startswith("kept") for key in counts):
        print("Preserved files were modified after install, or are project-owned facts; see the receipt for details.")
    print(f"Receipt: {UNINSTALL_RECEIPT}")


def run_uninstall(
    root: Path,
    source: Path,
    tier: int,
    agent: str | None,
    as_json: bool,
    should_apply: bool,
    keep_project_facts: bool,
) -> int:
    receipt = load_receipt(root)
    if receipt:
        recorded_agent = receipt.get("agent")
        if agent is None and isinstance(recorded_agent, str) and recorded_agent not in {"", "all"}:
            agent = recorded_agent
        recorded_tier = receipt.get("tier")
        if isinstance(recorded_tier, int) and recorded_tier in (1, 2):
            tier = recorded_tier
    removals = uninstall_removals(root, source, receipt, tier, agent, keep_project_facts)
    plan = render_uninstall_plan(root, source, removals, receipt, tier, agent, keep_project_facts)

    if should_apply:
        plan["read_only"] = False
        plan["confirmed_at"] = datetime.now(timezone.utc).isoformat()
        try:
            plan["results"] = apply_uninstall(root, source, removals)
        except (OSError, shutil.Error) as exc:
            plan["errors"] = [f"uninstall failed and rolled back: {exc}"]
            if as_json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print(f"HARNESS UNINSTALL FAILED AND ROLLED BACK: {exc}", file=sys.stderr)
            return 2
        if removals:
            receipt_path = root / UNINSTALL_RECEIPT
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    elif should_apply:
        print_uninstall_summary(plan)
    else:
        print(f"HARNESS UNINSTALL PLAN: {root}")
        print(f"Plan source: {plan['receipt_source']} | installed {plan['installed_version']} | tier {plan['tier']} | agent {plan['agent']}")
        for removal in removals:
            print(f"- {removal.kind:11} {removal.target} ({removal.reason})")
        print("Read-only plan. Confirm with the user, then rerun with --uninstall --apply.")
    return 0


def run_check(root: Path, source: Path, agent: str | None = None) -> tuple[int, list[str]]:
    context_files = ("AGENTS.md", "CLAUDE.md", "GEMINI.md") if agent is None else (str(agent_target(agent)["root_file"]),)
    failures: list[str] = []
    checks = [
        ("check_root_context.py", ["check_root_context.py", str(root), "--context-file", *context_files]),
        ("check_context_docs.py", ["check_context_docs.py", str(root)]),
        ("check_agent_policy.py", ["check_agent_policy.py", str(root / "docs/methodology/agent-policy.yaml")]),
        ("check_profile.py", ["check_profile.py", str(root / "docs/methodology/profile.yaml")]),
        ("resolve_context.py", ["resolve_context.py", "--root", str(root), "."]),
        ("context_cache.py benchmark", ["context_cache.py", "benchmark", "--root", str(root), "--target", ".", "--iterations", "1000", "--json"]),
        ("check_fitness_protection.py", ["check_fitness_protection.py", "--root", str(root)]),
        ("check_change_workspace.py", ["check_change_workspace.py", "--root", str(root)]),
    ]
    checks.extend(
        (
            f"verify_skill.py ({platform})",
            ["verify_skill.py", "engineering", "--project-root", str(root), "--platform", platform, "--source-root", str(source)],
        )
        for platform in skill_platforms_for(agent)
    )
    for tool in openspec_tools_for(agent):
        for skill in REQUIRED_OPENSPEC_SKILLS:
            path = root / OPENSPEC_SKILL_ROOTS[tool] / skill / "SKILL.md"
            if not path.is_file():
                failures.append(f"OpenSpec Skill missing ({tool}): {path}")
    for name, command in checks:
        script = source / "scripts" / command[0]
        if not script.is_file():
            failures.append(f"{name}: source script missing")
            continue
        completed = subprocess.run([sys.executable, str(script), *command[1:]], cwd=root, text=True, capture_output=True)
        if completed.returncode:
            failures.append(f"{name}: {completed.stdout.strip() or completed.stderr.strip()}")
    return (2 if failures else 0), failures


def check_summary(agent: str | None = None) -> str:
    platforms = ", ".join(skill_platforms_for(agent)) or "no native Skill platform"
    return f"Deterministic checks passed: root context, context docs, agent policy, profile, context resolution, stable context cache benchmark, fitness protection, engineering Skill ({platforms})."


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
    parser.add_argument("--agent", choices=tuple(AGENT_TARGETS))
    parser.add_argument("--tier", type=int, choices=(1, 2), default=2)
    parser.add_argument("--name", help=argparse.SUPPRESS)
    parser.add_argument("--stack", help=argparse.SUPPRESS)
    parser.add_argument("--plan", action="store_true", help="print a read-only plan (default)")
    parser.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--apply", action="store_true", help="apply the displayed plan after user confirmation")
    parser.add_argument("--check", action="store_true", help="run deterministic checks after onboarding")
    parser.add_argument("--uninstall", action="store_true", help="plan or apply removal of an installed Harness control plane")
    parser.add_argument("--keep-project-facts", action="store_true", help="keep root adapters and project configuration when uninstalling")
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
    if args.uninstall:
        return run_uninstall(
            root,
            source,
            min(args.tier, 2),
            args.agent,
            args.as_json,
            args.apply,
            args.keep_project_facts,
        )
    agent = args.agent
    status = detect_status(root, agent)
    effective_tier = min(args.tier, 2)
    installed_version = read_version(root / "docs/methodology/VERSION")
    target_version = read_version(source / "VERSION")
    version_relation = classify_versions(installed_version, target_version)
    if installed_version is None and status != "fresh":
        version_relation = "unversioned"
    actions = source_actions(source, root, effective_tier, status, agent)
    plan = render_plan(root, source, effective_tier, status, actions, agent, installed_version, target_version)

    if args.apply and version_relation in {"downgrade", "invalid", "unknown-target", "unversioned"}:
        plan["errors"] = [f"unsupported version transition: {version_relation}"]
        if args.as_json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"HARNESS ONBOARDING BLOCKED: unsupported version transition: {version_relation}", file=sys.stderr)
        return 2

    if args.apply:
        source_errors = validate_action_sources(source, actions, agent)
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
        code, failures = run_check(root, source, agent)
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
            print(check_summary(agent))
    elif args.check:
        print(f"ONBOARDING CHECK PASSED: {root}")
        print(check_summary(agent))
    else:
        print(f"HARNESS ONBOARDING PLAN: {status} project at {root}")
        for action in actions:
            print(f"- {action.kind:9} {action.target} ({action.reason})")
        print("Read-only plan. Ask the user for confirmation, then rerun with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
