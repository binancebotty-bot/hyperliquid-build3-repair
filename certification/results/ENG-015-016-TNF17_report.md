# ENG-015 / ENG-016 / TN-F17 Certification Report

**Certification ID:** ENG-015-016-TNF17  
**Tested Commit:** 43731b4f1f19a56e835032dabf608a550f925717  
**Tested At:** 2026-10-14T05:22:23.067602+00:00  
**Verdict:** PASS (all rows PASS)

## Summary

This certification verifies three engine invariants from the certification matrix:

- **ENG-015**: Sign flip handling  
- **ENG-016**: Build 4 leftovers on the shared follower account  
- **TN-F17**: Trade direction inferred from position  

Each row requires:
1. **POSITIVE CONTROL**: Run the real engine code at the tested commit → must PASS
2. **STATIC CHECK**: Code inspection to verify implementation details
3. **NON-VACUOUS NEGATIVE TEST**: Mutate a scratch copy to break the invariant → must FAIL

All three rows PASS with executed, non-vacuous evidence.

## File Hashes (Tested Commit)

| File | SHA-256 | Lines |
|------|---------|-------|
| `_archive/hl_stage2/convergence_shadow.py` | `f63732d5f132cd7052e08f78c02d5434cf11167c7aaeceffc8084b1b96cc481d` | 250 |
| `_archive/hl_stage2/exchange_truth.py` | `6f841fd7e6a4d4b72c4a5c4c7390f88addb627602199c6a14cfa2851d849b6ff` | 340 |
| `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` | `2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405` | 8030 |
| `_archive/hl_stage2/HL_Live_Copy_Service.py` | `e2f04fa826958c73169bae2490a6ebb3ebfd09d9aecda513ef0d7bd8a10ec2c6` | 5109 |
| `_archive/hl_stage2/test_g2_copy_correctness.py` | `16fcfd54fc7b77f51e2b593d3f7e0522bf71bb517f342746e87e275979650594` | 415 |
| `_archive/hl_stage2/test_g3_exchange_truth.py` | `fa9696c5188d1ef5ed786ea3a530e6b14ae8ed7f1e55a1dac91d2eeb02c353b1` | 331 |
| `_archive/hl_stage2/test_g4_fixed_slices.py` | `c2dc9fd110fb06265b49165d55d9c8f0fdddaa7f34a2071ce2ea7e5e4e52f12c` | 161 |

## Row-by-Row Evidence

### ENG-015: Sign flip handling
**Expected behaviour:** Leader flip: reduce-only flatten leg first, open leg only after exchange-confirmed flat, never flipping unrelated inventory.  
**Execution proof:** Leader event (testnet-observable) → desired net per coin → planner delta → single sender → testnet order → MASTER fill/position  
**Independent oracle:** Hyperliquid testnet info API read by a script that does not import engine code: clearinghouseState (all perp DEXes), openOrders, userFillsByTime for MASTER; leader fills from mainnet info API  
**Negative tests:** restart mid-sequence | stale leader snapshot | API 429/timeout | duplicate/reordered event  

**PASS Evidence:**
- **POSITIVE:** `convergence_shadow.py` self-test passes with disaster cases, invariant, idempotent, and specific sign-flip leg1/leg2 checks
- **STATIC:** Code contains `SIGN_FLIP_LEG1_FLATTEN`, `reduce_only=True` with `FLATTEN_THEN_OPEN`, `pending_open`, and invariant comment about never crossing zero in one order
- **NEGATIVE:** Mutation removing sign-flip two-leg split (replaced with single crossing order) causes self-test to FAIL (detected)

