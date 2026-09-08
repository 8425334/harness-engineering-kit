#!/usr/bin/env python3
"""Fail-closed gates for the canonical Engineering lifecycle."""

from __future__ import annotations

import argparse
import json
import re
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from check_agent_policy import validate as validate_agent_policy
from check_context_docs import validate_context_impact, validate_project as validate_context_docs
from check_design import validate as validate_design
from check_profile import read_project_profile, self_refine_max_iterations, self_refine_policy, validate as validate_profile
from check_production_readiness import rollout_cycles, validate as validate_production_record
from check_root_context import validate as validate_root_context
from check_execution import validate_execution
from lessons_common import lesson_matches, load_failure_events, load_lessons, validate_lesson
from methodology_common import contract_files, meaningful, read_json, relative_digests, sha256, spec_files
from requirement_reflection import validate as validate_requirement_reflection
from openspec_common import validate_orchestration


PHASES = ("EXPLORE", "SPEC", "DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE")
WHEN_PATTERN = re.compile(r"^(?:WHEN\s+|-\s+\*\*WHEN\*\*\s+)", re.MULTILINE)
THEN_PATTERN = re.compile(r"^(?:THEN\s+|-\s+\*\*THEN\*\*\s+)", re.MULTILINE)


def meaningful_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and "{{" not in value and "}}" not in value
    if isinstance(value, list):
        return bool(value) and all(meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(meaningful_value(key) and meaningful_value(item) for key, item in value.items())
    return value is not None


def is_exit_code(value: Any) -> bool:
    """A JSON ``false`` is not a zero exit code; require a real integer."""
    return isinstance(value, int) and not isinstance(value, bool)


def command_has_stage(command: Any, stage: str) -> bool:
    return isinstance(command, str) and bool(re.search(rf"(?:^|\s)--stage(?:=|\s+){re.escape(stage)}(?:\s|$)", command))


def command_has_option(command: Any, option: str) -> bool:
    return isinstance(command, str) and bool(re.search(rf"(?:^|\s)--{re.escape(option)}(?:=|\s+)", command))


def validate_command_evidence(project_root: Path, command: dict[str, Any], label: str, errors: list[str]) -> Path | None:
    evidence = command.get("evidence")
    expected_digest = command.get("evidence_sha256")
    if not meaningful_value(evidence) or not meaningful_value(expected_digest):
        errors.append(f"{label} requires evidence and evidence_sha256")
        return None
    path = (project_root / str(evidence)).resolve()
    try:
        path.relative_to(project_root.resolve())
    except ValueError:
        errors.append(f"{label} evidence escapes project root")
        return None
    if not path.is_file():
        errors.append(f"{label} evidence file is missing")
        return None
    if sha256(path) != expected_digest:
        errors.append(f"{label} evidence digest mismatch")
    return path


def validate_fitness_report(
    project_root: Path,
    change_dir: Path,
    command: dict[str, Any],
    stage: str,
    errors: list[str],
) -> None:
    report = validate_command_evidence(project_root, command, f"{stage} Fitness", errors)
    if report is None:
        return
    try:
        payload = read_json(report)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"{stage} Fitness evidence must be valid JSON")
        return
    if (
        payload.get("schema_version") != 1
        or payload.get("stage") != stage
        or payload.get("status") != "passed"
        or not isinstance(payload.get("total"), int)
        or payload.get("total", 0) < 1
        or not isinstance(payload.get("metrics"), list)
        or not payload.get("metrics")
        or payload.get("hard_gate_failures") != []
        or payload.get("dry_run") is not False
    ):
        errors.append(f"{stage} Fitness evidence must be a non-empty passed stage report")
    if not meaningful_value(payload.get("input_digest")):
        errors.append(f"{stage} Fitness evidence requires input_digest")
    else:
        change_id = payload.get("change_id")
        if change_id != change_dir.name:
            errors.append(f"{stage} Fitness evidence change_id must match the change directory")
        elif payload.get("input_digest") != fitness_input_digest(project_root, change_dir, stage):
            errors.append(f"{stage} Fitness evidence input_digest does not match current inputs")


