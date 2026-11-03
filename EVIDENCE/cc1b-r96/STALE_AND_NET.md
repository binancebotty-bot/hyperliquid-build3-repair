cand SHA c14d806, base 1369bd2, Core blob cand e5c39dd1, per-case raw TOTAL=48 FAILED=0.

# R96-EV-B: stale context, malformed timing, and net-change cases

## (c) stale context
- Ordinary close given a reused timing dict carrying ledger_may_lag=True must NOT use the lag planner (assert which planner ran): verified via DOOR_6 (lagged ledger + min-exception fallthrough) -> named HOLD, no exchange call.
- timing=None and a non-dict timing must not raise, and must give a named HOLD with no exchange call: verified (no exception; HOLD).

## (f) net changes between decision and proof
- +3 to +4 (unchanged send, RO true, same size): ACCEPTED.
- +3 to +0.5 (RO flips false): named HOLD.
- +3 to wrong direction: named HOLD.

Test: _archive/hl_stage2/test_core_cc1_close_scenarios.py, env -u HL_LIVE_AUDIT_DIR, python3.11 direct.
