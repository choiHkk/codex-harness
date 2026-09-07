## Change

<!-- Describe the concrete problem and resulting behavior. Mention migration steps when needed. -->

## Verification

<!-- List commands actually run and outcomes. Separate static checks, scripted functional tests, and live Codex observations. Explain material checks that were not run. -->

- [ ] `python3 scripts/validate.py --project .`
- [ ] `python3 -m unittest discover -s tests -v` (when relevant)
- [ ] Live Codex smoke test (when relevant; record client/version and observed agent behavior)

## Compatibility

<!-- Note affected agent roles, file ownership boundaries, installer preservation behavior, and documentation changes. Do not claim runtime verification based only on parsing. -->

- [ ] User-visible changes documented in `CHANGELOG.md` and relevant usage guides
