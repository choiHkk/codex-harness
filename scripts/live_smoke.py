#!/usr/bin/env python3
"""Opt-in live Codex regression: parallel writes, a blocker, and partial resume.

Uses an ordinary authenticated Codex session; not part of the offline unit suite.
Every run gets a new disposable project. No user-level configuration is changed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(project: Path, args: list[str]) -> dict:
    result = subprocess.run(args, cwd=project, text=True, capture_output=True, timeout=120)
    return {"command": args, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def run_hashes(project: Path, run_id: str) -> dict:
    directory = project / ".harness" / "runs" / run_id
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*"))
            if path.is_file() and not path.name.endswith(".lock")}


def protected_hashes(project: Path) -> dict[str, str]:
    """Capture fixture and installed executable inputs, excluding tool caches."""
    project = project.resolve()
    paths = {project / name for name in (
        "sentinel.txt", "plan.template.json", "tests/test_alpha.py", "tests/test_beta.py",
        "AGENTS.md", ".codex/config.toml", "_workspace/smoke_control.py",
    )}
    for directory in (project / ".agents/skills/harness", project / ".codex/agents"):
        if not directory.is_dir() or not directory.resolve().is_relative_to(project):
            raise ValueError(f"Invalid protected fixture directory: {directory}")
        for path in directory.rglob("*"):
            relative = path.relative_to(project)
            if any(part in CACHE_NAMES for part in relative.parts) or path.suffix in {".pyc", ".pyo"}:
                continue
            if not path.resolve().is_relative_to(project):
                raise ValueError(f"Protected fixture path escapes project: {relative}")
            if path.is_file():
                paths.add(path)
    output = {}
    for path in sorted(paths):
        if not path.is_file() or not path.resolve().is_relative_to(project):
            raise ValueError(f"Invalid protected fixture file: {path}")
        output[path.relative_to(project).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return output


def check_protected(project: Path, baseline: dict | None) -> str:
    source = "caller_supplied" if baseline is not None else "project_record"
    if baseline is None:
        baseline = json.loads((project / "_workspace/protected.json").read_text())
    if not isinstance(baseline, dict) or not baseline or any(
            not isinstance(name, str) or not isinstance(digest, str) for name, digest in baseline.items()):
        raise ValueError("Protected baseline must be a non-empty relative-path to SHA-256 mapping.")
    current = protected_hashes(project)
    if current != baseline:
        changed = sorted(name for name in set(current) | set(baseline) if current.get(name) != baseline.get(name))
        raise ValueError("Protected fixture files changed or baseline coverage differs: " + ", ".join(changed))
    return source


def peer_answers(events: list[dict], worker_ids: set[str]) -> list[dict]:
    """Cross-check explicit peer records without claiming native transport proof."""
    questions = {event["message_id"]: event for event in events
                 if event.get("kind") == "question" and event.get("sender") in worker_ids
                 and event.get("recipient") in worker_ids and event["sender"] != event["recipient"]}

    def delivery_recorded(message: dict) -> bool:
        if message.get("delivery") in {"sent", "received"}:
            return True
        return any(event.get("reply_to") == message["message_id"]
                   and event.get("kind") not in {"question", "answer"}
                   and event.get("delivery") in {"sent", "received"} for event in events)

    answers = []
    for event in events:
        question = questions.get(event.get("reply_to"))
        if (event.get("kind") == "answer" and question is not None
                and event.get("sender") == question["recipient"]
                and event.get("recipient") == question["sender"]
                and delivery_recorded(question) and delivery_recorded(event)):
            answers.append(event)
    return answers


def prepare(project: Path) -> Path:
    if project.exists():
        raise ValueError(f"Use a new disposable directory: {project}")
    # Import only for preparation, so a copied control script remains standalone.
    sys.path.insert(0, str(ROOT / "scripts"))
    from install import install
    install(project)
    (project / "specs").mkdir()
    (project / "tests").mkdir()
    (project / "_workspace").mkdir()
    (project / "specs/alpha.txt").write_text("ALPHA\n", encoding="utf-8")
    (project / "specs/beta.txt").write_text("UNRESOLVED\n", encoding="utf-8")
    for name in ("alpha", "beta"):
        (project / f"tests/test_{name}.py").write_text(
            f"import unittest\nfrom {name} import value\n\n"
            f"class TestValue(unittest.TestCase):\n"
            f"    def test_value(self):\n        self.assertEqual(value(), '{name.upper()}')\n",
            encoding="utf-8")
    (project / "sentinel.txt").write_text("Keep this existing project file unchanged.\n", encoding="utf-8")
    tasks = [{"id": name, "role": "harness_worker", "dependencies": [],
              "ownership": [f"{name}.py"], "required": True,
              "inputs": [f"specs/{name}.txt", f"tests/test_{name}.py"],
              "context": {"decisions": ["Implement value() returning the exact spec text; report blocked if spec disagrees with test."],
                          "skill_paths": []},
              "acceptance": [f"python3 -m unittest discover -s tests -p test_{name}.py -v passes"]}
             for name in ("alpha", "beta")]
    tasks.append({"id": "verify", "role": "harness_qa", "dependencies": ["alpha", "beta"],
                  "ownership": [], "required": True, "inputs": ["tests"],
                  "context": {"decisions": ["Verify both produced modules; do not change product code."], "skill_paths": []},
                  "acceptance": ["python3 -m unittest discover -s tests -v passes both tests"]})
    write_json(project / "plan.template.json", {"objective": "Exercise real parallel writes, explicit peer communication, failure gating and partial resume.", "tasks": tasks})
    shutil.copyfile(Path(__file__).resolve(), project / "_workspace/smoke_control.py")
    write_json(project / "_workspace/protected.json", protected_hashes(project))
    prompt = """Run the existing harness's LIVE REGRESSION in this disposable project. Do the work, not a design review.
