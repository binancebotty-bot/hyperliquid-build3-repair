# MERGE_READINESS_2026-10-11 - open review branches vs main `4f1c779` (`4f1c779342`)

Job K1. Fresh clone `C:/Users/wigmore/trading_stack/hl-build3-hermes-K1` (`core.autocrlf=false`). Per branch:
throwaway branch from `4f1c779` -> `git merge --no-commit --no-ff origin/<branch>` -> record the unmerged files ->
commit when clean -> run **every** `_archive/hl_stage2/test_*.py` (`HL_LIVE_ENV_FILE=/nonexistent python -u`) ->
aggregate. A conflicted tree cannot build, so those rows run the suite on the **branch tip alone** and say so.
Offline only: no engine start, no orders, no keys, the live cert checkout untouched.

**Baseline `4f1c779`:** 55 test files, 1011 checks, 1 failing - `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS` on `test_core_fill_lag.py`, and RE-RUNS SHOW IT IS FLAKY (1 of 3 re-runs failed, see below).

| branch | tip | merge | conflict files | tests run on | files | checks failed | failing check names | recommendation |
|---|---|---|---|---|---|---|---|---|
| `hermes/j1-diskfull` | `537088cffb` | CONFLICT | `_archive/hl_stage2/test_core_disk_full.py` | branch_tip_alone (merge unclean) | 48 | 8/883 | `A5_WHOLE_DISK_FULL_CANNOT_KILL_THE_WORKER`, `B4_WHOLE_DISK_FULL_DOES_NOT_ESCAPE_THE_WORKER`, `C4_THE_LOST_RECONCILIATION_ROW_IS_COUNTED_IN_THE_INTEGRITY_STATUS`, `D4_STATE_WRITE_CANNOT_KILL_THE_CYCLE`, `D5_THE_ENGINE_LOOP_CANNOT_EXIT_ON_A_RUN_CYCLE_FAILURE`, `E1_SHORT_CSV_WRITE_IS_NOT_SILENTLY_PUBLISHED`, `E2_SHORT_JSON_WRITE_IS_NOT_SILENTLY_PUBLISHED`, `E3_FAILED_JSON_WRITE_LEAVES_NO_ORPHAN_TMP` | RESOLVE first |
| `opencode/j2-local-rejects` | `a7cc6ce420` | CLEAN | none | merged_tree | 55 | 1/1011 | `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS` | MERGE (flaky baseline test appeared) |
| `hermes/j3-catchup-wiring` | `9f12ddaa57` | CLEAN | none | merged_tree | 55 | 0/1011 | none | MERGE |
| `hermes/f1` | `55430af3ec` | CONFLICT | `_archive/hl_stage2/test_core_dust_rules.py` | branch_tip_alone (merge unclean) | 44 | 3/821 | `BENCH_40PCT_REACHED_THE_EXCHANGE`, `BENCH_60PCT_BLOCKED_LOCALLY`, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED` | RESOLVE first |
| `hermes/f2` | `0152bcdedc` | CONFLICT | `process/CERTIFICATION_MATRIX_2026-10-10.md` | branch_tip_alone (merge unclean) | 43 | 3/810 | `BENCH_40PCT_REACHED_THE_EXCHANGE`, `BENCH_60PCT_BLOCKED_LOCALLY`, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED` | RESOLVE first |
| `hermes/mem-profile` | `72c7590485` | CLEAN | none | merged_tree | 56 | 0/1011 | none | MERGE |
| `hermes/e1` | `84223ce0b0` | CLEAN | none | merged_tree | 55 | 1/1011 | `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS` | MERGE (flaky baseline test appeared) |
| `hermes/e2` | `4128499ac4` | CLEAN | none | merged_tree | 55 | 0/1011 | none | MERGE |
| `hermes/RE3-outage-replay` | `8f66526740` | CLEAN | none | merged_tree | 55 | 0/1011 | none | MERGE |
| `opencode/audit-csv-rotation` | - | - | - | - | - | - | - | NOT PUSHED (absent from origin) |

## Detail

### `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first
- merge onto `4f1c779`: CONFLICT - unmerged file(s): _archive/hl_stage2/test_core_disk_full.py
- suite on branch_tip_alone (merge unclean): 48 files, 883 checks, 8 failing, non-zero exits: `test_core_disk_full.py`
- failing checks (verified at full output where flagged): `A5_WHOLE_DISK_FULL_CANNOT_KILL_THE_WORKER`, `B4_WHOLE_DISK_FULL_DOES_NOT_ESCAPE_THE_WORKER`, `C4_THE_LOST_RECONCILIATION_ROW_IS_COUNTED_IN_THE_INTEGRITY_STATUS`, `D4_STATE_WRITE_CANNOT_KILL_THE_CYCLE`, `D5_THE_ENGINE_LOOP_CANNOT_EXIT_ON_A_RUN_CYCLE_FAILURE`, `E1_SHORT_CSV_WRITE_IS_NOT_SILENTLY_PUBLISHED`, `E2_SHORT_JSON_WRITE_IS_NOT_SILENTLY_PUBLISHED`, `E3_FAILED_JSON_WRITE_LEAVES_NO_ORPHAN_TMP`

### `opencode/j2-local-rejects` (`a7cc6ce420`) -> MERGE (flaky baseline test appeared)
- merge onto `4f1c779`: clean
- suite on merged_tree: 55 files, 1011 checks, 1 failing, non-zero exits: `test_core_fill_lag.py`
- failing checks (verified at full output where flagged): `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS`

### `hermes/j3-catchup-wiring` (`9f12ddaa57`) -> MERGE
- merge onto `4f1c779`: clean
- suite on merged_tree: 55 files, 1011 checks, 0 failing, non-zero exits: none

