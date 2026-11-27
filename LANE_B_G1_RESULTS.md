# Lane B Gate 1 sizing/flip results

## Revision and scope

- Base revision: `cdea30d21743abd7094e6eda92f5346d6cd1f1a5` on `lane-b/g1-sizing-flip`.
- Task commit SHA(s): none. The workspace permits reading `.git` but rejected creation of `.git/index.lock` with `Permission denied`, so no commit could be created.
- Changed files:
  - `_archive/hl_stage2/HL_Live_Copy_Service_Core.py`
  - `_archive/hl_stage2/test_core_proportional_reduction.py`
  - `LANE_B_G1_RESULTS.md`
- Correction source read: PR #8 comment 7219806425, recording Ledger 1 as ACCEPT-WITH-CORRECTIONS. The implementation requirements followed here are the per-leader follower ledger, fixed $12 entry/add sizing, proportional reductions, close only on leader flat, split flips, one fixed intent for merged fills, fail-closed malformed position data, and independent same-coin opposing leaders.

## Change

`IntentBuilder.build()` now rejects a supplied `startPosition` that cannot be parsed as a finite number, including on an opening fill. It returns an `UNRESOLVED` zero-size intent before sizing or send eligibility can be granted. A missing `startPosition` remains allowed for opening fills; reductions without it already fail closed.

The existing code already routes production fills through `build_all()`, which splits a zero-crossing fill into a leader-flat reduction followed by a fresh fixed-size open. Existing regression tests cover proportional reductions, merged-fill sizing, and separate leader sleeves. No changes were made to those paths.

## Expected-failing regression

| Test | Expected on cdea30d2 | Reason |
|---|---|---|
| `test_malformed_start_position_blocks_an_open_too` | FAIL (inferred from source; not executed) | The old `build_all()` falls through to `build()` for a malformed start position. With a flat sleeve and an `Open Long` fill, old `build()` classifies it as an entry and can produce the configured fixed-size order instead of `UNRESOLVED`. |

## Test results and tally

Per the v2 instruction, no Python, pytest, uv, or other interpreter was executed. Therefore no before/after pass or failure counts are claimed.

| Test file | Before (`cdea30d2`) | After working-tree change |
|---|---|---|
| `_archive/hl_stage2/test_core_proportional_reduction.py` | Not run; the new regression is expected to fail as described above | Not run |
| `_archive/hl_stage2/test_core_proportional_sizing_regression.py` | Not run | Not run |
| `_archive/hl_stage2/test_core_shared_follower_leader_attribution.py` | Not run | Not run |
| Full suite, per-file results | Not run / unavailable | Not run by instruction |

The reported conflict between 8 and 13 nonzero test files cannot be reconciled from observed execution evidence in this turn. No matching tally record was found in the local Markdown, log, text, or JSON files or in the fetched PR #8 discussion. Without running the suite or obtaining the two original reports, choosing either count or explaining the difference would be speculation.

## Blockers

- Test execution is explicitly prohibited by the v2 addendum; the change is unverified at runtime.
- Local commits are blocked by `.git/index.lock` creation being denied. The working-tree edits are not committed.
- The v2 addendum says not to push, so no push was attempted. No restart, deploy, order, or mainnet action was performed.
