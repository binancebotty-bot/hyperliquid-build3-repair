# PASS-AUDIT slice 4 - UI-SSOT / UI-WALLET / UI-TRUTH PASS rows

task t_6a310ebd | read-only | register `origin/cert/local-main-b142cf8` @ `b142cf88d389e791160f691aac3d936852b99975` (sha256 `86b2237fe95f88ca9eb758fb42ddbdf3efdaef71e56f79a10e2d2635f44f341a`)

## Scope finding

The task premise is FALSE for this scope. Every PASS row with a `UI-SSOT-`, `UI-WALLET-` or `UI-TRUTH-` prefix (66 rows) is already named by at least one committed PASS_AUDIT blob; the 9 committed blobs cover 489 distinct row ids in total.

| Audit blob | Rows named |
|---|---:|
| `EVIDENCE/audits/PASS_AUDIT_SLICE2_t_f441e9fc.json` | 30 |
| `EVIDENCE/provenance/PASS_AUDIT_CONSOLIDATION_b142cf88d3.json` | 147 |
| `EVIDENCE/provenance/PASS_AUDIT_NONUI2_b142cf88d3.json` | 46 |
| `EVIDENCE/provenance/PASS_AUDIT_SLICE6_b142cf88d3.json` | 30 |
| `EVIDENCE/provenance/PASS_AUDIT_UILCC_HDR_BTN_GRAPH_b142cf88d3.json` | 27 |
| `EVIDENCE/provenance/PASS_AUDIT_UIPA2_b142cf88d3.json` | 78 |
| `EVIDENCE/provenance/PASS_AUDIT_UIPA3_b142cf88d3.json` | 78 |
| `EVIDENCE/provenance/PASS_AUDIT_b142cf88d3.json` | 183 |
| `EVIDENCE/provenance/PASS_AUDIT_slice3_t_e4186e8a.json` | 30 |

## Summary

audited=66 KEEP=14 DEMOTE=52 remaining_unaudited=0

rows where this slice conflicts with a prior KEEP: 29

- UI-SSOT-CARD-01
- UI-SSOT-CARD-02
- UI-SSOT-CARD-03
- UI-SSOT-CARD-04
- UI-SSOT-CARD-05
- UI-SSOT-CARD-06
- UI-SSOT-CARD-07
- UI-SSOT-CARD-08
- UI-SSOT-CARD-09
- UI-SSOT-PAGE-02
- UI-SSOT-PAGE-03
- UI-SSOT-PAGE-04
- UI-SSOT-PAGE-05
- UI-SSOT-PAGE-06
- UI-SSOT-PAGE-07
- UI-SSOT-PAGE-09
- UI-SSOT-PAGE-10
- UI-SSOT-PAGE-12
- UI-SSOT-TBL-01
- UI-SSOT-TBL-24
- UI-SSOT-TOP-01
- UI-SSOT-TOP-02
- UI-SSOT-TOP-03
- UI-SSOT-TOP-04
- UI-SSOT-TOP-05
- UI-SSOT-TOP-08
- UI-TRUTH-001
- UI-TRUTH-002
- UI-TRUTH-004

## Per-row verdicts