Read .agents/skills/harness/references/runtime-guide.md and the available custom roles. Use actual native harness_worker agents and a harness_qa agent. Do not substitute roles or invent native IDs. No recursive agents. Do not edit harness/config/tests/plan/sentinel files. Only workers may write alpha.py and beta.py; parent owns the run ledger and _workspace evidence. No network needed.

Use python3 .agents/skills/harness/scripts/run.py --project . for lifecycle commands. Use communication.py --project . --run first|resumed for separate message logs. Never edit generated plan/agents/result records by hand. Parent may write candidate result JSON files under _workspace then submit with run.py result. Result schema is run_id,task_id,status,summary,artifacts,checks[{name,status,evidence,required,command?}],issues. Record only observed checks. Agent state updates require actual native idle/stop/close evidence.

1. Initialize run first from plan.template.json. Spawn TWO harness_worker children into standby, collect real IDs, assign alpha and beta via run.py start, then give both their input.md and each other's IDs before waiting. You are not alone; each owns only its matching .py file. Tell them to read refreshed packets and preserve others' work. Have alpha ask beta a relevant contract question via actual native send (e.g. whether both functions use value() and whether beta has an input blocker); beta must answer with the observed mismatch and notify the parent. Record correlated question/answer and actual delivery observations with communication.py. The parent may relay/log if necessary but must actually deliver the exchange. Record sender/recipient as real native IDs and attach message IDs to native text. No fake heartbeat or invented delivery.
2. Alpha implements value() -> ALPHA and runs its test. Beta sees UNRESOLVED in its spec versus BETA in the test, runs its test to capture the actual failure, and returns blocked without guessing or modifying specs/tests. Record both results and observed idle states. QA remains pending. Do not silently fix the first-run blocker.
3. Run `python3 _workspace/smoke_control.py checkpoint --target .`. This external control checks that completion fails, records the original run hashes and alpha hash, and changes only beta's spec to BETA as an explicitly authorized scenario transition. Then run `run.py --project . resume --run first --new-run resumed`. It must reuse alpha and invalidate beta and verify.
4. Reuse the actual idle beta worker if available (or spawn another actual harness_worker within native limits), register beta in resumed, deliver the NEW input packet, and implement/test beta. Do not rerun alpha. Record beta's completed result and observed idle state. Start harness_qa only after dependencies have accepted results. Give it the verify packet; it runs both tests without product edits. Record the actual QA result and observed idle state.
5. Run `python3 .agents/skills/harness/scripts/validate.py --project . --run resumed --complete`. Export both communication logs to Markdown under _workspace/communications. Write _workspace/native-report.json with actual parent_thread_id if exposed, worker_agent_ids (all workers from first and resumed), qa_agent_id, role_fallbacks (empty if none), and a short description of the native question/answer. Do not claim closure when only idle is observed. Return the actual outcome and evidence paths.