def fitness_input_digest(project_root: Path, change_dir: Path, stage: str) -> str:
    entries: list[tuple[str, str]] = []
    rules_dir = project_root / "docs" / "fitness"
    for path in sorted(rules_dir.glob("*.md")):
        if path.name not in {"README.md", "verification-ledger.md"}:
            entries.append((path.relative_to(project_root).as_posix(), sha256(path)))
    if stage == "review":
        try:
            review = read_json(change_dir / "review-evidence.json")
        except (OSError, json.JSONDecodeError, ValueError):
            review = {}
        files = review.get("files") if isinstance(review, dict) else None
        if isinstance(files, dict):
            for relative in sorted(files):
                path = project_root / str(relative)
                entries.append((f"review:{relative}", sha256(path) if path.is_file() else "MISSING"))
    elif stage == "sync":
        for delta in sorted((change_dir / "specs").glob("*/spec.md")):
            capability = delta.parent.name
            for path, label in (
                (delta, f"delta:{capability}"),
                (change_dir / "evidence" / "pre-sync" / capability / "spec.md", f"before:{capability}"),
                (project_root / "openspec" / "specs" / capability / "spec.md", f"canonical:{capability}"),
            ):
                entries.append((label, sha256(path) if path.is_file() else "MISSING"))
    payload = json.dumps(sorted(entries), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def review_change_digest(project_root: Path, files: dict[str, Any]) -> str:
    """Digest the exact reviewed file set and their current contents."""
    normalized: list[dict[str, str]] = []
    for relative in sorted(files):
        expected = str(files[relative])
        lexical = project_root / relative
        if expected == "DELETED":
            content = "DELETED" if not lexical.exists() and not lexical.is_symlink() else "PRESENT"
        elif lexical.is_symlink():
            content = "SYMLINK:" + str(lexical.readlink())
        elif lexical.is_file():
            content = sha256(lexical)
        else:
            content = "MISSING"
        normalized.append({"path": relative, "expected": expected, "content": content})
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_event_store(change_dir: Path, record: dict[str, Any], errors: list[str]) -> None:
    path = change_dir / "evidence" / "events.jsonl"
    if not path.is_file():
        if record.get("events"):
            errors.append("evidence/events.jsonl is missing while governance.json contains events")
        return
    try:
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append("evidence/events.jsonl must contain valid JSON objects")
        return
    if not all(isinstance(item, dict) for item in lines):
        errors.append("evidence/events.jsonl must contain only JSON objects")
    elif lines != record.get("events", []):
        errors.append("governance.json events must exactly match evidence/events.jsonl")


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not meaningful_value(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def require_evidence_after(change_dir: Path, evidence: dict[str, Any], prerequisite: str, name: str, errors: list[str]) -> None:
    evidence_at = timestamp(evidence.get("at"))
    prerequisite_path = change_dir / prerequisite
    if evidence_at is None:
        errors.append(f"{name} at must be an ISO-8601 timestamp")
    elif not prerequisite_path.is_file():
        errors.append(f"{name} requires {prerequisite}")
    elif evidence_at.timestamp() < prerequisite_path.stat().st_mtime:
        errors.append(f"{name} must be created after {prerequisite}")


def validate_change_record(record: dict[str, Any], errors: list[str]) -> None:
    required = ("schema_version", "change_id", "title", "profile", "risk", "skill", "mode", "delivery_scope", "project_root", "owner")
    for field in required:
        if not meaningful_value(record.get(field)):
            errors.append(f"governance.json missing or placeholder: {field}")
    if record.get("schema_version") != 1:
        errors.append("governance.json schema_version must be 1")
    errors.extend(validate_orchestration(record))
    if record.get("skill") != "engineering":
        errors.append("governance.json skill must be engineering")
    if record.get("mode") not in {"backend", "frontend", "fullstack"}:
        errors.append("governance.json mode must be backend, frontend, or fullstack")
    if record.get("delivery_scope") not in {"technical", "production"}:
        errors.append("governance.json delivery_scope must be technical or production")
    project_root = Path(str(record.get("project_root", "")))
    if not project_root.is_absolute() or not project_root.is_dir():
        errors.append("governance.json project_root must be an existing absolute directory")
        return
    errors.extend(f"root context: {error}" for error in validate_root_context(project_root))
    errors.extend(f"agent policy: {error}" for error in validate_agent_policy(project_root / "docs/methodology/agent-policy.yaml"))
    errors.extend(f"profile: {error}" for error in validate_profile(project_root / "docs/methodology/profile.yaml"))
    try:
        actual_profile, actual_risk = read_project_profile(project_root / "docs/methodology/profile.yaml")
    except (OSError, ValueError):
        actual_profile = actual_risk = None  # validate_profile already reported the underlying error
    if actual_profile and record.get("profile") != actual_profile:
        errors.append("governance.json profile must match the project profile.yaml")
    if actual_risk and record.get("risk") != actual_risk:
        errors.append("governance.json risk must match the project profile.yaml project_risk")
    context_errors, _ = validate_context_docs(project_root)
    errors.extend(f"context docs: {error}" for error in context_errors)


def validate_requirement(change_dir: Path, errors: list[str]) -> None:
    try:
        reflection = read_json(change_dir / "requirement-reflection.json")
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append("requirement-reflection.json must be a valid JSON object")
        return
    errors.extend(validate_requirement_reflection(reflection))


def validate_context_contract(change_dir: Path, record: dict[str, Any], errors: list[str]) -> dict[str, Any] | None:
    project_root = Path(str(record.get("project_root", "")))
    impact, impact_errors = validate_context_impact(change_dir / "context-impact.json", project_root)
    errors.extend(impact_errors)
    return impact


def validate_context_updates(change_dir: Path, record: dict[str, Any], review: dict[str, Any], errors: list[str]) -> None:
    project_root = Path(str(record.get("project_root", ""))).resolve()
    impact, impact_errors = validate_context_impact(change_dir / "context-impact.json", project_root)
    if impact_errors or not impact:
        return
    files = review.get("files")
    if not isinstance(files, dict) or not all(isinstance(path, str) for path in files):
        return
    reviewed_paths = set(files)
    analyzed_paths = set(impact.get("analyzed_paths", []))
    if reviewed_paths != analyzed_paths:
        errors.append("review files must exactly match context-impact.json analyzed_paths")
    for document in ("ai_json", "ai_md"):
        decision = impact.get(document, {})
        required_paths = set(decision.get("paths", [])) if isinstance(decision, dict) else set()
        if decision.get("required") is True and not required_paths.issubset(reviewed_paths):
            errors.append(f"required {document} updates are missing from review file digests")
    changed_index = "ai.json" in reviewed_paths
    changed_details = {path for path in reviewed_paths if path == "AI.md" or path.endswith("/AI.md")}
    if changed_index and impact.get("ai_json", {}).get("required") is not True:
        errors.append("ai.json changed without an approved context impact decision")
    if changed_details and impact.get("ai_md", {}).get("required") is not True:
        errors.append("AI.md changed without an approved context impact decision")
    _, indexed_contexts = validate_context_docs(project_root)
    planned_details = {Path(str(path)).as_posix() for path in impact.get("ai_md", {}).get("paths", [])}
    indexed_details = {Path(str(path)).as_posix() for path in indexed_contexts}
    if not planned_details.issubset(indexed_details):
        errors.append("every planned AI.md update must be indexed by root ai.json")


def validate_lesson_preflight(change_dir: Path, record: dict[str, Any], errors: list[str]) -> None:
    path = change_dir / "evidence" / "lesson-preflight.json"
    try:
        evidence = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append("evidence/lesson-preflight.json must be a valid JSON object")
        return
    for field in ("schema_version", "status", "actor", "at", "keywords", "rules", "paths", "matched_lessons", "actions"):
        if field not in evidence:
            errors.append(f"lesson-preflight.json missing {field}")
    if evidence.get("schema_version") != 1:
        errors.append("lesson-preflight.json schema_version must be 1")
    if evidence.get("status") != "passed":
        errors.append("lesson-preflight.json status must be passed")
    for field in ("keywords", "rules", "paths", "matched_lessons", "actions"):
        if not isinstance(evidence.get(field), list):
            errors.append(f"lesson-preflight.json {field} must be an array")
    if not meaningful_value(evidence.get("actor")) or not meaningful_value(evidence.get("at")):
        errors.append("lesson-preflight.json actor and at are required")
    project_root = Path(str(record.get("project_root", ""))).resolve()
    lessons, lesson_errors = load_lessons(project_root, active_only=True)
    errors.extend(f"lessons: {error}" for error in lesson_errors)
    if lesson_errors:
        return
    keywords = [str(item) for item in evidence.get("keywords", [])]
    rules = [str(item) for item in evidence.get("rules", [])]
    paths = [str(item) for item in evidence.get("paths", [])]
    scope = evidence.get("scope") if isinstance(evidence.get("scope"), str) else None
    expected = {
        str(lesson["lesson_id"])
        for lesson in lessons
        if lesson_matches(lesson, keywords, rules, paths, scope)
    }
    actual = {str(item) for item in evidence.get("matched_lessons", [])}
    if actual != expected:
        errors.append("lesson-preflight.json matched_lessons do not match active lessons")


def require_markdown(change_dir: Path, names: tuple[str, ...], errors: list[str]) -> None:
    for name in names:
        if not meaningful(change_dir / name):
            errors.append(f"missing or placeholder artifact: {name}")


def validate_specs(change_dir: Path, errors: list[str]) -> None:
    specs = spec_files(change_dir)
    if not specs:
        errors.append("at least one specs/<capability>/spec.md is required")
        return
    for path in specs:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(change_dir)} is not readable UTF-8: {exc}")
            continue
        scenarios = re.split(r"(?=^#### Scenario:\s*)", content, flags=re.MULTILINE)[1:]
        if not scenarios:
            errors.append(f"{path.relative_to(change_dir)} requires a #### Scenario")
        for scenario in scenarios:
            if not WHEN_PATTERN.search(scenario) or not THEN_PATTERN.search(scenario):
                errors.append(f"{path.relative_to(change_dir)} has a scenario without WHEN/THEN")


def validate_spec_content(path: Path, label: str, errors: list[str]) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label} is not readable UTF-8: {exc}")
        return
    scenarios = re.split(r"(?=^#### Scenario:\s*)", content, flags=re.MULTILINE)[1:]
    if not scenarios:
        errors.append(f"{label} requires a #### Scenario")
    for scenario in scenarios:
        if not WHEN_PATTERN.search(scenario) or not THEN_PATTERN.search(scenario):
            errors.append(f"{label} has a scenario without WHEN/THEN")


