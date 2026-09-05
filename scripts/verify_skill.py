#!/usr/bin/env python3
"""Verify the Harness availability contract for a project-local Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


PLATFORMS = {
    "claude": (Path(".claude/skills"), Path.home() / ".claude/skills"),
    "codex": (Path(".agents/skills"), Path.home() / ".codex/skills"),
    "opencode": (Path(".opencode/skills"), Path.home() / ".config/opencode/skills"),
}
REQUIRED_MANIFEST_KEYS = ("name", "version", "entry", "platforms", "required_sections", "fallback")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_frontmatter(content: str) -> tuple[dict[str, str], list[str]]:
    if not content.startswith("---\n"):
        return {}, ["frontmatter must start with ---"]
    end = content.find("\n---", 4)
    if end < 0:
        return {}, ["frontmatter closing --- is missing"]
    fields: dict[str, str] = {}
    for line in content[4:end].splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.+?)\s*$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip().strip('"')
    errors = [f"frontmatter missing {key}" for key in ("name", "description") if not fields.get(key)]
    return fields, errors


def read_flat_yaml(path: Path) -> tuple[dict[str, object], list[str]]:
    data: dict[str, object] = {}
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {}, [str(exc)]
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            errors.append(f"invalid flat manifest/profile line: {line}")
            continue
        key, raw = line.split(":", 1)
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            data[key.strip()] = [item.strip().strip("'\"") for item in raw[1:-1].split(",") if item.strip()]
        else:
            data[key.strip()] = raw.strip("'\"")
    return data, errors


def source_files(source_dir: Path) -> list[Path]:
    files = [source_dir / "SKILL.md", source_dir / "manifest.yaml"]
    files.extend(sorted((source_dir / "references").glob("*.md")))
    files.extend(sorted((source_dir / "profiles").glob("*.yaml")))
    return files


def validate_source(skill: str, source_dir: Path, version: str | None) -> tuple[dict[str, object], list[str], dict[str, str]]:
    errors: list[str] = []
    manifest, manifest_errors = read_flat_yaml(source_dir / "manifest.yaml")
    errors.extend(manifest_errors)
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"manifest missing {key}")
    if manifest.get("name") != skill:
        errors.append("manifest name does not match Skill")
    if version and manifest.get("version") != version:
        errors.append("manifest version does not match methodology VERSION")
    if manifest.get("platforms") != ["claude", "codex", "opencode"]:
        errors.append("manifest platforms must be [claude, codex, opencode]")

    entry = source_dir / str(manifest.get("entry", "SKILL.md"))
    if not entry.is_file():
        errors.append(f"source entry missing: {entry}")
    else:
        content = entry.read_text(encoding="utf-8")
        fields, frontmatter_errors = parse_frontmatter(content)
        errors.extend(frontmatter_errors)
        if fields.get("name") != skill:
            errors.append("frontmatter name does not match Skill")
        sections = manifest.get("required_sections", [])
        if not isinstance(sections, list):
            errors.append("required_sections must be a list")
        else:
            for section in sections:
                if not re.search(rf"^##\s+{re.escape(str(section))}\s*$", content, re.MULTILINE):
                    errors.append(f"source missing required section: {section}")

    for mode in ("backend", "frontend", "fullstack"):
        profile_path = source_dir / "profiles" / f"{mode}.yaml"
        profile, profile_errors = read_flat_yaml(profile_path)
        errors.extend(f"{mode} profile: {error}" for error in profile_errors)
        if profile.get("mode") != mode:
            errors.append(f"{mode} profile has invalid mode")
        reference = profile.get("reference")
        if not reference or not (source_dir / str(reference)).is_file():
            errors.append(f"{mode} profile reference is missing")

    expected: dict[str, str] = {}
    for path in source_files(source_dir):
        if not path.is_file():
            errors.append(f"required source file missing: {path}")
        else:
            expected[str(path.relative_to(source_dir))] = digest(path)
    return manifest, errors, expected


def verify(skill: str, project_root: Path, platform: str, source_only: bool = False, source_root: Path | None = None) -> dict[str, object]:
    methodology_root = source_root.resolve() if source_root else Path(__file__).resolve().parent.parent
    source_dir = methodology_root / "templates" / skill
    if not source_dir.is_dir():
        # Installed copies live at docs/methodology/scripts/ with no templates/
        # sibling; they must not emit a wall of misleading "missing file" errors.
        return {
            "skill": skill,
            "platform": platform,
            "checks": {},
            "errors": [f"Skill source not found: {source_dir}. Run from a kit checkout or pass --source-root."],
            "status": "FAIL",
        }
    version_path = methodology_root / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else None
    manifest, errors, expected = validate_source(skill, source_dir, version)
    checks: dict[str, object] = {
        "availability_contract": "PASS" if not errors else "FAIL",
        "source_files": expected,
    }
    result: dict[str, object] = {"skill": skill, "platform": platform, "checks": checks, "errors": errors}
    if source_only:
        result["status"] = "PASS" if not errors else "FAIL"
        return result

    local_base, global_base = PLATFORMS[platform]
    candidates = (("local", project_root / local_base / skill), ("global", global_base / skill))
    discovered = next(((kind, path) for kind, path in candidates if (path / "SKILL.md").is_file()), None)
    if not discovered:
        errors.append(f"Skill is not discoverable for platform {platform}")
        checks["discoverable"] = "FAIL"
    else:
        kind, installed_dir = discovered
        checks["discoverable"] = f"PASS ({kind}: {installed_dir})"
        install_errors = 0
        for relative, expected_digest in expected.items():
            installed = installed_dir / relative
            if not installed.is_file():
                errors.append(f"installed Skill missing: {installed}")
                install_errors += 1
            elif digest(installed) != expected_digest:
                errors.append(f"installed Skill differs from source: {installed}")
                install_errors += 1
        installed_manifest, installed_errors = read_flat_yaml(installed_dir / "manifest.yaml")
        errors.extend(f"installed manifest: {error}" for error in installed_errors)
        if installed_manifest != manifest:
            errors.append("installed availability contract differs from source")
            install_errors += 1
        checks["content_digest"] = "PASS" if not install_errors and not installed_errors else "FAIL"
    result["status"] = "PASS" if not errors else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", choices=("engineering",))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--platform", choices=sorted(PLATFORMS), default="claude")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    result = verify(args.skill, args.project_root.resolve(), args.platform, args.source_only, args.source_root)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"SKILL {result['status']}: {args.skill} ({args.platform})")
        for key, value in result["checks"].items():
            if key != "source_files":
                print(f"- {key}: {value}")
        for error in result["errors"]:
            print(f"- ERROR: {error}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
