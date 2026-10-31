# CC1-CODA — B candidate; C STOP / handoff (31 Oct 2026)

Controller order: CC1-T-CODA-BC-PATCH-0821, issue #1 comment 6541081730.
Contracts: CC-1 M1 CS-I1..I4, R1/R3, I05/I06/I22/I23, CLOSES-SACRED; CH-2/4/8/9.
Review destination: gpt6:independent-reviewer-g3, control repo issue #14.

## Reproducible GitHub anchors (READ ONLY; live untouched)
- Requested builder base: `hermes/close-r3-fence@0bfb746`. **Not found** by GitHub fetch at this time.
- Resolved GitHub branch head: `hermes/close-r3-fence@29dcb5f5800e521f55c226f8591cd8503aab5d97`. The replacement task cannot claim the unavailable 0bfb746 as its base.
- Scratch branch `gpt/coda-bc-patch-0821`, rooted at verifiable 29dcb5f, ONLY. Do not apply to builder's working A without verifying its exact SHA and rebasing.
- Candidate B Core commit `73b60eb98dc85dbaadc58061238de5d3b75d02bd` (+60/-12, NET +48) and isolated test `dc531d3feb877626687bfe2598eade7addb517ec`. Apply from `0001-B-no-call.patch`.
- Unfilled-chain RED-only C witness `67ca5701eff6f44983e8524b7af5df90ce8d5294` (no Core modification), also in `0002-C-RED-witness-only.patch`.

## B — source candidate, not a PASS
- Reuses existing `update_send_attempt_row(... durable=True)` via one `_terminalise_pending_as_no_call` helper. After `pre_send` returns an actual attempt ID, an exception from the final `_master_gate_reason` or `_final_close_proof` yields durable `PRE_WIRE_FAULT_NO_EXCHANGE_CALL`, no SDK invocation, owed CLOSE escalation. A first/pre-pending gate exception is typed but generates no phantom pending row. `_send_real` now preserves the typed no-call result rather than classifying it as an exchange reject.
- Source-only; **NOT EXECUTED**. The test file asserts real isolated CSV pending→terminal close/reopen, zero calls and owed EXIT for first-gate and after-pending config/proof faults. Test seam fakes only data, lease ownership and error injection, not a real exchange. Reviewer must challenge the test's fake lease and complete path coverage.
- Required builder output: exact SHA/environment, `RESULT::...` and `TOTAL=n FAILED=m`, baseline RED and candidate GREEN; check B on **builder's verified A base** before merge.

## C — STOP, not a claimed implementation
- At 29dcb5f: `IntentBuilder.build` near L5283-5293 sizes every EXIT against **current actual** `before`. Unfilled E1 .09 leaves actual +1.00; E2 from leader start .91 wrongly computes `1.00 * (.09/.91)=.098901...`, not .09. An event-derived target history is not carried in current `IntentBuilder` / `ORDER_INTENT_FIELDS` with independently validated leader event-position continuity. Deriving it from physical sleeve alone is unsound; a new unverified cache/ledger is prohibited.
- W9 expected with zero follower fills: E1 +1.00→+.91 owed .09, E2 +.91→+.82 owes .09 (cumulative .18), E3 +.82→+.73 owes .09 (cumulative .27), E4 +.73→+.64 owes .09 (cumulative .36). Existing in-flight OID reservations must be subtracted independently before any new physical call. The RED-only test asserts size and unchanged physical ledger; it does not certify OID allocation.
- **Explicit hard-limit conflict:** controller requires `close_size = min(abs(wallet_pos),abs(wire_size),abs(intent.copy_size))`. Existing `_close_wire_plan` L8101-8105 can raise a close from requested .100 to whole-owned .105 if residual .005 is subminimum (I23). That exceeds the explicit `wire_size` and `intent.copy_size` bounds. Preserving the .105 dust close would require lifting the newly mandated bound, which the order expressly forbids without Boss ruling. I have NOT lifted the bound or silently deleted the accepted dust rule.
- Stop C source change here rather than invent a second target ledger, widen a close, or pass a contradictory case. The controller/reviewer must reconcile both constraints and identify the complete durable event-position/owed-reservation source before builder applies a C patch. This is **not** a request to lift the bound; it is a blocker recorded as instructed.

## Evidence / status
```
Artifact B code: SOURCE_ONLY, REVIEW_PENDING
Artifact B tests: NOT_RUN / TOTAL=NOT_RUN FAILED=NOT_RUN
Artifact C code: STOP_BLOCKED (no commit)
Artifact C test: RED_SPEC_ONLY, NOT_RUN / TOTAL=NOT_RUN FAILED=NOT_RUN
Git apply --check on builder A: NOT_RUN (0bfb746 unavailable)
Independent PASS: NONE
PR #8 promotion: PROHIBITED
Live engine a1acc28 / deployment: UNCHANGED, HOLD
```