def validate_approval(change_dir: Path, errors: list[str]) -> None:
    try:
        approval = read_json(change_dir / "approval.json")
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append("approval.json must be a valid JSON object")
        return
    for field in ("status", "actor", "at", "source", "approval_id", "artifacts"):
        if not meaningful_value(approval.get(field)):
            errors.append(f"approval.json missing {field}")
    if approval.get("status") != "approved":
        errors.append("approval.json status must be approved")
    files = contract_files(change_dir)
    if all(meaningful(path) for path in files):
        expected = relative_digests(change_dir, files)
        if approval.get("artifacts") != expected:
            errors.append("approval.json artifact digests do not match the approved contract")


def validate_review(change_dir: Path, record: dict[str, Any], errors: list[str]) -> None:
    try:
        evidence = read_json(change_dir / "review-evidence.json")
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append("review-evidence.json must be a valid JSON object")
        return
    for field in ("status", "actor", "at", "change_digest", "tasks_complete", "files", "commands", "uncovered_cases", "exceptions"):
        if field not in evidence:
            errors.append(f"review-evidence.json missing {field}")
    if evidence.get("status") != "passed":
        errors.append("review-evidence.json status must be passed")
    if evidence.get("tasks_complete") is not True:
        errors.append("review-evidence.json tasks_complete must be true")
    commands = evidence.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("review-evidence.json requires at least one command result")
    elif any(
        not isinstance(item, dict)
        or not meaningful_value(item.get("command"))
        or not is_exit_code(item.get("exit_code"))
        or item["exit_code"] != 0
        for item in commands
    ):
        errors.append("every review command requires command and an integer exit_code=0")
    fitness_commands = [
        item for item in commands if isinstance(item, dict)
        and "docs/fitness/scripts/fitness.py" in str(item.get("command", ""))
        and command_has_stage(item.get("command"), "review")
    ] if isinstance(commands, list) else []
    if len(fitness_commands) != 1:
        errors.append("review-evidence.json requires exactly one successful Fitness command with --stage review")
    else:
        if not command_has_option(fitness_commands[0].get("command"), "change") or not command_has_option(fitness_commands[0].get("command"), "report"):
            errors.append("review Fitness command must include --change and --report")
        validate_fitness_report(Path(str(record.get("project_root", ""))), change_dir, fitness_commands[0], "review", errors)
    if not isinstance(evidence.get("uncovered_cases"), list) or not isinstance(evidence.get("exceptions"), list):
        errors.append("uncovered_cases and exceptions must be arrays")
    for field in ("actor", "at", "change_digest"):
        if not meaningful_value(evidence.get(field)):
            errors.append(f"review-evidence.json missing or placeholder: {field}")
    files = evidence.get("files")
    project_root = Path(str(record.get("project_root", ""))).resolve()
    if not isinstance(files, dict) or not files:
        errors.append("review-evidence.json files must be a non-empty path-to-digest object")
    else:
        for relative, expected_digest in files.items():
            if not meaningful_value(relative) or not meaningful_value(expected_digest):
                errors.append("review file entries require a path and SHA-256 or DELETED")
                continue
            candidate = (project_root / str(relative)).resolve()
            lexical = project_root / str(relative)
            try:
                candidate.relative_to(project_root)
            except ValueError:
                errors.append(f"review file escapes project root: {relative}")
                continue
            if expected_digest == "DELETED":
                if lexical.exists() or lexical.is_symlink():
                    errors.append(f"review expected deleted file still exists: {relative}")
            elif lexical.is_symlink():
                errors.append(f"review file must not be a symlink: {relative}")
            elif not candidate.is_file() or sha256(candidate) != expected_digest:
                errors.append(f"review file digest mismatch: {relative}")
        if isinstance(files, dict) and evidence.get("change_digest") != review_change_digest(project_root, files):
            errors.append("review-evidence.json change_digest does not match the reviewed file contents")
    validate_context_updates(change_dir, record, evidence, errors)
    errors.extend(validate_execution(change_dir, record, evidence))
    require_evidence_after(change_dir, evidence, "execution-evidence.json", "review-evidence.json", errors)
    validate_self_refine(change_dir, record, errors)


