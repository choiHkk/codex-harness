# Verification record

## Issue #1 compatibility recheck — 2026-09-14

On macOS, installed **codex-cli 0.154.0** help still describes `--ephemeral`
as disabling session-file persistence. A bounded read-only probe ran with
`codex exec --ephemeral --json --sandbox read-only -C <checkout>` and inherited
model/reasoning settings. It requested one standby `harness_explorer`, with
no product reads, writes, or recursive delegation and no retry on spawn failure.

The CLI exited **0** and reported child ID `/root/compatibility_probe` and its
`READY` response. The captured JSONL contains a completed wait event and that
final report, but no spawn metadata independently confirming the dispatch.
This is a **reported success**, not proof of a fixed CLI version, native
parallelism, or a complete Harness workflow. The earlier 0.153.4 failure below
remains a separate observation. Use the actual first-spawn check described in
[compatibility](compatibility.md) for each session.

The same installed CLI also completed the updated ordinary-session regression:

```bash
python3 scripts/live_smoke.py run \
  --target _workspace/live-tests/issue-1-20260914 \
  --baseline-file /tmp/codex-harness-issue-1-20260914-baseline.json --timeout 900
```

The runner exited **0** using its caller-held protected-file baseline. It
verified rejection of the deliberately blocked first run, preservation of
that run and alpha's output, reuse of alpha, rerun of beta and QA, and both
final tests passing. Native tool metadata separately confirmed that alpha's
child ID returned before beta was spawned, with exactly two `harness_worker`
children and one `harness_qa`; the first child was reused without an extra
probe. The local verifier still labels transport records as reported; this
recheck does not independently audit all message contents or prove behavior
under the original missing-thread failure. Local evidence is retained under
the ignored fixture's `_workspace/` and `.harness/runs/issue-1-inputs/`.

For this change, independent offline QA passed **94 tests**, root and example
structural validation, `git diff --check`, and the changed documentation's
local links, anchors, and shell examples. These checks remain separate from
native execution evidence.

## 2026-09-07 baseline

Checked **2026-09-07 (Asia/Seoul)** against upstream revision
`cceac68ea1d0ad198ef4b7b906cd238375836387`, using Python **3.13.7** and
**codex-cli 0.153.4** on macOS.

## Automated checks

- `python3 -m unittest discover -s tests -v`: **94 tests passed**.
- `python3 scripts/validate.py --project .`: **5 agents, 1 skill, 0 errors**.
- `python3 scripts/validate.py --project examples/service-migration`:
  **2 agents, 1 skill, 0 errors**; the example task graph also passed validation.
- The local skill-creator validator accepted the factory and example skills.
- The local plugin-creator validator accepted `.codex-plugin/plugin.json` and
  the standard `skills/` payload.
- `git diff --check`: passed.

Tests exercise installation preservation, idempotency, dry runs, conflicts,
symlink destinations, rollback, logical role-name collisions, Unicode TOML
round trips, installed helper portability, invalid skill metadata, missing
references, task dependency cycles and simultaneous write ownership. Runtime
regressions additionally cover required check evidence, result/artifact/input
freshness, context refresh, immutable prior runs, contract updates through a new
plan template, retries, native lifecycle observations, capacity, and stop
acknowledgments. Communication tests include 24 concurrent writer processes,
Unicode and multiline payloads, correlated replies, corrupt-tail preservation,
and separate exports. Live-test evidence checks reject changed checker code and
unrelated delivery records; those offline tests do not simulate native agents.

