cand c14d80601ea840da5a873e61bd088a3f9a79da6c, base 1369bd2290a2d5d45749aa7fceaec4b748936dd0, Core blob cand e5c39dd13ceebd7674bb002f8f2fbecb8202a6c0, Core blob base c6fd5399a3f2d947c0eca153366a3f3447773700, per-case raw TOTAL=57 FAILED=0 (cand) / TOTAL=57 FAILED=9 (base)

## Mutant testing for W1_RECOVERY_USES_SAME_PLANNER

Each mutant was applied to the candidate Core copy (r96-wt worktree), the W1 test was re-run, and the Core was restored.

### M-A: delete `state["close_verified_sz_decimals"] = sz_dec` inside the decide() helper
**Location:** `HL_Live_Copy_Service_Core.py` line 8319 (in `_close_wire_plan` → `decide` helper)

**Edit:**
```python
# Before:
if kind == "SEND" and sz_dec is not None:
    state["close_verified_sz_decimals"] = sz_dec

# After (mutant):
if kind == "SEND" and sz_dec is not None:
    pass  # M-A mutant: deleted state["close_verified_sz_decimals"] = sz_dec
```

**Result — RED (W1 tests fail):**
```
RESULT::W1_RECOVERY_USES_SAME_PLANNER_FAIL | [{'px': 99.8, 'tif': 'Ioc', 'buy': False, 'size': 2.0, 'reduce_only': True}]
RESULT::W1_RECOVERY_ATTEMPT_RECORD_SEPARATE_FAIL | rows=[]
RESULT::W1_NO_UNKNOWN_PRECISION_REFUSAL_PASS
TOTAL=57 FAILED=9
```

**Analysis:** Without recording `close_verified_sz_decimals` during planning, the wire-time `_final_close_proof` reads `None`, passes `sz_dec=None` to `_close_wire_plan`, which triggers `CLOSE_PROOF_HOLD_UNKNOWN_PRECISION` and blocks the recovery order. This confirms the R96 fix is necessary.

---

### M-B: in `_final_close_proof` force `ledger_may_lag=False` in the `_close_wire_plan` call
**Location:** `HL_Live_Copy_Service_Core.py` line 5873 (in `_final_close_proof`)

**Edit:**
```python
# Before:
ro, actual, why = self._close_wire_plan(intent, size, dec, timing=timing,
                                        ledger_may_lag=bool((timing or {}).get("close_ledger_may_lag", False)))

# After (mutant):
ro, actual, why = self._close_wire_plan(intent, size, dec, timing=timing,
                                        ledger_may_lag=False)  # M-B mutant: forced ledger_may_lag=False
```

**Result — GREEN (W1 tests pass):**
```
RESULT::W1_RECOVERY_USES_SAME_PLANNER_PASS
RESULT::W1_RECOVERY_ATTEMPT_RECORD_SEPARATE_PASS
RESULT::W1_NO_UNKNOWN_PRECISION_REFUSAL_PASS
TOTAL=57 FAILED=0
```

**Analysis:** In this test scenario, the ledger is available and the exchange net matches the ledger net, so both `ledger_may_lag=True` and `ledger_may_lag=False` paths produce the same decision. The mutant does not cause a failure here, but it would diverge in scenarios where the ledger actually lags (the wire-time proof would use a stricter regime than the planning phase).

---

### M-C: make `_final_close_proof` return `""` right after reading `dec` so it never compares size/RO
**Location:** `HL_Live_Copy_Service_Core.py` line 5871-5877 (in `_final_close_proof`)

**Edit:**
```python
# Before:
dec = timing.get("close_verified_sz_decimals") if isinstance(timing, dict) else None
ro, actual, why = self._close_wire_plan(intent, size, dec, timing=timing,
                                        ledger_may_lag=bool((timing or {}).get("close_ledger_may_lag", False)))
if why:
    return why
return ("CLOSE_PROOF_HOLD_WIRE_SIZE_OR_RO_CHANGED"
        if abs(actual - size) > POSITION_EPSILON or ro != reduce_only else "")

# After (mutant):
dec = timing.get("close_verified_sz_decimals") if isinstance(timing, dict) else None
return ""  # M-C mutant: return early, never compares size/RO
```

**Result — GREEN (W1 tests pass):**
```
RESULT::W1_RECOVERY_USES_SAME_PLANNER_PASS
RESULT::W1_RECOVERY_ATTEMPT_RECORD_SEPARATE_PASS
RESULT::W1_NO_UNKNOWN_PRECISION_REFUSAL_PASS
TOTAL=57 FAILED=0
```

**Analysis:** The mutant bypasses the wire-time size/RO comparison entirely. In this test scenario, the planned size and RO match the wire parameters, so the early return doesn't change the outcome. However, this mutant would allow mismatched sizes or reduce_only flags to pass through undetected, breaking the wire-time proof guarantee.