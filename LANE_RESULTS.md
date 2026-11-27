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

## Lane b-close-recovery (2026-11-27)

- Root cause: `_withdraw_standing_close()` returned `SEND_NOT_ATTEMPTED_STANDING_CLOSE_IN_PLACE` when cancelling a standing recovery close failed, short-circuiting the new EXIT/REDUCE close before close-to-target sizing. It now keeps the recovery order tracked, reserves its full same-side size against the new close, records the cancellation failure, and continues through the existing target-sizing path.
- Regression added first: `FAILED_RECOVERY_CANCEL_DOES_NOT_BLOCK_CLOSE` in `test_core_standing_close_guard.py`; it checks that failed cancellation leaves the recovery row tracked while the unreserved close remainder continues.
- RED command: `python test_core_standing_close_guard.py` — 0 passed, 0 failed; Python could not launch (`Access is denied`), so the expected RED failure could not be observed.
- Before/after proportional command: `python -m pytest -q -p no:cacheprovider test_core_proportional_reduction.py` — before: 0 run (same launch error); after: 0 run (same launch error). Prior coordinator verification above recorded 14 passed, 14 subtests on this test before this lane change.
- After command: `python test_core_standing_close_guard.py` — 0 passed, 0 failed (Python launch denied). `git diff --check` passed.
- Graph navigation commands: `graphify query "close recovery standing close"` and `graphify explain "_withdraw_standing_close"` — both blocked because the graphify wrapper could not find `python`. The checked-in graph data was queried as a fallback and points to an older archived service.
- Blocker: this environment has no runnable Python (`python` is denied; `py` reports no installed Python, and the available Hermes venv interpreter is denied). Runtime test results, including the proportional-reduction green check, remain unverified here. No service, deploy, merge, commit, push, or CONTROL_STATE gate/action change was performed.