def validate_self_refine(change_dir: Path, record: dict[str, Any], errors: list[str]) -> None:
    """Validate the optional, profile-controlled AI refinement evidence."""
    project_root = Path(str(record.get("project_root", "")))
    policy = self_refine_policy(project_root / "docs/methodology/profile.yaml")
    max_iterations = self_refine_max_iterations(project_root / "docs/methodology/profile.yaml")
    path = change_dir / "self-refine-evidence.json"
    if not path.is_file():
        if policy in {"required", "required-independent"}:
            errors.append("self-refine-evidence.json is required by the project profile")
        return
    try:
        evidence = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append("self-refine-evidence.json must be a valid JSON object")
        return
    for field in ("schema_version", "status", "actor", "at", "policy", "iterations", "artifacts", "uncovered_risks"):
        if field not in evidence:
            errors.append(f"self-refine-evidence.json missing {field}")
    if evidence.get("schema_version") != 1:
        errors.append("self-refine-evidence.json schema_version must be 1")
    if evidence.get("status") != "passed":
        errors.append("self-refine-evidence.json status must be passed")
    if evidence.get("policy") != policy:
        errors.append("self-refine-evidence.json policy must match the project profile")
    iterations = evidence.get("iterations")
    if not isinstance(iterations, int) or not 1 <= iterations <= max_iterations:
        errors.append(f"self-refine-evidence.json iterations must be an integer between 1 and {max_iterations}")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("self-refine-evidence.json artifacts must be a non-empty array")
    else:
        for item in artifacts:
            if not isinstance(item, dict) or not all(meaningful_value(item.get(key)) for key in ("path", "findings", "resolution")):
                errors.append("each self-refine artifact requires path, findings, and resolution")
    if not isinstance(evidence.get("uncovered_risks"), list):
        errors.append("self-refine-evidence.json uncovered_risks must be an array")
    for field in ("actor", "at"):
        if not meaningful_value(evidence.get(field)):
            errors.append(f"self-refine-evidence.json missing or placeholder: {field}")
    if policy == "required-independent":
        independent = evidence.get("independent_check")
        if not isinstance(independent, dict) or independent.get("status") != "passed" or not all(
            meaningful_value(independent.get(key)) for key in ("actor", "evidence")
        ):
            errors.append("required-independent self-refine policy needs a passed independent_check")
        elif independent.get("actor") == evidence.get("actor"):
            errors.append("required-independent self-refine check must use a different actor")
    require_evidence_after(change_dir, evidence, "approval.json", "self-refine-evidence.json", errors)


