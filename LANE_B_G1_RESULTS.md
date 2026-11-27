# Lane B Gate 1 sizing/flip results

## Revision and scope

- Branch: `lane-b/g1-sizing-flip`
- Base: `7abee190d614a52fa73b7bbdb5728e510b608c99`
- Scope: reject malformed boolean EXIT `startPosition` consistently through `build()` and `build_all()` when fill size is `0.5`; no merge, deployment, or unrelated lane edits.
- Implementation: EXIT parsing now calls the shared `_parse_leader_start()` helper, preserving its strict boolean and overflow handling.

## TDD and verification

Regression `test_exit_boolean_start_position_with_partial_fill_fails_closed` was added before the production edit. On the base it failed at the `UNRESOLVED` assertion for both `build_all=False` and `build_all=True`; observed decision was `EXIT_ALLOWED`. After the implementation change:

```text
$ cd C:/Users/wigmore/lane-b-g1-reviewfix/_archive/hl_stage2 && python test_core_proportional_reduction.py
Ran 14 tests in 1.056s
OK
TOTAL=14 FAILED=0
exit code: 0
```

The pre-fix run returned exit code 1 (`Ran 14 tests`, with 2 failing subtests, both `EXIT_ALLOWED != UNRESOLVED`). The existing test for `10**400` EXIT input remains and passed for both entry points.

Exact direct probes after the fix:

```text
exit-bool-build: decision=UNRESOLVED copy_size=0.0 reduce_only=False
exit-bool-build_all: decision=UNRESOLVED copy_size=0.0 reduce_only=False
exit-huge-build: decision=UNRESOLVED copy_size=0.0 reduce_only=False
exit-huge-build_all: decision=UNRESOLVED copy_size=0.0 reduce_only=False
open-True: decision=UNRESOLVED copy_size=0.0 reduce_only=False
open-False: decision=UNRESOLVED copy_size=0.0 reduce_only=False
probe exit code: 0
```

The opening True/False probe used a flat follower sleeve and an `Open Long` fill; malformed supplied start positions remain fail-closed. Missing `startPosition` for opening fills remains covered as allowed by the existing test.

## Delivery and review

- `LANE_RESULTS.md` and this file replace stale uncommitted-SHA / tests-not-run claims with results from actual execution.
- Implementation and result documents are committed and pushed to `origin/lane-b/g1-sizing-flip`; obtain the final document commit with `git rev-parse HEAD`.
- Independent review is pending. No self-review is represented as an independent verdict.
- No merge, deploy, restart, order, or unrelated lane edit was performed.
