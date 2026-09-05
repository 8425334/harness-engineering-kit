"""Regression tests for the strict-review fixes in the control scripts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from check_agent_policy import validate as validate_agent_policy  # noqa: E402
from check_phase import check, is_exit_code  # noqa: E402
from check_production_readiness import rollout_cycles, validate as validate_production  # noqa: E402
from lessons_common import load_lessons, validate_lesson  # noqa: E402
from methodology_common import meaningful, write_json  # noqa: E402
from check_change_workspace import HOOK_COMMAND, check_workspace, hook_decision, install_hook  # noqa: E402
from check_task_plan import execution_waves, validate_execution, validate_plan  # noqa: E402
from dispatch_openspec import DispatchRequest, authorize, build_command, dispatch  # noqa: E402
from openspec_common import orchestration_contract  # noqa: E402
from record_task_completion import record_completion, resume_execution, sync_checkboxes  # noqa: E402


def run_script(name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / name), *arguments],
        capture_output=True,
        text=True,
    )


def base_lesson(**overrides: object) -> dict[str, object]:
    lesson = {
        "schema_version": 1, "lesson_id": "sample-lesson", "title": "t", "pattern": "p",
        "root_cause": "rc", "prevention": "pv", "verification": "v", "scope": "project",
        "status": "active", "keywords": ["k"], "paths": [], "rules": [],
        "source_changes": [], "source_events": [],
    }
    lesson.update(overrides)
    return lesson


def base_production_record(**overrides: object) -> dict[str, object]:
    record = {
        "schema_version": 1, "change_id": "demo-1", "title": "t", "environment": "production",
        "profile": "standard", "risk": "medium", "owner": "o", "service": "svc", "state": "INTAKE",
        "technical_done": False, "operational_done": False,
        "evidence": {"spec": "s", "tests": ["t"], "gates": ["g"], "review": "r"},
        "observability": {"dashboard": "d", "alerts": ["a"], "baseline": "b", "correlation": "c"},
        "rollout": {"strategy": "canary", "stages": ["1%", "25%", "100%"], "stop_conditions": ["sc"], "operator": "op"},
        "rollback": {"strategy": "st", "runbook": "rb", "owner": "o", "tested_at": "2026-01-01", "data_plan": "dp"},
        "approvals": {"reviewer": "rev", "approved_at": "2026-01-01"},
        "audit_log": "docs/methodology/production/audit/demo-1.jsonl",
    }
    record.update(overrides)
    return record


def write_task_plan(change_dir: Path, *, overlap: bool = False, cycle: bool = False) -> dict[str, object]:
    (change_dir / "specs/demo").mkdir(parents=True, exist_ok=True)
    (change_dir / "design.md").write_text("# Design\n\n## D1\n\nBoundaries.\n", encoding="utf-8")
    (change_dir / "specs/demo/spec.md").write_text("# Spec\n\nBehavior.\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text("# Tasks\n\n- [ ] T1 Implement API\n- [ ] T2 Add tests\n", encoding="utf-8")
    plan: dict[str, object] = {
        "schema_version": 1,
        "strategy": "parallel-when-supported",
        "tasks": [
            {
                "id": "T1", "title": "Implement API", "kind": "implementation",
                "depends_on": ["T2"] if cycle else [], "write_scope": ["src/api"],
                "contract_refs": ["design.md#D1", "specs/demo/spec.md"],
                "acceptance": ["API behavior is implemented."], "verification": ["test api"],
                "parallelizable": True,
            },
            {
                "id": "T2", "title": "Add tests", "kind": "test",
                "depends_on": ["T1"] if cycle else [],
                "write_scope": ["src/api/tests" if overlap else "tests/api"],
                "contract_refs": ["design.md#D1", "specs/demo/spec.md"],
                "acceptance": ["Behavior is covered."], "verification": ["test focused"],
                "parallelizable": True,
            },
        ],
        "integration": {
            "owner": "coordinator", "merge_order": ["T1", "T2"],
            "final_verification": ["test all"],
        },
    }
    write_json(change_dir / "task-plan.json", plan)
    return plan


def execution_record(*, parallel: bool = True) -> dict[str, object]:
    second_start = "2026-09-06T10:06:00+00:00" if parallel else "2026-09-06T10:31:00+00:00"
    return {
        "schema_version": 1,
        "strategy": "parallel" if parallel else "sequential",
        "fallback_reason": None if parallel else "runtime has no concurrent worker API",
        "coordinator": "coordinator",
        "capability": {
            "agent_parallelism": parallel,
            "isolation": "worktree" if parallel else "single-workspace",
            "max_concurrency": 2 if parallel else 1,
        },
        "started_at": "2026-09-06T10:01:00+00:00",
        "completed_at": "2026-09-06T10:50:00+00:00",
        "task_runs": [
            {
                "task_id": "T1", "actor": "worker-1", "status": "completed",
                "isolation": "worktree" if parallel else "single-workspace", "workspace": "worktree-1",
                "result_ref": "commit-1" if parallel else "shared-workspace:T1",
                "started_at": "2026-09-06T10:05:00+00:00", "completed_at": "2026-09-06T10:30:00+00:00",
                "changed_files": ["src/api/handler.py"],
                "commands": [{"command": "test api", "exit_code": 0, "evidence": "api.log"}],
            },
            {
                "task_id": "T2", "actor": "worker-2" if parallel else "coordinator", "status": "completed",
                "isolation": "worktree" if parallel else "single-workspace", "workspace": "worktree-2",
                "result_ref": "commit-2" if parallel else "shared-workspace:T2",
                "started_at": second_start, "completed_at": "2026-09-06T10:45:00+00:00",
                "changed_files": ["tests/api/test_handler.py"],
                "commands": [{"command": "test focused", "exit_code": 0, "evidence": "focused.log"}],
            },
        ],
        "integration": {
            "actor": "coordinator", "status": "passed", "order": ["T1", "T2"],
            "conflicts": [], "changed_files": [],
            "commands": [{"command": "test all", "exit_code": 0, "evidence": "all.log"}],
        },
    }


class LessonMemoryTests(unittest.TestCase):
    def test_retired_lessons_are_skipped_not_errors(self) -> None:
        """S1: retiring a lesson must not brick retrieval or the Explore gate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / "docs/methodology/lessons"
            lessons.mkdir(parents=True)
            write_json(lessons / "active-one.json", base_lesson(lesson_id="active-one"))
            write_json(lessons / "retired-one.json", base_lesson(lesson_id="retired-one", status="retired"))
            loaded, errors = load_lessons(root, active_only=True)
            self.assertEqual(errors, [])
            self.assertEqual([lesson["lesson_id"] for lesson in loaded], ["active-one"])

    def test_invalid_lesson_status_is_still_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / "docs/methodology/lessons"
            lessons.mkdir(parents=True)
            write_json(lessons / "weird.json", base_lesson(lesson_id="weird", status="frozen"))
            _, errors = load_lessons(root, active_only=True)
            self.assertTrue(any("status" in error for error in errors))

    def test_malformed_lesson_fields_are_blocked(self) -> None:
        """M7/L10: type checks keep broken lessons out of the active set."""
        for field, value in (("source_events", None), ("rules", "phase-review"), ("paths", "src/x"), ("keywords", [])):
            with self.subTest(field=field):
                errors = validate_lesson(base_lesson(**{field: value}))
                self.assertTrue(errors, f"{field}={value!r} must not validate")

    def test_event_id_uses_a_single_normalized_timestamp(self) -> None:
        """L9: the failure id ends in Z and matches the recorded `at`."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            (change_dir / "evidence").mkdir(parents=True)
            write_json(change_dir / "change.json", {
                "schema_version": 3, "change_id": "demo-1", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": str(Path(directory)), "state": "INTAKE",
                "owner": "o", "orchestration": orchestration_contract("demo-1"), "events": [],
            })
            completed = run_script(
                "record_failure.py", str(change_dir), "--source", "fitness", "--category", "fitness",
                "--rule", "demo-rule", "--message", "m", "--actor", "tester",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            event = json.loads((change_dir / "evidence/failure-events.jsonl").read_text().splitlines()[0])
            self.assertNotIn("+0000", event["event_id"])
            self.assertIn("Z-", event["event_id"], "the normalized timestamp must carry a Z suffix inside the id")
            stamp = event["event_id"].removeprefix("failure-").removesuffix("-demo-rule")
            self.assertTrue(event["at"].replace("+00:00", "Z").replace(":", "").startswith(stamp))


class TaskOrchestrationTests(unittest.TestCase):
    def test_valid_parallel_graph_has_deterministic_waves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            plan = write_task_plan(change_dir)
            loaded, errors = validate_plan(change_dir)
            self.assertEqual(errors, [])
            self.assertEqual(loaded, plan)
            self.assertEqual(execution_waves(plan), [["T1", "T2"]])
            completed = run_script("check_task_plan.py", str(change_dir), "--json")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["waves"], [["T1", "T2"]])

    def test_independent_parallel_tasks_must_have_disjoint_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir, overlap=True)
            _, errors = validate_plan(change_dir)
            self.assertTrue(any("overlapping write_scope" in error for error in errors))

    def test_cycles_and_task_markdown_drift_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir, cycle=True)
            (change_dir / "tasks.md").write_text("# Tasks\n\n- [ ] T2 Wrong order\n- [ ] T1 Wrong order\n", encoding="utf-8")
            _, errors = validate_plan(change_dir)
            self.assertTrue(any("acyclic" in error for error in errors))
            self.assertTrue(any("checkbox ids and order" in error for error in errors))

    def test_malformed_task_fields_block_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            plan = write_task_plan(change_dir)
            plan["tasks"][0]["depends_on"] = None  # type: ignore[index]
            plan["tasks"][1]["write_scope"] = 42  # type: ignore[index]
            write_json(change_dir / "task-plan.json", plan)
            completed = run_script("check_task_plan.py", str(change_dir), "--json")
            self.assertEqual(completed.returncode, 2)
            self.assertNotIn("Traceback", completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "BLOCKED")

    def test_every_analyzed_path_needs_a_task_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir)
            write_json(change_dir / "context-impact.json", {"analyzed_paths": ["src/api/handler.py", "docs/unowned.md"]})
            _, errors = validate_plan(change_dir)
            self.assertTrue(any("docs/unowned.md" in error and "no task owner" in error for error in errors))

    def test_task_markdown_is_unchecked_at_design_and_mutable_at_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir)
            (change_dir / "tasks.md").write_text("# Tasks\n\n- [x] T1 Implement API\n- [ ] T2 Add tests\n", encoding="utf-8")
            _, errors = validate_plan(change_dir)
            self.assertTrue(any("every checkbox unchecked" in error for error in errors))
            _, runtime_errors = validate_plan(change_dir, status_mode="runtime")
            self.assertEqual(runtime_errors, [])

    def test_recording_task_completion_ticks_open_spec_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo"
            plan = write_task_plan(change_dir)
            plan["tasks"][1]["depends_on"] = ["T1"]  # type: ignore[index]
            write_json(change_dir / "task-plan.json", plan)
            write_json(change_dir / "change.json", {
                "schema_version": 3, "change_id": "demo", "state": "IMPLEMENTING",
                "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "project_root": str(root), "orchestration": orchestration_contract("demo"), "events": [],
            })
            evidence = execution_record(parallel=False)
            first_run = evidence["task_runs"][0]  # type: ignore[index]
            evidence["task_runs"] = []
            write_json(change_dir / "execution-evidence.json", evidence)

            self.assertEqual(record_completion(change_dir, "T1", first_run), [])  # type: ignore[arg-type]
            markdown = (change_dir / "tasks.md").read_text(encoding="utf-8")
            self.assertIn("- [x] T1", markdown)
            self.assertIn("- [ ] T2", markdown)
            stored = json.loads((change_dir / "execution-evidence.json").read_text(encoding="utf-8"))
            self.assertEqual([run["task_id"] for run in stored["task_runs"]], ["T1"])
            self.assertEqual(json.loads((change_dir / "change.json").read_text())["events"][-1]["event"], "task.completed")

    def test_resume_reconciles_checkboxes_and_returns_next_wave(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo"
            plan = write_task_plan(change_dir)
            plan["tasks"][1]["depends_on"] = ["T1"]  # type: ignore[index]
            write_json(change_dir / "task-plan.json", plan)
            write_json(change_dir / "change.json", {
                "schema_version": 3, "change_id": "demo", "state": "IMPLEMENTING",
                "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "project_root": str(root), "orchestration": orchestration_contract("demo"), "events": [],
            })
            evidence = execution_record(parallel=False)
            evidence["task_runs"] = [evidence["task_runs"][0]]  # type: ignore[index]
            write_json(change_dir / "execution-evidence.json", evidence)

            payload, errors = resume_execution(change_dir, "resume-agent")

            self.assertEqual(errors, [])
            self.assertEqual(payload["completed_tasks"], ["T1"])  # type: ignore[index]
            self.assertEqual(payload["pending_tasks"], ["T2"])  # type: ignore[index]
            self.assertEqual(payload["ready_waves"], [["T2"]])  # type: ignore[index]
            self.assertIn("- [x] T1", (change_dir / "tasks.md").read_text(encoding="utf-8"))
            record = json.loads((change_dir / "change.json").read_text(encoding="utf-8"))
            self.assertEqual(record["events"][-1]["event"], "execution.resumed")

    def test_sync_rejects_incomplete_run_instead_of_ticking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir)
            evidence = execution_record()
            evidence["task_runs"][0]["commands"][0]["exit_code"] = 1  # type: ignore[index]
            write_json(change_dir / "execution-evidence.json", evidence)

            errors = sync_checkboxes(change_dir)

            self.assertTrue(any("exit_code=0" in error for error in errors))
            self.assertIn("- [ ] T1", (change_dir / "tasks.md").read_text(encoding="utf-8"))

    def test_valid_parallel_execution_proves_overlap_and_file_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir)
            write_json(change_dir / "execution-evidence.json", execution_record())
            self.assertEqual(sync_checkboxes(change_dir), [])
            record = {
                "events": [
                    {"event": "methodology.transition", "to": "IMPLEMENTING", "at": "2026-09-06T10:00:00+00:00"},
                    {"event": "methodology.transition", "to": "VERIFYING", "at": "2026-09-06T11:00:00+00:00"},
                ]
            }
            review = {"files": {"src/api/handler.py": "digest", "tests/api/test_handler.py": "digest"}}
            self.assertEqual(validate_execution(change_dir, record, review), [])

    def test_sequential_fallback_uses_the_same_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir)
            write_json(change_dir / "execution-evidence.json", execution_record(parallel=False))
            self.assertEqual(sync_checkboxes(change_dir), [])
            review = {"files": {"src/api/handler.py": "digest", "tests/api/test_handler.py": "digest"}}
            self.assertEqual(validate_execution(change_dir, {"events": []}, review), [])

    def test_false_parallel_claim_and_scope_escape_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            write_task_plan(change_dir)
            evidence = execution_record()
            evidence["task_runs"][1]["actor"] = "worker-1"  # type: ignore[index]
            evidence["task_runs"][0]["changed_files"] = ["src/other.py"]  # type: ignore[index]
            write_json(change_dir / "execution-evidence.json", evidence)
            self.assertTrue(sync_checkboxes(change_dir))
            self.assertIn("- [ ] T1", (change_dir / "tasks.md").read_text(encoding="utf-8"))
            review = {"files": {"src/other.py": "digest", "tests/api/test_handler.py": "digest"}}
            errors = validate_execution(change_dir, {"events": []}, review)
            self.assertTrue(any("different actors" in error for error in errors))
            self.assertTrue(any("outside write_scope" in error for error in errors))

    def test_parallel_runs_enforce_barriers_worktrees_and_declared_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "demo"
            plan = write_task_plan(change_dir)
            plan["tasks"][1]["parallelizable"] = False  # type: ignore[index]
            write_json(change_dir / "task-plan.json", plan)
            evidence = execution_record()
            evidence["capability"]["max_concurrency"] = 1  # type: ignore[index]
            evidence["task_runs"][1]["workspace"] = "worktree-1"  # type: ignore[index]
            write_json(change_dir / "execution-evidence.json", evidence)
            self.assertEqual(sync_checkboxes(change_dir), [])
            review = {"files": {"src/api/handler.py": "digest", "tests/api/test_handler.py": "digest"}}
            errors = validate_execution(change_dir, {"events": []}, review)
            self.assertTrue(any("non-parallel task overlapped" in error for error in errors))
            self.assertTrue(any("share a workspace" in error for error in errors))
            self.assertTrue(any("max_concurrency" in error for error in errors))
            self.assertTrue(any("exceeds" in error for error in errors))


class ProductionRecordTests(unittest.TestCase):
    def test_malformed_records_fail_closed(self) -> None:
        """M9: previously passing gaps now block the readiness gate."""
        cases = {
            "audit_log none": base_production_record(audit_log=None),
            "audit_log empty": base_production_record(audit_log=""),
            "audit_log absolute": base_production_record(audit_log="/var/log/audit.jsonl"),
            "stages as string": base_production_record(rollout={"strategy": "canary", "stages": "1% 25% 100%", "stop_conditions": ["sc"], "operator": "op"}),
            "stages empty": base_production_record(rollout={"strategy": "canary", "stages": [], "stop_conditions": ["sc"], "operator": "op"}),
            "stages duplicated": base_production_record(rollout={"strategy": "canary", "stages": ["1%", "1%"], "stop_conditions": ["sc"], "operator": "op"}),
            "wrong schema": base_production_record(schema_version=99),
            "unknown state": base_production_record(state="WHATEVER"),
            "done as string": base_production_record(technical_done="false", operational_done="false"),
            "placeholder window": base_production_record(
                state="DEPLOYED", technical_done=True, operational_done=True,
                observability={"dashboard": "d", "alerts": ["a"], "baseline": "b", "correlation": "c", "observation_window_minutes": "{{WINDOW}}"},
            ),
        }
        for name, record in cases.items():
            with self.subTest(case=name):
                self.assertTrue(validate_production(record), f"{name} must not pass")

    def test_valid_record_passes(self) -> None:
        self.assertEqual(validate_production(base_production_record()), [])

    def test_rollout_cycles_reset_on_rollback(self) -> None:
        """M10: a rollback restarts the rollout sequence from the first stage."""
        events = [
            {"to": "DEPLOYED", "rollout_stage": "1%"},
            {"to": "ROLLED_BACK", "evidence": ["rollback-done"]},
            {"to": "REMEDIATING"},
        ]
        self.assertEqual(rollout_cycles(events)[-1], [])
        events.extend([
            {"to": "DEPLOYED", "rollout_stage": "1%"},
            {"to": "DEPLOYED", "rollout_stage": "25%"},
            {"to": "DEPLOYED", "rollout_stage": "100%"},
        ])
        self.assertEqual(rollout_cycles(events)[-1], ["1%", "25%", "100%"])
        self.assertEqual(len(rollout_cycles(events)), 2)

    def test_non_dict_record_is_rejected_cleanly(self) -> None:
        """M13: a JSON array record exits 2 with a message, not a traceback."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / "docs/methodology/production/changes"
            changes.mkdir(parents=True)
            record_path = changes / "demo-1.json"
            record_path.write_text("[1, 2, 3]\n", encoding="utf-8")
            completed = run_script("change_state.py", str(record_path), "CLASSIFIED", "--actor", "t")
            self.assertEqual(completed.returncode, 2)
            self.assertIn("JSON object", completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stdout + completed.stderr)

    def test_record_outside_canonical_location_is_blocked(self) -> None:
        """L15: location checking matches the canonical directory layout."""
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "somewhere/production/changes/demo-1.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(base_production_record()), encoding="utf-8")
            completed = run_script("change_state.py", str(record_path), "CLASSIFIED", "--actor", "t")
            self.assertEqual(completed.returncode, 2)
            self.assertIn("docs/methodology/production/changes", completed.stdout + completed.stderr)


