# Quickstart

Start with the plugin in a Codex client that supports plugins. Python 3.11+ is needed when running the bundled helper scripts or the optional project installer, with no third-party Python packages. See [compatibility](compatibility.md) for supported surfaces and the project configuration contract.

## Install as a plugin (recommended)

### 1. Add the marketplace and install

Run in your terminal:

```bash
codex plugin marketplace add https://github.com/revfactory/codex-harness.git
codex plugin add codex-harness@codex-harness
```

The first command registers this repository's marketplace; the second installs its plugin. Both the marketplace ID and plugin ID are `codex-harness`. The displayed names are **Codex Harness** and **Harness for Codex**, respectively. You do not need a manual clone or the Python installer for this route.

These commands use the interface available in Codex CLI **0.153.4**. Check `codex plugin --help` if your version differs. Marketplace registration follows the [official packaging guide](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli).

To install through the desktop app after adding the marketplace, restart the app, open **Plugins**, choose **Codex Harness**, and install **Harness for Codex**. In an interactive Codex CLI session, `/plugins` provides a plugin browser for configured marketplaces. Plugins are not available in the IDE extension; use the desktop app or CLI for this route. [Official plugin guide](https://learn.chatgpt.com/docs/plugins).

### 2. Open the project in a new session

Open the project you want to configure, rather than the downloaded marketplace directory. For example:

```bash
codex -C /absolute/path/to/project
```

For a non-interactive ordinary session:

```bash
codex exec -C /absolute/path/to/project '$harness Build a harness for this project. Use subagents for independent tasks after checking the first native spawn.'
```

These examples keep your configured model and permissions. Single quotes preserve the literal `$harness` prompt in the shell. If you chose `--ephemeral` to avoid persistent session files, keep that choice and follow the [native spawn preflight](compatibility.md#native-spawn-preflight-and-ephemeral-sessions); do not silently switch to an ordinary session.

Start a new session after installation, then send:

```text
$harness Build a harness for this project. Use subagents in parallel for independent tasks.
```

Korean also works:

```text
$harness 이 프로젝트에 맞는 하네스를 구성해줘. 독립 작업은 서브에이전트로 병렬 처리해줘.
```

Harness inspects the project's existing instructions, agents, and skills, then creates the needed project files. Start a new thread if newly created custom roles are not yet available.

### 3. Check the installation

```bash
codex plugin list --marketplace codex-harness --json
```

Confirm that `codex-harness` is installed and enabled. You can also check it in `/plugins`; if disabled, press `Space` on the installed entry to enable it, then start a new session. [Official CLI plugin browser](https://learn.chatgpt.com/docs/plugins#plugin-browser-in-codex-cli).

| Installation route | What it provides |
| --- | --- |
| Plugin | The `harness` skill, references, and helper scripts in Codex's plugin cache; project files are created when you ask Harness to configure a project. |
| Project installer (optional) | Regular skill files in `.agents/skills/harness/`, five predefined agents in `.codex/agents/`, merged project configuration, and an `AGENTS.md` pointer. |

Plugin installation does not itself copy the seed team or project settings. For the predefined team, follow [Install into another project](#install-into-another-project). The manual helper commands later in this guide assume that project installation; with the plugin alone, ask `$harness` to locate and use the helpers in its installed skill directory.

### Install from a local checkout

For local development or a checkout containing marketplace changes that are not yet published:

```bash
git clone https://github.com/revfactory/codex-harness.git
cd codex-harness
codex plugin marketplace add .
codex plugin add codex-harness@codex-harness
```

If you already have this checkout, run only the last two commands from its root. Then open your target project in a new session. The catalog at [`.agents/plugins/marketplace.json`](../.agents/plugins/marketplace.json) points to the existing plugin at the repository root.

### Troubleshooting

- **`plugin` or `add` is unrecognized:** use a Codex CLI version exposing the commands above; inspect `codex --version` and `codex plugin --help`. The command is `codex plugin add`, not `codex plugin install`.
- **Marketplace or plugin not found:** run `codex plugin marketplace list` and `codex plugin list --marketplace codex-harness --available --json`. Confirm the source includes `.agents/plugins/marketplace.json`; use the local-checkout route for unpublished changes.
- **`harness` is missing:** confirm the plugin is installed and enabled, then start a new session in the target project. In the desktop app, use `@` to select the plugin or bundled skill. [Official plugin usage](https://learn.chatgpt.com/docs/plugins).
- **`.agents/skills/harness/scripts/...` is missing:** those project-local paths come from the optional project installer. Ask the plugin to use its installed helper paths, or install the project scaffold below.
- **`collab spawn failed: no thread with id`:** stop native fan-out and per-role retries in that session. Record the error and CLI version; no returned child ID means no `run.py start`. Follow the [preflight and fallback guidance](compatibility.md#native-spawn-preflight-and-ephemeral-sessions), preserving any explicit `--ephemeral` preference.

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

If you started with the plugin and do not have a checkout, clone the repository using the first two commands under [Install from a local checkout](#install-from-a-local-checkout). Then run from this repository root, replacing the absolute target path:

```bash
python3 scripts/install.py --target /absolute/path/to/project --dry-run
python3 scripts/install.py --target /absolute/path/to/project
python3 scripts/validate.py --project /absolute/path/to/project
```

The dry run previews the installation. The installer preserves existing project content and reports conflicts; read its output before continuing. It installs regular skill files into the target's `.agents/skills/harness/`, five seed agents, project subagent settings, and an `AGENTS.md` pointer. The target does not need a symlink. It does not edit `~/.codex/` or `~/.agents/`.

If an existing inline `agents = { ... }` table needs missing defaults, the installer may stop before any writes and ask for an expanded `[agents]` table. Preserve its existing values when expanding it, then rerun the dry run. See [configuration compatibility](compatibility.md) for an example.

Open the target directory in a new trusted local Codex session and use the same prompt. The plugin is sufficient for the skill workflow; this optional installer provides the predefined project scaffold.

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

The parent first creates one native agent with a standby-only instruction and inspects the returned result before wider fan-out. Only a successful spawn with a real child ID permits `start`, followed by delivery of the refreshed packet through the actual follow-up tool. Reuse that agent for its planned task within actual capacity. A missing-thread error stops retries; leave unstarted native tasks pending and record sequential parent work separately. See the [preflight](compatibility.md#native-spawn-preflight-and-ephemeral-sessions).

The parent registers actual results with `result`, and separately records confirmed session idleness or termination with `agent`. Important questions, answers, findings, and handoffs are explicitly recorded under `_workspace/communications/`; native delivery remains a separate tool call. Read-only roles ask the parent to log and route messages.

```bash
python3 .agents/skills/harness/scripts/communication.py --project . --run project-v1 view \
  --format markdown --output _workspace/communications/project-v1.md
python3 .agents/skills/harness/scripts/validate.py --project . --run project-v1 --complete
```

A later input change can start a new run through `run.py resume --run project-v1 --new-run project-v2`; affected results and dependents are invalidated and packets refreshed. Follow the [runtime guide](../skills/harness/references/runtime-guide.md) for the complete plan/result contracts, message correlation, and actual lifecycle order. These helpers do not spawn agents, send native messages, or stop an active writer.

## Live multi-agent smoke test

Static validation and exposed tools cannot establish native spawning or parallel execution. In a new trusted local Codex session, ask:

```text
First spawn one harness_explorer with a standby-only instruction: wait for the
task packet and do not read or write product files. Inspect its actual result
before starting another agent. If no child ID is returned, report the error and
stop this native smoke. For "collab spawn failed: no thread with id", do not retry
other roles in this session.
On success, reuse that child for the Explorer task below, then start a separate
harness_architect for the Architect task within actual capacity. Dispatch both
independent tasks before waiting for their results.
Explorer: inspect the harness entry points and cite the relevant files.
Architect: inspect the task ownership protocol and return a small improvement plan
in your response only. Both tasks are read-only and independent.
Have the parent combine the two results. Do not modify files.
```

Check that the first spawn returns a real child ID, two native subagent sessions start, each completes its assigned task, and the parent combines their results. Record the Codex client/version, session mode if known, effective configuration, discovered role names, observed overlap, returned evidence, and any errors. An instruction to run in parallel is not proof that the runtime did so.

For write-path verification, use a disposable project and explicitly assign separate temporary files to two workers. Verify both expected contents, unchanged sentinel files outside ownership, parent integration, and reviewer/QA results. Task packets and a completion checklist are in [multi-agent.md](multi-agent.md).

If roles are missing, confirm the project root and trust settings, validate the files, then start a new thread. Distinguish missing roles, unavailable tools, capacity limits, and the missing-thread error using the [compatibility guide](compatibility.md#native-spawn-preflight-and-ephemeral-sessions). The parent can perform suitable substantive work sequentially in the existing session, preserving the user's persistence preference. Native-only checks stay `failed` or `not_run` as observed; sequential fallback is not a successful native smoke.

## Repository checks

From this repository root:

```bash
python3 scripts/validate.py --project .
python3 -m unittest discover -s tests -v
```

Report static validation, automated script checks, and live runtime observations separately. Do not infer a live runtime pass from the commands above.
