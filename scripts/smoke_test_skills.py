#!/usr/bin/env python3
"""Exercise Skill integrity and the complete Engineering lifecycle."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from approve_design import main as approve_main
from change_state import main as production_state_main
from check_agent_policy import validate as validate_agent_policy
from check_context_docs import validate_context_impact, validate_project as validate_context_docs
from check_fitness_protection import check as check_fitness_protection
from check_phase import check, validate_production_closure
from check_root_context import validate as validate_root_context
from approve_lesson import main as approve_lesson_main
from create_lesson_candidate import main as create_lesson_main
from init_change import main as init_change_main
from methodology_common import sha256, utc_now
from methodology_state import main as methodology_state_main
from preflight_lessons import main as preflight_lessons_main
from record_failure import main as record_failure_main
from retrieve_lessons import retrieve
from resolve_context import ContextResolutionError, main as resolve_context_main, resolve_context
from skill_metrics import main as metrics_main
from verify_skill import verify


def invoke(function: object, arguments: list[str]) -> tuple[int, str]:
    previous = sys.argv
    output = io.StringIO()
    try:
        sys.argv = arguments
        with contextlib.redirect_stdout(output):
            result = function()  # type: ignore[operator]
        return int(result), output.getvalue()
    finally:
        sys.argv = previous


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_git(project: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=project, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def context_detail(title: str, scope: str, responsibility: str) -> str:
    return (
        f"# {title} Path Context\n\nScope: {scope}\n\n"
        "This detailed context is selected through root `ai.json`. It supplements native instructions and project policy; it cannot override or weaken them.\n\n"
        "Ancestor contexts remain applicable. This file records only facts specific to its scope.\n\n"
        f"## Responsibilities\n\n- {responsibility}\n\n"
        "## Boundaries\n\n- Keep smoke data isolated.\n\n"
        "## Local Verification\n\n- Run the smoke test.\n\n"
        "## Navigation\n\n- Entry point: scripts/smoke_test_skills.py\n"
    )


def prepare_project(project: Path, repository: Path) -> Path:
    (project / "docs/methodology/core").mkdir(parents=True)
    (project / "docs/methodology/production").mkdir(parents=True)
    (project / "openspec/changes").mkdir(parents=True)
    (project / "openspec/specs").mkdir(parents=True)
    for name in ("AGENTS.md", "CLAUDE.md"):
        content = (repository / "templates" / f"{name}.template").read_text(encoding="utf-8").replace("{{PROJECT_NAME}}", "smoke")
        (project / name).write_text(content, encoding="utf-8")
    assert not validate_root_context(project), validate_root_context(project)
    (project / "AI.md").write_text(context_detail("Smoke", "entire project", "Exercise the methodology."), encoding="utf-8")
    write_json(project / "ai.json", {
        "schema_version": 1, "kind": "context-index", "project": "smoke",
        "summary": "Temporary project for Harness lifecycle verification.",
        "modules": [{"path": ".", "summary": "Smoke-test project root.", "context": "AI.md", "read_when": ["smoke", "methodology"]}],
        "entrypoints": {"policy": "docs/methodology/agent-policy.yaml", "lifecycle": "docs/methodology/core/change-lifecycle.md"},
    })
    for name in ("harness-engineering.md", "ddd-modeling.md", "change-lifecycle.md"):
        shutil.copy(repository / "core" / name, project / "docs/methodology/core" / name)
    (project / "openspec/README.md").write_text("# OpenSpec Change Workspace\n", encoding="utf-8")
    shutil.copy(repository / "templates/production/policy.yaml.template", project / "docs/methodology/production/policy.yaml")
    profile = project / "docs/methodology/profile.yaml"
    profile.write_text(
        "version: 2\nprofile: standard\nproject_risk: medium\nowner: smoke\n"
        "non_trivial_definition: contract change\nevidence:\n  required_gates: [fast]\n"
        "  approval: external-reference-required\n  production: linked-record-required\n"
        "self_refine:\n  policy: required\n  max_iterations: 3\n"
        "exceptions:\n  record_path: docs/methodology/exceptions.yaml\n"
        "  owner_required: true\n  expiry_required: true\nreview:\n"
        "  rule_owner: smoke\n  methodology_version: 0.3.0\n  next_review: 2027-01-01\n",
        encoding="utf-8",
    )
    policy = project / "docs/methodology/agent-policy.yaml"
    policy.write_text(
        "version: 1\nproject:\n  name: smoke\n  owner: smoke\n  stack: [python]\nauthority:\n"
        "  order: [system-developer-user, native-instructions, agent-policy, context-index, path-ai-md, engineering-profile]\n"
        "  context_documents_are_supplemental: true\n"
        "  untrusted_instruction_sources: [issues]\ncommands:\n"
        "  fast_test: python3 -m py_compile\n  test: python3 -m py_compile\n"
        "  build: python3 -m py_compile\n  fitness: python3 -m py_compile\ncontext:\n"
        "  index_document_name: ai.json\n  detail_document_name: AI.md\n"
        "  index_max_bytes: 4096\n  detail_max_lines: 400\n"
        "  architecture_overview: docs/methodology/core/harness-engineering.md\n"
        "  dependency_rules: docs/methodology/core/ddd-modeling.md\npermissions:\n"
        "  readable_paths: [.]\n  writable_paths: [docs]\n  denied_paths: [.env]\n"
        "  protected_paths: [docs/fitness]\n  fitness_changes: human-approval-required\n"
        "  network: deny-by-default\n  production_writes: approval-required\n"
        "  destructive_operations: approval-required\ndelivery:\n"
        "  migration_guide: openspec/README.md\n  production_policy: docs/methodology/production/policy.yaml\n"
        "methodology:\n  lifecycle: docs/methodology/core/change-lifecycle.md\n"
        "  engineering_skill: engineering\n",
        encoding="utf-8",
    )
    assert not validate_agent_policy(policy), validate_agent_policy(policy)
    for target in (project / ".claude/skills/engineering", project / ".agents/skills/engineering"):
        shutil.copytree(repository / "templates/engineering", target)
    for platform in ("claude", "codex"):
        result = verify("engineering", project, platform, source_root=repository)
        assert result["status"] == "PASS", result
    return profile


def write_contract(change_dir: Path, capability: str, mode: str) -> str:
    (change_dir / "context-pack.md").write_text("# Context\nRelevant repository facts.\n", encoding="utf-8")
    (change_dir / "impact-analysis.md").write_text("# Impact\nAffected modules, risks, and callers.\n", encoding="utf-8")
    analyzed_paths = [f"src/{mode}.txt"]
    signals = ["none"]
    ai_json = {"required": False, "paths": [], "reason": "No project map or routing change."}
    ai_md = {"required": False, "paths": [], "reason": "No detailed path responsibility or boundary change."}
    if mode == "frontend":
        analyzed_paths.append("AI.md")
        signals = ["boundary"]
        ai_md = {"required": True, "paths": ["AI.md"], "reason": "The root path boundary gains frontend behavior."}
    elif mode == "fullstack":
        analyzed_paths.append("ai.json")
        signals = ["project-summary"]
        ai_json = {"required": True, "paths": ["ai.json"], "reason": "The project summary changes for the fullstack capability."}
    write_json(change_dir / "context-impact.json", {
        "schema_version": 1, "analyzed_paths": analyzed_paths, "signals": signals,
        "ai_json": ai_json, "ai_md": ai_md,
    })
    (change_dir / "proposal.md").write_text("# Proposal\n## Why\nRequired behavior.\n## Scope\nOne capability.\n", encoding="utf-8")
    spec = "# Capability\n### Requirement: Behavior\nThe system MUST respond.\n#### Scenario: accepted\nWHEN input is valid\nTHEN output is returned\n"
    (change_dir / "specs" / capability / "spec.md").write_text(spec, encoding="utf-8")
    (change_dir / "design.md").write_text("# Design\n### D1: Boundary\nUse the approved contract.\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text("# Tasks\n- [ ] Implement\n- [ ] Verify\n", encoding="utf-8")
    return spec


def exercise_context_guards(project: Path) -> None:
    index_path = project / "ai.json"
    original_index = index_path.read_text(encoding="utf-8")
    assert not validate_context_docs(project)[0]

    invalid_index = json.loads(original_index)
    invalid_index["rules"] = ["must not live in the index"]
    write_json(index_path, invalid_index)
    assert any("keys must be exactly" in error for error in validate_context_docs(project)[0])

    invalid_index = json.loads(original_index)
    invalid_index["summary"] = "x" * 5000
    write_json(index_path, invalid_index)
    assert any("exceeds 4096 bytes" in error for error in validate_context_docs(project)[0])
    index_path.write_text(original_index, encoding="utf-8")

    unindexed = project / "unindexed/AI.md"
    unindexed.parent.mkdir()
    shutil.copy(project / "AI.md", unindexed)
    assert any("not indexed" in error for error in validate_context_docs(project)[0])
    unindexed.unlink()
    unindexed.parent.rmdir()

    with tempfile.TemporaryDirectory(prefix="context-outside-") as outside:
        outside_detail = Path(outside) / "AI.md"
        shutil.copy(project / "AI.md", outside_detail)
        escaped = project / "escaped/AI.md"
        escaped.parent.mkdir()
        escaped.symlink_to(outside_detail)
        assert any("resolves outside project root" in error for error in validate_context_docs(project)[0])
        escaped.unlink()
        escaped.parent.rmdir()

    impact_path = project / "context-impact-negative.json"
    base = {
        "schema_version": 1,
        "analyzed_paths": ["src/example.txt"],
        "signals": ["none"],
        "ai_json": {"required": False, "paths": [], "reason": "No index route changes."},
        "ai_md": {"required": False, "paths": [], "reason": "No detailed context changes."},
    }
    write_json(impact_path, base)
    assert not validate_context_impact(impact_path, project)[1]

    invalid_impact = json.loads(json.dumps(base))
    invalid_impact["signals"] = ["none", "boundary"]
    write_json(impact_path, invalid_impact)
    assert any("none must be used alone" in error for error in validate_context_impact(impact_path, project)[1])

    invalid_impact = json.loads(json.dumps(base))
    invalid_impact["signals"] = ["boundary"]
    write_json(impact_path, invalid_impact)
    assert any("signals require ai_md update" in error for error in validate_context_impact(impact_path, project)[1])

    invalid_impact = json.loads(json.dumps(base))
    invalid_impact["analyzed_paths"] = ["src/"]
    write_json(impact_path, invalid_impact)
    assert any("not a directory" in error for error in validate_context_impact(impact_path, project)[1])

    invalid_impact = json.loads(json.dumps(base))
    invalid_impact["analyzed_paths"] = ["../outside.txt"]
    write_json(impact_path, invalid_impact)
    assert any("normalized POSIX" in error or "escapes project root" in error for error in validate_context_impact(impact_path, project)[1])

    invalid_impact = json.loads(json.dumps(base))
    invalid_impact["analyzed_paths"] = ["src\\example.txt"]
    write_json(impact_path, invalid_impact)
    assert any("normalized POSIX" in error for error in validate_context_impact(impact_path, project)[1])

    invalid_impact = json.loads(json.dumps(base))
    invalid_impact["analyzed_paths"] = ["src/invalid\u0000.txt"]
    write_json(impact_path, invalid_impact)
    assert validate_context_impact(impact_path, project)[1]

    write_json(impact_path, {"schema_version": 1, "analyzed_paths": {}, "signals": {}, "ai_json": [], "ai_md": "bad"})
    assert validate_context_impact(impact_path, project)[1]
    impact_path.unlink()


def exercise_context_resolution(project: Path) -> None:
    source_context = project / "src/AI.md"
    order_context = project / "src/order/AI.md"
    source_context.parent.mkdir(parents=True, exist_ok=True)
    order_context.parent.mkdir(parents=True, exist_ok=True)
    source_context.write_text(context_detail("Source", "src", "Define source-wide development boundaries."), encoding="utf-8")
    order_context.write_text(context_detail("Order", "src/order", "Implement order capabilities."), encoding="utf-8")

    index_path = project / "ai.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["modules"].extend([
        {"path": "src", "summary": "Source-level context.", "context": "src/AI.md", "read_when": ["source"]},
        {"path": "src/order", "summary": "Order module context.", "context": "src/order/AI.md", "read_when": ["order"]},
    ])
    write_json(index_path, index)
    assert not validate_context_docs(project)[0], validate_context_docs(project)[0]

    expected = [
        "docs/methodology/agent-policy.yaml",
        "docs/methodology/profile.yaml",
        "ai.json",
        "AI.md",
        "src/AI.md",
        "src/order/AI.md",
    ]
    path_result = resolve_context(project, ["src/order/service.py"])
    assert path_result["load_order"] == expected, path_result
    keyword_result = resolve_context(project, ["README.md"], ["order"])
    assert keyword_result["load_order"] == expected, keyword_result

    code, output = invoke(resolve_context_main, [
        "resolve_context.py", "src/order/service.py", "--root", str(project), "--keyword", "order",
    ])
    assert code == 0 and "CONTEXT RESOLVED" in output, output

    for targets, keywords in [(["../outside.py"], []), (["README.md"], ["missing-route"])]:
        try:
            resolve_context(project, targets, keywords)
        except ContextResolutionError:
            pass
        else:
            raise AssertionError(f"context resolution must fail closed: targets={targets}, keywords={keywords}")

    modules = index["modules"]
    index["modules"] = [module for module in modules if module["path"] != "."]
    write_json(index_path, index)
    assert any("must include path '.'" in error for error in validate_context_docs(project)[0])
    index["modules"] = modules
    write_json(index_path, index)


def exercise_fitness_protection() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-protection-") as temp:
        project = Path(temp)
        run_git(project, "init", "-q")
        run_git(project, "config", "user.name", "Smoke")
        run_git(project, "config", "user.email", "smoke@example.invalid")
        (project / "README.md").write_text("# Smoke\n", encoding="utf-8")
        run_git(project, "add", "README.md")
        run_git(project, "commit", "-q", "-m", "initial")

        fitness = project / "docs/fitness"
        scripts = fitness / "scripts"
        scripts.mkdir(parents=True)
        (fitness / "README.md").write_text("# Fitness\n", encoding="utf-8")
        (scripts / "check_example.py").write_text("print('ok')\n", encoding="utf-8")
        bootstrap = check_fitness_protection(project)
        assert bootstrap["status"] == "PASS" and bootstrap["reason"] == "initial-bootstrap", bootstrap
        run_git(project, "add", "docs/fitness")
        run_git(project, "commit", "-q", "-m", "bootstrap fitness")
        assert check_fitness_protection(project)["reason"] == "unchanged"

        (fitness / "README.md").write_text("# Changed Fitness\n", encoding="utf-8")
        (fitness / "new-rule.md").write_text("# New Rule\n", encoding="utf-8")
        blocked = check_fitness_protection(project)
        assert blocked["status"] == "BLOCKED" and len(blocked["changes"]) == 2, blocked
        approval = {
            "FITNESS_CHANGE_APPROVED_BY": "human-reviewer",
            "FITNESS_CHANGE_APPROVAL_SOURCE": "pull-request",
            "FITNESS_CHANGE_APPROVAL_ID": "PR-123",
            "FITNESS_CHANGE_APPROVAL_DIGEST": str(blocked["digest"]),
        }
        wrong_approval = {**approval, "FITNESS_CHANGE_APPROVAL_DIGEST": "0" * 64}
        assert check_fitness_protection(project, environment=wrong_approval)["status"] == "BLOCKED"
        approved = check_fitness_protection(project, environment=approval)
        assert approved["status"] == "PASS" and approved["reason"] == "human-approved", approved
        baseline = run_git(project, "rev-parse", "HEAD")
        run_git(project, "add", "docs/fitness")
        run_git(project, "commit", "-q", "-m", "approved fitness update")
        committed_change = check_fitness_protection(project, base=baseline)
        assert committed_change["status"] == "BLOCKED" and len(committed_change["changes"]) == 2, committed_change

        broken = scripts / "broken.py"
        broken.write_text("def broken(:\n", encoding="utf-8")
        run_git(project, "add", "docs/fitness/scripts/broken.py")
        run_git(project, "commit", "-q", "-m", "broken baseline")
        broken.write_text("def repaired():\n    return True\n", encoding="utf-8")
        syntax_repair = check_fitness_protection(project)
        assert syntax_repair["status"] == "PASS" and syntax_repair["reason"] == "python-syntax-repair", syntax_repair

        run_git(project, "add", "docs/fitness/scripts/broken.py")
        run_git(project, "commit", "-q", "-m", "repair syntax")
        (fitness / "new-rule.md").unlink()
        deletion = check_fitness_protection(project)
        assert deletion["status"] == "BLOCKED", deletion


def transition(change_dir: Path, state: str, expected: int = 0) -> str:
    code, output = invoke(methodology_state_main, ["methodology_state.py", str(change_dir), state, "--actor", "smoke"])
    assert code == expected, output
    return output


def create_production_record(path: Path, change_id: str) -> None:
    write_json(path, {
        "schema_version": 1, "change_id": change_id, "title": "Production smoke",
        "environment": "production", "profile": "standard", "risk": "medium",
        "owner": "smoke", "service": "checkout", "state": "INTAKE",
        "technical_done": True, "operational_done": True,
        "evidence": {"spec": "spec", "tests": ["tests"], "gates": ["gates"], "review": "review", "threat_model": "n/a", "audit": "n/a"},
        "observability": {"dashboard": "dashboard", "alerts": ["error-rate > baseline"], "baseline": "baseline", "correlation": change_id, "observation_window_minutes": 30},
        "rollout": {"strategy": "canary", "stages": ["1%", "25%", "100%"], "stop_conditions": ["error-rate > 2%"], "operator": "smoke"},
        "rollback": {"strategy": "feature-flag", "runbook": "runbook", "owner": "smoke", "tested_at": "2026-09-04", "data_plan": "not-applicable", "target_minutes": 15},
        "approvals": {"reviewer": "reviewer", "approved_at": "2026-09-04T00:00:00Z"},
        "audit_log": f"docs/methodology/production/audit/{change_id}.jsonl",
    })


def close_production(path: Path) -> None:
    states = ("CLASSIFIED", "CONTEXT_READY", "CONTRACT_READY", "PLAN_APPROVED", "IMPLEMENTING", "VERIFYING", "REVIEW_REQUIRED")
    for state in states:
        code, output = invoke(production_state_main, ["change_state.py", str(path), state, "--actor", "smoke"])
        assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "RELEASE_READY", "--actor", "smoke", "--evidence", "release-approved"])
    assert code == 0, output
    for stage in ("1%", "25%", "100%"):
        code, output = invoke(production_state_main, ["change_state.py", str(path), "DEPLOYED", "--actor", "smoke", "--rollout-stage", stage, "--evidence", f"stage-{stage}-healthy"])
        assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "OBSERVING", "--actor", "smoke", "--evidence", "observation-started"])
    assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "CLOSED", "--actor", "smoke", "--evidence", "observation-complete"])
    assert code == 0, output


def exercise_rollback(project: Path) -> None:
    path = project / "docs/methodology/production/changes/smoke-rollback.json"
    create_production_record(path, "smoke-rollback")
    for state in ("CLASSIFIED", "CONTEXT_READY", "CONTRACT_READY", "PLAN_APPROVED", "IMPLEMENTING", "VERIFYING", "REVIEW_REQUIRED"):
        code, output = invoke(production_state_main, ["change_state.py", str(path), state, "--actor", "smoke"])
        assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "RELEASE_READY", "--actor", "smoke", "--evidence", "release-approved"])
    assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "DEPLOYED", "--actor", "smoke", "--rollout-stage", "1%", "--evidence", "stage-unhealthy"])
    assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "ROLLED_BACK", "--actor", "smoke", "--evidence", "rollback-complete"])
    assert code == 0, output
    code, output = invoke(production_state_main, ["change_state.py", str(path), "CLOSED", "--actor", "smoke", "--evidence", "rollback-observed"])
    assert code == 0, output
    errors: list[str] = []
    validate_production_closure({
        "delivery_scope": "production", "production_record": str(path),
        "change_id": "smoke-rollback", "project_root": str(project),
    }, errors)
    assert not errors, errors


def exercise_mode(project: Path, profile: Path, mode: str) -> None:
    change_id = f"smoke-{mode}"
    production = mode == "fullstack"
    production_record = project / "docs/methodology/production/changes" / f"{change_id}.json"
    arguments = [
        "init_change.py", change_id, "--title", f"Smoke {mode}", "--mode", mode,
        "--owner", "smoke", "--profile-path", str(profile),
        "--policy-path", str(project / "docs/methodology/agent-policy.yaml"),
        "--trigger", "native-selection",
        "--root", str(project / "openspec/changes"),
    ]
    if production:
        create_production_record(production_record, change_id)
        arguments.extend(("--delivery-scope", "production", "--production-record", str(production_record)))
    code, output = invoke(init_change_main, arguments)
    assert code == 0, output
    change_dir = project / "openspec/changes" / change_id

    transition(change_dir, "EXPLORED", expected=2)
    spec = write_contract(change_dir, change_id, mode)
    code, output = invoke(preflight_lessons_main, [
        "preflight_lessons.py", str(change_dir), "--actor", "smoke",
        "--keyword", mode, "--scope", mode, "--path", f"src/{mode}.txt",
    ])
    assert code == 0, output
    code, output = invoke(record_failure_main, [
        "record_failure.py", str(change_dir), "--source", "fitness", "--category", "fitness",
        "--rule", "java-documentation", "--message", "Public API comment is missing.",
        "--actor", "smoke", "--path", f"src/{mode}.txt", "--evidence", "fitness-smoke",
    ])
    assert code == 0, output
    transition(change_dir, "EXPLORED")
    transition(change_dir, "CONTRACT_READY")
    transition(change_dir, "DESIGN_READY")
    code, output = invoke(approve_main, ["approve_design.py", str(change_dir), "--actor", "reviewer", "--source", "test", "--approval-id", f"approval-{mode}"])
    assert code == 0, output
    transition(change_dir, "APPROVED")

    spec_path = change_dir / "specs" / change_id / "spec.md"
    spec_path.write_text(spec + "\ncontract drift\n", encoding="utf-8")
    transition(change_dir, "IMPLEMENTING", expected=2)
    spec_path.write_text(spec, encoding="utf-8")
    transition(change_dir, "IMPLEMENTING")
    transition(change_dir, "VERIFYING")

    changed_file = project / "src" / f"{mode}.txt"
    changed_file.parent.mkdir(parents=True, exist_ok=True)
    changed_file.write_text(f"implemented {mode}\n", encoding="utf-8")
    write_json(change_dir / "self-refine-evidence.json", {
        "schema_version": 1, "status": "passed", "actor": "agent",
        "at": utc_now(), "policy": "required", "iterations": 2,
        "artifacts": [{"path": "proposal.md", "findings": "Missing failure behavior was identified.", "resolution": "Added the failure scenario to the contract."}],
        "uncovered_risks": [],
        "independent_check": {"status": "not-required", "actor": "N/A", "evidence": "N/A"},
    })
    review_files = {f"src/{mode}.txt": sha256(changed_file)}
    review_payload = {
        "schema_version": 1, "status": "passed", "actor": "reviewer",
        "at": utc_now(), "change_digest": "a" * 64, "tasks_complete": True,
        "files": review_files,
        "commands": [{"command": "python3 -m py_compile changed.py", "exit_code": 0, "evidence": "smoke"}],
        "uncovered_cases": [], "exceptions": [],
    }
    if mode in {"frontend", "fullstack"}:
        write_json(change_dir / "review-evidence.json", review_payload)
        transition(change_dir, "VERIFIED", expected=2)
    if mode == "frontend":
        detail = project / "AI.md"
        detail.write_text(detail.read_text(encoding="utf-8") + "\n## Frontend Note\n\n- Frontend boundaries are verified explicitly.\n", encoding="utf-8")
        review_files["AI.md"] = sha256(detail)
    elif mode == "fullstack":
        context_index = json.loads((project / "ai.json").read_text(encoding="utf-8"))
        context_index["summary"] = "Temporary project for Harness lifecycle and fullstack verification."
        write_json(project / "ai.json", context_index)
        review_files["ai.json"] = sha256(project / "ai.json")
    review_payload["at"] = utc_now()
    review_payload["files"] = review_files
    write_json(change_dir / "review-evidence.json", review_payload)
    changed_file.write_text(f"drifted {mode}\n", encoding="utf-8")
    transition(change_dir, "VERIFIED", expected=2)
    changed_file.write_text(f"implemented {mode}\n", encoding="utf-8")
    transition(change_dir, "VERIFIED")

    canonical_spec = project / "openspec/specs" / change_id / "spec.md"
    canonical_spec.parent.mkdir(parents=True)
    shutil.copy(spec_path, canonical_spec)
    write_json(change_dir / "sync-evidence.json", {
        "schema_version": 1, "actor": "smoke", "at": utc_now(), "targets": [],
    })
    transition(change_dir, "SYNCED", expected=2)
    write_json(change_dir / "sync-evidence.json", {
        "schema_version": 1, "actor": "smoke", "at": utc_now(),
        "targets": [{"source": f"specs/{change_id}/spec.md", "destination": f"openspec/specs/{change_id}/spec.md", "sha256": sha256(spec_path)}],
    })
    transition(change_dir, "SYNCED")
    code, output = invoke(create_lesson_main, [
        "create_lesson_candidate.py", str(change_dir), f"smoke-lesson-{mode}",
        "--title", f"Smoke {mode} lesson", "--pattern", "A lifecycle gate failure was observed.",
        "--root-cause", "The smoke change intentionally exercised a blocked gate.",
        "--prevention", "Run the matching preflight and phase gate before delivery.",
        "--verification", "Run the Engineering smoke test.", "--scope", mode,
        "--keyword", mode, "--rule", "phase-review", "--path", f"src/{mode}.txt", "--owner", "smoke",
    ])
    assert code == 0, output
    if mode == "backend":
        code, output = invoke(approve_lesson_main, [
            "approve_lesson.py", str(change_dir / "lesson-candidate.json"),
            "--actor", "reviewer", "--source", "smoke", "--approval-id", "lesson-approval-backend",
        ])
        assert code == 0, output
        retrieved = retrieve(project, ["backend"], ["phase-review"], [], None)
        assert not retrieved["errors"] and len(retrieved["lessons"]) == 1, retrieved
    write_json(change_dir / "archive-evidence.json", {
        "schema_version": 1, "actor": "smoke", "at": utc_now(),
        "destination": f"openspec/changes/archive/2026-09-04-{change_id}",
    })
    if production:
        transition(change_dir, "ARCHIVED", expected=2)
        close_production(production_record)
    transition(change_dir, "ARCHIVED")
    assert not check(change_dir, "ARCHIVE"), check(change_dir, "ARCHIVE")


def run() -> None:
    repository = Path(__file__).resolve().parent.parent
    if not (repository / "templates").is_dir() or not (repository / "core").is_dir():
        # Kit-dev-only script: it validates the kit's own templates and core
        # documents, so it must run from a kit checkout, never an installed copy.
        print("SKILL SMOKE FAIL: run from a kit checkout (templates/ and core/ not found next to scripts/)")
        raise SystemExit(2)
    with tempfile.TemporaryDirectory(prefix="methodology-smoke-") as temp:
        project = Path(temp)
        profile = prepare_project(project, repository)
        exercise_context_guards(project)
        exercise_context_resolution(project)
        exercise_fitness_protection()
        for mode in ("backend", "frontend", "fullstack"):
            exercise_mode(project, profile, mode)
        exercise_rollback(project)
        code, output = invoke(metrics_main, ["skill_metrics.py", str(project / "openspec/changes")])
        assert code == 0, output
        metrics = json.loads(output)
        assert metrics["triggered"] == 3 and metrics["archived"] == 3, metrics
        assert metrics["by_mode"] == {"backend": 1, "frontend": 1, "fullstack": 1}, metrics
        assert metrics["failure_events"] >= 3 and metrics["lesson_candidates"] == 3 and metrics["lesson_promotions"] == 1, metrics
        invalid_events = project / "openspec/changes/smoke-backend/evidence/events.jsonl"
        with invalid_events.open("a", encoding="utf-8") as stream:
            stream.write("not-json\n")
        code, _ = invoke(metrics_main, ["skill_metrics.py", str(project / "openspec/changes")])
        assert code == 2, "invalid metrics input must fail closed"
        print("SKILL SMOKE PASS: context guards, deterministic resolution, Fitness protection, two platforms, three modes, drift, sync, rollout, rollback, closure, metrics")


if __name__ == "__main__":
    try:
        run()
    except (AssertionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"SKILL SMOKE FAIL: {exc}")
        raise SystemExit(2)
