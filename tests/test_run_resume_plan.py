"""Replacement plans update a new run without rewriting prior contracts."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest

from test_run_checks import RunFixture
import test_run_state as state_tests


class ResumePlanTests(RunFixture):
    init = state_tests.RunStateTests.init
    stored = state_tests.RunStateTests.stored
    ready = state_tests.RunStateTests.ready
    start = state_tests.RunStateTests.start
    submit = state_tests.RunStateTests.submit
    release = state_tests.RunStateTests.release

    def accepted_run(self) -> dict:
        self.init([self.task("01"), self.task("02", dependencies=["01"]), self.task("03")])
        for identifier in ("01", "02", "03"):
            agent_id = f"fixture-native-{identifier}"
            self.start(identifier, agent_id)
            self.submit(task_id=identifier)
            self.release(agent_id)
        return self.stored()

    def old_bytes(self) -> dict:
        directory = self.project / ".harness/runs/current"
        return {path.relative_to(directory): path.read_bytes()
                for path in directory.rglob("*") if path.is_file()}

    def resume_with(self, template: dict, run_id: str = "resumed", success: bool = True) -> dict | None:
        path = self.directory / f"{run_id}-replacement.json"
        path.write_text(json.dumps(template), encoding="utf-8")
        before = path.read_bytes()
        result = self.cli("run.py", "resume", "--run", "current", "--new-run", run_id,
                          "--plan-file", path, success=success)
        self.assertEqual(path.read_bytes(), before)
        return json.loads(result.stdout) if success else None

    def test_changed_decision_invalidates_only_its_new_dependency_chain(self) -> None:
        template = deepcopy(self.accepted_run())
        before = self.old_bytes()
        template["tasks"][0]["context"]["decisions"] = ["Use the new response wrapper."]
        # Input order must not affect the new dependency traversal.
        template["tasks"].reverse()
        response = self.resume_with(template)
        states = {task["id"]: task["status"] for task in self.stored("resumed")["tasks"]}
        self.assertEqual(states, {"01": "pending", "02": "pending", "03": "completed"})
        self.assertEqual(response["reused"], ["03"])
        self.assertEqual(self.ready("resumed")["ready"], ["01"])
        self.assertEqual(self.old_bytes(), before)
        self.complete(success=False, run_id="resumed")

    def test_added_task_keeps_unchanged_completed_work_reusable(self) -> None:
        template = deepcopy(self.accepted_run())
        before = self.old_bytes()
        template["tasks"].insert(0, self.task("04", dependencies=["03"], ownership=["new-report.txt"]))
        response = self.resume_with(template)
        self.assertEqual(response["reused"], ["01", "02", "03"])
        new_task = next(task for task in self.stored("resumed")["tasks"] if task["id"] == "04")
        self.assertEqual(new_task["status"], "pending")
        self.assertEqual(new_task["attempts"], 0)
        self.assertIsNone(new_task["agent_id"])
        self.assertEqual(self.ready("resumed")["ready"], ["04"])
        self.assertEqual(self.old_bytes(), before)

    def test_removed_task_is_absent_from_new_run_and_preserved_in_old_run(self) -> None:
        template = deepcopy(self.accepted_run())
        before = self.old_bytes()
        template["tasks"] = [task for task in template["tasks"] if task["id"] != "02"]
        self.resume_with(template)
        self.assertEqual([task["id"] for task in self.stored("resumed")["tasks"]], ["01", "03"])
        self.assertFalse((self.project / ".harness/runs/resumed/task-02").exists())
        self.assertEqual(self.old_bytes(), before)
        self.complete(run_id="resumed")

    def test_changed_objective_or_ownership_is_applied_without_editing_history(self) -> None:
        original = self.accepted_run()
        before = self.old_bytes()
        objective_template = deepcopy(original)
        objective_template["objective"] = "A changed acceptance objective."
        self.resume_with(objective_template, "new-objective")
        objective_plan = self.stored("new-objective")
        self.assertEqual(objective_plan["objective"], objective_template["objective"])
        self.assertTrue(all(task["status"] == "pending" for task in objective_plan["tasks"]))
        ownership_template = deepcopy(original)
        ownership_template["tasks"][2]["ownership"] = ["new-location/report.txt"]
        response = self.resume_with(ownership_template, "new-ownership")
        self.assertEqual(response["reused"], ["01", "02"])
        task = self.stored("new-ownership")["tasks"][2]
        self.assertEqual(task["ownership"], ["new-location/report.txt"])
        self.assertEqual(task["status"], "pending")
        self.assertEqual(self.old_bytes(), before)

    def test_invalid_replacement_template_fails_before_creating_a_run(self) -> None:
        original = self.accepted_run()
        before = self.old_bytes()
        invalid_dependency = deepcopy(original)
        invalid_dependency["tasks"][0]["dependencies"] = ["missing-task"]
        invalid_context = deepcopy(original)
        invalid_context["tasks"][0]["ownership"] = ["spec.txt"]
        invalid_remap = deepcopy(original)
        invalid_remap["tasks"][0]["ownership"] = [".harness/runs/current/task-01/output.txt"]
        invalid_remap["tasks"][0]["inputs"] = [".harness/runs/invalid-3/task-01/output.txt"]
        for index, template in enumerate(({}, invalid_dependency, invalid_context, invalid_remap)):
            with self.subTest(template=index):
                identifier = f"invalid-{index}"
                self.resume_with(template, identifier, success=False)
                self.assertFalse((self.project / ".harness/runs" / identifier).exists())
                self.assertEqual(self.old_bytes(), before)


if __name__ == "__main__":
    unittest.main()
