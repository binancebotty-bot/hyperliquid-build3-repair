# Lane B results

- Branch: `lane-b/g1-sizing-flip`
- Base SHA: `5e92b50e55e210b9bd853bf1277a2b1c853d6e60`
- Current HEAD SHA: `5e92b50e55e210b9bd853bf1277a2b1c853d6e60` (changes are uncommitted)

## Changed files

- `_archive/hl_stage2/HL_Live_Copy_Service_Core.py`
- `_archive/hl_stage2/test_core_proportional_reduction.py`
- `LANE_RESULTS.md`

## Expected failures on the base SHA

In `test_every_malformed_start_position_shape_opens_fail_closed`, the subtests for `10**400`, `True`, and `False` are expected to fail on the base SHA. `10**400` raises `OverflowError` in `build_all`; booleans are accepted as `1.0` and `0.0`. The other malformed shapes are caught or become non-finite on the base. The missing-startPosition test is expected to remain allowed.

Tests were not run, per instruction. `git diff --check` completed without reporting whitespace errors.

## Blockers

- Commit creation was attempted but the sandbox denied writes under `.git`: `fatal: Unable to create '.git/index.lock': Permission denied`. The resulting commit SHA is unavailable. No push was attempted.
- No upstream `8014`/`8012` files or `CONTROL_STATE.json` were changed.
