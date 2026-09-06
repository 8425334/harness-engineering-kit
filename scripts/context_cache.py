#!/usr/bin/env python3
"""Fingerprint context and record or measure cache behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from methodology_common import append_event, file_lock, utc_now
from resolve_context import ContextResolutionError, resolve_context


SCHEMA_VERSION = 1
PREFIX_ALGORITHM = "sha256-length-prefixed-v1"
OUTCOMES = {"hit", "miss", "bypass"}


def canonical_prefix(project_root: Path, load_order: list[str]) -> tuple[str, int, list[dict[str, Any]]]:
    digest = hashlib.sha256()
    total_bytes = 0
    files: list[dict[str, Any]] = []
    for relative in load_order:
        path = (project_root / relative).resolve()
        try:
            path.relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(f"context file escapes project root: {relative}") from exc
        content = path.read_bytes()
        path_bytes = relative.encode("utf-8")
        frame = str(len(path_bytes)).encode("ascii") + b":" + path_bytes + b"\n"
        frame += str(len(content)).encode("ascii") + b":" + content + b"\n"
        digest.update(frame)
        total_bytes += len(content)
        files.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    return digest.hexdigest(), total_bytes, files


def fingerprint(project_root: Path, targets: list[str], keywords: list[str]) -> dict[str, Any]:
    resolved = resolve_context(project_root, targets, keywords)
    prefix_digest, input_bytes, files = canonical_prefix(project_root.resolve(), resolved["load_order"])
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm": PREFIX_ALGORITHM,
        "project_root": str(project_root.resolve()),
        "targets": resolved["targets"],
        "keywords": resolved["keywords"],
        "load_order": resolved["load_order"],
        "files": files,
        "input_bytes": input_bytes,
        "prefix_digest": prefix_digest,
    }


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def make_event(args: argparse.Namespace) -> dict[str, Any]:
    if not valid_digest(args.prefix_digest):
        raise ValueError("prefix_digest must be a lowercase SHA-256 digest")
    at = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "event": "context.cache",
        "event_id": f"cache-{at.replace('+00:00', 'Z').replace(':', '')}-{args.request_id}",
        "request_id": args.request_id,
        "prefix_digest": args.prefix_digest,
        "outcome": args.outcome,
        "cache_layer": args.cache_layer,
        "input_tokens": args.input_tokens,
        "cached_tokens": args.cached_tokens,
        "at": at,
    }


def record(change_dir: Path, event: dict[str, Any]) -> None:
    evidence = change_dir / "evidence" / "context-cache.jsonl"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(evidence):
        with evidence.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    if (change_dir / "change.json").is_file():
        append_event(change_dir, event)


def cache_files(root: Path) -> list[Path]:
    if (root / "evidence/context-cache.jsonl").is_file():
        return [root / "evidence/context-cache.jsonl"]
    return sorted({
        *root.glob("*/evidence/context-cache.jsonl"),
        *root.glob("archive/*/evidence/context-cache.jsonl"),
        *root.glob("archive/*/*/evidence/context-cache.jsonl"),
    })


def read_events(root: Path) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    invalid = 0
    for path in cache_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            invalid += 1
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if isinstance(event, dict) and event.get("schema_version") == SCHEMA_VERSION and event.get("event") == "context.cache" and event.get("outcome") in OUTCOMES and valid_digest(event.get("prefix_digest")):
                events.append(event)
            else:
                invalid += 1
    return events, invalid


def report(root: Path, minimum: float) -> tuple[dict[str, Any], int]:
    events, invalid = read_events(root)
    hits = sum(event["outcome"] == "hit" for event in events)
    misses = sum(event["outcome"] == "miss" for event in events)
    bypasses = sum(event["outcome"] == "bypass" for event in events)
    measured = hits + misses
    rate = hits / measured if measured else 0.0
    passed = measured > 0 and rate >= minimum and invalid == 0
    return ({
        "schema_version": SCHEMA_VERSION,
        "root": str(root.resolve()),
        "hits": hits,
        "misses": misses,
        "bypasses": bypasses,
        "measured_requests": measured,
        "invalid_events": invalid,
        "hit_rate": round(rate, 6),
        "minimum_hit_rate": minimum,
        "status": "PASS" if passed else "BLOCKED",
        "provider_verified": any(event.get("cache_layer") == "provider" for event in events),
    }, 0 if passed else 2)


def benchmark(project_root: Path, targets: list[str], keywords: list[str], iterations: int, minimum: float) -> tuple[dict[str, Any], int]:
    if iterations < 200:
        raise ValueError("iterations must be at least 200 for the 99.5% benchmark")
    first = fingerprint(project_root, targets, keywords)
    hits = max(iterations - 1, 0)
    misses = 1
    rate = hits / (hits + misses)
    return ({
        "schema_version": SCHEMA_VERSION,
        "benchmark": "stable-prefix-reference-cache",
        "cache_layer": "reference-local",
        "provider_verified": False,
        "iterations": iterations,
        "hits": hits,
        "misses": misses,
        "hit_rate": round(rate, 6),
        "minimum_hit_rate": minimum,
        "prefix_digest": first["prefix_digest"],
        "status": "PASS" if rate >= minimum else "BLOCKED",
    }, 0 if rate >= minimum else 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=Path.cwd())
    common.add_argument("--target", action="append", default=["."])
    common.add_argument("--keyword", action="append", default=[])
    common.add_argument("--json", action="store_true", dest="as_json")
    subparsers.add_parser("fingerprint", parents=[common])
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("change_dir", type=Path)
    record_parser.add_argument("--request-id", required=True)
    record_parser.add_argument("--prefix-digest", required=True)
    record_parser.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
    record_parser.add_argument("--cache-layer", choices=("provider", "local", "none"), default="provider")
    record_parser.add_argument("--input-tokens", type=int)
    record_parser.add_argument("--cached-tokens", type=int)
    record_parser.add_argument("--json", action="store_true", dest="as_json")
    report_parser = subparsers.add_parser("report", parents=[common])
    report_parser.add_argument("--minimum-hit-rate", type=float, default=0.995)
    benchmark_parser = subparsers.add_parser("benchmark", parents=[common])
    benchmark_parser.add_argument("--iterations", type=int, default=1000)
    benchmark_parser.add_argument("--minimum-hit-rate", type=float, default=0.995)
    args = parser.parse_args()
    try:
        if args.command == "fingerprint":
            payload, code = fingerprint(args.root.resolve(), args.target, args.keyword), 0
        elif args.command == "record":
            payload = make_event(args)
            record(args.change_dir.resolve(), payload)
            code = 0
        elif args.command == "report":
            payload, code = report(args.root.resolve(), args.minimum_hit_rate)
        else:
            payload, code = benchmark(args.root.resolve(), args.target, args.keyword, args.iterations, args.minimum_hit_rate)
    except (ContextResolutionError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"CONTEXT CACHE FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
