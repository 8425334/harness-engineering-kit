#!/usr/bin/env python3
"""Structural boundary guard for workspace federation (spec section 5.10).

Only Git and filesystem facts decide ownership:

* ``git -C <target> rev-parse --show-toplevel``
* ``git -C <target> rev-parse --show-superproject-working-tree``
* ``.git`` may be a directory (normal clone) or a file (worktree/submodule)
* the harness root is the first ancestor directory holding ``.hek/VERSION``,
  and that directory must be a Git top level

Directory names (``docs/methodology``, ``docs/sdd``), file names (``ai.json``,
``AI.md``) and version file contents never decide ownership.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


BLOCKED = "blocked"
WARNING = "warning"
INFO = "info"
LEVEL_RANK = {BLOCKED: 0, WARNING: 1, INFO: 2}

HARNESS_VERSION_REL = ".hek/VERSION"
POLICY_REL = ".hek/project/agent-policy.yaml"
WAIVERS_REL = ".hek/state/waivers"

#: Safety bound for the unbounded-style nesting walk. Real projects nest a unit
#: one or two levels deep; anything beyond this is pathological, but the walk is
#: still bounded so a runaway tree cannot hang a required check. The bound is
#: deliberately far above the previous fixed value of 3, which silently let a
#: unit nested four levels down pass verification.
NESTING_SCAN_LIMIT = 64

#: Directory names that never hold a unit repository worth enumerating.
PRUNE_DIRS = frozenset(
    {
        ".git", ".hek", ".hg", ".svn", ".idea", ".vscode",
        "node_modules", "target", "build", "dist", "out",
        ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    }
)


@dataclass(frozen=True)
class Diagnostic:
    """One machine-readable finding produced by discover/verify/guard."""

    level: str
    code: str
    message: str
    unit_id: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"level": self.level, "code": self.code, "message": self.message}
        if self.unit_id:
            payload["unit_id"] = self.unit_id
        return payload


def sort_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(
        diagnostics,
        key=lambda item: (LEVEL_RANK.get(item.level, 9), item.code, item.unit_id or "", item.message),
    )


def has_blocked(diagnostics: list[Diagnostic]) -> bool:
    return any(item.level == BLOCKED for item in diagnostics)


class GitError(RuntimeError):
    """Raised when a Git fact cannot be established for a path."""


def _git(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return 127, ""
    return completed.returncode, (completed.stdout or "").strip()


def existing_ancestor(path: Path) -> Path:
    """Nearest existing ancestor of ``path`` (``path`` itself when it exists)."""
    candidate = path if path.is_absolute() else (Path.cwd() / path)
    candidate = Path(os.path.abspath(candidate))
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return candidate
        candidate = parent
    return candidate


def git_toplevel(path: Path | str) -> Path | None:
    """Return the Git top level containing ``path``, or ``None`` outside Git."""
    target = existing_ancestor(Path(path))
    if target.is_file():
        target = target.parent
    code, output = _git(["rev-parse", "--show-toplevel"], target)
    if code != 0 or not output:
        return None
    resolved = Path(output.splitlines()[0].strip())
    try:
        return resolved.resolve()
    except OSError:
        return resolved


def git_superproject(path: Path | str) -> Path | None:
    """Return the superproject top level when ``path`` is a submodule."""
    target = existing_ancestor(Path(path))
    if target.is_file():
        target = target.parent
    code, output = _git(["rev-parse", "--show-superproject-working-tree"], target)
    if code != 0 or not output:
        return None
    resolved = Path(output.splitlines()[0].strip())
    return resolved.resolve() if resolved.exists() else resolved


def git_tracked(repo: Path, relative: str) -> bool:
    """True when ``relative`` is tracked by the repository at ``repo``."""
    code, _ = _git(["ls-files", "--error-unmatch", "--", relative], repo)
    return code == 0


def is_git_repo(path: Path) -> bool:
    """A Git work tree root, whether ``.git`` is a directory or a pointer file."""
    marker = path / ".git"
    return marker.is_dir() or marker.is_file()


def locate_harness_root(path: Path | str) -> Path | None:
    """First ancestor of ``path`` holding ``.hek/VERSION``; must be a Git root."""
    candidate = existing_ancestor(Path(path))
    if candidate.is_file():
        candidate = candidate.parent
    for directory in [candidate, *candidate.parents]:
        if (directory / HARNESS_VERSION_REL).is_file():
            return directory
    return None


def find_repos(root: Path | str, depth: int = 1) -> list[Path]:
    """Enumerate Git work tree roots: ``root`` itself plus ``depth`` levels below."""
    start = Path(root)
    if not start.exists():
        return []
    start = start.resolve()
    found: list[Path] = []

    def walk(directory: Path, level: int) -> None:
        if is_git_repo(directory):
            found.append(directory)
        if level >= depth:
            return
        try:
            children = sorted(directory.iterdir())
        except OSError:
            return
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            if child.name in PRUNE_DIRS or child.name.startswith("."):
                continue
            walk(child, level + 1)

    walk(start, 0)
    seen: set[Path] = set()
    unique: list[Path] = []
    for repo in found:
        if repo not in seen:
            seen.add(repo)
            unique.append(repo)
    return unique


def nested_repos_inside(repo: Path, depth: int | None = None) -> list[Path]:
    """Git work tree roots nested inside ``repo`` (``repo`` excluded).

    Deliberately independent of candidate enumeration depth: a nested repository
    is a structural violation no matter how deep ``--depth`` reached. Descent
    stops at a found repository because that already proves the violation.
    """
    limit = NESTING_SCAN_LIMIT if depth is None else depth
    nested: list[Path] = []

    def walk(directory: Path, level: int) -> None:
        if level > limit:
            return
        try:
            children = sorted(directory.iterdir())
        except OSError:
            return
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            if child.name in PRUNE_DIRS or child.name.startswith("."):
                continue
            if is_git_repo(child):
                nested.append(child.resolve())
                # Deeper repositories add no new information: ``repo`` already
                # contains a unit, which is the violation being reported.
                continue
            walk(child, level + 1)

    walk(repo, 1)
    return nested


def nesting_pairs(repos: Iterable[Path]) -> set[tuple[Path, Path]]:
    """``(outer, inner)`` pairs where one repository contains the other."""
    resolved = sorted({Path(repo).resolve() for repo in repos})
    pairs: set[tuple[Path, Path]] = set()
    for outer in resolved:
        for inner in resolved:
            if inner != outer and inner.is_relative_to(outer):
                pairs.add((outer, inner))
    return pairs


def detect_nesting(repos: Iterable[Path]) -> list[Diagnostic]:
    """Pairwise nesting detection over an explicit repository list."""
    return [
        Diagnostic(BLOCKED, "unit.nested", f"unit repository {inner} is nested inside {outer}")
        for outer, inner in sorted(nesting_pairs(repos))
    ]


def _waiver_for(harness_root: Path) -> dict | None:
    """Return an active, machine-readable nesting waiver, if one exists."""
    directory = harness_root / WAIVERS_REL
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("nested-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        expires = str(payload.get("expires_at", "")).strip()
        approved = str(payload.get("approved_by", "")).strip()
        if not expires or not approved:
            continue
        try:
            deadline = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        except ValueError:
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline <= datetime.now(timezone.utc):
            continue
        payload["path"] = str(path)
        return payload
    return None


def guard(target: Path | str, session_root: Path | str) -> list[Diagnostic]:
    """Boundary guard for one write target.

    ``session_root`` decides which harness owns the session; ``target`` is the
    path the session wants to modify. Both nesting (N1) and cross-repository
    writes (N2) fail closed with exit code 2.
    """
    target_path = Path(target)
    session = Path(session_root)
    session_toplevel = git_toplevel(session)
    target_toplevel = git_toplevel(target_path)
    if target_toplevel is None:
        return [
            Diagnostic(
                BLOCKED,
                "boundary.cross-repo",
                f"target is not inside a Git repository: {target_path}",
            )
        ]
    if session_toplevel is None:
        return [
            Diagnostic(
                BLOCKED,
                "harness.mismatch",
                f"session root is not inside a Git repository: {session}",
            )
        ]

    if target_toplevel == session_toplevel:
        target_harness = locate_harness_root(target_path)
        session_harness = locate_harness_root(session)
        if target_harness is None or session_harness is None or target_harness != session_harness:
            return [
                Diagnostic(
                    BLOCKED,
                    "harness.mismatch",
                    (
                        "target and session root must share one harness root "
                        f"(target={target_harness}, session={session_harness})"
                    ),
                )
            ]
        return []

    if target_toplevel.is_relative_to(session_toplevel):
        waiver = _waiver_for(locate_harness_root(session) or session_toplevel)
        if waiver is not None:
            return [
                Diagnostic(
                    INFO,
                    "nesting.waived",
                    (
                        f"nesting allowed by waiver {waiver.get('id', 'nested')} "
                        f"until {waiver.get('expires_at')}"
                    ),
                )
            ]
        return [
            Diagnostic(
                BLOCKED,
                "nested.detected",
                (
                    f"target {target_toplevel} is a nested repository inside the "
                    f"session repository {session_toplevel}"
                ),
            )
        ]

    return [
        Diagnostic(
            BLOCKED,
            "boundary.cross-repo",
            (
                f"target {target_toplevel} is outside the session repository "
                f"{session_toplevel}; open a session in the owning repository"
            ),
        )
    ]