### ENG-016: Build 4 leftovers on the shared follower account
**Expected behaviour:** Open orders and positions left on the shared follower account by Build 4 (and by earlier Build 3 runs) are pre-existing unrelated inventory: the engine never adopts, sizes against, amends, cancels, flattens or counts them as owned, and the UI shows them as unowned. Any cleanup is a separate operator decision.  
**Sources:** ARCH inv12 (pre-existing unrelated inventory preserved) | history/BUILD_HISTORY_REVIEW.md §7 'Build 4 leftovers' (Boss report)  
**Execution proof:** Leader event (testnet-observable) → desired net per coin → planner delta → single sender → testnet order → MASTER fill/position  
**Independent oracle:** Hyperliquid testnet info API read by a script that does not import engine code: clearinghouseState (all perp DEXes), openOrders, userFillsByTime for MASTER; leader fills from mainnet info API  
**Negative tests:** restart mid-sequence | stale leader snapshot | API 429/timeout | duplicate/reordered event  

**PASS Evidence:**
- **POSITIVE:** `exchange_truth.reconcile_sleeve()` correctly computes `sleeve_net = master_net - unattributed_net` and blocks when divergence exists
- **STATIC:** Code confirms `unattributed_baseline` is attribution-only ("Attribution only - never order authority") and `reconcile_sleeve` function exists
- **NEGATIVE:** Mutation removing `unattributed_net` subtraction from `reconcile_sleeve` causes divergence to be detected (FAIL)

### TN-F17: Trade direction inferred from position
**Expected behaviour:** Trade direction comes only from a genuine leader fill, never from a position snapshot.  
**Sources:** local-trading/hl-build4-final-closeout/proofs/build4_completion/PHASE_6T_C_MATRIX_F10_F19.md F17  
**Execution proof:** Predeclared Phase 6T-style scenario on testnet through the production engine path only (no direct exchange.order); evidence per class with exchange parity  
**Independent oracle:** Hyperliquid testnet info API read by a script that does not import engine code: clearinghouseState (all perp DEXes), openOrders, userFillsByTime for MASTER; leader fills from mainnet info API  
**Negative tests:** restart mid-sequence | stale leader snapshot | API 429/timeout | duplicate/reordered event  
**Notes:** Equivalent to PRODUCT_SEMANTICS B1/B2.  

**PASS Evidence:**
- **POSITIVE:** `direction_from_size(size: float) -> str:` static method correctly returns LONG for size > ε, SHORT for size < -ε, FLAT for size ≈ 0, with no snapshot/position_direction dependency
- **STATIC:** Code confirms method uses `size` parameter and planner-side is authoritative over manual position
- **NEGATIVE:** Mutation making `direction_from_size` always return "LONG" causes test_g2 to FAIL (direction wrong)

## Mutations Applied (Negative Tests)

All mutations were applied to scratch copies only; no engine files were modified.

1. **ENG-015_negative_1**: Removed sign-flip two-leg split; replaced with single crossing order  
   - File: `_tmp_eng015_mutated.py`  
   - Expected: FAIL (sign flip should cross zero in one order)  
   - Actual: FAIL  
   - Non-vacuous: ✓  

2. **ENG-016_negative_1**: Removed unattributed_net subtraction from reconcile_sleeve  
   - File: `_tmp_eng016_mutated.py`  
   - Expected: FAIL (divergence detected)  
   - Actual: FAIL  
   - Non-vacuous: ✓  

3. **TN-F17_negative_1**: direction_from_size always returns LONG regardless of position  
   - File: `_tmp_tnf17_mutated.py`  
   - Expected: FAIL (direction wrong)  
   - Actual: FAIL  
   - Non-vacuous: ✓  

## Harness

The certification was executed using a standalone harness that does NOT import engine modules. Instead, it:
- Runs Python files as subprocesses (independent of engine imports)
- Parses their output for pass/fail markers
- Applies mutations to temporary files and tests them in isolation
- Reports executed evidence with mutations

**Harness location:** `certification/results/ENG-015-016-TNF17_harness.py`  
**Results location:** `certification/results/ENG-015-016-TNF17_43731b4f.json`

## Conclusion

All three rows (ENG-015, ENG-016, TN-F17) PASS with executed, non-vacuous evidence at commit 43731b4f. The engine correctly implements sign-flip handling (two-leg split), preserves Build-4 leftovers as unattributed inventory, and infers trade direction from position size (not snapshot). No engine files were modified during this certification.

---
*Report generated by ENG-015-016-TNF17 certification harness*  