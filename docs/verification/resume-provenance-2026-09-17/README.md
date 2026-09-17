# Repeated-resume provenance verification

Tested on 2026-09-17 against baseline `79b82281d305c89181fbb216499d5f1e962c14ed`.

## Observed defect and correction

A task wrote its accepted output under run `current`. An unchanged resume reused
the task in run `reused`. After its declared input changed, another resume made
the task pending in run `rerun`, but assigned the original `current` output path.
Following that assignment overwrote the original output. Completion validation
still returned zero. No manual edits to stored plans or results were needed.

The correction resolves owned paths against the entire preserved run ancestry.
Stale tasks receive output paths in the new run, including directory, glob and
in-project symlink aliases. Ordinary project output paths remain unchanged.
Ownership in unrelated run records is rejected before the new run is created.
An unchanged task can still reuse its accepted result.

| Observation from the same reproducer | Baseline | Corrected |
| --- | --- | --- |
| First unchanged resume reused task | Yes | Yes |
| Input change made task pending | Yes | Yes |
| Assigned output run | `current` | `rerun` |
| Original accepted bytes preserved | No | Yes |
| Final completion exit status | 0 | 0 |

The final row is significant: completion success alone did not establish that
earlier accepted output remained intact. The reproducer checks the actual bytes.

## Reproduce

Python 3.11+ and Git are sufficient. No API key or third-party Python dependency
is needed. Run these commands from the checkout root. The reproducer creates
temporary fixtures and does not touch real projects or launch native agents.
`fixture-native-id` and lifecycle observations are deliberately simulated.

```bash
python3 scripts/reproduce_resume.py --repo . --output resume-after.json
python3 -m unittest discover -s tests -p test_resume_adversarial.py -v
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --project .
git diff --check
```

For an independent baseline comparison, choose a new worktree path:

```bash
git worktree add --detach ../codex-harness-audit-baseline 79b82281d305c89181fbb216499d5f1e962c14ed
python3 scripts/reproduce_resume.py --repo ../codex-harness-audit-baseline --output resume-before.json
```

Compare `original_output_unchanged`: baseline `false`, corrected `true`. The
reproducer is an observation tool and returns zero when it completes even if
preservation is false; use the regression tests for a failing CI assertion.

## Executed checks and raw evidence

- Existing baseline suite: **94/94 passed** — [raw log](baseline-tests.log).
- New core regression before correction: **failed as expected** — [raw log](before-resume.log).
- Identical public-CLI reproducer: [baseline trace](before-impact.json) and [corrected trace](after-impact.json). Each records all 10 commands, exit statuses and output.
- Corrected suite: **97/97 passed**, including three new tests. One test uses four subcases for directories, globs, aliases and ordinary project outputs — [raw log](fixed-tests.log).
- Structural validation: **passed** — [raw log](structure-validation.log). This is static validation, not a native runtime test.
- Independent review: [review record](review.md). Re-run its additional two conditions with `python3 experiments/resume-audit/additional_resume_review.py --repo .`.

The byte-preservation regression covers input changes, repeated unchanged reuse,
changed acceptance criteria, and preserved ancestor records. A negative test
checks that unrelated-run output ownership is rejected without creating the new run.

## Two explicitly unresolved boundary checks

The helpers maintain run-local ledgers. Additional checks asked for stronger,
cross-run guarantees that this correction does not implement:

1. A separate run can register a writer whose ownership overlaps a running
   writer recorded in another run.
2. After resume, an idle but unclosed ID in the previous run is not counted in
   the new run's configured capacity check.

Both stronger assertions **still fail**. They are preserved separately from the
regression suite, not counted among the 97 passes:

```bash
python3 experiments/resume-audit/cross_run_limitations.py -v
```

Expected current outcome: two failures, exit 1. See the
[original failure log](cross_run_limitations.log). These fixtures demonstrate
local bookkeeping behavior, not actual simultaneous native agents. Globally
counting every stored agent would also be incorrect without a native session
identity and authoritative lifecycle observations. The parent must continue
coordinating actual sessions and writers across runs.

## Limits and interpretation

The effect demonstrated here is preservation of accepted ancestor-run bytes in
the reproduced workflow. It is not evidence of improved model reasoning,
production task success, cost savings, or a complete security boundary.

The ancestry records must remain available; missing or invalid ancestry fails
before creating a new run. Undeclared dependencies, fabricated evidence,
concurrent external filesystem changes, hard-link identity, and arbitrary
agent writes are not solved. The test host was Linux with Python 3.12.14;
Windows, macOS and a live Codex CLI run were not tested in this audit.

Existing approaches already address checkpoints and reuse: see
[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers),
[Bazel remote caching](https://bazel.build/remote/caching), and
[Anthropic's long-running agent harness discussion](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
The contribution is a reproduced, corrected gap in this project's existing
behavior, not a new general orchestration method.
