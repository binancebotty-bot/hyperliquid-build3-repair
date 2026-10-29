# BASE RED TRIAGE — CC-1 P11 chunk A

**Measured by the coordinator**, not by a delegated worker. Chunk A was dispatched twice and both
attempts completed the analysis and then returned a corrupted summary with no commit; the numbers here
are from my own direct runs against a clean worktree at `a1acc28`, `C:/Users/wigmore/tmp/p11_basered`.

Interpreter: `C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe`, each file run
directly from `_archive/hl_stage2/`.

## Why this document exists

Three different "how many tests fail" numbers are in circulation for the same commit. They are all
defensible and none of them is the whole truth:

| method | files | failures | what it actually measures |
|---|---|---|---|
| direct per-file run, parse `TOTAL=n FAILED=m` | 167 | **14 files red** | tests that ran and reported failures |
| full-suite runner `fullreg.py -j 6` | 124 | **19** | whatever the runner's own file filter admits |
| enumerate by **exit code** (`!= 0`) | 167 | **24** | anything that exits non-zero, including import crashes and hangs |

The gap between 14 and 24 is the interesting one: **10 files exit non-zero without ever printing a
`TOTAL=` line.** A test that dies on import, or that silently runs nothing, is indistinguishable from a
passing test to anyone reading a summary. Chunk B exists to classify those.

## The 14 files that report failures

Counts and failing case names are literal from the run.

