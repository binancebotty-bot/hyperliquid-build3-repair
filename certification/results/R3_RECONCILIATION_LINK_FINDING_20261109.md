# R3 captured-reconciliation correlation finding (2026-11-09)

Judged historical-test commit: `0e5e5420d60a8e10ccfe8025beaad7caa816989e`.
Pinned snapshot: `snapshot_20261109T133856Z`.
Capture window: `1794229022124 <= created_at_ms < 1794231536107` (unchanged).

## Conflicting journal values

For intent `7f71ca1390325e8d494e89820ed9ef70`:

- `order_intents.csv.leader_fill_id` = `0x4203d18f74520cda437d04486ad0540203c100750f552bace5cc7ce23355e6c4`.
- `reconciliation.csv.leader_fill_id` = `0x8f305af45ac0ca5e90aa04486ad0540203c000d9f5c3e93032f9064719c4a449`.
- Host reported failure `R3_UNMATCHED_RECONCILIATION_LINK:5`; four additional mismatched reconciliation rows were reported but have not been supplied with row-level records in this author's evidence.

## Contract and disposition

The pinned `tests/test_r3_real_historical_evidence.py` asserts that a reconciliation row claiming both an intent and a leader fill references the same leader fill recorded by that intent. **Retain this assertion unchanged.**

The intent journal is the declared source of the intent's original leader-fill association; thus for the *intent association*, the order-intents value is authoritative **within these four CSVs**. The reconciliation value is inconsistent with that association. This does *not* prove whether the reconciliation row incorrectly copied an unrelated leader, describes a legitimate later linked leader, or is produced by a writer race. A later/related fill is not automatically an allowed intent-to-leader remapping.

Do not synthesize an allowed set, rewrite the snapshot, or certify the historical test green. The source writer's call path, reconciliation event type, and the remaining four full records must establish any permitted multi-leader linkage before a production change. Until then, **R3 remains RED (unresolved historical data-integrity discrepancy)**; a new commit hash does not change that verdict.

Host-reported time-window proofs: minimum `1794229022124` within range, maximum `1794231533922` strictly below exclusive end. These prove only the window boundaries, not the reconciliation join.

Review request: determine whether reconciliation's `leader_fill_id` means the intent's creator fill or a distinct later fill and supply code-level provenance and recorded association evidence. If a distinct later fill is legitimate, require an explicit separately recorded relation with event-specific validation, not accepting arbitrary `intent_id` to `leader_fill_id` combinations.
