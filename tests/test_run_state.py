"""Integration tests for durable task transitions and recovery, without agents."""

from __future__ import annotations

import json
import unittest

from test_run_checks import RunFixture


class RunStateTests(RunFixture):
    def init(self, tasks: list[dict] | None = None, run_id: str = "current") -> dict:
        tasks = tasks if tasks is not None else [self.task(status="pending", attempts=0)]
        for task in tasks:
            task.pop("input_fingerprints", None)
        template = self.directory / f"{run_id}-template.json"
        template.write_text(json.dumps({"objective": "Verify durable state transitions.", "tasks": tasks}), encoding="utf-8")
        return json.loads(self.cli("run.py", "init", "--plan-file", template, "--run-id", run_id).stdout)

    def stored(self, run_id: str = "current") -> dict:
        return json.loads((self.project / ".harness" / "runs" / run_id / "plan.json").read_text(encoding="utf-8"))

    def ready(self, run_id: str = "current") -> dict:
        return json.loads(self.cli("run.py", "ready", "--run", run_id).stdout)

    def start(self, task_id: str = "01", agent_id: str = "observed-agent-01", run_id: str = "current", success: bool = True):
        return self.cli("run.py", "start", "--run", run_id, "--task", task_id, "--agent-id", agent_id, success=success)

    def submit(self, result: dict | None = None, task_id: str = "01", run_id: str = "current", success: bool = True):
        payload = self.directory / "submitted-result.json"
        payload.write_text(json.dumps(result if result is not None else self.result(task_id, run_id)), encoding="utf-8")
        return self.cli("run.py", "result", "--run", run_id, "--task", task_id, "--result-file", payload, success=success)

    def release(self, agent_id: str = "observed-agent-01", run_id: str = "current"):
        return self.cli("run.py", "agent", "--run", run_id, "--agent-id", agent_id,
                        "--state", "closed", "--evidence", "Native runtime confirmed this agent thread closed.")

    def test_init_captures_current_inputs_and_preserves_existing_run(self) -> None:
        self.init()
        plan = self.stored()
        self.assertEqual(plan["schema_version"], 2)
        self.assertEqual(plan["project_root"], str(self.project))
        self.assertEqual(plan["tasks"][0]["input_fingerprints"], self.support.snapshot_inputs(self.project, ["spec.txt"]))
        before = (self.project / ".harness/runs/current/plan.json").read_bytes()
        template = self.directory / "duplicate.json"
        template.write_text(json.dumps({"objective": "Changed objective", "tasks": [self.task(status="pending")]}), encoding="utf-8")
        self.cli("run.py", "init", "--plan-file", template, "--run-id", "current", success=False)
        self.assertEqual((self.project / ".harness/runs/current/plan.json").read_bytes(), before)

    def test_dependency_requires_accepted_result_before_consumer_starts(self) -> None:
        self.init([self.task(status="pending", attempts=0), self.task("02", status="pending", attempts=0, dependencies=["01"])])
        self.assertEqual(self.ready()["ready"], ["01"])
        self.start("02", success=False)
        self.start()
        self.submit(self.result(checks=[]), success=False)
        self.assertEqual(self.stored()["tasks"][0]["status"], "running")
        self.assertNotIn("02", self.ready()["ready"])
        self.submit()
        self.assertIn("02", self.ready()["ready"])
        self.start("02", "observed-agent-02")
        self.submit(task_id="02")
        self.release()
        self.release("observed-agent-02")
        self.complete()

    def test_producer_output_may_be_created_after_run_init(self) -> None:
        self.init([
            self.task(status="pending", attempts=0, ownership=["producer.txt"]),
            self.task("02", status="pending", attempts=0, dependencies=["01"], ownership=["consumer.txt"]),
        ])
        self.start()
        (self.project / "producer.txt").write_text("Produced after initialization", encoding="utf-8")
        self.submit(self.result(artifacts=["producer.txt"]))
        self.start("02", "observed-agent-02")
        packet = self.project / ".harness/runs/current/task-02/input.md"
        self.assertTrue(packet.is_file())
        self.assertIn("producer.txt", packet.read_text(encoding="utf-8"))
        (self.project / "consumer.txt").write_text("Consumed producer output", encoding="utf-8")
        self.submit(self.result("02", artifacts=["consumer.txt"]), task_id="02")
        self.release()
        self.release("observed-agent-02")
        self.complete()

    def test_changed_immutable_input_blocks_start_and_successful_result(self) -> None:
        self.init()
        self.input.write_text("Changed before start", encoding="utf-8")
        self.start(success=False)
        self.assertNotIn("01", self.ready()["ready"])
        self.input.write_text("version one\n", encoding="utf-8")
        self.start()
        self.input.write_text("Changed while agent was running", encoding="utf-8")
        self.submit(success=False)
        self.assertEqual(self.stored()["tasks"][0]["status"], "running")

    def test_completed_result_does_not_fabricate_agent_closure(self) -> None:
        config = self.project / ".codex/config.toml"
        config.write_text("[agents]\nenabled = true\nmax_concurrent_threads_per_session = 1\n", encoding="utf-8")
        self.init([self.task(status="pending", attempts=0), self.task("02", status="pending", attempts=0)])
        self.start()
        self.submit()
        self.start("02", "observed-agent-02", success=False)
        self.release()
        self.start("02", "observed-agent-02")
        self.assertEqual(self.stored()["tasks"][1]["status"], "running")

    def test_simultaneous_write_ownership_is_rejected(self) -> None:
        self.init([
            self.task(status="pending", attempts=0, ownership=["src/"]),
            self.task("02", status="pending", attempts=0, ownership=["src/api.py"]),
        ])
        self.start()
        self.start("02", "observed-agent-02", success=False)
        self.assertEqual(self.stored()["tasks"][1]["status"], "pending")

    def test_mutable_owned_files_cannot_be_declared_immutable_inputs(self) -> None:
        template = self.directory / "conflicting-context.json"
        template.write_text(json.dumps({"objective": "Avoid impossible freshness checks", "tasks": [self.task(status="pending", ownership=["spec.txt"])]}), encoding="utf-8")
        self.cli("run.py", "init", "--plan-file", template, "--run-id", "current", success=False)
        self.assertFalse((self.project / ".harness/runs/current/plan.json").exists())

    def test_resume_reuses_unchanged_completed_results_and_keeps_old_run(self) -> None:
        self.init()
        self.start()
        self.submit()
        self.release()
        old_plan = (self.project / ".harness/runs/current/plan.json").read_bytes()
        old_result = (self.project / ".harness/runs/current/task-01/result.json").read_bytes()
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")
        resumed = self.stored("resumed")
        self.assertEqual(resumed["previous_run_id"], "current")
        self.assertEqual(resumed["tasks"][0]["status"], "completed")
        self.assertEqual(resumed["tasks"][0]["reused_from"], {"run_id": "current", "task_id": "01"})
        self.assertEqual((self.project / ".harness/runs/current/plan.json").read_bytes(), old_plan)
        self.assertEqual((self.project / ".harness/runs/current/task-01/result.json").read_bytes(), old_result)
        self.complete(run_id="resumed")

    def test_resume_invalidates_changed_task_and_dependent_consumers(self) -> None:
        self.init([
            self.task(status="pending", attempts=0),
            self.task("02", status="pending", attempts=0, dependencies=["01"], inputs=[]),
            self.task("03", status="pending", attempts=0, inputs=[]),
        ])
        for identifier in ("01", "02", "03"):
            agent = f"observed-agent-{identifier}"
            self.start(identifier, agent)
            self.submit(task_id=identifier)
            self.release(agent)
        self.input.write_text("New external requirement", encoding="utf-8")
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")
        states = {task["id"]: task["status"] for task in self.stored("resumed")["tasks"]}
        self.assertEqual(states, {"01": "pending", "02": "pending", "03": "completed"})
        self.assertEqual(self.ready("resumed")["ready"], ["01"])

    def test_resume_detects_changed_completed_artifact(self) -> None:
        self.init([self.task(status="pending", attempts=0, ownership=["output.txt"])])
        self.start()
        output = self.project / "output.txt"
        output.write_text("Original accepted artifact", encoding="utf-8")
        self.submit(self.result(artifacts=["output.txt"]))
        self.release()
        output.write_text("Changed after acceptance", encoding="utf-8")
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")
        self.assertEqual(self.stored("resumed")["tasks"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
