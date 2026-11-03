cand c14d80601ea840da5a873e61bd088a3f9a79da6c, base 1369bd2290a2d5d45749aa7fceaec4b748936dd0, Core blob cand e5c39dd13ceebd7674bb002f8f2fbecb8202a6c0, Core blob base c6fd5399a3f2d947c0eca153366a3f3447773700, per-case raw TOTAL=57 FAILED=0 (cand) / TOTAL=57 FAILED=9 (base)

## W1_RECOVERY_USES_SAME_PLANNER witness test

### Test scenario
A close IOC gets a partial fill (0.5 of 2.0), then a recovery is queued for the remainder (1.5). The recovery path calls `_close_wire_plan` with `sz_dec=3` and `ledger_may_lag=True`. We assert:
- Exactly ONE recovery order is placed (GTC), separate from the IOC
- It has its own cloid/oid, side, size, reduce_only, and attempt record
- No `CLOSE_PROOF_HOLD_UNKNOWN_PRECISION` refusal occurred

### Candidate (r96-candidate, commit 0d1cc72, Core blob e5c39dd13ceebd7674bb002f8f2fbecb8202a6c0) — GREEN
```
RESULT::W1_RECOVERY_USES_SAME_PLANNER_PASS
RESULT::W1_RECOVERY_ATTEMPT_RECORD_SEPARATE_PASS
RESULT::W1_NO_UNKNOWN_PRECISION_REFUSAL_PASS
TOTAL=57 FAILED=0
```

### Base (1369bd2, Core blob c6fd5399a3f2d947c0eca153366a3f3447773700) — RED
```
RESULT::W1_RECOVERY_USES_SAME_PLANNER_FAIL | [{'px': 99.8, 'tif': 'Ioc', 'buy': False, 'size': 2.0, 'reduce_only': True}]
RESULT::W1_RECOVERY_ATTEMPT_RECORD_SEPARATE_FAIL | rows=[]
RESULT::W1_NO_UNKNOWN_PRECISION_REFUSAL_PASS
TOTAL=57 FAILED=9
```

### Analysis
On base, the recovery order is not placed (only the IOC appears in `fake.calls`). The `_queue_exit_recovery_if_needed` path calls `_close_wire_plan` with `ledger_may_lag=True`, but the `decide()` helper does not record `close_verified_sz_decimals` in the timing state. At wire time, `_final_close_proof` reads `None` for `close_verified_sz_decimals`, passes `sz_dec=None` to `_close_wire_plan`, which returns `HOLD` with `CLOSE_PROOF_HOLD_UNKNOWN_PRECISION`, blocking the recovery order.

On candidate (R96), the `decide()` helper records `state["close_verified_sz_decimals"] = sz_dec` when `kind == "SEND"`. At wire time, `_final_close_proof` re-reads this value and re-runs the same decision with the same precision, allowing the recovery order to proceed.