| row | verdict | prior audit | why |
|---|---|---|---|
| UI-SSOT-CARD-01 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-01:PNL_CARD |
| UI-SSOT-CARD-02 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-02:REALISED_CARD |
| UI-SSOT-CARD-03 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-03:UNREALISED_CARD |
| UI-SSOT-CARD-04 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-04:DRAWDOWN_CARD |
| UI-SSOT-CARD-05 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-05:MAX_DD_CARD |
| UI-SSOT-CARD-06 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-06:EXPOSURE_CARD |
| UI-SSOT-CARD-07 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-07:COPYABILITY_CARD |
| UI-SSOT-CARD-08 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-08:ACTIVITY_CARD |
| UI-SSOT-CARD-09 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-CARD-09:DB_HEALTH_CARD |
| UI-SSOT-PAGE-02 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-02:<HTML_ELEMENT |
| UI-SSOT-PAGE-03 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-03:<STYLE_ELEMENT |
| UI-SSOT-PAGE-04 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-04:<SCRIPT_ELEMENT |
| UI-SSOT-PAGE-05 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-05:_SORT__ELEMENT |
| UI-SSOT-PAGE-06 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-06:_API_UI_STATE_ELEMENT |
| UI-SSOT-PAGE-07 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-07:NORM_BASE_ELEMENT |
| UI-SSOT-PAGE-08 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-08:FIXED_NOTIONAL_ELEMENT |
| UI-SSOT-PAGE-09 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-09:FEE_BPS_ELEMENT |
| UI-SSOT-PAGE-10 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-10:FRICTION_ELEMENT |
| UI-SSOT-PAGE-12 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-PAGE-12:COPY_MODE_ELEMENT |
| UI-SSOT-TBL-01 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-01:COLUMN; UI-SSOT-TBL-01:NO_WALLETS_FALLBACK |
| UI-SSOT-TBL-02 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-02:COLUMN |
| UI-SSOT-TBL-03 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-03:COLUMN |
| UI-SSOT-TBL-04 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-04:COLUMN |
| UI-SSOT-TBL-05 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-05:COLUMN |
| UI-SSOT-TBL-06 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-06:COLUMN |
| UI-SSOT-TBL-07 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-07:COLUMN |
| UI-SSOT-TBL-08 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-08:COLUMN |
| UI-SSOT-TBL-09 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-09:COLUMN |
| UI-SSOT-TBL-10 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-10:COLUMN |
| UI-SSOT-TBL-11 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-11:COLUMN |
| UI-SSOT-TBL-12 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-12:COLUMN |
| UI-SSOT-TBL-13 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-13:COLUMN |
| UI-SSOT-TBL-14 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-14:COLUMN |
| UI-SSOT-TBL-15 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-15:COLUMN |
| UI-SSOT-TBL-16 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-16:COLUMN |
| UI-SSOT-TBL-17 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-17:COLUMN |
| UI-SSOT-TBL-18 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-18:COLUMN |
| UI-SSOT-TBL-19 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-19:COLUMN |
| UI-SSOT-TBL-20 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-20:COLUMN |
| UI-SSOT-TBL-21 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-21:COLUMN |
| UI-SSOT-TBL-22 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-22:COLUMN |
| UI-SSOT-TBL-23 | DEMOTE | DEMOTE | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-23:COLUMN |
| UI-SSOT-TBL-24 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TBL-24:COLUMN |
| UI-SSOT-TOP-01 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TOP-01:NORM_BASE_ELEMENT; UI-SSOT-TOP-01:EMPTY_STATE_FALLBACK |
| UI-SSOT-TOP-02 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TOP-02:COPY_MODE_ELEMENT |
| UI-SSOT-TOP-03 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TOP-03:FIXED_NOTIONAL_ELEMENT |
| UI-SSOT-TOP-04 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TOP-04:FEE_BPS_ELEMENT |
| UI-SSOT-TOP-05 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TOP-05:COPY_FRICTION_BPS_ELEMENT |
| UI-SSOT-TOP-08 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-SSOT-TOP-08:DIRECTION_ELEMENT |
| UI-TRUTH-001 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-TRUTH-001:NO_TRUTH_TIER_FALLBACK |
| UI-TRUTH-002 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-TRUTH-002:CONDITIONAL_GREEN |
| UI-TRUTH-004 | DEMOTE | KEEP | UNSUBSTANTIATED: pass=True but the record's own detail reports a negative condition -> UI-TRUTH-004:FRESHNESS_SHOWN; UI-TRUTH-004:STALE_DATA_FLAG |
| UI-WALLET-001 | KEEP | KEEP | row record PASS; 11/11 checks pass (6 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-003 | KEEP | KEEP | row record PASS; 7/7 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-004 | KEEP | KEEP | row record PASS; 6/6 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-005 | KEEP | KEEP | row record PASS; 6/6 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-007 | KEEP | KEEP | row record PASS; 5/5 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-009 | KEEP | KEEP | row record PASS; 3/3 checks pass (1 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-010 | KEEP | KEEP | row record PASS; 7/7 checks pass (3 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-011 | KEEP | KEEP | row record PASS; 8/8 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-012 | KEEP | KEEP | row record PASS; 11/11 checks pass (3 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-013 | KEEP | KEEP | row record PASS; 4/4 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-016 | KEEP | KEEP | row record PASS; 6/6 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-017 | KEEP | KEEP | row record PASS; 6/6 checks pass (1 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-018 | KEEP | KEEP | row record PASS; 6/6 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |
| UI-WALLET-019 | KEEP | KEEP | row record PASS; 5/5 checks pass (2 negative tests), 0 failed; proof is the engine's own wallet/config semantics path, matching the row's declared execution_proof (UI action -> config write -> running engine reads it) |

## Evidence semantics finding

The UI-SSOT-* evidence artifact (`UI_CORRECTION_2d29211.json`) is unusable as a per-row proof record. Its harness (`UI_CORRECTION_harness_2d29211.py`) calls `check(name, passed, detail)` and appends `{'name','pass','detail'}` unconditionally, while passing a NEGATIVE-condition string as the detail even when the condition holds:

```python
check(f"{row_id}:COLUMN", h in html or h.upper() in html, f"{h} column not found")
```

so `UI-SSOT-TBL-01:COLUMN` records `pass=True` with detail `WALLET column not found`. 342 of 441 checks are of this shape. The detail describes the failure mode, not the observed result; it is not an inverted flag. Rows resting only on such checks are recorded UNSUBSTANTIATED (DEMOTE), not as passing.

The 14 `UI-WALLET-*` rows rest on `WALLET_fa9d9f55ff.json`, which stores a real per-row record with named checks and negative tests; all 14 KEEP.

## Non-goals

The register was NOT modified; nothing was re-probed; no live surface was touched.