| file | total/failed | failing cases |
|---|---|---|
| `test_core_append_truncate.py` | 7 / 5 | APPEND_FAILURE_RETURNS_FALSE; APPEND_FAILURE_LEAVES_NO_HALF_ROW; APPEND_FAILURE_SPILLS_ROW; NEXT_APPEND_IS_A_CLEAN_ROW; SPILLED_ROW_REPLAYED |
| `test_core_audit_reduce_only_matches_wire.py` | 8 / 8 | REDUCING; REDUCING_SEND_AUDIT_EQUALS_WIRE; INCREASING; INCREASING_SEND_AUDIT_EQUALS_WIRE; BOUNDARY; PURE_REDUCE_BOUNDARY_AUDIT_EQUALS_WIRE; TRIMMED; TRIMMED_CLOSE_AUDIT_EQUALS_WIRE |
| `test_core_disk_full.py` | 29 / 1 | B3_FINAL_ROW_WRITE_FAILURE_STILL_SENDS_THE_ORDER_ONCE_AND_KEEPS_IT_NAMED |
| `test_core_engine_gaps.py` | 24 / 2 | O2_EXIT_RECOVERY_GOES_THROUGH_THE_ONE_SITE; W2_ELEVEN_ACTIVE_WALLETS_REFUSED_AT_START |
| `test_core_fill_lag.py` | 15 / 3 | D1_FILL_OWNED_WHILE_THE_MAIN_CYCLE_IS_STUCK; S1_CYCLE_STATE_WRITE_KEEPS_COPY_CURSOR_AND_LAG_RECORD; P1_HOT_POLL_LEAVES_THE_RUNTIME_STATE_ALONE |
| `test_core_network_and_global_controls.py` | 71 / 7 | G12..MID_UNITS_KEPT; G13_CLOSE_WITHIN_DIFF_SENT_REDUCE_ONLY; G13_ZERO_CLOSE_DIFF_IS_OFF; R3_EXIT_PRICED_FROM_OWN_POSITION_WHEN_NO_MID; F1_SAME_NETWORK_ENTRY_PRICED_FROM_FRESH_MID_NOT_LEADER_PRICE; F1_PRICE_MOVED_TOO_FAR_IS_NOT_CHASED; F4_SAME_NETWORK_EXIT_UNCHANGED_LEADER_PRICE |
| `test_core_run3_fixes.py` | 61 / 9 | S2_* (4 late-entry / tolerance cases); N9_REDUCE_ONLY_REJECT_RESENT_AFTER_CATCH_UP; N9_NO_CATCH_UP_NO_BLIND_RESEND; G1_ORDER_CALL_ITSELF_REFUSES_UNCONFIRMED_MAINNET; G3_STALE_SNAPSHOT_REFRESHED_NOT_BLOCKED; G3_SIGN_CONFLICT_FROM_LAG_WAITED_FOR |
| `test_core_run4_fixes.py` | 54 / 10 | R1_RECOVERY_ORDER_WRITTEN_TO_SEND_ATTEMPTS...; P7_NO_STANDING_CLOSE_PLACED_AFTER_SENDING_IS_SWITCHED_OFF; C5_OPEN_SIZE_READ_FROM_THE_EXCHANGE...; C5_UNREADABLE_OPEN_ORDERS_KEEPS_THE_FULL_SIZE; O1_* (5 resting-entry cases) |
| `test_core_rw12_mode_at_send.py` | 13 / 1 | M6_UNREADABLE_MODE_FAILS_OPEN_LOUDLY |
| `test_core_trace_stamps.py` | 7 / 2 | (case names not machine-parseable from this file's output format) |
| `test_live_screen_truth.py` | 18 / 1 | L2_SUMMARY_HAS_WHOLE_ACCOUNT_VALUE |
| `test_readiness1_ambiguous_timeout_no_blind_resend.py` | 21 / 19 | B1..B21 ambiguous-timeout family (19 of 21 fail) |
| `test_screen_run4.py` | 86 / 9 | S1_ONE_LABEL_ON_SCREEN; S11_* (5 tally cases); S12_BANNER_FACTS; R6_TALLY_CLEAN_IS_NOT_PARTIAL |
| `test_t1a_cloid_pending_row.py` | 14 / 6 | A7_FILLED_IOC_OK; A8_CLOID_ON_THE_PHYSICAL_CALL; A9_ONE_PENDING_ROW_BEFORE_REPLY; A10_FINAL_ROW_APPENDED_SAME_ATTEMPT_ID; A11_CRASH_LEAVES_ONE_PENDING_ROW_WITH_CLOID; A13_PENDING_WRITE_FAILURE_SENDS_NOTHING |

## One classification I can make with confidence

`test_core_rw12_mode_at_send.py` — **M6_UNREADABLE_MODE_FAILS_OPEN_LOUDLY = REAL_DEFECT.**
Production `_send_time_wallet_mode_block` fails OPEN on an unreadable wallet mode for all lifecycles.
The engine can therefore send a close when it cannot read the mode that forbids sending. This is the
only red in the set where the engine's own behaviour is contradicted by a governance rule rather than
by an older expectation, and it is the one I would fix first.

## Shape signal that needs acting on

Two files fail almost entirely — `test_readiness1_ambiguous_timeout_no_blind_resend.py` (19 of 21) and
`test_core_audit_reduce_only_matches_wire.py` (8 of 8). Near-total failure is a different signature from
a one-case regression: it usually means either the capability the file tests does not exist, or the
file's fixture no longer constructs its precondition. Those two possibilities have opposite remedies
(build the capability vs delete/repair the test), so I am **not** guessing between them here.

## UNDECIDED — and what would settle each

The remaining 13 files are marked UNDECIDED. Settling them requires reading, per file, what the failing
assertion demands and comparing that against the current intended behaviour — not against what the test
says, because a test can encode a superseded rule. That comparison is the actual work of this slice and
it was not completed here. Naming that plainly is better than a table of confident-looking labels built
on inference.

Next step for each of the 13, in order of value: (1) does the failing assertion name a rule in
CC-1 / GUT that is still current? If yes -> REAL_DEFECT with the production line. (2) If the rule was
superseded -> STALE_TEST with the superseding reference. (3) If the fixture never builds its
precondition -> STALE_HARNESS. (4) If a later test covers the same invariant better -> DELETE_CANDIDATE.

## Provenance

- Worktree `C:/Users/wigmore/tmp/p11_basered`, detached at `a1acc28`.
- Runner baseline at the same commit: `files=124 pass=105 fail=19 REGRESSIONS(0)`.
- Exit-code census: 167 files, 24 non-zero.
- Chunk A was dispatched twice as a delegated task; both attempts produced no commit. This document
  replaces that attempt.