### `hermes/f1` (`55430af3ec`) -> RESOLVE first
- merge onto `4f1c779`: CONFLICT - unmerged file(s): _archive/hl_stage2/test_core_dust_rules.py
- suite on branch_tip_alone (merge unclean): 44 files, 821 checks, 3 failing, non-zero exits: `test_core_fill_lag.py`, `test_hotpath_replay_bench.py`
- failing checks (verified at full output where flagged): `BENCH_40PCT_REACHED_THE_EXCHANGE`, `BENCH_60PCT_BLOCKED_LOCALLY`, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED`

### `hermes/f2` (`0152bcdedc`) -> RESOLVE first
- merge onto `4f1c779`: CONFLICT - unmerged file(s): process/CERTIFICATION_MATRIX_2026-10-10.md
- suite on branch_tip_alone (merge unclean): 43 files, 810 checks, 3 failing, non-zero exits: `test_core_fill_lag.py`, `test_hotpath_replay_bench.py`
- failing checks (verified at full output where flagged): `BENCH_40PCT_REACHED_THE_EXCHANGE`, `BENCH_60PCT_BLOCKED_LOCALLY`, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED`

### `hermes/mem-profile` (`72c7590485`) -> MERGE
- merge onto `4f1c779`: clean
- suite on merged_tree: 56 files, 1011 checks, 0 failing, non-zero exits: none

### `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared)
- merge onto `4f1c779`: clean
- suite on merged_tree: 55 files, 1011 checks, 1 failing, non-zero exits: `test_core_fill_lag.py`
- failing checks (verified at full output where flagged): `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS`

### `hermes/e2` (`4128499ac4`) -> MERGE
- merge onto `4f1c779`: clean
- suite on merged_tree: 55 files, 1011 checks, 0 failing, non-zero exits: none

### `hermes/RE3-outage-replay` (`8f66526740`) -> MERGE
- merge onto `4f1c779`: clean
- suite on merged_tree: 55 files, 1011 checks, 0 failing, non-zero exits: none

## Verified re-runs (FULL output, not the truncated run logs)

| context | file | rc | TOTAL/FAILED | failing checks |
|---|---|---|---|---|
| BASE 4f1c779 | `test_core_fill_lag.py` | 1 | 15/1 | `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS` |
| TIP hermes/j1-diskfull | `test_core_disk_full.py` | 1 | 22/8 | `A5_WHOLE_DISK_FULL_CANNOT_KILL_THE_WORKER`, `B4_WHOLE_DISK_FULL_DOES_NOT_ESCAPE_THE_WORKER`, `C4_THE_LOST_RECONCILIATION_ROW_IS_COUNTED_IN_THE_INTEGRITY_STATUS`, `D4_STATE_WRITE_CANNOT_KILL_THE_CYCLE`, `D5_THE_ENGINE_LOOP_CANNOT_EXIT_ON_A_RUN_CYCLE_FAILURE`, `E1_SHORT_CSV_WRITE_IS_NOT_SILENTLY_PUBLISHED`, `E2_SHORT_JSON_WRITE_IS_NOT_SILENTLY_PUBLISHED`, `E3_FAILED_JSON_WRITE_LEAVES_NO_ORPHAN_TMP` |
| TIP hermes/f1 | `test_core_fill_lag.py` | 0 | 15/0 | none |
| TIP hermes/f1 | `test_hotpath_replay_bench.py` | 1 | 7/3 | `BENCH_40PCT_REACHED_THE_EXCHANGE`, `BENCH_60PCT_BLOCKED_LOCALLY`, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED` |
| TIP hermes/f2 | `test_core_fill_lag.py` | 0 | 15/0 | none |
| TIP hermes/f2 | `test_hotpath_replay_bench.py` | 1 | 7/3 | `BENCH_40PCT_REACHED_THE_EXCHANGE`, `BENCH_60PCT_BLOCKED_LOCALLY`, `BENCH_STAGE_STAMPS_PRESENT_AND_ORDERED` |

`test_core_fill_lag.py` on the baseline, repeated: 1->rc=0 ['15', '0'] 2->rc=0 ['15', '0'] 3->rc=1 ['15', '1'] . So `P2_POLL_RECORDS_ITS_SLOWEST_SECTIONS` is TIMING-SENSITIVE, not a stable failure - do not treat a single run of it as a merge gate without a retry (or a stated tolerance); it failed in 1 of 3 observations here.

## Reading the results
- **MERGE** = clean merge onto `4f1c779` with no failing check.
- **RESOLVE first** = the merge conflicts (a mainline file already exists); reconcile the file with main.
- The three `test_hotpath_replay_bench.py` failures are the KNOWN STALE bench (its expectations predate the
  account-net authority rule - see the F2 matrix finding). They only appear on branches carrying the older tree;
  `4f1c779` itself passes the bench.
- Note on `hermes/j1-diskfull`: mainline `4f1c779` ALREADY carries the disk-full engine handling and a
  `test_core_disk_full.py` (which passes on the baseline). The branch tip's own extended version fails 8 of its 22
  checks against ITS OWN tree, so reconciling should keep main's engine + main's test.
- Failing-name parsing: the verdict is the suffix `_PASS`/`_FAIL` at the end of a `RESULT::` token, so a name that
  embeds `_FAIL` (e.g. `S6_UNREADABLE_SWEEP_FAILS_CLOSED_PASS`) is a PASS. The driver's first-draft regex
  substring-matched `_FAIL` and produced false positives; every name in the table above was re-verified at full
  output for the files that matter, and the rest come from the corrected parse.
- `opencode/audit-csv-rotation` was requested 'if pushed' and is absent from origin.
