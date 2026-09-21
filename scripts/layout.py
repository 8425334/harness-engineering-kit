#!/usr/bin/env python3
"""Single source of truth for where Harness resources live in a host project.

Every control script used to hardcode the installed layout independently, so a
layout change meant editing dozens of files and any script that was missed kept
silently reading the old location. This module centralises that knowledge.

Two layouts are described:

``LEGACY``
    The pre-0.6 spread: ``docs/methodology/**``, ``docs/fitness/**``, and root
    ``ai.json`` / ``AI.md``. Still what ``ACTIVE`` resolves to until the
    single-directory layout is switched on.

``HEK``
    The single ``.hek/`` directory. ``openspec/`` stays at the repository root in
    both layouts because OpenSpec resolves its own root by walking up from the
    current directory.

``ACTIVE`` selects the layout that :func:`engineering_root` and the accessors
resolve to. The migration planner reads both through the explicit ``layout``
argument, so the table is not throwaway: it is exactly the old→new mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    """Project-relative locations of every Harness-owned artifact."""

    root: str
    #: Directory whose presence means "Harness is installed in this project".
    control_plane: str
    methodology: str
    #: Directory holding the project-owned policy documents. Coincides with
    #: ``methodology`` in the legacy layout, but they are separate concepts:
    #: those documents must survive an upgrade that replaces the methodology.
    policy_dir: str
    fitness: str
    context_index: str
    context_root: str
    version: str
    onboarding_receipt: str
    uninstall_receipt: str
    repair_receipt: str
    kit_identity: str
    lessons: str
    core: str
    scripts: str
    change_templates: str
    compaction: str
    production_changes: str
    production_audit: str
    production_policy: str
    production_readme: str
    production_template: str
    fitness_ledger: str


#: Pre-0.6 layout. Kept because the migration must read it to compute moves.
LEGACY = Layout(
    root=".",
    control_plane="docs/methodology",
    methodology="docs/methodology",
    policy_dir="docs/methodology",
    fitness="docs/fitness",
    context_index="ai.json",
    # A path document sits next to the code it describes, so the legacy search
    # root is the whole repository rather than one directory.
    context_root=".",
    version="docs/methodology/VERSION",
    onboarding_receipt="docs/methodology/onboarding.json",
    uninstall_receipt="docs/methodology/uninstall.json",
    repair_receipt="docs/methodology/repair.json",
    kit_identity="docs/methodology/kit-identity.json",
    lessons="docs/methodology/lessons",
    core="docs/methodology/core",
    scripts="docs/methodology/scripts",
    change_templates="docs/methodology/change-templates",
    compaction="docs/methodology/compaction",
    production_changes="docs/methodology/production/changes",
    production_audit="docs/methodology/production/audit",
    production_policy="docs/methodology/production/policy.yaml",
    production_readme="docs/methodology/production/README.md",
    production_template="docs/methodology/production/change-record.template.json",
    fitness_ledger="docs/fitness/verification-ledger.md",
)

#: Single-directory layout. Everything Harness owns lives under ``.hek/``.
HEK = Layout(
    root=".hek",
    control_plane=".hek",
    methodology=".hek/kit",
    policy_dir=".hek/project",
    fitness=".hek/fitness",
    context_index=".hek/context/ai.json",
    context_root=".hek/context",
    version=".hek/VERSION",
    onboarding_receipt=".hek/state/onboarding.json",
    uninstall_receipt=".hek/state/uninstall.json",
    repair_receipt=".hek/state/repair.json",
    kit_identity=".hek/state/kit-identity.json",
    lessons=".hek/state/lessons",
    core=".hek/kit/core",
    scripts=".hek/kit/scripts",
    change_templates=".hek/kit/change-templates",
    compaction=".hek/kit/compaction",
    production_changes=".hek/project/production/changes",
    production_audit=".hek/project/production/audit",
    production_policy=".hek/project/production/policy.yaml",
    production_readme=".hek/project/production/README.md",
    production_template=".hek/project/production/change-record.template.json",
    fitness_ledger=".hek/fitness/verification-ledger.md",
)

#: Which layout the accessors resolve to.
ACTIVE = HEK

#: Release that switches :data:`ACTIVE` to :data:`HEK`.
TARGET_VERSION = "0.6.0"


#: Present only in the Kit's own checkout, never in an installed copy.
KIT_CHECKOUT_MARKER = ("templates", "engineering", "SKILL.md")

#: Both install layouts place the control scripts at the same depth:
#: ``<root>/docs/methodology/scripts`` and ``<root>/.hek/kit/scripts``.
INSTALLED_SCRIPTS_DEPTH = 3


def is_kit_checkout(directory: Path) -> bool:
    """True when ``directory`` is a Kit source tree rather than an installation."""
    return directory.joinpath(*KIT_CHECKOUT_MARKER).is_file()


def project_root(explicit: Path | str | None = None) -> Path:
    """Return the host project root.

    ``explicit`` always wins. Otherwise the caller's own location is used so that
    a script installed without ``--root`` still finds the project:

    * Kit checkout — ``layout.py`` sits in ``<repo>/scripts/``, one level down.
    * Installed — it sits three levels down, the same distance in both layouts,
      which is what makes one expression cover both.
    """
    if explicit is not None:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    checkout = here.parents[1]
    if is_kit_checkout(checkout):
        return checkout
    if len(here.parents) > INSTALLED_SCRIPTS_DEPTH:
        return here.parents[INSTALLED_SCRIPTS_DEPTH]
    return checkout


def _rel(layout: Layout, attribute: str, module_path: str | None = None) -> str:
    """Return the project-relative path for ``attribute``.

    ``context_doc`` is the one entry that depends on the module being described,
    so it is routed here rather than exposed as a plain field.
    """
    if attribute == "context_doc":
        root = layout.context_root
        prefix = "" if root in (".", "") else f"{root}/"
        if module_path in (None, "", "."):
            return f"{prefix}AI.md"
        return f"{prefix}{str(module_path).strip('/')}/AI.md"
    return str(getattr(layout, attribute))


def path(attribute: str, root: Path | str | None = None, *, module_path: str | None = None,
         layout: Layout | None = None) -> Path:
    """Resolve a Harness artifact to an absolute path."""
    active = layout if layout is not None else ACTIVE
    return project_root(root) / _rel(active, attribute, module_path)


def relative(attribute: str, *, module_path: str | None = None, layout: Layout | None = None) -> str:
    """Return the project-relative (POSIX) path, for contracts and messages."""
    return _rel(layout if layout is not None else ACTIVE, attribute, module_path)


# Named accessors. Scripts call these instead of writing literals so that the
# next layout change touches this file only.

POLICY_NAME = "agent-policy.yaml"
PROFILE_NAME = "profile.yaml"
IDENTITY_NAME = "identity.yaml"
CONTRACTS_DIR_NAME = "contracts"


def policy_rel(*, layout: Layout | None = None) -> str:
    """Project-relative path of the agent policy, as stored in contracts."""
    return f"{relative('policy_dir', layout=layout)}/{POLICY_NAME}"


def profile_rel(*, layout: Layout | None = None) -> str:
    """Project-relative path of the methodology profile."""
    return f"{relative('policy_dir', layout=layout)}/{PROFILE_NAME}"


def identity_rel(*, layout: Layout | None = None) -> str:
    """Project-relative path of the unit self-description (federation identity)."""
    return f"{relative('policy_dir', layout=layout)}/{IDENTITY_NAME}"


def contracts_dir_rel(*, layout: Layout | None = None) -> str:
    """Project-relative directory holding local contract snapshots."""
    return f"{relative('policy_dir', layout=layout)}/{CONTRACTS_DIR_NAME}"


def policy_path(root: Path | str | None = None, *, layout: Layout | None = None) -> Path:
    return project_root(root) / policy_rel(layout=layout)


def profile_path(root: Path | str | None = None, *, layout: Layout | None = None) -> Path:
    return project_root(root) / profile_rel(layout=layout)


def identity_path(root: Path | str | None = None, *, layout: Layout | None = None) -> Path:
    return project_root(root) / identity_rel(layout=layout)


def contracts_dir(root: Path | str | None = None, *, layout: Layout | None = None) -> Path:
    return project_root(root) / contracts_dir_rel(layout=layout)


def protected_prefix(*, layout: Layout | None = None) -> str:
    """Pathspec for the protected Fitness control plane."""
    return f"{relative('fitness', layout=layout)}/"


def fitness_script_rel(*, layout: Layout | None = None) -> str:
    """Path of the Fitness runner.

    Evidence records the command that was actually run and the phase gate matches
    that string, so the installer and the gate must derive it from one place.
    """
    return f"{relative('fitness', layout=layout)}/scripts/fitness.py"


def receipt_path(root: Path | str | None = None, *, layout: Layout | None = None) -> Path:
    return path("onboarding_receipt", root, layout=layout)


def kit_identity_path(root: Path | str | None = None, *, layout: Layout | None = None) -> Path:
    """Path of the record that says which Kit content this project installed."""
    return path("kit_identity", root, layout=layout)


def context_doc_path(root: Path | str | None, module_path: str | None = None,
                     *, layout: Layout | None = None) -> Path:
    return path("context_doc", root, module_path=module_path, layout=layout)