class GateAndLifecycleTests(unittest.TestCase):
    def test_change_id_must_match_directory_name(self) -> None:
        """L17: a hand-edited change.json cannot carry a foreign change_id."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "change.json", {
                "schema_version": 3, "change_id": "other-id", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": "/nonexistent", "state": "INTAKE",
                "owner": "o", "orchestration": orchestration_contract("other-id"), "events": [],
            })
            errors = check(change_dir, "EXPLORE")
            self.assertTrue(any("must match the change directory name" in error for error in errors))

    def test_review_exit_code_must_be_an_integer(self) -> None:
        """L18: JSON false is not a zero exit code."""
        self.assertTrue(is_exit_code(0))
        self.assertFalse(is_exit_code(False))
        self.assertFalse(is_exit_code("0"))
        self.assertFalse(is_exit_code(None))

    def test_binary_artifact_is_not_meaningful(self) -> None:
        """M12: non-UTF-8 artifacts fail the gate instead of crashing it."""
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "spec.md"
            binary.write_bytes(b"# spec\n\n\xff\xfe binary")
            self.assertFalse(meaningful(binary))

    def test_policy_location_is_enforced(self) -> None:
        """M4: a policy outside docs/methodology fails with a clear error."""
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "agent-policy.yaml"
            policy.write_text("version: 1\n", encoding="utf-8")
            errors = validate_agent_policy(policy)
            self.assertTrue(any("docs/methodology/agent-policy.yaml" in error for error in errors))

    def test_init_change_rejects_non_canonical_policy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profile.yaml").write_text("version: 2\n", encoding="utf-8")
            (root / "agent-policy.yaml").write_text("version: 1\n", encoding="utf-8")
            completed = run_script(
                "init_change.py", "demo-1", "--title", "T", "--mode", "backend", "--owner", "o",
                "--trigger", "native-selection",
                "--profile-path", str(root / "profile.yaml"),
                "--policy-path", str(root / "agent-policy.yaml"),
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("docs/methodology/agent-policy.yaml", completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stdout + completed.stderr)

    def test_approve_design_refuses_to_rebind(self) -> None:
        """M11: an existing approval blocks silent digest rebinding."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "change.json", {
                "schema_version": 3, "change_id": "demo-1", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": "/nonexistent", "state": "DESIGN_READY",
                "owner": "o", "orchestration": orchestration_contract("demo-1"), "events": [],
            })
            write_json(change_dir / "approval.json", {"schema_version": 1, "status": "approved"})
            completed = run_script(
                "approve_design.py", str(change_dir), "--actor", "reviewer",
                "--source", "test", "--approval-id", "AP-2",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("already exists", completed.stdout + completed.stderr)

    def test_preflight_requires_project_root(self) -> None:
        """L14: a change record without project_root fails loudly, not via CWD."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "change.json", {"schema_version": 3, "change_id": "demo-1", "state": "INTAKE", "orchestration": orchestration_contract("demo-1")})
            completed = run_script("preflight_lessons.py", str(change_dir), "--actor", "tester")
            self.assertEqual(completed.returncode, 2)
            self.assertIn("project_root", completed.stdout + completed.stderr)

    def test_approve_lesson_validates_before_writing(self) -> None:
        """L13: a change workspace outside project_root is blocked before any write."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            elsewhere = Path(directory) / "elsewhere/changes/demo-1"
            (project / "docs/methodology/lessons").mkdir(parents=True)
            (elsewhere / "evidence").mkdir(parents=True)
            write_json(elsewhere / "change.json", {
                "schema_version": 3, "change_id": "demo-1", "state": "VERIFYING",
                "orchestration": orchestration_contract("demo-1"),
                "project_root": str(project), "events": [],
            })
            write_json(elsewhere / "lesson-candidate.json", base_lesson(lesson_id="demo-lesson", status="candidate"))
            (elsewhere / "evidence/failure-events.jsonl").write_text("", encoding="utf-8")
            completed = run_script(
                "approve_lesson.py", str(elsewhere / "lesson-candidate.json"),
                "--actor", "reviewer", "--source", "test", "--approval-id", "AP-1",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("does not contain", completed.stdout + completed.stderr)
            self.assertFalse((project / "docs/methodology/lessons/demo-lesson.json").exists())


class MetricsTests(unittest.TestCase):
    def test_archived_changes_still_count(self) -> None:
        """M5: metrics must include the documented archive destination."""
        with tempfile.TemporaryDirectory() as directory:
            changes = Path(directory)
            # Documented layout: openspec/changes/archive/<date>-<change-id>/.
            archived = changes / "archive/2026-09-05-demo-1/evidence"
            archived.mkdir(parents=True)
            (archived / "events.jsonl").write_text(
                '{"event": "skill.triggered", "change_id": "demo-1", "at": "2026-01-01T00:00:00Z", "mode": "backend"}\n'
                '{"event": "methodology.transition", "change_id": "demo-1", "at": "2026-01-01T00:00:01Z", "to": "ARCHIVED"}\n',
                encoding="utf-8",
            )
            (changes / "archive/2026-09-05-demo-1/lesson-candidate.json").write_text("{}", encoding="utf-8")
            write_json(changes / "archive/2026-09-05-demo-1/execution-evidence.json", execution_record())
            completed = run_script("skill_metrics.py", str(changes))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metrics = json.loads(completed.stdout)
            self.assertEqual(metrics["triggered"], 1)
            self.assertEqual(metrics["archived"], 1)
            self.assertEqual(metrics["completion_rate"], 1.0)
            self.assertEqual(metrics["lesson_candidates"], 1)
            self.assertEqual(metrics["execution_by_strategy"], {"parallel": 1})
            self.assertEqual(metrics["parallel_adoption_rate"], 1.0)
            self.assertEqual(metrics["task_runs"], 2)
            self.assertEqual(metrics["max_declared_concurrency"], 2)

    def test_missing_changes_root_fails_closed(self) -> None:
        """L12: a nonexistent root reports an error instead of silent zeros."""
        completed = run_script("skill_metrics.py", "/nonexistent/changes-root")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CHANGES ROOT MISSING", completed.stdout + completed.stderr)


class AtomicityTests(unittest.TestCase):
    def test_write_json_replaces_atomically_and_cleans_up(self) -> None:
        """M8: no .tmp remnants and the payload round-trips."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested/record.json"
            payload = {"schema_version": 1, "items": ["a"]}
            write_json(target, payload)
            write_json(target, {**payload, "items": ["a", "b"]})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["items"], ["a", "b"])
            self.assertEqual(list(Path(directory, "nested").glob("*.tmp")), [])


class ChangeWorkspaceGuardTests(unittest.TestCase):
    """Workspace-ownership guard (check_change_workspace.py)."""

    def _registered(self, change_dir: Path, project_root: Path, change_id: str | None = None) -> None:
        write_json(change_dir / "change.json", {
            "schema_version": 3, "change_id": change_id or change_dir.name, "title": "t",
            "profile": "standard", "risk": "medium", "skill": "engineering", "mode": "backend",
            "trigger": "manual-fallback", "delivery_scope": "technical",
            "project_root": str(project_root), "state": "INTAKE", "owner": "o",
            "orchestration": orchestration_contract(change_id or change_dir.name), "events": [],
        })

    def test_missing_or_empty_changes_root_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(check_workspace(root), [])
            (root / "openspec/changes").mkdir(parents=True)
            self.assertEqual(check_workspace(root), [])

    def test_all_registered_changes_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo-1"
            change_dir.mkdir(parents=True)
            self._registered(change_dir, root)
            self.assertEqual(check_workspace(root), [])

    def test_unmanaged_directory_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            orphan = root / "openspec/changes/realtime-3d-explosion"
            orphan.mkdir(parents=True)
            (orphan / "proposal.md").write_text("# proposal\n", encoding="utf-8")
            errors = check_workspace(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("openspec/changes/realtime-3d-explosion", errors[0])
            self.assertIn("missing canonical change.json", errors[0])

    def test_unmanaged_directories_are_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / "openspec/changes"
            for name in ("zz-orphan", "aa-orphan"):
                (changes / name).mkdir(parents=True)
            errors = check_workspace(root)
            self.assertEqual([error.split(":")[0] for error in errors], [
                "openspec/changes/aa-orphan",
                "openspec/changes/zz-orphan",
            ])

    def test_archive_dot_entries_and_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / "openspec/changes"
            (changes / "archive/2026-09-05-open-a").mkdir(parents=True)
            (changes / ".hidden-draft").mkdir(parents=True)
            (changes / "notes.md").write_text("x", encoding="utf-8")
            (changes / "orphan").mkdir(parents=True)
            errors = check_workspace(root)
            self.assertEqual([error.split(":")[0] for error in errors], ["openspec/changes/orphan"])

    def test_bad_schema_and_foreign_change_id_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad_schema = root / "openspec/changes/bad-schema"
            bad_schema.mkdir(parents=True)
            write_json(bad_schema / "change.json", {"schema_version": 1, "change_id": "bad-schema"})
            wrong_id = root / "openspec/changes/wrong-id"
            wrong_id.mkdir(parents=True)
            write_json(wrong_id / "change.json", {"schema_version": 3, "change_id": "other-id", "orchestration": orchestration_contract("other-id")})
            errors = check_workspace(root)
            self.assertTrue(any("bad-schema" in error and "schema_version" in error for error in errors))
            self.assertTrue(any("wrong-id" in error and "must match" in error for error in errors))

    def test_phase_gate_fails_closed_on_unmanaged_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registered = root / "openspec/changes/registered"
            orphan = root / "openspec/changes/orphan"
            registered.mkdir(parents=True)
            orphan.mkdir(parents=True)
            (orphan / "proposal.md").write_text("# x\n", encoding="utf-8")
            self._registered(registered, root)
            errors = check(registered, "EXPLORE")
            self.assertTrue(any(error.startswith("workspace:") and "orphan" in error for error in errors))
            self._registered(orphan, root)
            errors = check(registered, "EXPLORE")
            self.assertFalse(any(error.startswith("workspace:") for error in errors))

    def test_hook_decision_blocks_unmanaged_write_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / "openspec/changes"
            (changes / "ok").mkdir(parents=True)
            (changes / "bad").mkdir(parents=True)
            (changes / "archive/old").mkdir(parents=True)
            self._registered(changes / "ok", root)
            self.assertTrue(hook_decision("Write", {"file_path": str(changes / "bad/x.md")}, root))
            self.assertEqual(hook_decision("Write", {"file_path": str(changes / "ok/x.md")}, root), [])
            self.assertEqual(hook_decision("Edit", {"file_path": str(changes / "archive/old/x.md")}, root), [])
            self.assertEqual(hook_decision("Write", {"file_path": str(root / "src/a.ts")}, root), [])
            self.assertEqual(hook_decision("Bash", {"command": "cat package.json"}, root), [])

    def test_hook_decision_blocks_openspec_lane_but_allows_harness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(hook_decision("Bash", {"command": "openspec apply --change demo-1"}, root))
            self.assertTrue(hook_decision("Bash", {"command": "openspec new change demo-2"}, root))
            self.assertTrue(hook_decision("Bash", {"command": "npx openspec archive demo-3"}, root))
            self.assertTrue(hook_decision("Bash", {"command": "openspec status --change demo-1"}, root))
            self.assertEqual(hook_decision("Bash", {"command": "openspec templates --json"}, root), [])
            harness = (
                "python3 docs/methodology/scripts/init_change.py demo-1 --title T --mode frontend "
                "--owner o --trigger manual-fallback --fallback-reason drafted-outside"
            )
            self.assertEqual(hook_decision("Bash", {"command": harness}, root), [])
            dispatcher = "python3 docs/methodology/scripts/dispatch_openspec.py openspec/changes/demo-1 status"
            self.assertEqual(hook_decision("Bash", {"command": dispatcher}, root), [])

    def test_orchestration_contract_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo-1"
            change_dir.mkdir(parents=True)
            self._registered(change_dir, root)
            record = json.loads((change_dir / "change.json").read_text(encoding="utf-8"))
            record.pop("orchestration")
            write_json(change_dir / "change.json", record)
            self.assertTrue(any("orchestration" in error for error in check_workspace(root)))

    def test_cli_scan_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "openspec/changes/orphan").mkdir(parents=True)
            completed = run_script("check_change_workspace.py", "--root", str(root))
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn("BLOCKED", completed.stdout + completed.stderr)
            self.assertIn("orphan", completed.stdout + completed.stderr)
            (root / "openspec/changes").joinpath("orphan").rmdir()
            completed = run_script("check_change_workspace.py", "--root", str(root))
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_install_hook_is_idempotent_and_preserves_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / ".claude/settings.json"
            settings.parent.mkdir(parents=True)
            write_json(settings, {
                "permissions": {"allow": ["Bash(python3 *)"]},
                "hooks": {"PreToolUse": [{"matcher": "Bash(npm *)", "hooks": [{"type": "command", "command": "echo hi"}]}]},
            })
            first, path = install_hook(root)
            self.assertEqual(path, settings.resolve())
            self.assertIn(first, {"created", "updated", "updated-with-backup"})
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(data["permissions"], {"allow": ["Bash(python3 *)"]})
            self.assertTrue(any("echo hi" in item["command"] for hook in data["hooks"]["PreToolUse"] for item in hook["hooks"]))
            self.assertTrue(any(HOOK_COMMAND == item["command"] for hook in data["hooks"]["PreToolUse"] for item in hook["hooks"]))
            second, _ = install_hook(root)
            self.assertIn("unchanged", second)
            matches = [
                item["command"]
                for hook in data["hooks"]["PreToolUse"]
                if isinstance(hook, dict)
                for item in hook["hooks"]
            ]
            self.assertEqual(matches.count(HOOK_COMMAND), 1)


class OpenSpecDispatcherTests(unittest.TestCase):
    def test_builds_only_fixed_json_commands_and_enforces_phases(self) -> None:
        record = {
            "change_id": "demo-1", "state": "EXPLORED",
            "orchestration": orchestration_contract("demo-1"),
        }
        request = DispatchRequest("instructions", "proposal")
        self.assertEqual(authorize(record, request), [])
        self.assertEqual(
            build_command("openspec", "demo-1", request),
            ["openspec", "instructions", "proposal", "--change", "demo-1", "--json"],
        )
        self.assertTrue(authorize({**record, "state": "IMPLEMENTING"}, request))
        self.assertEqual(
            build_command("openspec", "demo-1", DispatchRequest("validate")),
            ["openspec", "validate", "demo-1", "--type", "change", "--strict", "--json", "--no-interactive"],
        )

    def test_dispatch_records_parent_child_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo-1"
            (change_dir / "evidence").mkdir(parents=True)
            write_json(change_dir / "change.json", {
                "schema_version": 3, "change_id": "demo-1", "state": "EXPLORED",
                "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "project_root": str(root), "orchestration": orchestration_contract("demo-1"), "events": [],
            })
            fake = subprocess.CompletedProcess([], 0, stdout='{"status":"ok"}\n', stderr="")
            with patch("dispatch_openspec.subprocess.run", return_value=fake) as invoked:
                code, stdout, stderr = dispatch(change_dir, DispatchRequest("status"))
            self.assertEqual((code, stderr), (0, ""))
            self.assertIn('"status":"ok"', stdout)
            self.assertEqual(invoked.call_args.args[0], ["openspec", "status", "--change", "demo-1", "--json"])
            record = json.loads((change_dir / "change.json").read_text(encoding="utf-8"))
            self.assertEqual(record["events"][-1]["event"], "openspec.dispatched")
            self.assertEqual(record["events"][-1]["parent"], "harness-engineering")
            self.assertEqual(record["events"][-1]["child"], "openspec")


if __name__ == "__main__":
    unittest.main()
