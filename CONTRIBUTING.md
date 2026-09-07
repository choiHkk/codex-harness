# Contributing to Harness for Codex

This repository is an independent Codex migration of [revfactory/harness](https://github.com/revfactory/harness). Keep native agent configuration, the canonical skill, installation behavior, and documentation consistent.

## Local setup

Use Python 3.11+ and a Codex client supporting project skills and native subagents. No third-party Python packages are required. Open this checkout as a trusted local project in a new Codex session to exercise the skill and agents.

```bash
python3 scripts/validate.py --project .
python3 -m unittest discover -s tests -v
```

For installer changes, exercise a temporary target and verify preservation of existing files, reported conflicts, and repeated installation. For agent/skill behavior, follow the [live smoke procedure](docs/quickstart.md#live-multi-agent-smoke-test). Record automated and live checks separately; report checks you could not run. Do not claim runtime discovery or concurrency based on syntax validation.

## Change boundaries

- `skills/harness/` is the single physical skill source. Keep `.agents/skills/harness` as its project-discovery symlink and the plugin manifest pointed at `./skills/`. The installer copies regular files to a target's `.agents/skills/harness/`; keep bundled helpers usable there without this checkout.
- `.codex/agents/*.toml` contains narrow project roles. Inherit models and effort unless a deliberate override is necessary.
- The parent owns scheduling and integration. Give parallel workers disjoint write ownership and explicit dependencies.
- Keep read-only roles non-editing; QA owns verification, not product fixes.
- Preserve existing user content during installation. Validate conflicts before making changes.
- Update English and Korean usage instructions when commands or layout change; keep the Japanese entry point accurate.
- Preserve upstream license and attribution. Treat upstream changelog entries and measurements as history.

## Pull requests and issues

Describe the concrete problem, resulting behavior, changed interfaces, and relevant verification. Include a minimal reproduction for defects, plus Codex client/version, OS, Python version, effective project settings, and whether the failure occurred in static validation, installation, or a live session. Redact credentials and private project data from logs.

Prefer focused changes and tests that establish a material behavior or boundary. Documentation-only edits do not need tests that duplicate the wording. Use clear English or Korean commit messages; `feat:`, `fix:`, `docs:`, and `test:` prefixes are useful but not required by tooling.

Update `CHANGELOG.md` for user-visible behavior changes. Document migration steps when an existing project must change. Do not add promises about release schedules, response SLAs, or CI checks unless the corresponding process actually exists.

## License

Contributions use the repository's [Apache License 2.0](LICENSE). Be respectful of other contributors and preserve their work when editing the shared workspace.
