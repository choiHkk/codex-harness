# Quickstart

Use a Codex client that supports project skills and native custom subagents. Python 3.11+ is required for the helper scripts; no third-party Python packages are needed. See [compatibility](compatibility.md) for the documented configuration contract.

## Use this checkout

1. Open the repository directory as a trusted local project in Codex.
2. Start a new session so Codex can discover `.agents/skills/harness/SKILL.md` and `.codex/agents/*.toml`.
3. Send the prompt below.

The checkout keeps one physical skill under `skills/harness/`. The `.agents/skills/harness` symlink points to `../../skills/harness` for project discovery; the plugin reads the same source through its standard `skills/` package directory.

```text
$harness 이 프로젝트에 맞는 하네스를 구성해줘. 독립 작업은 서브에이전트로 병렬 처리해줘.
```

Harness audits existing instructions, agents, and skills before adding anything. The parent chooses a proportionate team, assigns file ownership, generates the needed artifacts, and validates them. If generated roles are unavailable in the current session, start a new thread before testing those roles.

## Install into another project

Run from this repository root, replacing the absolute target path:

```bash
python3 scripts/install.py --target /absolute/path/to/project --dry-run
python3 scripts/install.py --target /absolute/path/to/project
python3 scripts/validate.py --project /absolute/path/to/project
```

The dry run previews the installation. The installer preserves existing project content and reports conflicts; read its output before continuing. It installs regular skill files into the target's `.agents/skills/harness/`, five seed agents, project subagent settings, and an `AGENTS.md` pointer. The target does not need a symlink. It does not edit `~/.codex/` or `~/.agents/`.

If an existing inline `agents = { ... }` table needs missing defaults, the installer may stop before any writes and ask for an expanded `[agents]` table. Preserve its existing values when expanding it, then rerun the dry run. See [configuration compatibility](compatibility.md) for an example.

Open the target directory in a new trusted local Codex session and use the same prompt. Installing only the optional Codex plugin supplies the skill; it does not copy project agent TOMLs or config.

## Add a focused agent

Usually, let `$harness` inspect the project and write suitable instructions. To create one manually, prepare an instruction file describing the narrow role, ownership boundary, expected evidence, and return format, then run from the installed project:

```bash
python3 .agents/skills/harness/scripts/create_agent.py \
  --target . \
  --name api_reviewer \
  --description "Review API changes for interface compatibility and error handling." \
  --instructions-file /absolute/path/to/api-reviewer.md \
  --sandbox-mode read-only
python3 .agents/skills/harness/scripts/validate.py --project .
```

Start a new thread if Codex does not discover the new role. Models and reasoning effort inherit from the parent unless you deliberately configure an override.

## Manage a run and its communication record

After installing, ask `$harness` to inspect the actual project and prepare a plan with immutable inputs, accepted decisions, skill paths, dependencies, ownership, and acceptance criteria. Initialize and inspect it from the target project:

```bash
python3 .agents/skills/harness/scripts/run.py --project . init \
  --plan-file /absolute/path/to/project-plan.json --run-id project-v1
python3 .agents/skills/harness/scripts/run.py --project . ready --run project-v1
python3 .agents/skills/harness/scripts/run.py --project . status --run project-v1
```

The parent first creates a native agent with a standby-only instruction, uses its real ID for `start`, then sends the refreshed packet through the actual follow-up tool. It registers actual results with `result`, and separately records confirmed session idleness or termination with `agent`. Important questions, answers, findings, and handoffs are explicitly recorded under `_workspace/communications/`; native delivery remains a separate tool call. Read-only roles ask the parent to log and route messages.

```bash
python3 .agents/skills/harness/scripts/communication.py --project . --run project-v1 view \
  --format markdown --output _workspace/communications/project-v1.md
python3 .agents/skills/harness/scripts/validate.py --project . --run project-v1 --complete
```

A later input change can start a new run through `run.py resume --run project-v1 --new-run project-v2`; affected results and dependents are invalidated and packets refreshed. Follow the [runtime guide](../skills/harness/references/runtime-guide.md) for the complete plan/result contracts, message correlation, and actual lifecycle order. These helpers do not spawn agents, send native messages, or stop an active writer.

## Live multi-agent smoke test

Static validation cannot establish runtime discovery or parallel execution. In a new trusted local Codex session, ask:

```text
Use harness_explorer and harness_architect as two separate subagents in parallel.
Explorer: inspect the harness entry points and cite the relevant files.
Architect: inspect the task ownership protocol and return a small improvement plan
in your response only. Both tasks are read-only and independent.
Have the parent combine the two results. Do not modify files.
```

Check that two native subagent sessions start, each completes its assigned task, and the parent combines their results. Record the Codex client/version, effective configuration, discovered role names, observed overlap, returned evidence, and any errors. An instruction to run in parallel is not proof that the runtime did so.

For write-path verification, use a disposable project and explicitly assign separate temporary files to two workers. Verify both expected contents, unchanged sentinel files outside ownership, parent integration, and reviewer/QA results. Task packets and a completion checklist are in [multi-agent.md](multi-agent.md).

If roles are missing, confirm the project root and trust settings, validate the files, then start a new thread. If subagent tools are unavailable or capacity is exhausted, have the parent complete the work sequentially and report the reduced execution mode.

## Repository checks

From this repository root:

```bash
python3 scripts/validate.py --project .
python3 -m unittest discover -s tests -v
```

Report static validation, automated script checks, and live runtime observations separately. Do not infer a live runtime pass from the commands above.
