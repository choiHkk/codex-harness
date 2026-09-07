"""Regression tests for recorded native lifecycle and immutable run boundaries."""

from __future__ import annotations

import json
import unittest

from test_run_checks import RunFixture
import test_run_state as state_tests


class RunLifecycleTests(RunFixture):
    # Share command setup without inheriting and rerunning the state test cases.
    init = state_tests.RunStateTests.init
    stored = state_tests.RunStateTests.stored
    ready = state_tests.RunStateTests.ready
    start = state_tests.RunStateTests.start
    submit = state_tests.RunStateTests.submit

    def observe(self, state: str, agent_id: str = "observed-agent-01", run_id: str = "current",
                evidence: str = "Fixture runtime observed the stated lifecycle.", success: bool = True):
        return self.cli("run.py", "agent", "--run", run_id, "--agent-id", agent_id,
                        "--state", state, "--evidence", evidence, success=success)

    def test_capacity_stays_occupied_until_closure_but_idle_agent_can_be_reused(self) -> None:
        (self.project / ".codex/config.toml").write_text(
            "[agents]\nmax_concurrent_threads_per_session = 1\n", encoding="utf-8"
        )
        self.init([self.task("01"), self.task("02")])
        self.start()
        self.submit()
        rejected = self.start("02", "new-native-id", success=False)
        self.assertIn("capacity", rejected.stderr)
        self.observe("idle", evidence="", success=False)
        self.observe("idle")
        self.start("02", "new-native-id", success=False)
        self.start("02", "observed-agent-01")
        self.submit(task_id="02")
        registry = json.loads((self.project / ".harness/runs/current/agents.json").read_text())
        self.assertEqual(list(registry["agents"]), ["observed-agent-01"])
        self.assertEqual(registry["agents"]["observed-agent-01"]["task_id"], "02")
        self.observe("idle")
        self.complete()

    def test_default_retry_limit_counts_failed_attempts_and_rejects_third_dispatch(self) -> None:
        self.init([self.task(ownership=["output.txt"])])
        output = self.project / "output.txt"
        for attempt in (1, 2):
            self.start()
            output.write_text(f"Attempt {attempt}", encoding="utf-8")
            self.submit(self.result(status="failed", artifacts=["output.txt"],
                                    checks=[{"name": "Retry fixture", "status": "failed", "evidence": "Expected failure"}],
                                    issues=["Input requires another implementation."]))
            self.observe("idle")
            self.assertEqual(self.stored()["tasks"][0]["attempts"], attempt)
        before = self.stored()
        rejected = self.start(success=False)
        self.assertIn("Retry limit", rejected.stderr)
        self.assertNotIn("01", self.ready()["ready"])
        self.assertEqual(self.stored(), before)

    def test_explicit_retry_limit_is_honored(self) -> None:
        self.init([self.task(max_attempts=1)])
        self.start()
        self.submit(self.result(status="blocked", checks=[], issues=["Required fixture input unavailable."]))
        self.observe("idle")
        self.start(success=False)
        self.assertEqual(self.stored()["tasks"][0]["attempts"], 1)

    def test_stop_request_holds_ownership_and_blocks_resume_until_observed_stopped(self) -> None:
        self.init([self.task("01", ownership=["shared.txt"]), self.task("02", ownership=["shared.txt"])])
        self.start()
        self.submit(self.result(status="failed", checks=[], issues=["Fixture worker failed."]))
        self.observe("stop_requested")
        self.observe("idle", success=False)
        self.start("02", "replacement-native-id", success=False)
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed", success=False)
        self.assertFalse((self.project / ".harness/runs/resumed").exists())
        self.observe("stopped")
        self.start("02", "replacement-native-id")
        self.submit(task_id="02")
        self.observe("idle", agent_id="replacement-native-id")
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")
        statuses = {task["id"]: task["status"] for task in self.stored("resumed")["tasks"]}
        self.assertEqual(statuses, {"01": "pending", "02": "completed"})

    def test_artifacts_cannot_contain_state_that_result_recording_mutates(self) -> None:
        self.init()
        self.start()
        plan_path = self.project / ".harness/runs/current/plan.json"
        before = plan_path.read_bytes()
        artifacts = [".harness/runs/current/task-01", ".harness/runs/current/plan.json",
                     ".harness/runs/current/agents.json", "_workspace/communications/current.jsonl"]
        for artifact in artifacts:
            with self.subTest(artifact=artifact):
                rejected = self.submit(self.result(artifacts=[artifact]), success=False)
                self.assertIn("mutable harness state", rejected.stderr)
                self.assertEqual(plan_path.read_bytes(), before)
                self.assertFalse((self.project / ".harness/runs/current/task-01/result.json").exists())

    def test_resume_remaps_pending_run_outputs_and_preserves_previous_bytes(self) -> None:
        self.init([self.task(ownership=["./.harness/runs/current/task-01/outputs/"])])
        old_directory = self.project / ".harness/runs/current"
        previous_output = old_directory / "task-01/outputs/report.txt"
        previous_output.parent.mkdir()
        previous_output.write_text("Previous partial output", encoding="utf-8")
        before = {path.relative_to(old_directory): path.read_bytes()
                  for path in old_directory.rglob("*") if path.is_file()}
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")
        task = self.stored("resumed")["tasks"][0]
        self.assertEqual(task["ownership"], [".harness/runs/resumed/task-01/outputs/"])
        self.start(run_id="resumed")
        artifact = ".harness/runs/resumed/task-01/outputs/report.txt"
        new_output = self.project / artifact
        new_output.parent.mkdir()
        new_output.write_text("New current output", encoding="utf-8")
        self.submit(self.result(run_id="resumed", artifacts=[artifact]), run_id="resumed")
        self.observe("idle", run_id="resumed")
        self.complete(run_id="resumed")
        after = {path.relative_to(old_directory): path.read_bytes()
                 for path in old_directory.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
