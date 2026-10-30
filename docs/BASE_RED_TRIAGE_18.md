# BASE_RED_TRIAGE_18 — assertion-failing test files on base `a1acc28`

Scope: the 17 `_archive/hl_stage2/` files that FAIL with a real assertion on base `a1acc28`
(worktree `C:/Users/wigmore/tmp/triage_18`, branch `docs/triage-18`).
The 15 no-verdict files are covered separately on branch `docs/test-triage-facts` (commit `6d622ed`).

Method: every file was executed with
`C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe <file>` from `_archive/hl_stage2`;
failing case names are taken verbatim from the `RESULT::<NAME>_FAIL` lines. Where a row is a
REAL_DEFECT the production file:line was read, not inferred from the test name.

Classification legend: **REAL_DEFECT** (engine wrong), **STALE_TEST** (asserts a superseded rule),
**STALE_HARNESS** (fixture broken / not a production fault), **DUPLICATE** (covered better elsewhere),
**UNDECIDED** (missing evidence named).

> **Batch note that applies to many rows below:** on base `a1acc28` `ConfigManager.master_real_orders_enabled`
is `self.send_mode != "OFF"` (`HL_Live_Copy_Service_Core.py:4069-4071`) and `send_mode` is derived by
`_send_mode_of` (`:4005-4022`), which now honours `global_controls.send_mode` first. A fixture that writes
only `auto_send_enabled` **plus** a `global_controls` dict still works, but a fixture that leaves
`auto_send_enabled` out, or that writes `global_controls` with no `send_mode` while an older test expected
arming, ends at OFF and every send comes back `ORDER_REJECTED []` with
`notes=gate refusal, no exchange call: MASTER_REAL_ORDERS_OFF`. That signature appears in
`test_core_network_and_global_controls.py`, `test_core_run3_fixes.py` and
`test_core_run4_fixes.py`; it is a harness/arming problem, not an engine behaviour change.

## Rows

| file | total/failed | failing case names | classification | production file:line for REAL_DEFECT | impact |
|---|---|---|---|---|---|
| test_core_append_truncate.py | 7/5 | `APPEND_FAILURE_RETURNS_FALSE`, `APPEND_FAILURE_LEAVES_NO_HALF_ROW`, `APPEND_FAILURE_SPILLS_ROW`, `NEXT_APPEND_IS_A_CLEAN_ROW`, `SPILLED_ROW_REPLAYED` | **STALE_HARNESS** | — | Test monkey-patches `Path.open` to return a half-writing wrapper; `append_csv` (`HL_Live_Copy_Service_Core.py:2022`) keeps a cached append handle in `_AUDIT_HANDLES` (`:2055-2061`) and only calls `path.open("a")` on first use, so the second append never goes through the patched `Path.open` and the injected ENOSPC never fires — ret=True and no spill. The truncate/spill paths themselves are unexercised, so this file proves nothing either way. |
| test_core_audit_reduce_only_matches_wire.py | 8/8 | `REDUCING`, `REDUCING_SEND_AUDIT_EQUALS_WIRE`, `INCREASING`, `INCREASING_SEND_AUDIT_EQUALS_WIRE`, `BOUNDARY`, `PURE_REDUCE_BOUNDARY_AUDIT_EQUALS_WIRE`, `TRIMMED`, `TRIMMED_CLOSE_AUDIT_EQUALS_WIRE` | **STALE_HARNESS** | — | Every send ends `status=ORDER_REJECTED`, `wire=None` — the fake exchange is never called because the fixture writes a config the send gate reads as OFF (no `send_mode`, and the test's own `ConfigManager` never arms sending). The audit-vs-wire invariant is untested here, not disproved. |
| test_core_deferred_entry_refusal.py | 14/12 | `R1_STALE_THEN_FRESH_WITHIN_TOLERANCE_TAKES`, `R6_ORD_010_OLD_ENTRY_TAKES_THE_RULE_WITH_SWITCH_OFF` | **STALE_TEST** for R1, **UNDECIDED** for R6 | — | R1 asserts a within-tolerance late entry must *not* rest a limit; current production `_send_real` (`:8417-8435`) deliberately takes the missed-entry rule and rests a GTC limit at the leader's price inside tolerance — the test encodes the pre-Boss rule. R6 expects the ORD_010 remedy to act while the master switch is OFF; production `_apply_missed_entry_rule_on_refusal` (`:12771-12778`) returns `None` for `MASTER_REAL_ORDERS_OFF` **by design** (run 11 wrote ~140 refused rows/min), and the observed outcome is `OWNERSHIP_GATE_MISSING_EXCHANGE_PROOF`, so the test needs a ruling on whether the ownership gate or the switch-off short-circuit should win — missing: the controller decision on ORD_010-with-sending-off. |
| test_core_disk_full.py | 29/1 | `B3_FINAL_ROW_WRITE_FAILURE_STILL_SENDS_THE_ORDER_ONCE_AND_KEEPS_IT_NAMED` | **STALE_HARNESS** | — | `sent=1` (the order really is sent once) but `pending_row_with_cloid=False`: the test's fake exchange exposes `order(self, coin, is_buy, size, px, tif, reduce_only=False)` with no `cloid` keyword, and `_exchange_accepts_cloid` (`:3830-3845`) therefore correctly omits the cloid — so the pending row cannot carry one. Fixture limitation, and the production cloid-omission logic is if anything the safer branch. |
| test_core_engine_gaps.py | 24/2 | `O2_EXIT_RECOVERY_GOES_THROUGH_THE_ONE_SITE`, `W2_ELEVEN_ACTIVE_WALLETS_REFUSED_AT_START` | **STALE_HARNESS** (O2), **STALE_HARNESS** (W2) | — | O2 asserts the standing close is `reduce_only=True`; production `_queue_exit_recovery_if_needed` (`:7235-7246`) has carried the deliberate Boss (12 Oct) ruling that the recovery close is **not** reduce-only (it is sized to the follower's net target and guarded by `guard_standing_closes()`), so the assertion is superseded. W2 fails on `engine-global.lock` held by an unrelated live engine (pid 19168, `state_20261027`) — a machine-state collision, not a limit-check defect. |
| test_core_fill_lag.py | 15/3 | `D1_FILL_OWNED_WHILE_THE_MAIN_CYCLE_IS_STUCK`, `S1_CYCLE_STATE_WRITE_KEEPS_COPY_CURSOR_AND_LAG_RECORD`, `P1_HOT_POLL_LEAVES_THE_RUNTIME_STATE_ALONE` | **UNDECIDED** | — | All three are missing evidence, not proven defects: D1 stubs `c.write_live_integrity_status` to block, and the log shows `[status_write_failure:live-integrity-status] TimeoutError`, so the cycle thread may have died before the assertion — needs a run with the stub replaced by a real block (or the thread's exception recorded). S1 compares the whole `COPY_POLL_STATE_FILE` dict to a snapshot taken *before* `state_writer.write(...)`, which now legitimately adds `last_state_write_ms`/`created_at_ms` (`:11710-11714`), so the equality is too strict — but whether the copy cursor is preserved needs the diff printed. P1 compares `CORE_RUNTIME_STATE_FILE` mtime, and the same `state_write_failure` timeout can rewrite that file from the cycle path — needs P1 isolated from the stuck-cycle stub. |
