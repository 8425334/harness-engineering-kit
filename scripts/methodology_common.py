#!/usr/bin/env python3
"""Shared primitives for the Engineering change lifecycle."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def meaningful(path: Path) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8").strip()
    return bool(content) and "{{" not in content and "}}" not in content


def spec_files(change_dir: Path) -> list[Path]:
    return sorted(path for path in (change_dir / "specs").glob("*/spec.md") if path.is_file())


def contract_files(change_dir: Path) -> list[Path]:
    return [
        change_dir / "context-pack.md",
        change_dir / "impact-analysis.md",
        change_dir / "context-impact.json",
        change_dir / "proposal.md",
        *spec_files(change_dir),
        change_dir / "design.md",
        change_dir / "tasks.md",
    ]


def relative_digests(change_dir: Path, files: list[Path]) -> dict[str, str]:
    return {str(path.relative_to(change_dir)): sha256(path) for path in files}


def append_event(change_dir: Path, event: dict[str, Any], update_record: bool = True) -> None:
    evidence_dir = change_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with (evidence_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    if update_record:
        record_path = change_dir / "change.json"
        record = read_json(record_path)
        record.setdefault("events", []).append(event)
        record["updated_at"] = event["at"]
        write_json(record_path, record)


def append_failure_event(change_dir: Path, failure: dict[str, Any]) -> None:
    """Append a normalized failure without changing the lifecycle state."""
    evidence_dir = change_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with (evidence_dir / "failure-events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(failure, ensure_ascii=False) + "\n")
