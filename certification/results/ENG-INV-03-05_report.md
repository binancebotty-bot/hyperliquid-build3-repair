# ENG-INV-03-05 CORRECTED Census Report

## Summary

| Field | Value |
|-------|-------|
| **Verdict** | **PASS** |
| **Tested Commit** | `43731b4f1f19a56e835032dabf608a550f925717` |
| **Repo** | `C:\Users\wigmore\hyperliquid-build3-repair` |
| **Date** | 2026-10-14 |

## Target Files

| File | Lines | SHA-256 |
|------|-------|---------|
| `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` | 8030 | `2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405` |
| `_archive/hl_stage2/HL_Live_Copy_Service.py` | 5109 | `e2f04fa826958c73169bae2490a6ebb3ebfd09d9aecda513ef0d7bd8a10ec2c6` |

Sanity anchor: Core = 8030 lines at HEAD 43731b4 -- **matches expected**.

## Invariants Checked

| Invariant | Result | Details |
|-----------|--------|---------|
| (a) No new third-party imports | **PASS** | 0 third-party imports found |
| (b) No new persistent stores | **PASS** | 0 persistent-store constructors found |
| (c) No Build 4 control-plane imports | **PASS** | 0 Build-4 imports found |

## Internal Imports (correctly classified as INTERNAL, not third-party)

| File | Line | Module |
|------|------|--------|
| Core | L101 | `exchange_truth` |
| UI | L136 | `convergence_shadow` |
| UI | L814 | `exchange_truth` |

## Non-Vacuous Negative Test

To prove the census is not vacuously passing, three mutations were introduced into scratch copies:

| Mutation | Description | Expected | Actual | Result |
|----------|-------------|----------|--------|--------|
| Positive control | Unmutated repo | PASS | PASS | OK |
| A: Third-party import | `import zmq` added to Core | FAIL (1 third-party) | FAIL (1 third-party) | DETECTED |
| B: Persistent store | `sqlite3.connect("mutant.db")` added to Core | FAIL (1 persistent store) | FAIL (1 persistent store) | DETECTED |
| C: Build 4 import | `import proof_core.mission_control` added to Core | FAIL (1 Build-4 import) | FAIL (1 Build-4 import) | DETECTED |

**All mutations correctly detected. Census is non-vacuous.**

## Method

- Independent AST-based scanner (no engine imports)
- Repo root passed as CLI parameter (no hardcoded foreign paths)
- Target files asserted to exist before scanning
- stdlib baseline documented in script
- Internal modules resolved by checking for matching `.py` files in the repo

## Artifacts

- `certification/results/ENG-INV-03-05_43731b4f.json` -- machine-readable results
- `certification/results/ENG-INV-03-05_report.md` -- this report
- `census_eng_inv_03_05_corrected.py` -- census script (attached)
- `mutation_test_eng_inv_03_05.py` -- mutation test script (attached)
