# Review - PR #96, commit 52a5c4a9 (ops/test_apply_hotfix.py rewrite)

VERDICT: APPROVE

The claim (suite executes, 8 outcome-bound tests, mutation controls really go red) is verified by execution. Both strongest guarantees were independently proven load-bearing by mutating ops/apply_hotfix.py in scratch copies; each mutation turns a named test red. Defects below are real but non-blocking.

## Executed evidence

1. Suite from worktree root, CPython 3.11. Last line verbatim:

       TOTAL=8 FAILED=0

   Exit 0. Eight RESULT::..._PASS lines, in order: TIMESTAMP_RULES, REPLAY_PROOF, SWAP_PASS_AND_GAP_BOUNDARY, MUTATION_GAP_THRESHOLD, PRECOMPILE_FAILURE_NEVER_STOPS, AMBIGUOUS_STOP_ISOLATED, SINGLE_FAULT_ROLLBACK, MUTATION_SEMANTIC_CONFIG_GUARD.

2. Parent 35ec1e3e6 file (git cat-file) fails py_compile at line 225 `except HOTFIX.HotfixError as exc:` - whole file was dead code. New file compiles and runs. Confirmed, not asserted.

3. Mutation A (rollback identity): scratch copy, rollback call changed from old_sha to target_sha. Result TOTAL=8 FAILED=1, red on APPLY_HOTFIX_SINGLE_FAULT_ROLLBACK, on-disk build_sha observed as bbbb... (NEW) instead of aaaa... Load-bearing.

4. Mutation B (semantic config): removed "live_config_semantic_sha256" from the invariant loop (helper line 399). Result TOTAL=8 FAILED=2, red on APPLY_HOTFIX_REPLAY_PROOF ("guard did not fire: live_config_semantic_sha256") and on APPLY_HOTFIX_MUTATION_SEMANTIC_CONFIG_GUARD (the suite's own control). Load-bearing.

5. Patch drift: pr96_out patch replayed onto the parent file; after CRLF->LF normalisation byte-identical to the committed file (equal True). SEMANTIC DRIFT: no. Raw difference is line endings only (patch carries CRLF, 413 whitespace warnings; committed blob is LF). Cosmetic.

## Defects (non-blocking)

1. ops/test_apply_hotfix.py:384 - vacuous assertion. After the fault, asserts CURRENT_AUDIT_DIR equals str(pair["state"]), which make_pair:69 already wrote and real_pointer:342 rewrites to the same string. Cannot distinguish rewritten from untouched. Would prove it: seed a different sentinel pointer before the swap, or assert the pointer hash changed.

2. ops/test_apply_hotfix.py:329-384 - no in-suite mutation control for rollback restoration. Only the semantic guard and the gap threshold have built-in red controls. Rollback was proven load-bearing here only by external mutation (evidence 3). Would prove it: add check_mutation_rollback_sha running the fault loop against a copy whose rollback passes target_sha and assert red.

3. ops/test_apply_hotfix.py:325 - weakened message assertion: `"ambiguous" in message or "could not be restored" in message` accepts the rollback-failed message as success. The events assertion on :324 is the real guard. Would prove it: assert the exact ambiguous prefix and assert "could not be restored" not in message.

4. ops/test_apply_hotfix.py:118-125 - replay watch stubbed flat: first_healthy_cycle always returns after+gap_ms first call and time.sleep is a no-op, so the helper retry/tolerance path (apply_hotfix.py:538-542) and the timeout branch (:543-544) are never executed. Untested behaviour, not false green, but the allow-list could hide real drift. Would prove it: one case raising "not caught up" twice then succeeding, and one timeout case with patched time.monotonic.

5. ops/test_apply_hotfix.py:146-155 - manual/xyz digest rules have equality cases only; a constant-returning digest would pass both. The config block (157-165) does carry a negative case. Would prove it: change signed_size / positions_by_coin and assert the digest changes.

6. ops/test_apply_hotfix.py:298 - `out["events"] == []` cannot distinguish "raised before any event" from "never ran", since boom raises before appending. Byte-identical launch spec and absent swap record (299-301) carry the real weight. Would prove it: assert the raised message is "precompile failed: injected".

## Per-test: observed vs assumed

- check_timestamp_and_digest_rules (141): OBSERVES digest_json over real files for manual/xyz/config, raw-bytes change plus semantic stability for config. ASSUMES key-order/indent rewriting is fair non-semantic churn (it is); constant-digest hole for two scopes (defect 5).
- check_replay_proof (197): OBSERVES raised messages from real replay_proof on a real CSV/state fixture, the exact proof dict for the gap fill, and the "another send attempt" refusal after a real duplicate row. ASSUMES fixture representativeness; no negative case for non-zero unresolved_count.
- check_swap_pass_and_boundary (259): OBSERVES exit code, printed verdicts, exact ordered effects with save-record last, the deactivation_to_healthy_ms line, and on-disk last_swap.json fields. ASSUMES patched validate_pair/checkout_info/SP are faithful - swap identity checks live in the helper and are not exercised here.
- check_mutation_gap_threshold (277): OBSERVES 20s -> 1 unmutated, 0 with MAX_GAP_MS=1e9. Genuine boundary and genuine control.
- check_precompile_failure_never_stops_the_pair (287): OBSERVES exception type, empty effects, byte-identical launch env and pointer, no swap record. Defect 6 cosmetic.
- check_ambiguous_stop_isolated (304): OBSERVES no rewrite/pointer/start events and unchanged launch-spec bytes. Defect 3 weakens the message half.
- check_single_fault_rollback_restores_state (329): OBSERVES on-disk build_sha==OLD_SHA, restored script path, last start_pair args, pointer. Sha and start args are strong (mutation A); pointer vacuous (defect 1); five fault sites covered.
- check_mutation_semantic_config_guard (236): OBSERVES exact raise string on the real module then "PASSED" on a key-removed copy. Correct polarity.

## Scratch artefacts

mutants/mutA/, mutants/mutB/, driftcheck/, parent_test.py under the rev96 scratch dir. Nothing in the committed worktree was modified or deleted.