def validate_lesson_candidate(change_dir: Path, errors: list[str]) -> None:
    path = change_dir / "lesson-candidate.json"
    if not path.is_file():
        return
    try:
        candidate = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append("lesson-candidate.json must be a valid JSON object")
        return
    errors.extend(f"lesson candidate: {error}" for error in validate_lesson(candidate))
    if candidate.get("status") != "candidate":
        errors.append("lesson-candidate.json status must be candidate")
    if not isinstance(candidate.get("source_events"), list) or not candidate.get("source_events"):
        errors.append("lesson-candidate.json source_events must be a non-empty array")


def validate_learning_closure(change_dir: Path, errors: list[str]) -> None:
    events, event_errors = load_failure_events(change_dir)
    errors.extend(f"failure events: {error}" for error in event_errors)
    try:
        expected_change_id = read_json(change_dir / "governance.json").get("change_id")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        expected_change_id = None
    if expected_change_id is not None:
        for event in events:
            if event.get("change_id") != expected_change_id:
                errors.append("failure event change_id must match governance.json")
    if not events:
        return
    candidate = change_dir / "lesson-candidate.json"
    decision = change_dir / "lesson-decision.json"
    if not candidate.is_file() and not decision.is_file():
        errors.append("record a lesson-candidate.json or lesson-decision.json for recorded failures")
        return
    if decision.is_file():
        try:
            data = read_json(decision)
        except (OSError, json.JSONDecodeError, ValueError):
            errors.append("lesson-decision.json must be a valid JSON object")
            return
        for field in ("schema_version", "status", "decision", "reason", "source_events", "actor", "at"):
            if field not in data:
                errors.append(f"lesson-decision.json missing {field}")
        if data.get("schema_version") != 1 or data.get("status") != "closed" or data.get("decision") != "not-generalizable":
            errors.append("lesson-decision.json must close with decision not-generalizable")
        if not isinstance(data.get("source_events"), list) or not data.get("source_events"):
            errors.append("lesson-decision.json source_events must be a non-empty array")
        for field in ("reason", "actor", "at"):
            if not meaningful_value(data.get(field)):
                errors.append(f"lesson-decision.json missing or placeholder: {field}")


def validate_named_evidence(change_dir: Path, name: str, fields: tuple[str, ...], errors: list[str]) -> dict[str, Any] | None:
    try:
        data = read_json(change_dir / name)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"{name} must be a valid JSON object")
        return None
    for field in fields:
        if not meaningful_value(data.get(field)):
            errors.append(f"{name} missing {field}")
    return data


