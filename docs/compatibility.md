# Codex compatibility

Configuration contract checked against [OpenAI's native subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) on **2026-09-07**. This is a documentation compatibility target, not a claim that every Codex client/version has been exercised.

## Required surfaces

- A Codex client that discovers project skills under `.agents/skills/` and native custom agents under `.codex/agents/`.
- A trusted local project with its project configuration enabled.
- Python 3.11+ for this repository's standard-library-only installer and validation scripts.

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

The Codex plugin manifest packages the skill. It does not automatically deploy `.codex/agents/`, `.codex/config.toml`, or `AGENTS.md` into a project. Use `scripts/install.py` for the complete project scaffold.

Sandbox declarations express the intended agent policy. Parent session runtime overrides and platform restrictions can affect the effective sandbox. Ownership instructions do not create per-file access controls. Check the active client's effective policy when verifying write boundaries. [OpenAI subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents).

If custom roles are absent, verify the working project root, trust/configuration loading, and TOML validity, then start a new thread. If native subagent tools are unavailable, the parent can still follow the workflow sequentially; it should report that execution mode explicitly.

## Local helpers and native runtime actions

`run.py` manages v2 run plans, input fingerprints, refreshed packets, results, and a separate agent registry. Directory fingerprints omit common runtime caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`), `.DS_Store`, and `.pyc`/`.pyo`; an explicitly named file input is still fingerprinted. `communication.py` appends explicit events under `_workspace/communications/` and can export them. Their filesystem state does not spawn or stop native agents, release slots, or transmit messages. The parent pairs local records with actual runtime tool outcomes.

Use native tool schemas from the active session; no universal fork flag or peer-message API is assumed. Related agent reuse requires a refreshed packet and a supported follow-up action. Independent reviewers may use fresh context when the runtime supports it. A stop request must be followed by an observed stop or idle acknowledgment before write ownership moves.

Read-only agents remain read-only and ask the parent to record important messages. Logging is explicit and does not automatically capture all Codex internal communication. Successful `--run ID --complete` validation checks the recorded evidence and freshness; it remains distinct from observed native discovery, delivery, permissions, and concurrency. See the [runtime guide](../skills/harness/references/runtime-guide.md).

## Evidence to record

Keep the output of `python3 scripts/validate.py --project .` and the automated test suite separate from a live smoke result. For runtime reports, include client/version, project root, effective subagent settings, discovered roles, observed concurrent sessions, and the parent integration result. Follow the [quickstart live smoke procedure](quickstart.md#live-multi-agent-smoke-test).

The [verification record](verification.md) documents a successful two-custom-agent read workflow on Codex CLI 0.153.4 and a failed ephemeral-session probe. There is no maintained cross-version matrix or performance benchmark. Static validation alone still does not imply a live runtime pass.