This is a bounded fixture: two 2-line modules and two small unit tests. Continue through the deliberate blocker using the checkpoint transition; no user confirmation is needed. If native delegation is unavailable or a required check fails, report the failure honestly and leave evidence intact.
"""
    path = project / "_workspace/prompt.md"
    path.write_text(prompt, encoding="utf-8")
    return path


def checkpoint(project: Path) -> dict:
    path = project / "_workspace/checkpoint.json"
    if path.exists():
        raise ValueError("The first-run checkpoint already exists; preserve the evidence.")
    plan = json.loads((project / ".harness/runs/first/plan.json").read_text())
    tasks = {task["id"]: task for task in plan["tasks"]}
    if {key: task["status"] for key, task in tasks.items()} != {
            "alpha": "completed", "beta": "blocked", "verify": "pending"}:
        raise ValueError("Expected alpha completed, beta blocked, verify pending before resume.")
    registry = json.loads((project / ".harness/runs/first/agents.json").read_text())["agents"]
    if len(registry) != 2 or any(a["state"] in {"running", "stop_requested"} for a in registry.values()):
        raise ValueError("Observe both native workers idle/stopped before the checkpoint.")
    result = command(project, [sys.executable, ".agents/skills/harness/scripts/validate.py", "--project", ".", "--run", "first", "--complete"])
    if result["exit_code"] == 0 or "beta" not in result["stdout"] + result["stderr"]:
        raise ValueError("Completion must reject the required blocked beta task.")
    output = {"first_completion": result, "old_run_hashes": run_hashes(project, "first"),
              "alpha_hash": hashlib.sha256((project / "alpha.py").read_bytes()).hexdigest()}
    write_json(path, output)
    (project / "specs/beta.txt").write_text("BETA\n", encoding="utf-8")
    return output


def verify(project: Path, baseline: dict | None = None) -> dict:
    # Validate installed code before importing any module controlled by the run.
    baseline_source = check_protected(project, baseline)
    sys.path.insert(0, str(project / ".agents/skills/harness/scripts"))
    from communication import read_events
    from run_checks import validate_completion
    checkpoint_data = json.loads((project / "_workspace/checkpoint.json").read_text())
    if checkpoint_data["old_run_hashes"] != run_hashes(project, "first"):
        raise ValueError("Resume modified the previous run's records.")
    if checkpoint_data["alpha_hash"] != hashlib.sha256((project / "alpha.py").read_bytes()).hexdigest():
        raise ValueError("Unchanged alpha output was modified during resume.")
    directory = project / ".harness/runs/resumed"
    errors = validate_completion(project, directory)
    if errors:
        raise ValueError("Completion rejected: " + "; ".join(errors))
    plan = json.loads((directory / "plan.json").read_text())
    tasks = {task["id"]: task for task in plan["tasks"]}
    if tasks["alpha"].get("reused_from") != {"run_id": "first", "task_id": "alpha"} or tasks["alpha"]["attempts"] != 0:
        raise ValueError("Expected alpha result reuse without another dispatch.")
    if any(tasks[name]["attempts"] != 1 or tasks[name].get("reused_from") for name in ("beta", "verify")):
        raise ValueError("Expected exactly one resumed beta and QA dispatch.")
    first_plan = json.loads((project / ".harness/runs/first/plan.json").read_text())
    first_tasks = {task["id"]: task for task in first_plan["tasks"]}
    first_registry = json.loads((project / ".harness/runs/first/agents.json").read_text())["agents"]
    resumed_registry = json.loads((directory / "agents.json").read_text())["agents"]
    first_workers = {first_tasks[name].get("agent_id") for name in ("alpha", "beta")}
    if len(first_workers) != 2 or any(not isinstance(identifier, str) or not identifier for identifier in first_workers):
        raise ValueError("First-run plan must identify two distinct worker agents.")
    for name in ("alpha", "beta"):
        if first_registry.get(first_tasks[name]["agent_id"], {}).get("task_id") != name:
            raise ValueError(f"First-run {name} agent does not agree with its registry.")
    for name in ("beta", "verify"):
        if resumed_registry.get(tasks[name].get("agent_id"), {}).get("task_id") != name:
            raise ValueError(f"Resumed {name} agent does not agree with its registry.")
    events = read_events(project, "first")
    answers = peer_answers(events, first_workers)
    if not answers:
        raise ValueError("Missing correlated worker question/answer with delivery observations linked to both messages.")
    native = json.loads((project / "_workspace/native-report.json").read_text())
    reported_workers = native.get("worker_agent_ids")
    workers = first_workers | {tasks["beta"]["agent_id"]}
    if (native.get("role_fallbacks") != [] or not isinstance(reported_workers, list)
            or any(not isinstance(identifier, str) for identifier in reported_workers)
            or set(reported_workers) != workers
            or native.get("qa_agent_id") != tasks["verify"].get("agent_id")
            or native.get("qa_agent_id") in workers):
        raise ValueError("Reported worker and QA IDs must match the task registries with no reported role substitution.")
    test = command(project, [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    if test["exit_code"] or "Ran 2 tests" not in test["stderr"]:
        raise ValueError("Independent final tests failed: " + test["stdout"] + test["stderr"])
    output = {"verified_at": datetime.now(timezone.utc).isoformat(), "project": str(project),
              "reported_worker_agent_ids": native["worker_agent_ids"], "reported_qa_agent_id": native["qa_agent_id"],
              "native_provenance_checked": False,
              "native_provenance_note": "Native roles, overlapping execution and transport require independent native tool metadata review.",
              "protected_baseline_source": baseline_source,
              "first_completion_exit": checkpoint_data["first_completion"]["exit_code"],
              "final_completion_errors": errors, "preserved_previous_run": True,
              "reused_tasks": ["alpha"], "rerun_tasks": ["beta", "verify"],
              "reported_correlated_answers": len(answers), "recorded_first_run_events": len(events), "tests": test}
    write_json(project / "_workspace/verification.json", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "checkpoint", "verify"))
    parser.add_argument("--target", type=Path, required=True, help="A NEW disposable project directory for prepare/run.")
    parser.add_argument("--timeout", type=int, default=1200, help="Live CLI timeout in seconds.")
    parser.add_argument("--baseline-file", type=Path,
                        help="Trusted external baseline for verify; new baseline output for prepare/run.")
    args = parser.parse_args()
    project = args.target.expanduser().resolve()
    try:
        if args.action in {"prepare", "run"}:
            prompt = prepare(project)
            baseline = protected_hashes(project)
            if args.baseline_file:
                baseline_file = args.baseline_file.expanduser().resolve()
                if baseline_file.is_relative_to(project) or baseline_file.exists():
                    raise ValueError("Use a new baseline file outside the disposable project.")
                write_json(baseline_file, baseline)
            if args.action == "prepare":
                print(prompt)
                return 0
            executable = shutil.which("codex")
            if not executable:
                raise ValueError("codex executable is unavailable; prepared fixture is preserved.")
            invocation = [executable, "exec", "--strict-config", "--json", "--sandbox", "workspace-write",
                          "--skip-git-repo-check", "-C", str(project),
                          "-c", f"projects.{json.dumps(str(project))}.trust_level=\"trusted\"",
                          "--output-last-message", str(project / "_workspace/native-result.md"), "-"]
            write_json(project / "_workspace/invocation.json", invocation)
            print(f"Running native Codex regression in {project}", flush=True)
            with prompt.open() as source, (project / "_workspace/native-events.jsonl").open("w") as out, \
                    (project / "_workspace/native-stderr.log").open("w") as err:
                result = subprocess.run(invocation, stdin=source, stdout=out, stderr=err, timeout=args.timeout)
            if result.returncode:
                raise ValueError(f"Native Codex exited {result.returncode}; inspect _workspace/native-stderr.log.")
            output = verify(project, baseline)
        elif args.action == "checkpoint":
            output = checkpoint(project)
        else:
            baseline = None
            if args.baseline_file:
                baseline_file = args.baseline_file.expanduser().resolve()
                if baseline_file.is_relative_to(project):
                    raise ValueError("The trusted baseline file must be outside the disposable project.")
                baseline = json.loads(baseline_file.read_text())
            output = verify(project, baseline)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
