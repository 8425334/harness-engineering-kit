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
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cmp_to_key
from pathlib import Path
from typing import Any

try:
    from . import layout
    from .openspec_common import openspec_environment, openspec_executable
    from .versioning import (
        KIT_DEV_ONLY_SCRIPTS,
        KIT_FINGERPRINT_ALGORITHM,
        classify_versions,
        compare_versions,
        kit_manifest,
        manifest_fingerprint,
        parse_version,
        read_version,
        source_fingerprint,
    )
except ImportError:
    import layout
    from openspec_common import openspec_environment, openspec_executable
    from versioning import (
        KIT_DEV_ONLY_SCRIPTS,
        KIT_FINGERPRINT_ALGORITHM,
        classify_versions,
        compare_versions,
        kit_manifest,
        manifest_fingerprint,
        parse_version,
        read_version,
        source_fingerprint,
    )


ROOT_FILES = {
    "templates/AGENTS.md.template": "AGENTS.md",
    "templates/CLAUDE.md.template": "CLAUDE.md",
    "templates/GEMINI.md.template": "GEMINI.md",
    "templates/agent-policy.yaml.template": layout.policy_rel(),
    "templates/methodology-profile.yaml.template": layout.profile_rel(),
    "templates/ai.json.template": layout.relative("context_index"),
    "templates/path-document.md.template": layout.relative("context_doc", module_path="."),
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

# Paths that only a retired layout ever created. They are historical facts, not
# layout-relative targets, so they stay literal across layout changes.
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

#: Versions this Kit shipped *under the legacy* ``docs/methodology`` layout.
#: Ownership may only be inferred from a legacy tree when it carries HEK-specific
#: evidence *and* its version is in this set; a product with its own
#: ``docs/methodology/VERSION = 1.0.0`` must not be mistaken for a HEK install
#: (spec section 5.10). 1.0.0 is deliberately absent: that release only ever used
#: the ``.hek/`` layout, so it cannot be legacy evidence.
KNOWN_HEK_RELEASES = ("0.1.0", "0.3.0", "0.4.0", "0.5.0", "0.5.1", "0.6.0")

JAVA_SCANNER = "templates/fitness/JavaParameterScanner.java.template"

# Kit-development scripts that must not be installed into target projects:
# they validate the kit's own checkout and would fail in the installed layout.
RELEASE_MIGRATIONS = "migrations/releases.json"

ONBOARDING_RECEIPT = layout.relative("onboarding_receipt")
UNINSTALL_RECEIPT = layout.relative("uninstall_receipt")

# Seed content for the tier-2 verification ledger. Uninstall compares against
# this digest so a ledger that was actually filled in is never deleted.
FITNESS_LEDGER_SEED = "# Fitness Verification Ledger\n\n"
FITNESS_LEDGER_SHA256 = hashlib.sha256(FITNESS_LEDGER_SEED.encode("utf-8")).hexdigest()

# Project-owned facts that an uninstall keeps when --keep-project-facts is set.
# They are the files onboarding fills from repository evidence and the user is
# most likely to want after the control plane is gone.
PROJECT_FACT_TARGETS = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        layout.relative("context_index"),
        layout.relative("context_doc", module_path="."),
        layout.policy_rel(),
        layout.profile_rel(),
        "openspec/config.yaml",
    }
)


@dataclass(frozen=True)
class Action:
    kind: str
    source: str | None
    target: str
    reason: str
    #: Project-relative origin for ``move``/``move-tree``. These actions relocate
    #: content that already exists in the host project, so their origin is a
    #: target-side path rather than a Kit source path.
    from_target: str | None = None
    #: For ``remove``: the digest the file must still carry. A mismatch means the
    #: project edited it after the plan was produced, so it is kept instead.
    expected_sha256: str | None = None


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


class WorkspaceRootError(ValueError):
    """The requested root is a workspace (many units), not a single project."""


def looks_like_workspace_root(directory: Path) -> bool:
    """True when ``directory`` only contains other Git repositories.

    Orchestration roots must never be mistaken for a project: ``--unit-id`` (or
    an explicit ``--project-root``) is required so the installer never writes a
    control plane at the workspace level.
    """
    try:
        children = list(directory.iterdir())
    except OSError:
        return False
    repositories = [
        child
        for child in children
        if child.is_dir() and ((child / ".git").is_dir() or (child / ".git").is_file())
    ]
    return len(repositories) >= 2


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
        current = Path.cwd().resolve()
        if looks_like_workspace_root(current):
            raise WorkspaceRootError(
                "current directory contains multiple Git units; run the command with an explicit "
                "--project-root <unit> (or `hek workspace exec <unit> -- hek init`)"
            )
        return current


