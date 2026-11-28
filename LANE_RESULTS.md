# Lane results: core invariant test evidence

## Current lane run: 14 core invariant checks

`certification/test_core_invariants.py` is the source-level harness for the 14 numbered invariants in `ARCHITECTURE.md`. Its existing skips for INV-09, INV-10, and INV-14 are explicitly marked `MISSING`; their assertions were not weakened or replaced.

### Count reconciliation

| Evidence | Before correction | After correction |
|---|---:|---:|
| This table | 8 PASS / 0 FAIL / 6 UNKNOWN | 11 PASS / 0 FAIL / 3 MISSING |
| Harness | 11 PASS / 0 FAIL / 3 skipped (MISSING) | 11 PASS / 0 FAIL / 3 skipped (MISSING) |

Root cause: the old table combined current harness results with archived G3 fixture results for INV-09/10 and older source-census classifications for other rows. Those evidence sources do not represent the dedicated current-tree harness. The table below now reports exactly that harness's result for every invariant. Archived fixture runs are not counted as current invariant results.

### Current invariant results

| Invariant | Harness test | Result | Evidence |
|---|---|---|---|
| ENG-INV-01 — One process | `test_inv01_one_process` | **PASS** | Current-tree source guard |
| ENG-INV-02 — Exactly one physical production `.order()` call site | `test_inv02_one_physical_order_callsite` | **PASS** | Current-tree source guard |
| ENG-INV-03 — No unapproved dependency | `test_inv03_no_unapproved_dependency` | **PASS** | Current-tree source guard and approved-dependency list |
| ENG-INV-04 — No new authoritative persistent trading-state store | `test_inv04_only_existing_authoritative_store` | **PASS** | Current-tree source guard |
| ENG-INV-05 — No Build 4 control-plane/platform import | `test_inv05_no_build4_control_plane_import` | **PASS** | Current-tree source guard |
| ENG-INV-06 — No new engine/runtime around Build 3 | `test_inv06_no_second_engine_runtime` | **PASS** | Current-tree source guard |
| ENG-INV-07 — Leader mutable state isolated by `(wallet, coin)` | `test_inv07_leader_mutable_state_scoped_by_wallet_coin` | **PASS** | Current-tree source guard |
| ENG-INV-08 — Startup/recovery truth includes relevant perp DEX scopes; missing scope fails closed | `test_inv08_multidex_truth` | **PASS** | Current-tree source guard |
| ENG-INV-09 — Exchange truth outranks local replay; manual follower-position file is not authoritative | `test_inv09_exchange_truth_beats_manual_position_file` | **MISSING** | Requires replay/recovery against an independent all-DEX exchange-position oracle |
| ENG-INV-10 — API acknowledgement is not settlement; sends need independent MASTER verification | `test_inv10_acknowledgement_is_not_settlement` | **MISSING** | Requires an executed send and independent MASTER-account fill/position oracle |
| ENG-INV-11 — MASTER and signer are distinct; account truth is read from MASTER | `test_inv11_master_and_signer_are_separate` | **PASS** | Current-tree source guard |
| ENG-INV-12 — Convergence moves actual toward desired and preserves unrelated inventory | `test_inv12_convergence_preserves_unrelated_inventory` | **PASS** | Current-tree source guard |
| ENG-INV-13 — Restart/recovery snapshots establish truth for verification only and create zero trade authority | `test_inv13_restart_snapshot_creates_no_trade_authority` | **PASS** | Current-tree source guard |
| ENG-INV-14 — No mainnet/LIVE activation without explicit approval | `test_inv14_no_live_activation_without_explicit_approval` | **MISSING** | Requires an observed LIVE activation attempt and explicit-approval oracle |

These 11 passes are source-level checks, not live exchange certification. INV-09, INV-10, and INV-14 remain MISSING because their required independent runtime or approval oracles were not available. No exchange writes, LIVE/mainnet activation, or deployment were performed.

### Exact commands and results

The first two commands were run before opening repository source. The graphify wrapper could not be used because it invokes `python`, which is not on PATH. Invoking the graphify query script with the installed Python succeeded, but its fallback graph was stale and unrelated to this clone; `explain` returned no matching file.

| Command | Result |
|---|---|
| `& 'C:/Users/wigmore/AppData/Roaming/uv/python/cpython-3.14-windows-x86_64-none/python.exe' 'C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py' query invariant` | Completed before source browsing; returned unrelated bridge graph entries. |
| `& 'C:/Users/wigmore/AppData/Roaming/uv/python/cpython-3.14-windows-x86_64-none/python.exe' 'C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py' explain certification/test_core_invariants.py` | Completed before source browsing; no matching file explanation. |
| `& 'C:/Users/wigmore/AppData/Roaming/uv/python/cpython-3.14-windows-x86_64-none/python.exe' certification/test_core_invariants.py` — before documentation correction | **14 run; 11 passed; 0 failed; 3 skipped (MISSING)**. |
| `& 'C:/Users/wigmore/AppData/Roaming/uv/python/cpython-3.14-windows-x86_64-none/python.exe' certification/test_core_invariants.py` — after documentation correction | **14 run; 11 passed; 0 failed; 3 skipped (MISSING)**. |

The count discrepancy is corrected in this document only; the existing harness already had explicit MISSING skips for all three blocked invariants. The installed Python 3.14 executable was used because the `python` launcher is absent from PATH. The local `graphify-out` index is unavailable, and the graphify fallback is unrelated, so graph-index coverage is a tooling blocker.
