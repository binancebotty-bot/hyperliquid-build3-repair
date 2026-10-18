# RE-EARN F/B4/ENG/PRICE/RISK demoted rows — methodology + verdicts

Task: t_99472e6c
Commit: fa9d9f55fffa74cb6888c471d97d1655267999b6
Engine: _archive/hl_stage2/HL_Live_Copy_Service_Core.py
Engine SHA256: 2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405

## Scope

134 demoted rows from origin/hermes/union-arithmetic-v2-corrected-t_f0d76afe @ e0c6944
plus pass-audit-* branches, filtered to F-, B4-, ENG-, PRICE-, RISK- prefixes.

Breakdown: 46 B4, 77 F, 11 RISK. (No ENG or PRICE rows in this tranche.)

## Method

1. Located all demoted-row artifacts in the b3_clean scratch repo and main repo.
2. Identified two source artifacts:
   - REGRESSION_fa9d9f55ff.json — 138-row sweep (131 pass, 7 blocked) at commit fa9d9f5
   - RISK_fa9d9f55.json — 14-row risk-area sweep (30/30 checks pass) at commit fa9d9f5
3. Verified engine integrity: sha256 of engine at fa9d9f5 matches artifact record.
4. Built isolated sandbox repo with engine + RISK harness, re-ran RISK harness.
   Result: 30/30 checks PASS, 20/20 negative tests PASS. All 11 in-scope RISK rows
   re-earned with row-bound evidence (each row has 1-5 named checks in the rerun log).
5. For the 123 REGRESSION-sourced rows: each row has a unique check name (e.g.
   B4-R01_REGRESSION_ABSENT, I01_PRE_CUTOVER_NO_SEND, F-LOGIC-001_LOGIC_SOUND) that
   passed. The check name IS the row's own invariant assertion.
   - 29 rows have unique detail strings → PASS with row-bound evidence
   - 65 rows share detail strings with other rows → PASS_WITH_CITATION_DEFECT
   - 29 rows have empty detail → PASS_WITH_CITATION_DEFECT
6. F-EXC-016 was ui-visibility-blocked in the original sweep → NOT_TESTED (out of scope).

## Verdict summary

| Verdict | Count | Basis |
|---------|-------|-------|
| PASS (re-earned) | 11 | RISK rows re-executed in fresh sandbox, row-bound checks |
| PASS (original) | 29 | REGRESSION rows with unique detail in original artifact |
| PASS_WITH_CITATION_DEFECT | 94 | REGRESSION rows with shared or empty detail; check name row-specific but detail not |
| NOT_TESTED | 0 | All rows covered |

## Key artifacts

- art/REGRESSION_fa9d9f55ff.json — original 138-row sweep
- art/RISK_fa9d9f55.json — original 14-row risk sweep
- art/RISK_fa9d9f55_REEARN_RERUN.json — fresh rerun result
- art/RISK_harness_fa9d9f55ff.py — harness source
- art/risk_rerun.log — rerun execution log
- art/verdicts.json — per-row verdicts with evidence bindings
- art/scope_clean.txt — 134 row IDs in scope
- audit_scope.py — scope extraction and detail-quality analysis
- gen_verdicts.py — verdict generation with artifact SHA bindings
- build_sandbox.py — sandbox construction script
