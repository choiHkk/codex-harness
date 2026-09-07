"""Completion checks use recorded task results and actual temporary files."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "harness" / "scripts"


class RunFixture(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="harness-run-tests-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.project = self.directory / "project"
        self.project.mkdir()
        self.input = self.project / "spec.txt"
        self.input.write_text("version one\n", encoding="utf-8")
        agents = self.project / ".codex" / "agents"
        agents.mkdir(parents=True)
        (agents / "test-worker.toml").write_text(
            'name = "test_worker"\ndescription = "Check assigned files"\n'
            'developer_instructions = "Use only assigned files and report evidence."\n',
            encoding="utf-8",
        )
        (self.project / ".codex" / "config.toml").write_text(
            "[agents]\nenabled = true\nmax_concurrent_threads_per_session = 3\n", encoding="utf-8"
        )
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        self.support = importlib.import_module("run_support")
        self.checks = importlib.import_module("run_checks")
        self.state = importlib.import_module("run_state")

    def task(self, identifier: str = "01", **changes: object) -> dict:
        task = {
            "id": identifier, "role": "test_worker", "dependencies": [],
            "ownership": [], "acceptance": ["The assigned behavior is verified."],
            "status": "completed", "attempts": 1, "required": True,
            "inputs": ["spec.txt"], "context": {"decisions": [], "skill_paths": []},
            "agent_id": None,
            **changes,
        }
        paths = list(dict.fromkeys(task["inputs"] + task["context"]["skill_paths"]))
        task.setdefault("input_fingerprints", self.support.snapshot_inputs(self.project, paths))
        return task

    def plan(self, tasks: list[dict] | None = None, run_id: str = "current", **changes: object) -> dict:
        plan = {
            "schema_version": 2, "run_id": run_id, "previous_run_id": None,
            "project_root": str(self.project), "objective": "Verify a bounded workflow.",
            "tasks": tasks if tasks is not None else [self.task()], **changes,
        }
        for task in plan["tasks"]:
            task.setdefault("contract_fingerprint", self.state.task_contract_fingerprint(plan["objective"], task))
            if task["status"] == "completed":
                task.setdefault("artifact_fingerprints", {})
        return plan

    def write_plan(self, plan: dict, directory_id: str | None = None) -> Path:
        directory = self.project / ".harness" / "runs" / (directory_id or plan["run_id"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        if not (directory / "agents.json").exists():
            (directory / "agents.json").write_text(json.dumps({"run_id": plan["run_id"], "agents": {}}), encoding="utf-8")
        return directory

    @staticmethod
    def result(task_id: str = "01", run_id: str = "current", **changes: object) -> dict:
        return {
            "task_id": task_id, "run_id": run_id, "status": "completed",
            "summary": "Checked the assigned behavior.", "artifacts": [],
            "checks": [{"name": "Behavior check", "status": "passed", "evidence": "Inspected the expected response and its consumer."}],
            "issues": [], **changes,
        }

    def write_result(self, result: dict, run_id: str = "current", task_id: str = "01") -> None:
        directory = self.project / ".harness" / "runs" / run_id / f"task-{task_id}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
        plan_file = directory.parent / "plan.json"
        if plan_file.exists():
            plan = json.loads(plan_file.read_text(encoding="utf-8"))
            try:
                fingerprints = self.support.snapshot_inputs(self.project, result["artifacts"])
            except (OSError, TypeError, ValueError):
                return
            for task in plan["tasks"]:
                if task["id"] == task_id:
                    task["artifact_fingerprints"] = fingerprints
            plan_file.write_text(json.dumps(plan), encoding="utf-8")

    def cli(self, script: str, *arguments: object, success: bool = True) -> subprocess.CompletedProcess:
        command = [sys.executable, str(SCRIPTS / script), "--project", str(self.project), *(str(item) for item in arguments)]
        result = subprocess.run(command, cwd=self.directory, capture_output=True, text=True, timeout=30,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        detail = f"{command}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        if success:
            self.assertEqual(result.returncode, 0, detail)
        else:
            self.assertNotEqual(result.returncode, 0, detail)
        return result

    def complete(self, success: bool = True, run_id: str = "current") -> subprocess.CompletedProcess:
        return self.cli("validate.py", "--run", run_id, "--complete", success=success)


class CompletionTests(RunFixture):
    def test_read_only_completed_result_with_required_evidence_passes(self) -> None:
        self.write_plan(self.plan())
        self.write_result(self.result())
        self.complete()

    def test_structural_validation_allows_unfinished_work_but_completion_fails(self) -> None:
        self.write_plan(self.plan([self.task(status="pending", attempts=0)]))
        self.cli("validate.py")
        self.complete(success=False)

    def test_legacy_plan_needs_migration_for_completion(self) -> None:
        legacy = self.plan()
        del legacy["schema_version"]
        self.write_plan(legacy)
        self.cli("validate.py")
        result = self.complete(success=False)
        self.assertIn("migrate", result.stderr.lower())

    def test_completed_task_cannot_omit_result_file(self) -> None:
        self.write_plan(self.plan())
        self.complete(success=False)

    def test_result_identity_and_status_must_match_plan(self) -> None:
        self.write_plan(self.plan())
        for field, value in (("run_id", "another-run"), ("task_id", "another-task"), ("status", "failed")):
            with self.subTest(field=field):
                self.write_result(self.result(**{field: value}))
                self.complete(success=False)

    def test_completed_result_requires_a_passed_required_check(self) -> None:
        self.write_plan(self.plan())
        for checks in (
            [],
            [{"name": "optional", "status": "passed", "evidence": "Reviewed", "required": False}],
            [{"name": "test", "status": "failed", "evidence": "Assertion failed"}],
            [{"name": "test", "status": "not_run", "evidence": "No test environment"}],
            [{"name": "test", "status": "passed", "evidence": "   "}],
            [{"name": "test", "status": "passed"}],
        ):
            with self.subTest(checks=checks):
                self.write_result(self.result(checks=checks))
                self.complete(success=False)

    def test_one_pass_does_not_hide_another_required_failure(self) -> None:
        self.write_plan(self.plan())
        checks = self.result()["checks"] + [{"name": "Regression", "status": "failed", "evidence": "Expected two rows, got one", "required": True}]
        self.write_result(self.result(checks=checks))
        self.complete(success=False)

    def test_optional_unrun_check_and_skipped_optional_task_are_explicit(self) -> None:
        self.write_plan(self.plan([self.task(), self.task("02", status="skipped", required=False, attempts=0)]))
        checks = self.result()["checks"] + [{"name": "Optional browser check", "status": "not_run", "evidence": "No browser attached", "required": False}]
        self.write_result(self.result(checks=checks))
        self.complete()

    def test_optional_completed_task_still_needs_valid_result(self) -> None:
        self.write_plan(self.plan([self.task(), self.task("02", required=False)]))
        self.write_result(self.result())
        self.complete(success=False)

    def test_declared_artifact_must_exist_inside_project(self) -> None:
        self.write_plan(self.plan())
        outside = self.directory / "outside.txt"
        outside.write_text("Outside project", encoding="utf-8")
        (self.project / "outside-link").symlink_to(outside)
        for artifact in ("missing.txt", "../outside.txt", str(outside), "outside-link"):
            with self.subTest(artifact=artifact):
                self.write_result(self.result(artifacts=[artifact]))
                self.complete(success=False)
        directory = self.project / "outputs"
        directory.mkdir()
        (directory / "report.txt").write_text("Validated output", encoding="utf-8")
        self.write_result(self.result(artifacts=["outputs", "outputs/report.txt"]))
        self.complete()

    def test_file_change_invalidates_completed_context(self) -> None:
        self.write_plan(self.plan())
        self.write_result(self.result())
        self.input.write_text("version two\n", encoding="utf-8")
        self.complete(success=False)

    def test_directory_changes_invalidate_completed_context(self) -> None:
        directory = self.project / "requirements"
        directory.mkdir()
        original = directory / "first.txt"
        original.write_text("Original requirement", encoding="utf-8")
        plan = self.plan([self.task(inputs=["requirements"])])
        self.write_plan(plan)
        self.write_result(self.result())
        self.complete()
        added = directory / "second.txt"
        added.write_text("New requirement", encoding="utf-8")
        self.complete(success=False)
        added.unlink()
        original.unlink()
        self.complete(success=False)

    def test_missing_input_becoming_present_invalidates_snapshot(self) -> None:
        self.write_plan(self.plan([self.task(inputs=["future-input.txt"])]))
        self.write_result(self.result())
        self.complete()
        (self.project / "future-input.txt").write_text("New input", encoding="utf-8")
        self.complete(success=False)

    def test_skill_context_changes_invalidate_completed_result(self) -> None:
        skill = self.project / "procedure.md"
        skill.write_text("Original procedure", encoding="utf-8")
        self.write_plan(self.plan([self.task(context={"decisions": [], "skill_paths": ["procedure.md"]})]))
        self.write_result(self.result())
        self.complete()
        skill.write_text("Changed procedure", encoding="utf-8")
        self.complete(success=False)

    def test_dependency_result_changes_invalidate_completed_consumer(self) -> None:
        dependency = self.project / "accepted-dependency.json"
        dependency.write_text('{"version": 1}', encoding="utf-8")
        task = self.task(dependency_fingerprints=self.support.snapshot_inputs(self.project, ["accepted-dependency.json"]))
        self.write_plan(self.plan([task]))
        self.write_result(self.result())
        self.complete()
        dependency.write_text('{"version": 2}', encoding="utf-8")
        self.complete(success=False)

    def test_previous_run_must_exist_and_have_consistent_identity(self) -> None:
        self.write_result(self.result())
        for previous in ("missing", "current", "../outside"):
            with self.subTest(previous=previous):
                self.write_plan(self.plan(previous_run_id=previous))
                self.complete(success=False)
        self.write_plan(self.plan(run_id="wrong-identity"), directory_id="previous")
        self.write_plan(self.plan(previous_run_id="previous"))
        self.complete(success=False)
        self.write_plan(self.plan(run_id="previous"))
        self.complete()

    def test_run_id_and_project_root_must_match_actual_location(self) -> None:
        self.write_result(self.result())
        self.write_plan(self.plan(run_id="different"), directory_id="current")
        self.complete(success=False)
        self.write_plan(self.plan(project_root=str(self.directory)))
        self.complete(success=False)

    def test_failed_result_can_report_failure_without_passing_checks(self) -> None:
        task = self.task(status="failed")
        result = self.result(status="failed", checks=[], summary="Required dependency could not be read.")
        self.assertEqual(self.checks.validate_result(self.project, self.project / ".harness/runs/current", task, result), [])
        result["status"] = "not_a_status"
        self.assertTrue(self.checks.validate_result(self.project, self.project / ".harness/runs/current", task, result))

    def test_managed_completion_requires_snapshot_fields_and_registry(self) -> None:
        plan = self.plan()
        for field in ("contract_fingerprint", "artifact_fingerprints"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(plan))
                del changed["tasks"][0][field]
                self.write_plan(changed)
                self.complete(success=False)
        directory = self.write_plan(plan)
        self.write_result(self.result())
        (directory / "agents.json").unlink()
        self.complete(success=False)

    def test_registry_requires_observed_quiescence_before_completion(self) -> None:
        directory = self.write_plan(self.plan())
        self.write_result(self.result())
        for state in ("running", "stop_requested", "idle", "stopped", "closed"):
            with self.subTest(state=state):
                registry = {"run_id": "current", "agents": {"observed-agent": {"state": state, "evidence": "Observed the native lifecycle state."}}}
                (directory / "agents.json").write_text(json.dumps(registry), encoding="utf-8")
                self.complete(success=state not in {"running", "stop_requested"})

    def test_changed_accepted_artifact_or_contract_blocks_completion(self) -> None:
        artifact = self.project / "report.txt"
        artifact.write_text("Accepted report", encoding="utf-8")
        plan = self.plan()
        directory = self.write_plan(plan)
        self.write_result(self.result(artifacts=["report.txt"]))
        self.complete()
        artifact.write_text("Unverified changed report", encoding="utf-8")
        self.complete(success=False)
        artifact.write_text("Accepted report", encoding="utf-8")
        plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
        plan["tasks"][0]["context"]["decisions"] = ["A different contract now applies."]
        self.write_plan(plan)
        self.complete(success=False)


if __name__ == "__main__":
    unittest.main()
