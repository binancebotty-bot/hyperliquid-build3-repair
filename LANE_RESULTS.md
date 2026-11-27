# Lane results

- Branch: `lane-b/g1-sizing-flip`
- Verified base: `7abee190d614a52fa73b7bbdb5728e510b608c99`
- Scope: EXIT `startPosition=True` with a valid partial fill (`size=0.5`) now fails closed through both `IntentBuilder.build()` and `build_all()`.
- Implementation: EXIT parsing now uses the existing strict `_parse_leader_start()` helper, which rejects booleans and overflow values.
- Regression: `test_exit_boolean_start_position_with_partial_fill_fails_closed` exercises both entry points. The test failed on the base with `EXIT_ALLOWED` in both cases and passed after the change.
- Preserved checks: the existing `10**400` EXIT case and malformed `True`/`False` opening cases remain covered by the targeted test file.
- Verification: `_archive/hl_stage2/test_core_proportional_reduction.py` — 14 tests passed after the fix. Exact runtime probe output is recorded in `LANE_B_G1_RESULTS.md`.
- Delivery: implementation and result-document changes are committed and pushed to `origin/lane-b/g1-sizing-flip`; use `git rev-parse HEAD` for the final documentation commit SHA. No merge or deployment was performed.
- Review: independent review is pending; no self-review is represented as an independent verdict.

## Coordinator verification (2026-11-27)

HEAD: 43dd5877

Command: `python -m pytest -q -p no:cacheprovider _archive/hl_stage2/test_core_proportional_reduction.py`
Result: 14 passed, 14 subtests passed (EXIT boolean startPosition regression included).

