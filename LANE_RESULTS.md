# Lane G: Flake determinism

## Revision identifiers

- Branch: `lane-g/flake-determinism`
- Base SHA: `5e92b50e55e210b9bd853bf1277a2b1c853d6e60`
- Starting HEAD SHA: `5e92b50e55e210b9bd853bf1277a2b1c853d6e60`
- Final commit SHA: unavailable; Git could not write `.git/index.lock` (`Permission denied`). Changes remain uncommitted.

## Test findings and changes

1. `_archive/hl_stage2/test_core_missed_entry_rule.py`
   - Flaky assertion texts: `R7_KEY_STOP_HOLDS_LEADER_CURSOR_FOR_REPLAY` (`cur == before`) and `R7_HELD_CURSOR_DOES_NOT_GROW_THE_READ_WINDOW` (`len(starts_b) == 2 and starts_b[1] > starts_b[0] + 1000000`).
   - Root cause: `run_cycle` skips leader polling until its interval is due, while the test's live clock could advance between setting the cursor and entering the cycle. Depending on timing, the key-stop path might not run the asserted poll, or the repeated poll windows could be too close together.
   - Fix: keep the existing R7 test change: use one fixed clock sample for the key-stop cycle and reset `_last_leader_poll_ms` before each asserted poll cycle. Assertions are unchanged; the check now deterministically reaches the intended poll path and read-window growth.

2. `_archive/hl_stage2/test_g2_copy_correctness.py`
   - Flaky assertion texts: `durable order_intents.csv retains planner reduce_only (read back from disk)` and `durable live_fills.csv records the PLANNER follower side, not the leader fill side`.
   - Root cause: service intent IDs are `DRYRUN-{utc_now_ms()}-{len(processed_ids)+1}`. The test pinned `utc_now_ms()` to a constant, allowing IDs to repeat when the processed-fill count matched. The CSV readback then found an older row with the same ID, so the durable assertions read stale planner fields.
   - Fix: remove the test-wide clock override. The service's real millisecond clock and existing processed-count suffix keep generated IDs unique; no audit timestamp needed pinning for these assertions. Both assertions are unchanged.

## Changed files

- `_archive/hl_stage2/test_core_missed_entry_rule.py`
- `_archive/hl_stage2/test_g2_copy_correctness.py`
- `LANE_RESULTS.md`

## Verification and blockers

- No Python or other interpreter was run, per task constraint; test outcomes after this correction are therefore unverified. The user reported R7 at 6/6 before this correction and G2 at 3/3 failing after the constant-clock change; no post-correction run was made.
- `git diff --check` passed.
- Git staging/commit was attempted, but both failed because `.git/index.lock` could not be created (`Permission denied`). No push was attempted.
- No keys or live exchange calls were used. No upstream 8014/8012 files or `CONTROL_STATE.json` were changed.