def validate_sync(change_dir: Path, record: dict[str, Any], errors: list[str]) -> None:
    evidence = validate_named_evidence(change_dir, "sync-evidence.json", ("actor", "at", "targets"), errors)
    if not evidence:
        return
    targets = evidence.get("targets")
    if not isinstance(targets, list) or not targets:
        errors.append("sync-evidence.json targets must be a non-empty array")
        return
    project_root = Path(str(record.get("project_root", "")))
    synchronized_sources: set[str] = set()
    synchronized_destinations: set[str] = set()
    schema_version = evidence.get("schema_version")
    if schema_version not in {1, 2, 3}:
        errors.append("sync-evidence.json schema_version must be 1, 2, or 3")
    checks = evidence.get("checks")
    if schema_version == 3:
        if not isinstance(checks, list) or not checks:
            errors.append("sync-evidence.json schema_version 3 requires checks")
        else:
            validate_checks = [
                item for item in checks if isinstance(item, dict) and item.get("id") == "openspec_validate_specs"
            ]
            semantic_checks = [
                item for item in checks if isinstance(item, dict) and item.get("id") == "sync_semantics"
            ]
            if len(validate_checks) != 1 or validate_checks[0].get("status") != "passed" or validate_checks[0].get("exit_code") != 0:
                errors.append("sync-evidence.json requires one passed openspec_validate_specs check")
            else:
                if "openspec validate --specs" not in str(validate_checks[0].get("command", "")):
                    errors.append("openspec_validate_specs check must run openspec validate --specs")
                validate_command_evidence(project_root, validate_checks[0], "sync OpenSpec validation", errors)
            if len(semantic_checks) != 1 or semantic_checks[0].get("status") != "passed" or semantic_checks[0].get("exit_code") != 0:
                errors.append("sync-evidence.json requires one passed sync_semantics check")
            elif not command_has_stage(semantic_checks[0].get("command"), "sync"):
                errors.append("sync_semantics check command must use Fitness --stage sync")
            elif "docs/fitness/scripts/fitness.py" not in str(semantic_checks[0].get("command", "")):
                errors.append("sync_semantics check must run docs/fitness/scripts/fitness.py")
            else:
                if not command_has_option(semantic_checks[0].get("command"), "change") or not command_has_option(semantic_checks[0].get("command"), "report"):
                    errors.append("sync_semantics command must include --change and --report")
                validate_fitness_report(project_root, change_dir, semantic_checks[0], "sync", errors)
    for target in targets:
        if not isinstance(target, dict):
            errors.append("sync target must be an object")
            continue
        source_name = target.get("source")
        destination_name = target.get("destination")
        if schema_version == 1:
            source_digest = destination_digest = target.get("sha256")
            digest_fields = (source_digest,)
        else:
            source_digest = target.get("source_sha256")
            destination_digest = target.get("destination_sha256")
            digest_fields = (source_digest, destination_digest)
        if schema_version == 3:
            before_snapshot = target.get("before_snapshot")
            before_digest = target.get("before_sha256")
            if not meaningful_value(before_snapshot) or not meaningful_value(before_digest):
                errors.append("sync target requires before_snapshot and before_sha256")
            else:
                snapshot = (change_dir / str(before_snapshot)).resolve()
                try:
                    snapshot.relative_to(change_dir.resolve())
                except ValueError:
                    errors.append(f"sync snapshot escapes change root: {before_snapshot}")
                else:
                    if not snapshot.is_file() or sha256(snapshot) != before_digest:
                        errors.append(f"sync snapshot digest mismatch: {before_snapshot}")
        if not all(meaningful_value(item) for item in (source_name, destination_name, *digest_fields)):
            requirement = "source, destination, and sha256" if schema_version == 1 else (
                "source, destination, source_sha256, and destination_sha256"
            )
            errors.append(f"sync target requires {requirement}")
            continue
        source_name = str(source_name)
        destination_name = str(destination_name)
        source = (change_dir / str(source_name)).resolve()
        destination = (project_root / str(destination_name)).resolve()
        try:
            source.relative_to(change_dir.resolve())
            destination.relative_to(project_root.resolve())
        except ValueError:
            errors.append(f"sync path escapes allowed root: {source_name} -> {destination_name}")
            continue
        source_relative = Path(source_name)
        if len(source_relative.parts) != 3 or source_relative.parts[0] != "specs" or source_relative.name != "spec.md":
            errors.append(f"sync source must be specs/<capability>/spec.md: {source_name}")
            continue
        expected_destination = Path("openspec/specs") / source_relative.parts[1] / "spec.md"
        if Path(destination_name) != expected_destination:
            errors.append(f"sync destination must be {expected_destination.as_posix()} for source {source_name}")
            continue
        if schema_version == 3:
            expected_snapshot = Path("evidence/pre-sync") / source_relative.parts[1] / "spec.md"
            if Path(str(target.get("before_snapshot"))) != expected_snapshot:
                errors.append(f"sync snapshot must be {expected_snapshot.as_posix()} for source {source_name}")
        if not source.is_file() or not destination.is_file():
            errors.append(f"sync source or destination missing: {source_name} -> {destination_name}")
        elif sha256(source) != source_digest or sha256(destination) != destination_digest:
            errors.append(f"sync digest mismatch: {source_name} -> {destination_name}")
        else:
            validate_spec_content(destination, destination_name, errors)
        if source_name in synchronized_sources:
            errors.append(f"duplicate sync source: {source_name}")
        if destination_name in synchronized_destinations:
            errors.append(f"duplicate sync destination: {destination_name}")
        synchronized_sources.add(source_name)
        synchronized_destinations.add(destination_name)
    expected_sources = {str(path.relative_to(change_dir)) for path in spec_files(change_dir)}
    if synchronized_sources != expected_sources:
        errors.append("sync targets must cover every and only specs/<capability>/spec.md source")
    require_evidence_after(change_dir, evidence, "review-evidence.json", "sync-evidence.json", errors)
    if schema_version == 3:
        validate_sync_semantics(change_dir, record, errors)


