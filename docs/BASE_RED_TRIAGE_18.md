# BASE_RED_TRIAGE_18 — assertion-failing test files on base `a1acc28`

Scope: the 17 `_archive/hl_stage2/` files that FAIL with a real assertion on base `a1acc28`
(worktree `C:/Users/wigmore/tmp/triage_18`, branch `docs/triage-18`). The 15 no-verdict files are
covered separately on branch `docs/test-triage-facts` (commit `6d622ed`).

Method: each file run with
`C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe <file>` from `_archive/hl_stage2`;
failing case names taken verbatim from `RESULT::<NAME>_FAIL` lines (unittest failures from `FAIL:`
lines). Production `file:line` was read for every REAL_DEFECT. Where a row turns on arming, the file
was re-run from a **scratch copy** with `"auto_send_enabled": False` flipped to `True` — no test or
Core file in the repo was modified.

Classification legend: **REAL_DEFECT** (engine wrong), **STALE_TEST** (asserts a superseded rule),
**STALE_HARNESS** (fixture broken / not a production fault), **DUPLICATE** (covered better elsewhere),
**UNDECIDED** (missing evidence named).

## The arming change that drives most of this board

`ConfigManager.master_real_orders_enabled` is `self.send_mode != "OFF"`
(`HL_Live_Copy_Service_Core.py:4069-4071`); `send_mode` comes from `_send_mode_of`
(`:4005-4022`), which honours `global_controls.send_mode` first and otherwise reads legacy
`auto_send_enabled`. `SenderGateway._master_gate_reason` (`:5650-5665`) is consulted **inside**
`_place_order` (`:5711-5715`) and returns `MASTER_REAL_ORDERS_OFF` before any exchange call when the
mode is OFF.

Every fixture that writes `"auto_send_enabled": False` and then calls `_send_real` directly now gets
`ORDER_REJECTED`, zero fake-exchange calls and no audit rows — the gate refusing, not the behaviour
under test. Flipping that one literal to `True` in a scratch copy turns most of this board green, so
those failures are counted as harness, not engine.

## Rows

| file | total/failed | failing case names | classification | production file:line for REAL_DEFECT | impact |
|---|---|---|---|---|---|
| test_core_append_truncate.py | 7/5 | `APPEND_FAILURE_RETURNS_FALSE`, `APPEND_FAILURE_LEAVES_NO_HALF_ROW`, `APPEND_FAILURE_SPILLS_ROW`, `NEXT_APPEND_IS_A_CLEAN_ROW`, `SPILLED_ROW_REPLAYED` | **STALE_HARNESS** | — | Test patches `Path.open` to inject a short write, but `append_csv` (`HL_Live_Copy_Service_Core.py:2022`) keeps a cached append handle and only calls `path.open("a")` on first use, so the patch never fires: `ret=True`, no spill, no truncation. The crash-safety paths are unexercised, not disproved. |
| test_core_audit_reduce_only_matches_wire.py | 8/8 | `REDUCING`, `REDUCING_SEND_AUDIT_EQUALS_WIRE`, `INCREASING`, `INCREASING_SEND_AUDIT_EQUALS_WIRE`, `BOUNDARY`, `PURE_REDUCE_BOUNDARY_AUDIT_EQUALS_WIRE`, `TRIMMED`, `TRIMMED_CLOSE_AUDIT_EQUALS_WIRE` | **STALE_HARNESS** | — | The file never writes `LIVE_CONFIG_FILE`, so `send_mode` is OFF and every send returns `ORDER_REJECTED` with `wire=None` and no audit row — the master gate (`:5650-5665`), not the audit-vs-wire invariant. |
| test_core_deferred_entry_refusal.py | 14/2 | `R1_STALE_THEN_FRESH_WITHIN_TOLERANCE_TAKES`, `R6_ORD_010_OLD_ENTRY_TAKES_THE_RULE_WITH_SWITCH_OFF` | **STALE_TEST** (R1), **UNDECIDED** (R6) | — | R1 encodes the pre-Boss rule (a within-tolerance late entry must not rest a limit); production `_send_real` (`:8417-8435`) deliberately rests a GTC at the leader's price inside tolerance. R6 wants the ORD_010 missed-entry remedy to act while the master switch is OFF, but `_apply_missed_entry_rule_on_refusal` (`:12771-12778`) returns `None` for `MASTER_REAL_ORDERS_OFF` on purpose. Missing: a controller ruling on whether ORD_010 outranks switch-off. |
| test_core_disk_full.py | 29/1 | `B3_FINAL_ROW_WRITE_FAILURE_STILL_SENDS_THE_ORDER_ONCE_AND_KEEPS_IT_NAMED` | **STALE_HARNESS** | — | The order is sent exactly once (`sent=1`) but the row carries no cloid: the fake `order()` has no `cloid` parameter, so `_exchange_accepts_cloid` (`:3830-3845`) correctly omits it. Fixture limitation; the production branch exercised is the safer one. |
| test_core_engine_gaps.py | 24/2 | `O2_EXIT_RECOVERY_GOES_THROUGH_THE_ONE_SITE`, `W2_ELEVEN_ACTIVE_WALLETS_REFUSED_AT_START` | **STALE_TEST** (O2), **STALE_HARNESS** (W2) | — | O2 asserts the recovery close is `reduce_only=True`; production carries the deliberate 12 Oct Boss ruling that it is **not** reduce-only, sized to the follower's net target and guarded by `guard_standing_closes()` (`:7230-7248`). W2 fails on `engine-global.lock` held by an unrelated live engine on this machine — host-state collision, not a limit check. |
| test_core_fill_lag.py | 15/3 | `D1_FILL_OWNED_WHILE_THE_MAIN_CYCLE_IS_STUCK`, `S1_CYCLE_STATE_WRITE_KEEPS_COPY_CURSOR_AND_LAG_RECORD`, `P1_HOT_POLL_LEAVES_THE_RUNTIME_STATE_ALONE` | **UNDECIDED** | — | Missing evidence, not proven defects. D1 stubs `write_live_integrity_status` to block and the log shows `[status_write_failure:live-integrity-status] TimeoutError`, so the cycle thread may have died before the assertion. S1 compares the whole `COPY_POLL_STATE_FILE` dict against a pre-write snapshot, and `state_writer.write` now legitimately adds `last_state_write_ms`/`created_at_ms` (`:11710-11714`) — needs the diff printed. P1 compares an mtime the same failing write path can rewrite — needs isolation from the stuck-cycle stub. |
