#!/usr/bin/env python3
"""Fail-closed gates for the canonical Engineering lifecycle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from check_agent_policy import validate as validate_agent_policy
from check_context_docs import validate_context_impact, validate_project as validate_context_docs
from check_profile import read_project_profile, self_refine_max_iterations, self_refine_policy, validate as validate_profile
from check_production_readiness import rollout_cycles, validate as validate_production_record
from check_root_context import validate as validate_root_context
from lessons_common import lesson_matches, load_failure_events, load_lessons, validate_lesson
from methodology_common import contract_files, meaningful, read_json, relative_digests, sha256, spec_files


PHASES = ("EXPLORE", "SPEC", "DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE")


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


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not meaningful_value(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def require_evidence_after_state(record: dict[str, Any], evidence: dict[str, Any], state: str, name: str, errors: list[str]) -> None:
    evidence_at = timestamp(evidence.get("at"))
    transitions = [
        timestamp(item.get("at")) for item in record.get("events", [])
        if isinstance(item, dict) and item.get("event") == "methodology.transition" and item.get("to") == state
    ]
    state_times = [item for item in transitions if item is not None]
    if evidence_at is None:
        errors.append(f"{name} at must be an ISO-8601 timestamp")
    elif not state_times or evidence_at < max(state_times):
        errors.append(f"{name} must be created after the latest transition to {state}")


def validate_change_record(record: dict[str, Any], errors: list[str]) -> None:
    required = ("schema_version", "change_id", "title", "profile", "risk", "skill", "mode", "delivery_scope", "project_root", "state", "owner")
    for field in required:
        if not meaningful_value(record.get(field)):
            errors.append(f"change.json missing or placeholder: {field}")
    if record.get("schema_version") != 2:
        errors.append("change.json schema_version must be 2")
    if record.get("skill") != "engineering":
        errors.append("change.json skill must be engineering")
    if record.get("mode") not in {"backend", "frontend", "fullstack"}:
        errors.append("change.json mode must be backend, frontend, or fullstack")
    if record.get("delivery_scope") not in {"technical", "production"}:
        errors.append("change.json delivery_scope must be technical or production")
    project_root = Path(str(record.get("project_root", "")))
    if not project_root.is_absolute() or not project_root.is_dir():
        errors.append("change.json project_root must be an existing absolute directory")
        return
    errors.extend(f"root context: {error}" for error in validate_root_context(project_root))
    errors.extend(f"agent policy: {error}" for error in validate_agent_policy(project_root / "docs/methodology/agent-policy.yaml"))
    errors.extend(f"profile: {error}" for error in validate_profile(project_root / "docs/methodology/profile.yaml"))
    try:
        actual_profile, actual_risk = read_project_profile(project_root / "docs/methodology/profile.yaml")
    except (OSError, ValueError):
        actual_profile = actual_risk = None  # validate_profile already reported the underlying error
    if actual_profile and record.get("profile") != actual_profile:
        errors.append("change.json profile must match the project profile.yaml")
    if actual_risk and record.get("risk") != actual_risk:
        errors.append("change.json risk must match the project profile.yaml project_risk")
    context_errors, _ = validate_context_docs(project_root)
    errors.extend(f"context docs: {error}" for error in context_errors)


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
            if not re.search(r"^WHEN\s+", scenario, re.MULTILINE) or not re.search(r"^THEN\s+", scenario, re.MULTILINE):
                errors.append(f"{path.relative_to(change_dir)} has a scenario without WHEN/THEN")


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
            try:
                candidate.relative_to(project_root)
            except ValueError:
                errors.append(f"review file escapes project root: {relative}")
                continue
            if expected_digest == "DELETED":
                if candidate.exists():
                    errors.append(f"review expected deleted file still exists: {relative}")
            elif not candidate.is_file() or sha256(candidate) != expected_digest:
                errors.append(f"review file digest mismatch: {relative}")
    validate_context_updates(change_dir, record, evidence, errors)
    require_evidence_after_state(record, evidence, "VERIFYING", "review-evidence.json", errors)
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
    require_evidence_after_state(record, evidence, "VERIFYING", "self-refine-evidence.json", errors)


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
    for target in targets:
        if not isinstance(target, dict):
            errors.append("sync target must be an object")
            continue
        source_name = target.get("source")
        destination_name = target.get("destination")
        expected_digest = target.get("sha256")
        if not all(meaningful_value(item) for item in (source_name, destination_name, expected_digest)):
            errors.append("sync target requires source, destination, and sha256")
            continue
        source = (change_dir / str(source_name)).resolve()
        destination = (project_root / str(destination_name)).resolve()
        try:
            source.relative_to(change_dir.resolve())
            destination.relative_to(project_root.resolve())
        except ValueError:
            errors.append(f"sync path escapes allowed root: {source_name} -> {destination_name}")
            continue
        if not source.is_file() or not destination.is_file():
            errors.append(f"sync source or destination missing: {source_name} -> {destination_name}")
        elif sha256(source) != expected_digest or sha256(destination) != expected_digest:
            errors.append(f"sync digest mismatch: {source_name} -> {destination_name}")
        synchronized_sources.add(str(source_name))
    expected_sources = {str(path.relative_to(change_dir)) for path in spec_files(change_dir)}
    if synchronized_sources != expected_sources:
        errors.append("sync targets must cover every and only specs/<capability>/spec.md source")
    require_evidence_after_state(record, evidence, "VERIFIED", "sync-evidence.json", errors)


def validate_production_closure(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("delivery_scope") != "production":
        return
    production_record = record.get("production_record")
    if not production_record:
        errors.append("production delivery requires change.json production_record")
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
        errors.append("production record change_id does not match Engineering change")
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
        record = read_json(change_dir / "change.json")
    except (OSError, json.JSONDecodeError, ValueError):
        return ["change.json must be a valid JSON object"]
    if str(record.get("change_id", "")) != change_dir.name:
        errors.append(f"change.json change_id must match the change directory name: {change_dir.name}")
    validate_change_record(record, errors)
    validate_context_contract(change_dir, record, errors)
    require_markdown(change_dir, ("context-pack.md", "impact-analysis.md"), errors)
    if phase == "EXPLORE":
        validate_lesson_preflight(change_dir, record, errors)
    if phase in {"SPEC", "DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE"}:
        require_markdown(change_dir, ("proposal.md",), errors)
        validate_specs(change_dir, errors)
    if phase in {"DESIGN", "EXECUTE", "REVIEW", "SYNC", "ARCHIVE"}:
        require_markdown(change_dir, ("design.md", "tasks.md"), errors)
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
            require_evidence_after_state(record, archive, "SYNCED", "archive-evidence.json", errors)
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
