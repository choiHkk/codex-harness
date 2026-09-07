# Migration from Claude Code to Codex

This independent migration starts from [revfactory/harness at `cceac68ea1d0ad198ef4b7b906cd238375836387`](https://github.com/revfactory/harness/commit/cceac68ea1d0ad198ef4b7b906cd238375836387). It preserves the project-analysis and team-design approach while replacing runtime-specific artifacts and orchestration assumptions.

## Artifact mapping

| Upstream Claude Code surface | Codex surface here | Migration behavior |
| --- | --- | --- |
| `skills/harness/SKILL.md` | Migrated `skills/harness/SKILL.md`, discovered through `.agents/skills/harness` | One physical source; project discovery symlink; installer copies regular files to the target |
| `.claude/agents/*.md` | `.codex/agents/*.toml` | Native `name`, `description`, `developer_instructions`; optional sandbox |
| `.claude/skills/<name>/` | `.agents/skills/<name>/` | Reusable domain procedures stay in skills |
| `CLAUDE.md` harness registration | `AGENTS.md` pointer | Short entry point; detailed orchestration stays in the skill |
| `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` | Codex plugin packages the skill; project installer supplies agents/config |
| Claude marketplace install commands | `python3 scripts/install.py --target ...` | Explicit, project-scoped installation with dry run and preservation |
| Experimental Agent Teams environment flag | Native `[agents]` project settings | No Claude-specific environment flag |
| Team/task/message APIs | Available native subagent tools | Parent schedules, receives evidence, and integrates |
| Agent Markdown tool/model fields | TOML role instructions and supported settings | Inherit parent model and effort by default |
| Assumed parallel completion | Separate static, functional, and live verification | No runtime success claim from generated files alone |

The plugin packages the standard `skills/` directory. This checkout exposes its single `skills/harness/` source through `.agents/skills/harness -> ../../skills/harness`; an installed target gets regular files under `.agents/skills/harness/` and needs no symlink.

Do not mechanically rename `.claude/` to `.codex/`: agent formats, skills discovery, plugin scope, and runtime tools differ. Inspect existing project agents and skills before generating replacements. Reuse compatible roles and preserve user-authored content; the installer reports conflicts instead of replacing it blindly.

## Pattern mapping

| Pattern | Codex execution |
| --- | --- |
| Pipeline | Parent schedules each task after accepting its predecessor's output |
| Fan-out/fan-in | Independent bounded children run concurrently; parent combines results |
| Expert pool | Parent selects the smallest relevant subset of specialist roles |
| Producer/reviewer | Worker produces a change, read-only reviewer returns findings, owner fixes |
| Supervisor | Parent dynamically dispatches tasks with explicit dependencies and file ownership |
| Hierarchical decomposition | Parent flattens the design into leaf tasks; no recursive spawning by default |

The parent owns shared configuration and final verification. Child agents return status, evidence, actual checks, and risks. Read-only roles cannot write plan documents or fixes; QA writes only assigned tests and verification artifacts in addition to normal test outputs.

## Adopting an existing project

1. Inspect existing `AGENTS.md`, `.codex/`, and `.agents/skills/` alongside any old Claude artifacts.
2. Run the project installer with `--dry-run`; inspect any collisions before installation.
3. Install the starting team, then open the project in a new trusted local Codex session.
4. Ask `$harness` to adapt existing domain roles and procedures, retaining useful constraints and removing obsolete runtime instructions.
5. Run project validation and targeted functional checks, then perform the [live smoke test](quickstart.md#live-multi-agent-smoke-test).

The installer does not translate arbitrary old agent Markdown files automatically. Domain adaptation is performed by the harness workflow after inspecting the project. Keep upstream history and attribution distinct from Codex compatibility evidence. Original Claude Code benchmarks and release labels are historical information, not Codex results.

See [compatibility](compatibility.md), [multi-agent architecture](multi-agent.md), and [the preserved upstream changelog](../CHANGELOG.md) for context.
