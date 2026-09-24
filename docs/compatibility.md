# Codex compatibility

Configuration contract checked against [OpenAI's native subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) on **2026-09-07**. This is a documentation compatibility target, not a claim that every Codex client/version has been exercised.

## Required surfaces

- For plugin installation: a supported desktop app or Codex CLI. The official plugin guide currently excludes the IDE extension. [OpenAI plugin documentation](https://learn.chatgpt.com/docs/plugins).
- For the project scaffold: a Codex client that discovers project skills under `.agents/skills/` and native custom agents under `.codex/agents/`.
- A trusted local project with its project configuration enabled.
- Python 3.11+ when running the bundled helpers or project installer; plugin installation itself does not run these Python scripts.

## Plugin installation contract

The repository catalog is `.agents/plugins/marketplace.json`, with marketplace ID `codex-harness` and plugin ID `codex-harness`. Its local source path `./` resolves from the repository root to `.codex-plugin/plugin.json`, which packages `./skills/`. Marketplace paths are relative to the marketplace root. [OpenAI packaging reference](https://developers.openai.com/plugins/build/plugins#marketplace-metadata).

On **2026-09-07**, the installed **Codex CLI 0.153.4** help confirmed `codex plugin marketplace add <SOURCE>`, `codex plugin add <PLUGIN@MARKETPLACE>`, and `codex plugin list --marketplace <NAME> --json`. This documents that CLI interface, not a minimum supported version or a cross-client installation test. Follow the [plugin quickstart](quickstart.md#install-as-a-plugin-recommended), then start a new session to load the installed skill.

## Project configuration

Each custom agent TOML provides `name`, `description`, and `developer_instructions`. These seed agents set `sandbox_mode` according to role and inherit model and reasoning effort from the parent. Newly created agents may require a new thread for discovery. [OpenAI subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents).

The checked-in project settings are:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
```

The current documented native feature is enabled by default; this configuration makes the project's intent explicit. The concurrency setting limits subagent threads in the session; runtime availability can impose a lower cap. The legacy `max_threads` spelling remains supported in the documented runtime, but this project uses the current spelling and does not set `max_depth`. [OpenAI subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents).

The installer preserves existing user settings, including a disabled subagent setting or a legacy concurrency key, and reports file conflicts. Run the validator and inspect the effective configuration after installation; it may differ from this repository's defaults.

Not every TOML representation can be extended without rewriting user content. When an inline `agents = { ... }` table lacks defaults the installer needs to add, it may fail with a diagnostic before any writes. Expand the table while preserving its values, then retry. For example:

```toml
# Before
agents = { enabled = true }
```

```toml
# After
[agents]
enabled = true
```

Place unrelated root-level settings before the expanded table, or keep them in their original named tables, so the conversion does not change their scope.

## Discovery and execution limits

The physical skill source is `skills/harness/`, and the native plugin manifest uses `skills = "./skills/"`. In this checkout, `.agents/skills/harness` is a symlink to `../../skills/harness`, exposing that same source for project skill discovery. There is no second skill copy to synchronize.

The project installer reads through the discovery alias and copies regular files into the target's `.agents/skills/harness/`. The installed project is self-contained and does not depend on a symlink back to this checkout.

The Codex plugin manifest packages the skill. Installation alone creates no project files. Explicit `$harness` or `$codex-harness:harness` invocation builds or updates a durable harness in the current target project by default, even when paired with an ordinary content task. An explicit read-only request or instruction not to build a harness takes precedence. Agent definitions belong under that project's `.codex/agents/*.toml`, reusable skills under `.agents/skills/`, and the `AGENTS.md` pointer, project configuration, and run records are created as appropriate. When Codex is started in the target, native agents work there; the plugin cache supplies the skill bundle that invocation copies into the target project. Use `scripts/install.py` for the optional predefined five-role scaffold. Manual `.agents/skills/harness/scripts/...` examples work after invocation or project installation.

Sandbox declarations express the intended agent policy. Parent session runtime overrides and platform restrictions can affect the effective sandbox. Ownership instructions do not create per-file access controls. Check the active client's effective policy when verifying write boundaries. [OpenAI subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents).

If custom roles are absent, verify the working project root, trust/configuration loading, and TOML validity, then start a new thread. An available built-in role can cover a suitable task with explicit instructions; report that substitution. Role discovery and exposed subagent tools do not establish that native spawning works in the current session.

Native spawn has no `cwd` parameter and inherits the parent project's session directory. Start Codex in the target project (`codex -C /absolute/path/to/project`) before using its agents. From a session started elsewhere, explicit workdir can place bootstrap files in the target, but native agents need a fresh session there. A `workspace-write` test returned `Operation not permitted` when writing target `.codex/agents/` and `.agents/skills/`. If this occurs, report the incomplete bootstrap and permission error; do not relocate definitions or silently change permissions.

## Native spawn preflight and ephemeral sessions

Before wider fan-out, use the first planned agent as a compatibility check:

1. Inspect the active native tool schema, available roles, and actual capacity. If no native tool is exposed, proceed with the sequential fallback below.
2. Spawn one agent with a standby-only instruction: wait for the refreshed task packet and do not read or write product files. Inspect the actual tool result before spawning more agents.
3. Only when a real child ID is returned, register it with `run.py start` if using a run plan, then dispatch the refreshed packet through the actual follow-up tool. Reuse this child for its planned task and count it against capacity; no separate throwaway probe is needed.

If the result contains `collab spawn failed: no thread with id`, stop further spawn attempts in that session. Preserve the full error and client/version as evidence. Retrying each role or switching to a built-in role does not address this missing-thread failure. Without a returned child ID, do not call `run.py start` or invent an agent ID. Capacity errors are a separate case: inspect actual session states and use supported lifecycle controls before a justified retry.

`codex exec --ephemeral` avoids persisting session rollout files to disk. This is the documented flag meaning and was confirmed by installed **Codex CLI 0.154.0** help on **2026-09-14**; it is not a guarantee of native subagent compatibility. The [CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli) and [subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents) do not establish that combination's compatibility. Known ephemeral mode is a reason to check the first spawn carefully; the Python helpers do not detect the parent CLI mode.

The [verification record](verification.md) contains the historical **0.153.4** ephemeral failure and ordinary-session success, plus a bounded **0.154.0** ephemeral probe that reported success without independent spawn metadata. These observations neither establish universal incompatibility nor identify a fixed version.

If native spawning is unavailable or fails, the parent can complete suitable substantive work sequentially in the existing session and report that mode. Preserve the user's persistence preference; do not silently restart without `--ephemeral`. An ordinary invocation is an option when persistent sessions are acceptable; see the [quickstart](quickstart.md#2-open-the-project-in-a-new-session). Keep native tasks that never started pending and record parent work separately, without synthetic IDs or native results. Native-only smoke checks remain `failed` for an observed failure or `not_run` for unexecuted checks; sequential work does not make that smoke pass.

## Local helpers and native runtime actions

`run.py` manages v2 run plans, input fingerprints, refreshed packets, results, and a separate agent registry. Directory fingerprints omit common runtime caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`), `.DS_Store`, and `.pyc`/`.pyo`; an explicitly named file input is still fingerprinted. `communication.py` appends explicit events under `_workspace/communications/` and can export them. Their filesystem state does not spawn or stop native agents, release slots, or transmit messages. The parent pairs local records with actual runtime tool outcomes.

Use native tool schemas from the active session; no universal fork flag or peer-message API is assumed. Related agent reuse requires a refreshed packet and a supported follow-up action. Independent reviewers may use fresh context when the runtime supports it. A stop request must be followed by an observed stop or idle acknowledgment before write ownership moves.

Read-only agents remain read-only and ask the parent to record important messages. Logging is explicit and does not automatically capture all Codex internal communication. Successful `--run ID --complete` validation checks the recorded evidence and freshness; it remains distinct from observed native discovery, delivery, permissions, and concurrency. See the [runtime guide](../skills/harness/references/runtime-guide.md).

## Evidence to record

Keep the output of `python3 scripts/validate.py --project .` and the automated test suite separate from a live smoke result. For runtime reports, include client/version, project root, effective subagent settings, discovered roles, observed concurrent sessions, and the parent integration result. Follow the [quickstart live smoke procedure](quickstart.md#live-multi-agent-smoke-test).

The [verification record](verification.md) distinguishes historical live results from the more limited current probe. There is no maintained cross-version matrix or performance benchmark. Static validation alone still does not imply a live runtime pass.