GitHub Actions passed on Ubuntu with **Python 3.11 and 3.13** for the first
published migration commit `53660b1`: [CI run](https://github.com/revfactory/codex-harness/actions/runs/34080033451).
Both jobs ran the automated suite, native artifact validation, and whitespace
checks. The authenticated live Codex regression remains outside CI.

## Live write, blocker, communication, and resume regression

Ran the opt-in fixture with **codex-cli 0.153.4** in an ordinary
`workspace-write` session:

```bash
python3 scripts/live_smoke.py run \
  --target _workspace/live-tests/native-20260907
```

Parent thread: `01a0799c-0bc4-7261-8dae-c1bb7e028575`.

| Observation | Result |
| --- | --- |
| Native workers | Actual `harness_worker` spawns returned `/root/alpha_worker` and `/root/beta_worker` |
| First output | Alpha wrote `alpha.py` and passed its acceptance test |
| Deliberate blocker | Beta observed `UNRESOLVED` in its spec versus expected `BETA`, captured the failing test, and returned blocked |
| Peer exchange | Alpha asked about the function contract and beta's blocker; the parent recorded the correlated answer and reported native send/receipt observations |
| Failure gate | First-run completion exited **1**, identifying blocked beta and pending QA |
| Partial resume | After the controlled spec correction, alpha was reused with **0 new attempts**; the same beta worker read a new packet and wrote/tested `beta.py` |
| Independent QA | Actual `harness_qa` spawn returned `/root/verify_qa`; both tests passed |
| Final completion | Resumed run passed with **0 completion errors** |
| Preservation | Previous run records and the reused alpha file retained their checkpoint hashes |
| Lifecycle | Final native observations showed completed child turns; recorded as idle, with no closure claim |
| Communication records | **13 first-run + 13 resumed-run events**, including lifecycle entries; JSONL and Markdown saved separately |

The primary session independently reran both product tests and the stronger
evidence verifier against an external baseline covering **30 protected fixture
files**. The baseline was captured during the live run and checked afterward;
future `run` invocations capture their full baseline before launching Codex.
Sanitized native collaboration tool metadata was also checked against all three
reported role IDs and final lifecycle observations. Message bodies and model
analysis are not copied into that metadata extract.

Local evidence lives under
`_workspace/live-tests/native-20260907/_workspace/`:

- `verification.json`: independent state, preservation, correlation, and test checks.
- `native-tool-metadata.json`: inspected native role dispatch and lifecycle metadata.
- `native-report.json`, `native-events.jsonl`, `native-result.md`: session observations and CLI output.
- `communications/first.jsonl`, `communications/resumed.jsonl`, and corresponding `.md` exports.
- `checkpoint.json`: the rejected first completion and previous-run hashes.

These artifacts are local and Git-ignored. The standalone verifier labels native
IDs and message delivery as **reported**; it does not authenticate native
transport or measure execution overlap. The separate metadata review verifies
role dispatch and final lifecycle observations. This run is a small functional
regression, not a throughput benchmark or a guarantee for every Codex client.
The later `resume --plan-file` option and additional boundary guards were covered
by the offline CLI tests; this live run exercised input-file changes with the
original task graph.

Reproduce with a new disposable target. An authenticated local Codex CLI is
required; the live command is deliberately outside unattended CI.

## Earlier read-only native subagent smoke

Ran `codex exec --strict-config --json --sandbox read-only` from the final
checkout with a bounded prompt: start `harness_explorer` and `harness_reviewer`
before waiting, assign each one independent file to read, collect their actual
results, and make no project edits or recursive delegations.

Final parent thread: `01a0781b-3657-7811-8ba0-a3ac06a8f0d7`.

| Observation | Result |
| --- | --- |
| Skill discovery | Runtime listed `codex-harness:harness` |
| Explorer | `/root/smoke_explorer` read `.codex/config.toml` and returned concurrency **3** |
| Reviewer | `/root/smoke_reviewer` read the factory skill and returned all **six** architecture patterns |
| Scheduling | Both custom subagents started before the first wait; both returned results |
| Role substitution | None; the requested custom roles were used |
| Project mutations | None during this read-only smoke |

This confirms custom-role discovery and a small parallel read workflow on the
tested local CLI. It does not benchmark throughput or certify every client,
write sandbox, domain workflow, or three-worker workload. The
[service migration example](../examples/service-migration/README.md) is a
validated starter template, not an already migrated application.

An earlier `--ephemeral` probe discovered the roles but could not spawn them:
the runtime returned `collab spawn failed: no thread with id`. The ordinary
session above passed. Use an ordinary session for the documented live smoke;
this observation does not establish the behavior of other CLI versions.

For local project invocation use `$harness`; when loaded as the plugin, the
skill picker can display the namespaced `codex-harness:harness` name.
