"""Version and upgrade classification for Harness onboarding."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


_VERSION_PATTERN = re.compile(
    r"^v?(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()


def parse_version(value: str) -> Version:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid semantic version: {value!r}")
    prerelease_value = match.group("prerelease")
    prerelease = tuple(prerelease_value.split(".")) if prerelease_value else ()
    if any(item.isdigit() and len(item) > 1 and item.startswith("0") for item in prerelease):
        raise ValueError(f"invalid semantic version: {value!r}")
    return Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=prerelease,
    )


def _compare_prerelease(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_item, right_item in zip(left, right):
        if left_item == right_item:
            continue
        left_numeric = left_item.isdigit()
        right_numeric = right_item.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_item) > int(right_item) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_item > right_item else -1
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def compare_versions(left: Version, right: Version) -> int:
    left_core = (left.major, left.minor, left.patch)
    right_core = (right.major, right.minor, right.patch)
    if left_core != right_core:
        return 1 if left_core > right_core else -1
    return _compare_prerelease(left.prerelease, right.prerelease)


def read_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return "<invalid-version-file>"


def classify_versions(installed: str | None, target: str | None) -> str:
    if target is None:
        return "unknown-target"
    try:
        target_parsed = parse_version(target)
        installed_parsed = parse_version(installed) if installed is not None else None
    except ValueError:
        return "invalid"
    if installed_parsed is None:
        return "fresh"
    comparison = compare_versions(installed_parsed, target_parsed)
    if comparison < 0:
        return "upgrade"
    if comparison > 0:
        return "downgrade"
    return "same"


#: Recorded next to every fingerprint so a future change to the manifest rules
#: is visible in the installed record instead of silently reshaping digests.
KIT_FINGERPRINT_ALGORITHM = "sha256-kit-manifest-v1"

#: Kit sources that exist only for development. They are never installed, so
#: they must not make two installations of the same release look different.
KIT_DEV_ONLY_SCRIPTS = frozenset({"smoke_test_skills.py"})

#: Shipped trees whose bytes decide install and upgrade behaviour. Documentation,
#: examples, and tests are deliberately excluded: editing them changes no
#: installed file and must not make a Kit look like a different release.
KIT_ASSET_TREES = ("bin", "core", "migrations", "scripts", "templates")
KIT_ASSET_FILES = ("VERSION",)
MANIFEST_EXCLUDED_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"})


def kit_manifest(source: Path) -> dict[str, str]:
    """Map every shipped Kit asset to its SHA-256 digest.

    A version number states what a release is called; this manifest states what
    it contains. Equal versions with different bytes produce different
    manifests, which is the fact a same-version upgrade has to act on.
    """
    manifest: dict[str, str] = {}
    for relative in KIT_ASSET_FILES:
        path = source / relative
        if path.is_file() and not path.is_symlink():
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for tree in KIT_ASSET_TREES:
        base = source / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in MANIFEST_EXCLUDED_PARTS for part in path.relative_to(base).parts):
                continue
            if tree == "scripts" and path.parent == base and path.name in KIT_DEV_ONLY_SCRIPTS:
                continue
            manifest[path.relative_to(source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def manifest_fingerprint(manifest: dict[str, str]) -> str:
    """Collapse a manifest into one stable digest."""
    payload = json.dumps(sorted(manifest.items()), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_fingerprint(source: Path) -> str:
    """Content identity of a Kit checkout, independent of its version number."""
    return manifest_fingerprint(kit_manifest(source))
