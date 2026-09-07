"""Behavioral integration tests for the Codex harness command-line tools.

All mutations occur in temporary projects. These tests exercise generated files,
TOML round trips, validation failures, and preservation of existing projects.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.py"
SKILL = ROOT / ".agents" / "skills" / "harness"
CREATE_AGENT = SKILL / "scripts" / "create_agent.py"
VALIDATE = SKILL / "scripts" / "validate.py"
ROOT_VALIDATE = ROOT / "scripts" / "validate.py"


def snapshot(root: Path) -> dict[str, tuple[str, object]]:
    """Record directories, file bytes, and symlinks without following symlinks."""
    if not root.exists():
        return {}
    result: dict[str, tuple[str, object]] = {}
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                result[relative] = ("symlink", os.readlink(path))
            elif path.is_dir():
                result[relative] = ("directory", None)
            else:
                result[relative] = ("file", path.read_bytes())
    return result


class HarnessCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="codex-harness-test-")
        self.addCleanup(self.temporary.cleanup)
        # macOS exposes its temporary root through the system /var symlink.
        # Use its physical path; individual tests create destination symlinks.
        self.directory = Path(self.temporary.name).resolve()
        self.project = self.directory / "project"
        self.project.mkdir()
        self.instructions = self.directory / "instructions.md"
        self.instructions.write_text("Inspect the assigned scope and report evidence.\n", encoding="utf-8")

    def run_cli(self, script: Path, *arguments: object, success: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(script), *(str(argument) for argument in arguments)],
            cwd=cwd or ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        detail = f"Command: {result.args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        if success:
            self.assertEqual(result.returncode, 0, detail)
        else:
            self.assertNotEqual(result.returncode, 0, detail)
        return result

    def install(self, *arguments: object, success: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run_cli(INSTALL, "--target", self.project, *arguments, success=success)

    def create_agent(self, name: str = "example_reviewer", *arguments: object, success: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            CREATE_AGENT,
            "--target", self.project,
            "--name", name,
            "--description", "Review the assigned implementation.",
            "--instructions-file", self.instructions,
            *arguments,
            success=success,
        )

    def validate(self, success: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run_cli(VALIDATE, "--project", self.project, success=success)

    @staticmethod
    def task(identifier: str, **changes: object) -> dict[str, object]:
        return {
            "id": identifier,
            "role": "example_reviewer",
            "dependencies": [],
            "ownership": [],
            "acceptance": ["The assigned contract is checked against evidence."],
            "status": "pending",
            "attempts": 0,
            "required": True,
            **changes,
        }

    def write_plan(self, tasks: list[dict[str, object]]) -> None:
        directory = self.project / ".harness" / "runs" / "integration-test"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "plan.json").write_text(
            json.dumps({"run_id": "integration-test", "objective": "Verify a bounded team workflow.", "tasks": tasks}),
            encoding="utf-8",
        )

    @staticmethod
    def file_helper():
        specification = importlib.util.spec_from_file_location("harness_test_common", SKILL / "scripts" / "common.py")
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

    def test_install_copies_seed_roles_and_complete_skill(self) -> None:
        self.install()
        roles = list((self.project / ".codex" / "agents").glob("*.toml"))
        self.assertGreaterEqual(len(roles), 2)
        for source in SKILL.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                destination = self.project / ".agents" / "skills" / "harness" / source.relative_to(SKILL)
                self.assertTrue(destination.is_file(), str(destination))
                self.assertEqual(destination.read_bytes(), source.read_bytes())
        config = tomllib.loads((self.project / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertTrue(config["agents"]["enabled"])
        self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 3)
        self.validate()
        self.run_cli(ROOT_VALIDATE, "--project", self.project)

    def test_install_preserves_user_configuration_and_instructions(self) -> None:
        original_config = '''model = "existing-user-model"
model_reasoning_effort = "high"
[agents]
enabled = false
max_threads = 7
[mcp_servers.example]
command = "example-server"
args = ["--stdio"]
env = { EXTRA = "existing value" }
'''
        codex = self.project / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text(original_config, encoding="utf-8")
        original_agents = "# Project instructions\n\nUse the existing build workflow.\n"
        (self.project / "AGENTS.md").write_text(original_agents, encoding="utf-8")
        self.install()
        actual = tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))
        expected = tomllib.loads(original_config)
        for key in ("model", "model_reasoning_effort", "mcp_servers"):
            self.assertEqual(actual[key], expected[key])
        self.assertFalse(actual["agents"]["enabled"])
        self.assertEqual(actual["agents"]["max_threads"], 7)
        self.assertNotIn("max_concurrent_threads_per_session", actual["agents"])
        self.assertIn(original_agents, (self.project / "AGENTS.md").read_text(encoding="utf-8"))
        self.validate()

    def test_install_is_idempotent(self) -> None:
        self.install()
        first = snapshot(self.project)
        self.install()
        self.assertEqual(snapshot(self.project), first)

    def test_installed_skill_helpers_run_outside_source_checkout(self) -> None:
        self.install()
        scripts = self.project / ".agents" / "skills" / "harness" / "scripts"
        self.run_cli(
            scripts / "create_agent.py",
            "--target", self.project,
            "--name", "portable_reviewer",
            "--description", "Review this project.",
            "--instructions-file", self.instructions,
            cwd=self.directory,
        )
        self.assertTrue((self.project / ".codex" / "agents" / "portable_reviewer.toml").is_file())
        self.run_cli(scripts / "validate.py", "--project", self.project, cwd=self.directory)

    def test_install_dry_run_does_not_create_destination(self) -> None:
        destination = self.directory / "not-created"
        self.run_cli(INSTALL, "--target", destination, "--dry-run")
        self.assertFalse(destination.exists())

    def test_install_dry_run_preserves_existing_project(self) -> None:
        (self.project / "README.md").write_text("Existing project\n", encoding="utf-8")
        before = snapshot(self.project)
        self.install("--dry-run")
        self.assertEqual(snapshot(self.project), before)

    def test_install_rejects_conflicting_skill_before_any_writes(self) -> None:
        skill = self.project / ".agents" / "skills" / "harness"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Keep my existing skill.\n", encoding="utf-8")
        before = snapshot(self.project)
        self.install(success=False)
        self.assertEqual(snapshot(self.project), before)

    def test_install_rejects_conflicting_agent_without_overwriting(self) -> None:
        self.install()
        role = next((self.project / ".codex" / "agents").glob("*.toml"))
        role.write_text(role.read_text(encoding="utf-8") + "\n# Local customization\n", encoding="utf-8")
        before = snapshot(self.project)
        self.install(success=False)
        self.assertEqual(snapshot(self.project), before)

    def test_install_rejects_existing_role_name_under_different_filename(self) -> None:
        source = next((ROOT / ".codex" / "agents").glob("*.toml"))
        agents = self.project / ".codex" / "agents"
        agents.mkdir(parents=True)
        (agents / "custom.toml").write_bytes(source.read_bytes())
        before = snapshot(self.project)
        self.install(success=False)
        self.assertEqual(snapshot(self.project), before)

    def test_install_rejects_malformed_config_before_any_writes(self) -> None:
        codex = self.project / ".codex"
        codex.mkdir()
        (codex / "config.toml").write_text('[agents\nenabled = true\n', encoding="utf-8")
        before = snapshot(self.project)
        self.install(success=False)
        self.assertEqual(snapshot(self.project), before)

    def test_install_rejects_symlink_destination_components(self) -> None:
        for relative in (".codex", ".agents/skills", "AGENTS.md"):
            with self.subTest(relative=relative):
                project = self.directory / ("symlink-" + relative.replace("/", "-"))
                project.mkdir()
                outside = self.directory / ("outside-" + relative.replace("/", "-"))
                link = project / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                if relative == "AGENTS.md":
                    outside.write_text("External instructions\n", encoding="utf-8")
                else:
                    outside.mkdir()
                link.symlink_to(outside, target_is_directory=outside.is_dir())
                before = snapshot(self.directory)
                self.run_cli(INSTALL, "--target", project, success=False)
                self.assertEqual(snapshot(self.directory), before)

    def test_file_write_failure_rolls_back_earlier_created_files(self) -> None:
        helper = self.file_helper()
        first = self.project / "generated" / "first.txt"
        second = self.project / "existing.txt"
        second.write_bytes(b"Original content")
        before = snapshot(self.project)
        original_open = Path.open

        def fail_second_write(path, mode="r", *arguments, **options):
            if path == second and mode == "wb":
                raise PermissionError("Simulated filesystem write denial")
            return original_open(path, mode, *arguments, **options)

        with mock.patch.object(Path, "open", new=fail_second_write):
            with self.assertRaises(PermissionError):
                helper.apply_files({first: b"Generated content", second: b"Replacement content"})
        self.assertEqual(snapshot(self.project), before)

    def test_exclusive_create_collision_preserves_concurrent_writer_file(self) -> None:
        helper = self.file_helper()
        first = self.project / "generated" / "first.txt"
        contested = self.project / "shared" / "contested.txt"
        original_open = Path.open

        def race_before_create(path, mode="r", *arguments, **options):
            if path == contested and mode == "xb":
                with original_open(path, "xb") as stream:
                    stream.write(b"Concurrent writer content")
            return original_open(path, mode, *arguments, **options)

        with mock.patch.object(Path, "open", new=race_before_create):
            with self.assertRaises(FileExistsError):
                helper.apply_files({first: b"Generated content", contested: b"Harness content"})
        self.assertFalse(first.exists())
        self.assertFalse(first.parent.exists())
        self.assertEqual(contested.read_bytes(), b"Concurrent writer content")

    def test_create_agent_round_trips_unicode_quotes_and_newlines(self) -> None:
        description = '검토자 "계약" \\ integration\n第二行'
        instructions = 'Compare "producer" and "consumer".\n한글과 日本語를 보존한다.\nLiteral \\\\ and triple """ quotes.\n'
        self.instructions.write_text(instructions, encoding="utf-8")
        self.run_cli(
            CREATE_AGENT,
            "--target", self.project,
            "--name", "contract_reviewer",
            "--description", description,
            "--instructions-file", self.instructions,
            "--sandbox-mode", "read-only",
        )
        output = self.project / ".codex" / "agents" / "contract_reviewer.toml"
        parsed = tomllib.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(parsed["name"], "contract_reviewer")
        self.assertEqual(parsed["description"], description)
        self.assertEqual(parsed["developer_instructions"], instructions)
        self.assertEqual(parsed["sandbox_mode"], "read-only")
        self.assertNotIn("model", parsed)

    def test_create_agent_accepts_workspace_write(self) -> None:
        self.create_agent("implementation_worker", "--sandbox-mode", "workspace-write")
        output = self.project / ".codex" / "agents" / "implementation_worker.toml"
        parsed = tomllib.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(parsed["sandbox_mode"], "workspace-write")

    def test_create_agent_rejects_existing_definition(self) -> None:
        self.create_agent()
        self.instructions.write_text("Different instructions\n", encoding="utf-8")
        before = snapshot(self.project)
        self.create_agent(success=False)
        self.assertEqual(snapshot(self.project), before)

    def test_create_agent_rejects_existing_role_name_under_different_filename(self) -> None:
        self.create_agent("reusable_reviewer")
        existing = self.project / ".codex" / "agents" / "reusable_reviewer.toml"
        existing.rename(existing.parent / "custom-role.toml")
        before = snapshot(self.project)
        self.create_agent("reusable_reviewer", success=False)
        self.assertEqual(snapshot(self.project), before)

    def test_create_agent_rejects_invalid_names_without_writes(self) -> None:
        for name in ("../escape", "nested/agent", "with-dash", "UpperCase", "with space", "1agent", ""):
            with self.subTest(name=name):
                before = snapshot(self.directory)
                self.create_agent(name, success=False)
                self.assertEqual(snapshot(self.directory), before)

    def test_create_agent_dry_run_does_not_write(self) -> None:
        before = snapshot(self.project)
        self.create_agent("dry_run_reviewer", "--dry-run")
        self.assertEqual(snapshot(self.project), before)

    def test_validate_rejects_missing_agent_required_fields(self) -> None:
        self.install()
        agent = self.project / ".codex" / "agents" / "broken_reviewer.toml"
        agent.write_text('name = "broken_reviewer"\ndescription = "Missing instructions"\n', encoding="utf-8")
        self.validate(success=False)

    def test_validate_rejects_duplicate_agent_names(self) -> None:
        self.install()
        self.create_agent()
        agent = self.project / ".codex" / "agents" / "example_reviewer.toml"
        (agent.parent / "second_reviewer.toml").write_bytes(agent.read_bytes())
        self.validate(success=False)

    def test_validate_rejects_invalid_skill_frontmatter(self) -> None:
        self.install()
        skill = self.project / ".agents" / "skills" / "invalid-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text('---\nname: invalid-skill\n---\nMissing description.\n', encoding="utf-8")
        self.validate(success=False)

    def test_validate_requires_valid_frontmatter_description_string(self) -> None:
        self.create_agent()
        skill = self.project / ".agents" / "skills" / "extra-review"
        skill.mkdir(parents=True)
        for description in ("false", "42", "[review]", "{scope: review}", "'unterminated"):
            with self.subTest(description=description):
                (skill / "SKILL.md").write_text(
                    f"---\nname: extra-review\ndescription: {description}\n---\nReview assigned files.\n",
                    encoding="utf-8",
                )
                self.validate(success=False)
        (skill / "SKILL.md").write_text(
            '---\nname: extra-review\ndescription: "false"\n---\nReview assigned files.\n',
            encoding="utf-8",
        )
        self.validate()

    def test_validate_rejects_broken_relative_markdown_file_reference(self) -> None:
        self.install()
        skill = self.project / ".agents" / "skills" / "harness" / "SKILL.md"
        with skill.open("a", encoding="utf-8") as stream:
            stream.write("\nRead [additional requirements](references/missing-requirements.md).\n")
        self.validate(success=False)

    def test_validate_rejects_stale_claude_runtime_in_active_reference(self) -> None:
        self.install()
        reference = self.project / ".agents" / "skills" / "harness" / "references" / "obsolete-runtime.md"
        reference.write_text("Use TeamCreate and CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1.\n", encoding="utf-8")
        self.validate(success=False)

    def test_validate_ignores_archived_material_and_unrelated_user_files(self) -> None:
        self.install()
        archive = self.project / "archive" / "upstream"
        archive.mkdir(parents=True)
        (archive / "SKILL.md").write_text("Use TeamCreate and .claude/agents/.\n", encoding="utf-8")
        (self.project / "README.md").write_text("Historical [link](no-such-file.md).\n", encoding="utf-8")
        (self.project / "application.toml").write_text("[not valid TOML\n", encoding="utf-8")
        self.validate()

    def test_plan_accepts_documented_statuses(self) -> None:
        self.create_agent()
        for status in ("pending", "running", "completed", "blocked", "failed", "skipped"):
            with self.subTest(status=status):
                self.write_plan([self.task("review", status=status, required=status != "skipped")])
                self.validate()

    def test_plan_requires_string_arrays(self) -> None:
        self.create_agent()
        for field in ("dependencies", "ownership", "acceptance"):
            for value in ("a string is not an array", [1], [None]):
                with self.subTest(field=field, value=value):
                    self.write_plan([self.task("review", **{field: value})])
                    self.validate(success=False)

    def test_plan_rejects_unknown_dependency_and_cycles(self) -> None:
        self.create_agent()
        for tasks in (
            [self.task("review", dependencies=["missing"])],
            [self.task("review", dependencies=["review"])],
            [self.task("first", dependencies=["second"]), self.task("second", dependencies=["first"])],
        ):
            with self.subTest(tasks=tasks):
                self.write_plan(tasks)
                self.validate(success=False)

    def test_plan_rejects_invalid_status_and_skipping_required_task(self) -> None:
        self.create_agent()
        for status in ("done", "unknown", "skipped"):
            with self.subTest(status=status):
                self.write_plan([self.task("required-review", status=status, required=True)])
                self.validate(success=False)

    def test_plan_started_tasks_require_completed_dependencies(self) -> None:
        self.create_agent()
        for status in ("running", "completed"):
            for dependency_status in ("pending", "running", "blocked", "failed", "skipped"):
                with self.subTest(status=status, dependency_status=dependency_status):
                    self.write_plan([
                        self.task("producer", status=dependency_status, required=dependency_status != "skipped"),
                        self.task("consumer", status=status, dependencies=["producer"]),
                    ])
                    self.validate(success=False)

    def test_plan_allows_completed_handoff_and_sequential_file_ownership(self) -> None:
        self.create_agent()
        self.write_plan([
            self.task("producer", status="completed", ownership=["src/adapter.py"]),
            self.task("consumer", status="running", dependencies=["producer"], ownership=["src/adapter.py"]),
        ])
        self.validate()

    def test_plan_rejects_simultaneous_overlapping_write_ownership(self) -> None:
        self.create_agent()
        for left, right in (
            ("src/adapter.py", "src/adapter.py"),
            ("src/adapter.py", "src/./adapter.py"),
            ("src/adapter.py", "src//adapter.py"),
            ("src", "src/adapter.py"),
            ("src/*", "src/adapter.py"),
            (".", "src/adapter.py"),
        ):
            with self.subTest(left=left, right=right):
                self.write_plan([
                    self.task("first", status="running", ownership=[left]),
                    self.task("second", status="running", ownership=[right]),
                ])
                self.validate(success=False)

    def test_plan_allows_parallel_readers_and_disjoint_writers(self) -> None:
        self.create_agent()
        for left, right in (([], []), (["src/a.py"], ["src/ab.py"]), (["src/frontend/"], ["src/backend/"])):
            with self.subTest(left=left, right=right):
                self.write_plan([
                    self.task("first", status="running", ownership=left),
                    self.task("second", status="running", ownership=right),
                ])
                self.validate()

    def test_plan_rejects_ownership_outside_project(self) -> None:
        self.create_agent()
        for path in ("../outside", "src/../../outside", "/tmp/absolute", "C:\\outside", "C:/outside"):
            with self.subTest(path=path):
                self.write_plan([self.task("writer", ownership=[path])])
                self.validate(success=False)


if __name__ == "__main__":
    unittest.main()