def render_identity_template(template: str, *, unit_id: str, workspace_id: str, unit_kind: str, repo_url: str) -> str:
    """Fill the identity draft with everything derivable from the repository."""
    replacements = {
        "{{WORKSPACE_ID}}": workspace_id,
        "{{UNIT_ID}}": unit_id,
        "{{UNIT_KIND}}": unit_kind,
        "{{REPO_URL}}": repo_url,
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def git_remote_url(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return "{{REPO_URL}}"
    return result.stdout.strip() or "{{REPO_URL}}"


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


def installed_version_path(root: Path) -> Path:
    """Version marker of the *installed* layout, which may still be the legacy one.

    Reading only the active path reported a pre-0.6 project as unversioned, which
    the transition guard then refused to migrate.
    """
    active = layout.path("version", root)
    if active.is_file():
        return active
    legacy = root / layout.relative("version", layout=layout.LEGACY)
    if layout.relative("control_plane", layout=layout.LEGACY) != layout.relative("control_plane"):
        if legacy.is_file() and hek_install_evidence(root):
            return legacy
    return active


def hek_install_evidence(root: Path) -> bool:
    """True only when HEK-specific evidence proves this is one of our installs.

    Directory names such as ``docs/methodology`` are not evidence: an unrelated
    product shipping the same tree would otherwise be adopted and blocked by the
    version guard. Evidence is ``.hek/VERSION`` or a legacy tree that carries
    both ``scripts/`` and ``core/`` with a version this Kit actually released.
    """
    if (root / layout.relative("version")).is_file():
        return True
    legacy_root = root / layout.relative("control_plane", layout=layout.LEGACY)
    if not (legacy_root / "scripts").is_dir() or not (legacy_root / "core").is_dir():
        return False
    version = read_version(legacy_root / "VERSION")
    return version in KNOWN_HEK_RELEASES


def legacy_unverified(root: Path) -> bool:
    """A ``docs/methodology`` tree that is not provably a HEK installation."""
    candidate = root / layout.relative("control_plane", layout=layout.LEGACY)
    return candidate.is_dir() and not hek_install_evidence(root)


def identity_check_required(root: Path) -> bool:
    """Federation checks stay off until a unit opts in with an identity file."""
    return (root / layout.identity_rel()).is_file()


def relayout_source(root: Path) -> Path | None:
    """Return the legacy control-plane root when it needs relocating.

    Probed through the layout table rather than hardcoded paths, so it keeps
    working if either layout's shape changes again.
    """
    legacy_root = layout.relative("control_plane", layout=layout.LEGACY)
    active_root = layout.relative("control_plane")
    if legacy_root == active_root:
        return None
    candidate = root / legacy_root
    if not candidate.is_dir() or (root / active_root).exists():
        return None
    if not hek_install_evidence(root):
        return None
    return candidate


def detect_status(root: Path, agent: str | None = None) -> str:
    # A pre-0.6 installation must migrate before anything else, including when
    # retired pre-0.5 markers are also present.
    if relayout_source(root) is not None:
        return "relayout"
    # ``docs/methodology`` without HEK-specific evidence is some other product's
    # tree; its markers must not turn the project into an unmigratable "legacy"
    # install. Treat it as fresh and report ``legacy.unverified`` instead.
    if legacy_unverified(root):
        return "fresh"
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
            layout.path("version", root).is_file()
            and layout.policy_path(root).is_file()
            and root_ready
            and skill_ready
        )
        if canonical:
            return "current"
    if agent is None:
        canonical = (
            layout.path("version", root).is_file()
            and layout.policy_path(root).is_file()
            and (root / ".agents/skills/engineering/SKILL.md").is_file()
        )
        if canonical:
            return "current"
    if any((root / target).exists() for target in ROOT_FILES.values()):
        return "partial"
    return "fresh"


#: Never scanned for legacy path documents, so a migration does not pick up
#: unrelated `AI.md` files or content it is about to move.
LEGACY_CONTEXT_EXCLUDES = frozenset({
    ".git", ".hek", ".claude", ".agents", ".opencode", ".cursor", ".gemini", ".trae",
    "node_modules", "target", "build", "dist", ".venv", "venv",
})


def _relayout_file_moves() -> list[tuple[str, str]]:
    """(legacy, active) pairs for single files that relocate rather than reinstall."""
    legacy = layout.LEGACY
    pairs = [
        (layout.policy_rel(layout=legacy), layout.policy_rel()),
        (layout.profile_rel(layout=legacy), layout.profile_rel()),
        (layout.relative("context_index", layout=legacy), layout.relative("context_index")),
        (layout.relative("onboarding_receipt", layout=legacy), layout.relative("onboarding_receipt")),
    ]
    for attribute in ("production_policy", "production_readme", "production_template"):
        pairs.append((layout.relative(attribute, layout=legacy), layout.relative(attribute)))
    return pairs


def _relayout_tree_moves() -> list[tuple[str, str]]:
    """(legacy, active) pairs for directories relocated wholesale."""
    legacy = layout.LEGACY
    return [
        (layout.relative("fitness", layout=legacy), layout.relative("fitness")),
        (layout.relative("lessons", layout=legacy), layout.relative("lessons")),
    ]


def _relayout_context_moves(root: Path) -> list[tuple[str, str]]:
    """(legacy, active) pairs for every path document, the root one included.

    The legacy index is authoritative because it is what the project actually
    routed by; a directory walk is the fallback when it cannot be read.
    """
    index_path = root / layout.relative("context_index", layout=layout.LEGACY)
    modules: list[str] = []
    if index_path.is_file():
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                modules = [
                    str(module["path"])
                    for module in payload.get("modules") or []
                    if isinstance(module, dict) and module.get("path") is not None
                ]
        except (OSError, UnicodeError, json.JSONDecodeError):
            modules = []
    if not modules:
        for path in sorted(root.rglob("AI.md")):
            relative = path.relative_to(root)
            if any(part in LEGACY_CONTEXT_EXCLUDES for part in relative.parts):
                continue
            modules.append(relative.parent.as_posix())
    return [
        (
            layout.relative("context_doc", module_path=module, layout=layout.LEGACY),
            layout.relative("context_doc", module_path=module),
        )
        for module in dict.fromkeys(modules)
    ]


def _relayout_removals(root: Path, skipped: list[str]) -> list[Action]:
    """Delete actions for whatever the moves left behind in the legacy tree.

    Each entry carries the digest seen at plan time, so an apply that finds
    different content keeps the file and reports ``kept-modified`` instead of
    deleting something the project changed in between.
    """
    base = root / layout.relative("control_plane", layout=layout.LEGACY)
    if not base.is_dir():
        return []
    actions: list[Action] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(relative == entry or relative.startswith(entry) for entry in skipped):
            continue
        actions.append(Action(
            "remove", None, relative, "superseded by the .hek layout",
            expected_sha256=sha256(path),
        ))
    return actions


def relayout_path_map() -> list[tuple[str, str]]:
    """(legacy, active) project-relative prefixes, longest legacy first.

    Longest-first matters: ``docs/methodology/core`` must be repointed before the
    generic ``docs/methodology`` prefix swallows it.
    """
    legacy = layout.LEGACY
    pairs = [
        (layout.policy_rel(layout=legacy), layout.policy_rel()),
        (layout.profile_rel(layout=legacy), layout.profile_rel()),
    ]
    for attribute in (
        "core", "scripts", "change_templates", "compaction", "lessons", "fitness",
        "production_changes", "production_audit", "production_policy", "production_readme",
        "production_template", "methodology",
    ):
        pairs.append((layout.relative(attribute, layout=legacy), layout.relative(attribute)))
    return sorted(
        ((old, new) for old, new in pairs if old and old != new),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )


def repoint_path(value: str) -> str:
    """Rewrite one project-relative path string into the active layout."""
    for legacy_rel, active_rel in relayout_path_map():
        value = value.replace(legacy_rel, active_rel)
    return value


def rewrite_policy_paths(text: str) -> str:
    """Repoint a project policy at the active layout.

    Textual rather than a YAML round-trip so the project's comments, ordering and
    formatting survive; only paths the layout table can name are touched. The
    result is a candidate: the caller compares and skips the write if unchanged.
    """
    for legacy_rel, active_rel in relayout_path_map():
        text = text.replace(legacy_rel, active_rel)

    # The control plane writes evidence under .hek/state, so the directory has to
    # be writable or the first governed change fails on its own permission model.
    match = re.search(r"^([ \t]*writable_paths:[ \t]*)\[(.*?)\][ \t]*$", text, re.MULTILINE)
    if match:
        entries = [item.strip().strip("\"'") for item in match.group(2).split(",") if item.strip()]
        if layout.HEK.root not in entries:
            entries.append(layout.HEK.root)
            rendered = ", ".join(f'"{entry}"' for entry in entries)
            text = f"{text[:match.start()]}{match.group(1)}[{rendered}]{text[match.end():]}"
    return text


def rewrite_index_references(payload: dict[str, Any]) -> dict[str, Any]:
    """Repoint an ``ai.json`` index at the active layout.

    Structural rather than textual: the module list is what routes every task, so
    each entry is recomputed from the layout table instead of string-matched.
    """
    modules = payload.get("modules")
    if isinstance(modules, list):
        for module in modules:
            if isinstance(module, dict) and module.get("path") is not None:
                module["context"] = layout.relative("context_doc", module_path=str(module["path"]))
    entrypoints = payload.get("entrypoints")
    if isinstance(entrypoints, dict):
        if str(entrypoints.get("policy", "")) == layout.policy_rel(layout=layout.LEGACY):
            entrypoints["policy"] = layout.policy_rel()
        else:
            entrypoints["policy"] = repoint_path(str(entrypoints.get("policy", "")))
        entrypoints["lifecycle"] = repoint_path(str(entrypoints.get("lifecycle", "")))
    return payload


def relayout_plan(root: Path, actions: list[Action]) -> list[Action]:
    """Turn a fresh-install plan into a migration plan for a pre-0.6 install.

    Moves are emitted first so they occupy their destinations before the normal
    install actions run; those then report ``preserved`` rather than writing a
    placeholder over content the project already owns.
    """
    moves: list[Action] = []
    replaced: set[str] = set()
    skipped: list[str] = []

    def add_move(legacy_rel: str, active_rel: str, reason: str, kind: str = "move") -> None:
        if not (root / legacy_rel).exists():
            return
        moves.append(Action(kind, None, active_rel, reason, from_target=legacy_rel))
        skipped.append(f"{legacy_rel}/" if kind == "move-tree" else legacy_rel)
        if kind == "move":
            replaced.add(active_rel)

    for legacy_rel, active_rel in _relayout_file_moves():
        add_move(legacy_rel, active_rel, "existing project content")

    # Path documents move before the wholesale trees so a document that happens
    # to live inside one of them lands under .hek/context instead of following
    # its directory.
    for legacy_rel, active_rel in _relayout_context_moves(root):
        add_move(legacy_rel, active_rel, "existing path context")

    for legacy_rel, active_rel in _relayout_tree_moves():
        add_move(legacy_rel, active_rel, "existing project content", kind="move-tree")

    # The policy is the one file whose *contents* also point at the old layout,
    # so it is rewritten after it lands. Run it right after the moves and before
    # the install actions so the check step sees a coherent policy.
    policy_target = layout.policy_rel()
    if any(action.kind == "move" and action.target == policy_target for action in moves):
        moves.append(Action("rewrite-policy", None, policy_target, "repoint policy at the .hek layout"))
    index_target = layout.relative("context_index")
    if any(action.kind == "move" and action.target == index_target for action in moves):
        moves.append(Action("rewrite-index", None, index_target, "repoint context index at the .hek layout"))

    kept = [action for action in actions if action.target not in replaced]
    prunes = [
        Action("prune-empty", None, rel, "legacy layout directory is now unused")
        for rel in (
            layout.relative("fitness", layout=layout.LEGACY),
            layout.relative("control_plane", layout=layout.LEGACY),
        )
        if (root / rel).is_dir()
    ]
    return moves + kept + _relayout_removals(root, skipped) + prunes


def source_actions(
    source: Path,
    root: Path,
    tier: int,
    status: str,
    agent: str | None = None,
    unit_id: str | None = None,
) -> list[Action]:
    actions: list[Action] = []
    if unit_id:
        actions.append(
            Action("create-identity", "templates/identity.yaml.template", layout.identity_rel(), "unit identity draft")
        )
    for relative, target in root_files_for(agent).items():
        destination = root / target
        if destination.is_file():
            actions.append(Action("preserve", relative, target, "existing project configuration"))
        else:
            actions.append(Action("create", relative, target, "required Harness entrypoint"))

    for relative in sorted((source / "core").glob("*.md")):
        actions.append(Action("sync", str(relative.relative_to(source)), f"{layout.relative('core')}/{relative.name}", "canonical methodology"))
    for relative in sorted((source / "scripts").glob("*.py")):
        if relative.name in KIT_DEV_ONLY_SCRIPTS:
            continue
        actions.append(Action("sync", str(relative.relative_to(source)), f"{layout.relative('scripts')}/{relative.name}", "canonical control script"))
    for relative in sorted((source / "templates/workflow").glob("*.template")):
        actions.append(Action("sync", str(relative.relative_to(source)), f"{layout.relative('change_templates')}/{relative.name}", "change evidence template"))
    for relative in sorted((source / "templates/openspec-schema").rglob("*")):
        if relative.is_file():
            target = Path("openspec/schemas/harness-engineering") / relative.relative_to(source / "templates/openspec-schema")
            actions.append(Action("sync", str(relative.relative_to(source)), target.as_posix(), "OpenSpec lifecycle schema"))
    for relative in sorted((source / "templates/compaction").glob("*")):
        if relative.is_file():
            target_name = relative.name.replace(".template", "")
            actions.append(Action("sync", str(relative.relative_to(source)), f"{layout.relative('compaction')}/{target_name}", "portable compaction recovery resource"))
    for relative in sorted((source / "templates/hooks").glob("*.template")):
        target_name = relative.name.replace(".template", "")
        target = f"{layout.relative('methodology')}/hooks/{target_name}"
        actions.append(Action("sync", str(relative.relative_to(source)), target, "structural write guard hook"))
    actions.extend(
        Action("mkdir", None, target, "Harness workspace directory")
        for target in (
            layout.relative("production_changes"),
            layout.relative("production_audit"),
            layout.relative("lessons"),
            "openspec/changes",
            "openspec/specs",
        )
    )
    version_file = source / "VERSION"
    if version_file.is_file():
        actions.append(Action("sync", "VERSION", layout.relative("version"), "installed methodology version"))

    # agent-policy.yaml references the production policy at every tier, so the
    # production control scaffold must be installed at every tier as well.
    for relative in sorted((source / "templates/production").glob("*.template")):
        target = {
            "README.md.template": layout.relative("production_readme"),
            "policy.yaml.template": layout.relative("production_policy"),
            "change-record.json.template": layout.relative("production_template"),
        }.get(relative.name)
        if target:
            actions.append(Action("create", str(relative.relative_to(source)), target, "production control"))

    if tier >= 1:
        minimal_fitness = {"fitness.py.template", "check_sdd_quality.py.template"}
        for relative in sorted((source / "templates/fitness").glob("*.py.template")):
            if tier < 2 and relative.name not in minimal_fitness:
                continue
            actions.append(Action("create", str(relative.relative_to(source)), f"{layout.relative('fitness')}/scripts/{relative.stem}", "optional Fitness control"))
        sdd_rule = source / "templates/fitness/rules/sdd-quality.md.template"
        actions.append(Action("create", str(sdd_rule.relative_to(source)), f"{layout.relative('fitness')}/sdd-quality.md", "required staged Fitness control"))
    if tier >= 2:
        actions.append(Action("create", JAVA_SCANNER, f"{layout.relative('fitness')}/scripts/JavaParameterScanner.java", "Java Fitness scanner"))
        actions.append(Action("create-empty", None, layout.relative("fitness_ledger"), "Fitness verification ledger"))
        fitness_readme = source / "templates/fitness/README.md"
        if fitness_readme.is_file():
            actions.append(Action("create", str(fitness_readme.relative_to(source)), f"{layout.relative('fitness')}/README.md", "optional Fitness control"))
        for relative in sorted((source / "templates/fitness/rules").glob("*.md.template")):
            if relative.name == "sdd-quality.md.template":
                continue
            actions.append(Action("create", str(relative.relative_to(source)), f"{layout.relative('fitness')}/{relative.stem}", "optional Fitness rule"))
        lessons_readme = source / "templates/lessons/README.md.template"
        if lessons_readme.is_file():
            actions.append(Action("create", str(lessons_readme.relative_to(source)), f"{layout.relative('lessons')}/README.md", "lesson memory"))

    for platform in skill_platforms_for(agent):
        actions.append(Action("sync-tree", "templates/engineering", f"{SKILL_ROOTS[platform]}/engineering", "selected Agent Skill discovery"))
    tools = openspec_tools_for(agent)
    if tools:
        actions.append(Action("openspec-init", None, ",".join(tools), "generate native OpenSpec lifecycle Skills"))
    else:
        actions.append(Action("report", None, "OpenSpec native Skills", "selected Agent has no OpenSpec Skill adapter; use OpenSpec CLI operations directly"))

    # Recorded last, so the identity always describes the content this run
    # installed rather than the content the show began with.
    actions.append(Action("record-identity", None, layout.relative("kit_identity"), "Kit version consistency record"))

    if status == "legacy":
        actions.append(Action("report", None, "legacy architecture", "preserve legacy files; route future work to engineering Skill"))
    if (root / "docs/sdd").exists():
        actions.append(Action("report", None, "docs/sdd", "legacy SDD workspace requires manual migration to openspec/changes; no files are deleted automatically"))
    if status == "relayout":
        actions = relayout_plan(root, actions)
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


def read_kit_identity(root: Path) -> dict[str, object] | None:
    """Read the Kit identity recorded by the last successful installation."""
    path = root / layout.relative("kit_identity")
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def kit_identity_record(source: Path) -> dict[str, object]:
    """Describe which Kit content this installation came from.

    A version number is a release name; the fingerprint is the content behind
    it. Recording both is what lets a later run tell "same release, same bytes"
    apart from "same release, different bytes".
    """
    manifest = kit_manifest(source)
    return {
        "schema_version": 1,
        "version": read_version(source / "VERSION") or "unknown",
        "algorithm": KIT_FINGERPRINT_ALGORITHM,
        "fingerprint": manifest_fingerprint(manifest),
        "files": len(manifest),
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }


def recorded_fingerprint(root: Path) -> str:
    """Fingerprint recorded by the last install, or ``unknown``."""
    identity = read_kit_identity(root)
    if isinstance(identity, dict) and isinstance(identity.get("fingerprint"), str):
        return str(identity["fingerprint"])
    return "unknown"


def content_drift(source: Path, root: Path, actions: list[Action]) -> dict[str, list[str]]:
    """Compare every canonical resource the plan syncs with what is installed.

    Only ``sync`` actions count: those are the Harness-owned files an upgrade
    replaces wholesale. Project-owned facts are created or preserved, never
    synchronized, so a project differing from the Kit there is not drift.
    """
    missing: list[str] = []
    modified: list[str] = []
    expected: set[str] = set()
    for action in actions:
        if action.kind != "sync":
            continue
        expected.add(action.target)
        source_file = source / str(action.source)
        target = root / action.target
        if not target.is_file():
            missing.append(action.target)
        elif not source_file.is_file() or sha256(source_file) != sha256(target):
            modified.append(action.target)
    # Files the Kit used to ship and no longer does. Reported, never deleted:
    # only an uninstall is allowed to remove Harness content.
    stale: list[str] = []
    for directory in sorted({str(Path(action.target).parent) for action in actions if action.kind == "sync"}):
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if relative not in expected:
                stale.append(relative)
    return {"missing": sorted(missing), "modified": sorted(modified), "stale": sorted(stale)}


def identity_relation(source_digest: str, root: Path, drift: dict[str, list[str]]) -> str:
    """``match``, ``drift``, or ``unknown`` for the installed Kit identity."""
    if read_kit_identity(root) is None:
        return "unknown"
    if recorded_fingerprint(root) != source_digest:
        return "drift"
    return "drift" if drift["missing"] or drift["modified"] else "match"


def drift_examples(drift: dict[str, list[str]], limit: int = 5) -> str:
    """One human-readable list of the files that actually differ."""
    files = [*drift["missing"], *drift["modified"]]
    if not files:
        return ""
    shown = ", ".join(files[:limit])
    return shown + (f" (+{len(files) - limit} more)" if len(files) > limit else "")


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
    warnings: list[dict[str, str]] = []
    if legacy_unverified(root):
        warnings.append(
            {
                "code": "legacy.unverified",
                "message": (
                    f"{layout.relative('control_plane', layout=layout.LEGACY)} exists but carries no "
                    "HEK-specific evidence; treating the project as fresh. Directory names never "
                    "decide ownership."
                ),
            }
        )
    installed_version = installed_version if installed_version is not None else read_version(installed_version_path(root))
    target_version = target_version if target_version is not None else read_version(source / "VERSION")
    version_relation = classify_versions(installed_version, target_version)
    if installed_version is None and status != "fresh":
        version_relation = "unversioned"
    source_digest = source_fingerprint(source)
    drift = content_drift(source, root, actions)
    identity = identity_relation(source_digest, root, drift)
    if identity == "drift":
        code = "version.same-content-drift" if version_relation == "same" else "identity.content-drift"
        examples = drift_examples(drift)
        warnings.append({
            "code": code,
            "message": (
                f"installed {installed_version or 'unknown'} does not match the content of Kit "
                f"{target_version or 'unknown'}; a release number does not prove byte-identical files"
                + (f" (differing: {examples})" if examples else "")
                + ". Re-run the plan with --apply to synchronize, and bump VERSION if this content change is a release."
            ),
        })
    elif identity == "unknown" and status != "fresh":
        warnings.append({
            "code": "identity.missing",
            "message": (
                f"{layout.relative('kit_identity')} is missing, so this installation cannot prove which Kit "
                "content it came from. The next apply records it."
            ),
        })
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
        "source_fingerprint": source_digest,
        "installed_fingerprint": recorded_fingerprint(root),
        "identity_relation": identity,
        "content_drift": drift,
        "migration_manifest_errors": validate_release_manifest(source),
        "release_migrations": release_migrations(source, installed_version, target_version, version_relation),
        "tier": tier,
        "agent": agent or "all",
        "native_root_file": agent_target(agent)["root_file"] if agent else "AGENTS.md + CLAUDE.md + GEMINI.md",
        "read_only": True,
        "legacy_files_preserved": True,
        "legacy_markers": legacy_markers,
        "warnings": warnings,
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
    fitness_dir = layout.relative("fitness")
    if any(action.target.startswith(layout.protected_prefix()) for action in actions):
        required.extend(
            path.relative_to(source).as_posix()
            for path in (source / "templates/fitness").glob("*.py.template")
            if any(action.target == f"{fitness_dir}/scripts/{path.stem}" for action in actions)
        )
        required.append("templates/fitness/rules/sdd-quality.md.template")
    if any(action.target == f"{fitness_dir}/README.md" for action in actions):
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


def apply_actions(
    root: Path,
    source: Path,
    actions: list[Action],
    *,
    identity: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    snapshots: dict[Path, tuple[bytes, int]] = {}
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    #: (origin, destination) pairs recorded so a rollback can relocate them back.
    moved: list[tuple[Path, Path]] = []

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
                    target.write_text(FITNESS_LEDGER_SEED, encoding="utf-8")
                    created_files.append(target)
                    results.append({"target": action.target, "result": "created", "sha256": sha256(target)})
                continue
            if action.kind == "move":
                origin = root / str(action.from_target)
                target = root / action.target
                ensure_safe_target(root, origin)
                ensure_safe_target(root, target)
                if not origin.is_file():
                    results.append({"target": action.target, "result": "missing", "from": action.from_target})
                    continue
                if target.exists():
                    # Never overwrite the destination. A populated target means an
                    # earlier run or a hand-written file, and replacing it would
                    # discard content the migration cannot reproduce.
                    results.append({"target": action.target, "result": "preserved", "from": action.from_target})
                    continue
                ensure_dir(target.parent)
                shutil.move(str(origin), str(target))
                moved.append((origin, target))
                results.append({
                    "target": action.target,
                    "result": "moved",
                    "from": action.from_target,
                    "sha256": sha256(target),
                })
                continue
            if action.kind == "move-tree":
                origin = root / str(action.from_target)
                target = root / action.target
                ensure_safe_target(root, origin)
                ensure_safe_target(root, target)
                if not origin.is_dir():
                    results.append({"target": action.target, "result": "missing", "from": action.from_target})
                    continue
                ensure_dir(target.parent)
                tree: dict[str, str] = {}
                preserved = 0
                for item in sorted(origin.rglob("*")):
                    if not item.is_file():
                        continue
                    destination = target / item.relative_to(origin)
                    ensure_safe_target(root, destination)
                    if destination.exists():
                        preserved += 1
                        tree[item.relative_to(origin).as_posix()] = sha256(destination)
                        continue
                    ensure_dir(destination.parent)
                    shutil.move(str(item), str(destination))
                    moved.append((item, destination))
                    tree[item.relative_to(origin).as_posix()] = sha256(destination)
                results.append({
                    "target": action.target,
                    "result": "moved",
                    "from": action.from_target,
                    "files": len(tree) - preserved,
                    "preserved": preserved,
                    "tree": tree,
                })
                continue
            if action.kind == "remove":
                target = root / action.target
                ensure_safe_target(root, target)
                if not target.is_file():
                    results.append({"target": action.target, "result": "missing"})
                    continue
                if action.expected_sha256 and sha256(target) != action.expected_sha256:
                    # Edited between plan and apply: keep it and say so rather
                    # than deleting content the user changed.
                    results.append({"target": action.target, "result": "kept-modified"})
                    continue
                snapshot(target)
                target.unlink()
                results.append({"target": action.target, "result": "removed"})
                continue
            if action.kind == "rewrite-policy":
                target = root / action.target
                ensure_safe_target(root, target)
                if not target.is_file():
                    results.append({"target": action.target, "result": "missing"})
                    continue
                original = target.read_text(encoding="utf-8")
                updated = rewrite_policy_paths(original)
                if updated == original:
                    results.append({"target": action.target, "result": "unchanged"})
                    continue
                snapshot(target)
                target.write_text(updated, encoding="utf-8", newline="")
                results.append({"target": action.target, "result": "updated", "sha256": sha256(target)})
                continue
            if action.kind == "rewrite-index":
                target = root / action.target
                ensure_safe_target(root, target)
                if not target.is_file():
                    results.append({"target": action.target, "result": "missing"})
                    continue
                original = target.read_text(encoding="utf-8")
                try:
                    payload = json.loads(original)
                except (UnicodeError, json.JSONDecodeError):
                    results.append({"target": action.target, "result": "unreadable"})
                    continue
                updated = json.dumps(
                    rewrite_index_references(payload), ensure_ascii=False, indent=2
                ) + "\n"
                if updated == original:
                    results.append({"target": action.target, "result": "unchanged"})
                    continue
                snapshot(target)
                target.write_text(updated, encoding="utf-8", newline="")
                results.append({"target": action.target, "result": "updated", "sha256": sha256(target)})
                continue
            if action.kind == "prune-empty":
                # Only ever removes directories that hold no files, deepest
                # first, so a directory still carrying unexpected content stays.
                stale = root / action.target
                if stale.is_dir():
                    directories = sorted(
                        (item for item in stale.rglob("*") if item.is_dir()),
                        key=lambda item: len(item.parts),
                        reverse=True,
                    )
                    for directory in directories:
                        try:
                            directory.rmdir()
                        except OSError:
                            pass
                    try:
                        stale.rmdir()
                    except OSError:
                        pass
                results.append({"target": action.target, "result": "pruned"})
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
                    environment = openspec_environment(isolated_home)
                    openspec = openspec_executable()
                    commands = (
                        [openspec, "config", "set", "profile", "custom"],
                        [openspec, "config", "set", "workflows", json.dumps(OPENSPEC_WORKFLOWS)],
                        [openspec, "init", str(staging), "--tools", action.target, "--profile", "custom", "--no-animation"],
                    )
                    for command in commands:
                        completed = subprocess.run(
                            command,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            capture_output=True,
                            env=environment,
                            check=False,
                        )
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
                with tempfile.TemporaryDirectory(prefix="hek-openspec-schema-home-") as schema_home:
                    schema_check = subprocess.run(
                        [openspec_executable(), "schema", "validate", "harness-engineering", "--json"],
                        cwd=root,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        env=openspec_environment(schema_home),
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
            if action.kind == "record-identity":
                # Written last, so the identity always describes the content this
                # run installed rather than the content the run began with.
                target = root / action.target
                ensure_safe_target(root, target)
                snapshot(target)
                ensure_dir(target.parent)
                target.write_text(
                    json.dumps(kit_identity_record(source), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                results.append({"target": action.target, "result": "recorded", "sha256": sha256(target)})
                continue
            if not action.source:
                continue
            source_file = source / action.source
            target = root / action.target
            ensure_safe_target(root, target)
            if action.kind == "create-identity":
                if target.exists():
                    results.append({"target": action.target, "result": "preserved"})
                    continue
                values = identity or {}
                rendered = render_identity_template(
                    source_file.read_text(encoding="utf-8"),
                    unit_id=values.get("unit_id", ""),
                    workspace_id=values.get("workspace_id", "{{WORKSPACE_ID}}"),
                    unit_kind=values.get("unit_kind", "backend"),
                    repo_url=values.get("repo_url", "{{REPO_URL}}"),
                )
                ensure_dir(target.parent)
                target.write_text(rendered, encoding="utf-8")
                created_files.append(target)
                results.append({"target": action.target, "result": "created", "sha256": sha256(target)})
                continue
            overwrite = action.kind == "sync"
            snapshot(target)
            ensure_dir(target.parent)
            result = copy_file(source_file, target, overwrite)
            results.append({"target": action.target, "result": result, "sha256": sha256(target)})
    except (OSError, shutil.Error):
        # Relocate moved content back first: until this runs, the origin paths are
        # missing, and the created-file cleanup below expects to find the
        # destinations it recorded.
        for origin, destination in reversed(moved):
            if destination.exists() and not origin.exists():
                try:
                    origin.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(destination), str(origin))
                except (OSError, shutil.Error):
                    pass
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


def resolve_target(root: Path, target: str) -> Path | None:
    """Resolve a planned target inside root, rejecting absolute or escaping paths."""
    base = Path(os.path.abspath(os.fspath(root)))
    candidate = Path(os.path.abspath(os.fspath(root / target)))
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def symlinked_component(root: Path, target: str) -> str | None:
    """Return the first symlinked path component of target, if any."""
    base = Path(os.path.abspath(os.fspath(root)))
    current = base
    for part in Path(target).parts:
        current = current / part
        if current.is_symlink():
            return current.relative_to(base).as_posix()
    return None


def expected_file_digest(source: Path, relative: str | None) -> str | None:
    """Digest of the Kit source file a target was copied from, when it exists."""
    if not relative:
        return None
    candidate = source / relative
    if candidate.is_file() and not candidate.is_symlink():
        return sha256(candidate)
    return None


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
    the install preserved, and files edited after install, stay in place. Without
    a receipt nothing is deleted unless it is still byte-identical to the Kit
    source, and targets that cannot be verified are kept rather than deleted.
    """

    removals: list[Removal] = []
    seen: set[str] = set()

    def add(removal: Removal) -> None:
        if removal.target in seen:
            return
        path = resolve_target(root, removal.target)
        if path is None or not path.exists():
            return
        symlink = symlinked_component(root, removal.target)
        if symlink and removal.kind != "keep":
            removal = Removal("keep", removal.target, f"symlinked path ({symlink}) is left in place")
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
                    if not isinstance(expected, dict) or not expected:
                        add(Removal("keep", directory, "no recorded digests; left in place instead of deleting unverified files"))
                        continue
                    add(Removal("remove-tree", directory, "OpenSpec lifecycle Skill generated by Harness", expected_tree=expected))
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
        # Anything that cannot be verified against the Kit source is kept.
        for action in source_actions(source, root, tier, "fresh", agent):
            if action.kind == "report":
                continue
            if action.kind == "mkdir":
                add(Removal("prune-dir", action.target, action.reason))
            elif action.kind == "sync-tree":
                add(Removal("remove-tree", action.target, action.reason, source="templates/engineering"))
            elif action.kind == "openspec-init":
                for directory in openspec_skill_directories(action.target):
                    add(Removal("keep", directory, "Kit source cannot prove this generated Skill is unmodified"))
            elif action.kind == "create-empty":
                add(Removal("remove", action.target, action.reason, expected_sha256=FITNESS_LEDGER_SHA256))
            else:
                # create/sync/preserve: removable only while byte-identical to the Kit source.
                digest = expected_file_digest(source, action.source)
                if digest is None:
                    continue
                add(Removal("remove", action.target, action.reason, source=action.source, expected_sha256=digest))

    receipt_path = root / ONBOARDING_RECEIPT
    if receipt_path.is_file():
        add(Removal("remove", ONBOARDING_RECEIPT, "Harness onboarding receipt", expected_sha256=sha256(receipt_path)))

    identity_path = root / layout.relative("kit_identity")
    if identity_path.is_file():
        # A generated state record, like the receipt: Harness owns it outright.
        add(Removal("remove", layout.relative("kit_identity"), "Harness Kit identity record", expected_sha256=sha256(identity_path)))

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
        "installed_version": read_version(installed_version_path(root)) or "unknown",
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
    if not expected and removal.source:
        expected = source_tree_map(source, removal.source)
    if not expected:
        # Never delete a tree we cannot verify against recorded or source digests.
        return {"target": target, "result": "kept-unverified"}
    removed = 0
    preserved: list[str] = []
    for item in walk_regular_files(path):
        relative = item.relative_to(path).as_posix()
        digest = expected.get(relative)
        if digest is None or sha256(item) != digest:
            preserved.append(relative)
            continue
        item.unlink()
        removed_files.append(item)
        removed += 1
    if removed == 0 and not preserved:
        return {"target": target, "result": "missing"}
    if preserved:
        return {"target": target, "result": "removed-partial", "files": removed, "preserved": sorted(preserved)}
    return {"target": target, "result": "removed", "files": removed}


def _relative_target(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _target_is_safe(root: Path, target: Path) -> bool:
    """True when no symlink sits on the path; unsafe targets are kept, not removed."""
    try:
        ensure_safe_target(root, target)
    except OSError:
        return False
    return True


def _empty_subtree(root: Path, base: Path) -> tuple[list[str], list[Path]]:
    """Return blockers and removable directories (deepest-first) for an empty tree.

    A blocker is anything that keeps the tree from being removed: a regular file,
    a symlink (which is never followed), or a directory that cannot be listed.
    """
    blockers: list[str] = []
    directories: list[Path] = [base]
    stack = [base]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            blockers.append(f"{_relative_target(root, directory)}: {exc}")
            continue
        for entry in entries:
            if entry.is_symlink() or not entry.is_dir():
                blockers.append(_relative_target(root, entry))
                continue
            directories.append(entry)
            stack.append(entry)
    directories.sort(key=lambda item: len(item.parts), reverse=True)
    return blockers, directories


def _prune_directory(root: Path, path: Path, target: str, pruned_dirs: list[Path]) -> dict[str, object]:
    if not path.exists():
        return {"target": target, "result": "missing"}
    if path.is_symlink() or not path.is_dir():
        return {"target": target, "result": "kept-unsafe"}
    blockers, directories = _empty_subtree(root, path)
    if blockers:
        return {"target": target, "result": "kept-nonempty", "files": sorted(blockers)[:20]}
    for directory in directories:
        directory.rmdir()
        pruned_dirs.append(directory)
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
            if removal.kind == "keep":
                results.append({"target": removal.target, "result": "kept"})
                continue
            target = resolve_target(root, removal.target)
            if target is None or not _target_is_safe(root, target):
                results.append({"target": removal.target, "result": "kept-unsafe"})
                continue
            if removal.kind == "prune-dir":
                results.append(_prune_directory(root, target, removal.target, pruned_dirs))
                continue
            if removal.kind == "remove":
                backup(target)
                entry = _remove_regular_file(root, target, removal.target, removal.expected_sha256)
                if entry["result"] == "removed":
                    removed_files.append(target)
                results.append(entry)
                continue
            if removal.kind == "remove-tree":
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
            if not candidate.exists() or candidate.is_symlink() or not candidate.is_dir():
                continue
            if not _target_is_safe(root, candidate):
                continue
            blockers, directories = _empty_subtree(root, candidate)
            if blockers:
                continue
            for directory in directories:
                directory.rmdir()
                pruned_dirs.append(directory)
            results.append({"target": _relative_target(root, candidate), "result": "pruned"})
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
            try:
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                plan["errors"] = [f"uninstall applied but the receipt could not be written: {exc}"]
                if as_json:
                    print(json.dumps(plan, ensure_ascii=False, indent=2))
                else:
                    print(f"HARNESS UNINSTALL WARNING: receipt not written: {exc}", file=sys.stderr)
                return 2

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


def check_kit_identity(root: Path, source: Path) -> list[str]:
    """Fail closed when the installation cannot prove which Kit it came from.

    Equal version numbers are not evidence. The documented upgrade rule is that
    a same-version run still checks for drift, and this is that check: it
    compares the recorded Kit fingerprint with the checkout being run and the
    recorded digest of every canonical resource with the installed bytes.
    """
    identity = read_kit_identity(root)
    if identity is None:
        return [
            f"kit identity missing: {layout.relative('kit_identity')} does not record the installed Kit content; "
            "run `hek init --apply` from the Kit checkout you intend to run"
        ]
    actions = source_actions(source, root, 1, detect_status(root), None)
    drift = content_drift(source, root, actions)
    digest = source_fingerprint(source)
    recorded = recorded_fingerprint(root)
    failures: list[str] = []
    if recorded != digest or drift["missing"] or drift["modified"]:
        examples = drift_examples(drift)
        failures.append(
            f"kit content drift: installed {recorded[:12]} does not match Kit {digest[:12]}"
            + (f" (differing: {examples})" if examples else "")
            + "; run `hek init --apply` from the Kit checkout you intend to run"
        )
    recorded_version = identity.get("version")
    installed_version = read_version(installed_version_path(root))
    if isinstance(recorded_version, str) and recorded_version != installed_version:
        failures.append(
            f"kit identity records version {recorded_version} but {layout.relative('version')} says "
            f"{installed_version or 'unknown'}"
        )
    return failures


def run_check(root: Path, source: Path, agent: str | None = None) -> tuple[int, list[str]]:
    """Prove the installation matches the Kit it claims to be running."""
    context_files = ("AGENTS.md", "CLAUDE.md", "GEMINI.md") if agent is None else (str(agent_target(agent)["root_file"]),)
    failures: list[str] = check_kit_identity(root, source)
    checks = [
        ("check_root_context.py", ["check_root_context.py", str(root), "--context-file", *context_files]),
        ("check_context_docs.py", ["check_context_docs.py", str(root)]),
        ("check_agent_policy.py", ["check_agent_policy.py", str(layout.policy_path(root))]),
        ("check_profile.py", ["check_profile.py", str(layout.profile_path(root))]),
        ("resolve_context.py", ["resolve_context.py", "--root", str(root), "."]),
        ("context_cache.py benchmark", ["context_cache.py", "benchmark", "--root", str(root), "--target", ".", "--iterations", "1000", "--json"]),
        ("check_fitness_protection.py", ["check_fitness_protection.py", "--root", str(root)]),
        ("check_change_workspace.py", ["check_change_workspace.py", "--root", str(root)]),
    ]
    # A single repository without an identity keeps the pre-federation behaviour:
    # the check is skipped rather than failing on a file the project never had.
    if identity_check_required(root):
        checks.append(("check_identity.py", ["check_identity.py", "--root", str(root)]))
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
        # Decode as UTF-8 explicitly: the locale codec (GBK on a Chinese Windows)
        # raises inside the reader thread and truncates the reported failure.
        completed = subprocess.run(
            [sys.executable, str(script), *command[1:]], cwd=root,
            text=True, encoding="utf-8", errors="replace", capture_output=True,
        )
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
    print(f"Receipt: {ONBOARDING_RECEIPT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--source-root", "--source", dest="source_root", type=Path, help="Harness kit checkout; defaults to this script's repository")
    parser.add_argument("--agent", choices=tuple(AGENT_TARGETS))
    parser.add_argument("--tier", type=int, choices=(1, 2), default=2)
    parser.add_argument("--unit-id", help="Draft .hek/project/identity.yaml for this workspace unit")
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

    try:
        root = project_root(args.project_root)
    except WorkspaceRootError as exc:
        print(f"HARNESS ONBOARDING ERROR: {exc}", file=sys.stderr)
        return 2
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
    installed_version = read_version(installed_version_path(root))
    target_version = read_version(source / "VERSION")
    version_relation = classify_versions(installed_version, target_version)
    if installed_version is None and status != "fresh":
        version_relation = "unversioned"
    unit_id = args.unit_id.strip() if args.unit_id else None
    if unit_id and not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", unit_id):
        print("HARNESS ONBOARDING ERROR: --unit-id must match ^[a-z0-9][a-z0-9-]{1,63}$", file=sys.stderr)
        return 2
    actions = source_actions(source, root, effective_tier, status, agent, unit_id)
    plan = render_plan(root, source, effective_tier, status, actions, agent, installed_version, target_version)
    if status == "relayout":
        plan["migration_required"] = True

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
        identity_values = (
            {
                "unit_id": unit_id,
                "workspace_id": root.name,
                "unit_kind": "backend",
                "repo_url": git_remote_url(root),
            }
            if unit_id
            else None
        )
        try:
            plan["results"] = apply_actions(root, source, actions, identity=identity_values)
        except (OSError, shutil.Error) as exc:
            plan["errors"] = [f"apply failed and rolled back: {exc}"]
            if args.as_json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print(f"HARNESS ONBOARDING FAILED AND ROLLED BACK: {exc}", file=sys.stderr)
            return 2
        receipt = root / ONBOARDING_RECEIPT
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.check:
        code, failures = run_check(root, source, agent)
        plan["check"] = {"status": "passed" if not failures else "failed", "failures": failures}
        receipt = root / ONBOARDING_RECEIPT
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
        if status == "relayout":
            # Migrating relocates project-owned content and deletes the superseded
            # tree, so it never runs without an explicit --apply.
            print("Read-only migration plan: this project still uses the pre-0.6 layout.")
            print("Review the moves and deletions above, then rerun with --apply to migrate.")
            return 2
        print("Read-only plan. Ask the user for confirmation, then rerun with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