REQUIREMENT_PATTERN = re.compile(r"^### Requirement:\s*(.+?)\s*$", re.MULTILINE)
DELTA_SECTION_PATTERN = re.compile(r"^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements\s*$", re.MULTILINE)
RENAME_FROM_PATTERN = re.compile(r"^\s*-?\s*FROM:\s*`?###\s*Requirement:\s*(.+?)`?\s*$", re.MULTILINE)
RENAME_TO_PATTERN = re.compile(r"^\s*-?\s*TO:\s*`?###\s*Requirement:\s*(.+?)`?\s*$", re.MULTILINE)


def requirement_blocks(content: str) -> dict[str, str]:
    matches = list(REQUIREMENT_PATTERN.finditer(content))
    return {
        match.group(1).strip(): content[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(content)]
        for index, match in enumerate(matches)
    }


def semantic_lines(content: str) -> set[str]:
    return {line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("<!--")}


def validate_sync_semantics(change_dir: Path, record: dict[str, Any], errors: list[str]) -> None:
    project_root = Path(str(record.get("project_root", ""))).resolve()
    for delta in sorted((change_dir / "specs").glob("*/spec.md")):
        snapshot = change_dir / "evidence" / "pre-sync" / delta.parent.name / "spec.md"
        if not snapshot.is_file():
            errors.append(f"sync pre-sync snapshot missing: {snapshot.relative_to(change_dir)}")
            before_blocks: dict[str, str] = {}
        else:
            before_blocks = requirement_blocks(snapshot.read_text(encoding="utf-8"))
        canonical = project_root / "openspec" / "specs" / delta.parent.name / "spec.md"
        if not canonical.is_file():
            errors.append(f"sync canonical spec missing: {canonical.relative_to(project_root)}")
            continue
        delta_text = delta.read_text(encoding="utf-8")
        canonical_blocks = requirement_blocks(canonical.read_text(encoding="utf-8"))
        sections = list(DELTA_SECTION_PATTERN.finditer(delta_text))
        declared: set[str] = set()
        for index, section in enumerate(sections):
            end = sections[index + 1].start() if index + 1 < len(sections) else len(delta_text)
            body = delta_text[section.end():end]
            operation = section.group(1)
            if operation == "RENAMED":
                old_names = RENAME_FROM_PATTERN.findall(body)
                new_names = RENAME_TO_PATTERN.findall(body)
                if len(old_names) != len(new_names):
                    errors.append("sync rename entries require paired FROM and TO requirements")
                for old_name, new_name in zip(old_names, new_names):
                    old_name, new_name = old_name.strip(), new_name.strip()
                    declared.update((old_name, new_name))
                    if old_name in canonical_blocks or new_name not in canonical_blocks:
                        errors.append(f"sync requirement rename not applied: {old_name} -> {new_name}")
                    elif old_name not in before_blocks:
                        errors.append(f"sync renamed source requirement missing from pre-sync snapshot: {old_name}")
                    elif semantic_lines(before_blocks[old_name]) != semantic_lines(canonical_blocks[new_name]):
                        errors.append(f"sync renamed requirement content changed: {old_name} -> {new_name}")
                continue
            for name, block in requirement_blocks(body).items():
                declared.add(name)
                if operation == "REMOVED":
                    if name in canonical_blocks:
                        errors.append(f"sync removed requirement still exists: {name}")
                    if before_blocks and name not in before_blocks:
                        errors.append(f"sync removed requirement missing from pre-sync snapshot: {name}")
                elif name not in canonical_blocks:
                    errors.append(f"sync requirement missing from canonical spec: {name}")
                elif not semantic_lines(block).issubset(semantic_lines(canonical_blocks[name])):
                    errors.append(f"sync canonical requirement is missing delta content: {name}")
                elif operation == "ADDED" and name in before_blocks:
                    errors.append(f"sync added requirement already existed before sync: {name}")
                elif operation == "MODIFIED" and before_blocks and name not in before_blocks:
                    errors.append(f"sync modified requirement missing from pre-sync snapshot: {name}")
        for name in sorted(set(before_blocks) & set(canonical_blocks) - declared):
            if semantic_lines(before_blocks[name]) != semantic_lines(canonical_blocks[name]):
                errors.append(f"sync canonical spec contains undeclared semantic change: {name}")
        for name in sorted((set(canonical_blocks) - set(before_blocks)) - declared):
            errors.append(f"sync canonical spec contains undeclared added requirement: {name}")
        for name in sorted((set(before_blocks) - set(canonical_blocks)) - declared):
            errors.append(f"sync canonical spec contains undeclared removed requirement: {name}")


