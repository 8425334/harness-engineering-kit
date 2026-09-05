#!/usr/bin/env python3
"""Shared primitives for the Engineering change lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically replace ``path`` so a crash never leaves a truncated record."""
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f"{path.name}.", suffix=".tmp", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


@contextmanager
def file_lock(path: Path, timeout: float = 30.0, stale_after: float = 60.0) -> Iterator[None]:
    """Best-effort exclusive lock guarding a read-modify-write of ``path``.

    Concurrent scripts (gate failures, state transitions, lesson approvals) mutate
    the same JSON records; the lock serializes those sequences.  A lock older than
    ``stale_after`` seconds belonged to a crashed holder and is broken, and a lock
    that still cannot be acquired within ``timeout`` is force-broken so that
    availability wins over perfect exclusion.  Corruption is already impossible
    because :func:`write_json` replaces atomically; the lock only prevents lost
    updates.
    """
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    descriptor: int | None = None
    while True:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                try:  # one final attempt after breaking the stuck lock
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except OSError:
                    descriptor = None  # proceed unlocked rather than failing the caller
                break
            time.sleep(0.05)
    try:
        if descriptor is not None:
            os.close(descriptor)
        yield
    finally:
        if descriptor is not None:
            try:
                lock_path.unlink()
            except OSError:
                pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def meaningful(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return False
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


def append_event_line(change_dir: Path, event: dict[str, Any]) -> None:
    """Append one event line; the caller is responsible for holding the lock."""
    evidence_dir = change_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with (evidence_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def append_event(change_dir: Path, event: dict[str, Any], update_record: bool = True) -> None:
    record_path = change_dir / "change.json"
    with file_lock(record_path):
        append_event_line(change_dir, event)
        if update_record:
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
