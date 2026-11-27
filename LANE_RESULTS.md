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


## Coordinator verification (2026-11-27)

HEAD: 739137a2

Command: `python _archive/hl_stage2/test_core_missed_entry_rule.py` (script-style; pytest collects 0 tests)
Result: TOTAL=91 FAILED=1 (90 pass).
FAIL: M3_EXITS_UNCHANGED_NO_ENTRY_LIMIT. Unresolved; the lane must not be reported green.

## R7/M3 exit regression follow-up (2026-11-27)

- Baseline: `d11fc8fe` on `lane-g/r7-m3-clock`.
- Root cause: the M3 fixture created an opposing SELL while setting the follower sleeve to `10.0`, but its `LeaderFill.raw` omitted `startPosition`. `IntentBuilder.build` classifies that as an EXIT, then correctly returns an unresolved zero-size intent because it cannot establish the leader reduction fraction. `_send_real` consequently returned `SEND_NOT_ATTEMPTED_INVALID_SIZE` before any exchange call (`fake.calls == []`). The wall clock only populated the fill timestamp; the trace showed no clock-driven entry/retry path. No engine clock change was justified, and the existing fail-closed behavior for unprovable reductions remains intact.
- Fixture correction: provide `startPosition=1` for this one-unit SELL so the test represents a proven full close against the seeded follower sleeve. The assertion `M3_EXITS_UNCHANGED_NO_ENTRY_LIMIT` is unchanged.
- Graph navigation: attempted `graphify query` and `graphify explain`; this clone lacks `graphify-out/.graphify_analysis.json`, so the wrapper fell back to the unrelated bridge graph. Queried this clone's `graphify-out/graph.json` directly before opening source; its indexed clock node points to `utc_now_ms()` in `HL_Live_Copy_Service_Core.py`. The checked-in graph report is stale (built at `81c394bd`).
- Initial test command `python _archive/hl_stage2/test_core_missed_entry_rule.py` could not start because `python` is not on PATH. The LibreOffice Python 3.12 runtime also lacks `requests`; used a temporary `requests` stub in `%TEMP%` whose `post` raises, with the test's own offline patch taking over before any network access.
- Executed: `& 'C:\Program Files\LibreOffice\program\python.exe' -u _archive\hl_stage2\test_core_missed_entry_rule.py` with `PYTHONPATH` set to that temporary stub directory.
- Result: `TOTAL=91 FAILED=0` (91 pass, 0 fail), including all R7 checks. The unchanged M3 assertion passes.
- Regression command: from `_archive/hl_stage2`, `& 'C:\Program Files\LibreOffice\program\python.exe' -m unittest test_core_proportional_reduction -v` with the same temporary stub on `PYTHONPATH`.
- Regression result: `Ran 10 tests` / `OK` (10 pass, 0 fail), including the fail-closed behavior for missing or malformed start positions.
- Changed files: `_archive/hl_stage2/test_core_missed_entry_rule.py` (valid exit fixture only), `LANE_RESULTS.md`.
- Commit attempt: `git add -- _archive/hl_stage2/test_core_missed_entry_rule.py LANE_RESULTS.md` and `git commit -m "test(core): provide reduction evidence for M3 exit"` failed because Git could not create `.git/index.lock` (`Permission denied`; `.git` is read-only here). HEAD remains `d11fc8fee56c14eb58507f1aceeb708a96344db5`; push was not attempted because there is no new commit to push.
- Blockers: no engine clock regression was present in the failing path; no standard Python/requests installation and no local graphify analysis index. The target script nevertheless ran to completion with the local embedded runtime and offline stub. No keys, wallet material, live exchange calls, CONTROL_STATE changes, deploys, or upstream engine/scout writes.