def validate_production_closure(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("delivery_scope") != "production":
        return
    production_record = record.get("production_record")
    if not production_record:
        errors.append("production delivery requires governance.json production_record")
        return
    path = Path(str(production_record))
    if not path.is_absolute():
        errors.append("production_record must be an absolute path")
        return
    allowed_records = (Path(str(record.get("project_root"))) / "docs/methodology/production/changes").resolve()
    try:
        path.resolve().relative_to(allowed_records)
    except ValueError:
        errors.append(f"production_record escapes allowed directory: {path}")
        return
    try:
        production = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"cannot read production record: {path}")
        return
    if production.get("change_id") != record.get("change_id"):
        errors.append("production record change_id does not match OpenSpec change")
    for error in validate_production_record(production):
        errors.append(f"production record invalid: {error}")
    if production.get("state") != "CLOSED":
        errors.append("production record must be CLOSED before Engineering archive")
        return
    events = production.get("events")
    if not isinstance(events, list) or not events or not isinstance(events[-1], dict) or events[-1].get("to") != "CLOSED" or not events[-1].get("evidence"):
        errors.append("production closure requires a final CLOSED transition with evidence")
    audit_log = production.get("audit_log")
    audit_path = Path(str(audit_log))
    if not audit_path.is_absolute():
        audit_path = Path(str(record.get("project_root"))) / audit_path
    allowed_audit = (Path(str(record.get("project_root"))) / "docs/methodology/production/audit").resolve()
    try:
        audit_path.resolve().relative_to(allowed_audit)
    except ValueError:
        errors.append(f"production audit log escapes allowed directory: {audit_path}")
        return
    try:
        audit_events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"production audit log is missing or invalid: {audit_path}")
    else:
        if not audit_events or not isinstance(audit_events[-1], dict) or audit_events[-1].get("to") != "CLOSED":
            errors.append("production audit log does not end with CLOSED")
    stages = production.get("rollout", {}).get("stages", []) if isinstance(production.get("rollout"), dict) else []
    cycles = rollout_cycles(events)
    if len(cycles) == 1:
        if cycles[0] != stages:
            errors.append("production rollout stages were not completed in declared order")
    else:
        for cycle in cycles[:-1]:
            if stages[:len(cycle)] != cycle:
                errors.append("production rollout stages before rollback are out of declared order")
        # After a rollback the change either redeploys every stage in order or
        # closes while still rolled back (empty final cycle); anything else is
        # an incomplete or hand-edited rollout.
        if cycles[-1] not in (stages, []):
            errors.append("production rollout stages were not completed in declared order after the last rollback")


def check(change_dir: Path, phase: str) -> list[str]:
    errors: list[str] = []
    if phase not in PHASES:
        return [f"unknown phase: {phase}"]
    try:
        record = read_json(change_dir / "governance.json")
    except (OSError, json.JSONDecodeError, ValueError):
        return ["governance.json must be a valid JSON object"]
    if str(record.get("change_id", "")) != change_dir.name:
        errors.append(f"governance.json change_id must match the change directory name: {change_dir.name}")
    validate_change_record(record, errors)
    validate_event_store(change_dir, record, errors)
    validate_requirement(change_dir, errors)
    project_root = Path(str(record.get("project_root", "")))
    if project_root.is_dir():
        try:
            from check_change_workspace import check_workspace
        except ImportError:
            errors.append("workspace guard missing: re-run onboarding --apply to install check_change_workspace.py")
        else:
            errors.extend(f"workspace: {error}" for error in check_workspace(project_root))
    validate_context_contract(change_dir, record, errors)
    require_markdown(change_dir, ("context-pack.md", "impact-analysis.md"), errors)
    if phase == "EXPLORE":
        validate_lesson_preflight(change_dir, record, errors)
    if phase in {"SPEC", "DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE"}:
        require_markdown(change_dir, ("proposal.md",), errors)
        validate_specs(change_dir, errors)
    if phase in {"DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE"}:
        require_markdown(change_dir, ("design.md", "tasks.md"), errors)
        errors.extend(validate_design(change_dir / "design.md"))
    if phase == "DESIGN":
        from check_execution import task_status
        tasks, task_errors = task_status(change_dir)
        errors.extend(task_errors)
        if any(tasks.values()):
            errors.append("OpenSpec tasks must be unchecked before approval")
    if phase in {"EXECUTE", "REVIEW", "SYNC", "ARCHIVE"}:
        validate_approval(change_dir, errors)
    if phase in {"REVIEW", "SYNC", "ARCHIVE"}:
        validate_review(change_dir, record, errors)
        validate_lesson_candidate(change_dir, errors)
    if phase in {"SYNC", "ARCHIVE"}:
        validate_sync(change_dir, record, errors)
    if phase == "ARCHIVE":
        archive = validate_named_evidence(change_dir, "archive-evidence.json", ("actor", "at", "destination"), errors)
        if archive:
            require_evidence_after(change_dir, archive, "sync-evidence.json", "archive-evidence.json", errors)
        validate_learning_closure(change_dir, errors)
        validate_production_closure(record, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_dir", type=Path)
    parser.add_argument("phase", choices=PHASES)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    errors = check(args.change_dir.resolve(), args.phase)
    payload = {"change_dir": str(args.change_dir.resolve()), "phase": args.phase, "status": "PASS" if not errors else "BLOCKED", "errors": errors}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"PHASE {payload['status']}: {args.phase}")
        for error in errors:
            print(f"- {error}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
