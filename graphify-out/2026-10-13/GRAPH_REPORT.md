# Graph Report - hyperliquid-build3-repair  (2026-10-10)

## Corpus Check
- 26 files · ~205,800 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 2 file(s) not represented in the graph (top: (none) 1, .csv 1)

## Summary
- 1036 nodes · 3275 edges · 43 communities (42 shown, 1 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 148 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `43731b4f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- sleeve_from_leader_event_position
- exchange_truth.py
- self_test
- Architecture Contract — Hyperliquid Build 3 Repair
- load_ui_state
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- json
- HL_Copy_App_SSOT.py
- Any
- Any
- test_g4_order_cap.py
- utc_now_iso
- load_json
- pathlib
- test_g3_exchange_truth.py
- gen_matrix.py
- attach_send_result
- tempfile
- G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)
- HL_Live_Copy_Service_Core.py
- fnum
- ConfigManager
- utc_now_ms
- LeaderFill
- canonical_coin_key
- _live_audit_summary
- run_self_test
- get_model_state_cached
- build_live_integrity_status
- main
- ._process_leader_fill
- global_controls_tests
- test_core_network_and_global_controls.py
- render_chart
- Testnet run handover — 2026-10-09
- ._shared_thread
- Certification (Build 3 Repair)

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 88 edges
2. `fnum()` - 62 edges
3. `self_test()` - 61 edges
4. `run_self_test()` - 60 edges
5. `SenderGateway` - 57 edges
6. `utc_now_ms()` - 56 edges
7. `DryRunLiveCopyService` - 51 edges
8. `build_model_state()` - 37 edges
9. `fnum()` - 34 edges
10. `Intent` - 33 edges

## Surprising Connections (you probably didn't know these)
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Precise blocker for Architect ruling` --references--> `executable_price_from_fill_payload()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `dry_run_intent_audit_decision()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `fetch_public_executable_quote()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py
- `Trace table` --references--> `FixedModeAuthorityConflict`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py

## Import Cycles
- None detected.

## Communities (43 total, 1 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (48): append_send_attempt(), classify_ignored_ws_message(), on_message(), executable_price_from_fill_payload(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since() (+40 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (10): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, fnum(), LeaderFill, LiveWalletConfig, side_from_signed() (+2 more)

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.20
Nodes (5): Trace table, event_authorised_desired_net(), FixedModeAuthorityConflict, proportional_sleeve_scale(), sleeve_from_leader_event_position()

### Community 3 - "exchange_truth.py"
Cohesion: 0.08
Nodes (20): claim_network_stamp(), env_with_file(), _fill_key(), identity_ok(), list_perp_dexes(), master_account_net(), master_exposure(), master_userfills() (+12 more)

### Community 4 - "self_test"
Cohesion: 0.09
Nodes (19): append_csv(), atomic_write_json(), configure_paths(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), last_csv_row(), load_local_env_file() (+11 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.13
Nodes (36): _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_norm(), api_set_ui_state(), api_wallet_meta(), _clean_wallet_config(), _clean_wallet_include() (+28 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "convergence_shadow.py"
Cohesion: 0.35
Nodes (6): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test()

### Community 9 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 12 - "json"
Cohesion: 0.12
Nodes (30): _account_reconciliation_baseline_timestamp(), _archive_manual_reconciliation_ledger_row(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_reconciliation(), _earliest_real_order_filled_ms() (+22 more)

### Community 13 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (41): alignment_status_for_key(), _apply_price_model(), avg(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure() (+33 more)

### Community 14 - "Any"
Cohesion: 0.09
Nodes (9): classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), Intent, _response_text(), send_terminal_state(), SenderGateway (+1 more)

### Community 15 - "Any"
Cohesion: 0.08
Nodes (61): active_wallet(), active_wallet_row(), _append_exchange_history(), block_num(), _build_live_wallet_derived(), contract_money_equal(), core_missing(), core_td() (+53 more)

### Community 16 - "test_g4_order_cap.py"
Cohesion: 0.22
Nodes (3): check(), main(), engine()

### Community 17 - "utc_now_iso"
Cohesion: 0.15
Nodes (14): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_open(), on_ping(), on_pong(), schedule_proactive_recycle() (+6 more)

### Community 18 - "load_json"
Cohesion: 0.20
Nodes (7): audit_notes_for_fill(), ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), load_json(), load_unresolved_sends(), ws_coverage_for_fill()

### Community 19 - "pathlib"
Cohesion: 0.20
Nodes (4): check(), main(), fresh(), wire_account_net()

### Community 20 - "test_g3_exchange_truth.py"
Cohesion: 0.22
Nodes (4): check(), Fixture, reset_master(), with_master()

### Community 21 - "gen_matrix.py"
Cohesion: 0.14
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 22 - "attach_send_result"
Cohesion: 0.28
Nodes (6): attach_send_result(), clear_unresolved_send(), _mut(), persist_unresolved_send(), _mut(), _state_write()

### Community 23 - "tempfile"
Cohesion: 0.21
Nodes (4): check(), main(), check(), main()

### Community 24 - "G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)"
Cohesion: 0.33
Nodes (5): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question

### Community 25 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.07
Nodes (30): acquire_instance_lock(), _append_core_fatal_row(), atomic_write_json(), _attribution_json_safe(), canonical_coin_resolved(), _check(), ensure_csv_header(), ensure_dirs() (+22 more)

### Community 26 - "fnum"
Cohesion: 0.09
Nodes (8): DedupeStore, ExchangeReconciler, fnum(), load_json(), ServiceStateWriter, update_xyz_position_state_from_fills(), xyz_fill_after_position(), xyz_observation_preferred()

### Community 27 - "ConfigManager"
Cohesion: 0.08
Nodes (18): ConfigManager, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+10 more)

### Community 28 - "utc_now_ms"
Cohesion: 0.16
Nodes (9): claim_copy_fill_process_marker(), CopyAccountIngestor, CopyFillMatcher, normalise_copy_fill_side(), read_csv_rows(), repair_recovery_copy_fills(), _market_fixture(), utc_now_ms() (+1 more)

### Community 29 - "LeaderFill"
Cohesion: 0.11
Nodes (6): bval(), follower_mid(), IntentBuilder, is_valid_wallet(), LeaderFill, LeaderFillIngestor

### Community 30 - "canonical_coin_key"
Cohesion: 0.20
Nodes (5): canonical_coin_key(), follower_position_mark(), ManualLedger, normalise_wallet(), repair_flat_ledger_only_positions()

### Community 31 - "_live_audit_summary"
Cohesion: 0.13
Nodes (22): _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_wallet_rows(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), _build_recent_send_warning_groups(), get_live_audit_summary() (+14 more)

### Community 32 - "run_self_test"
Cohesion: 0.11
Nodes (6): LiveCopyCore, main(), run_self_test(), _clean_account_fixture(), _write_csv(), WSManager

### Community 33 - "get_model_state_cached"
Cohesion: 0.16
Nodes (16): api_equity(), api_get_ui_state(), api_metrics(), api_state(), api_trades(), get_model_state_cached(), get_wallet_meta(), home() (+8 more)

### Community 34 - "build_live_integrity_status"
Cohesion: 0.13
Nodes (9): build_live_integrity_status(), is_active_row(), is_current_core_row(), is_historical_core_row(), _manual_sleeve_exists(), row_ms(), classify_integrity_severity(), load_xyz_position_state() (+1 more)

### Community 35 - "main"
Cohesion: 0.16
Nodes (5): check(), main(), config(), gate(), wallets()

### Community 36 - "._process_leader_fill"
Cohesion: 0.23
Nodes (4): append_csv(), AuditLogWriter, CycleSummary, stale_snapshot_replay_reason()

### Community 37 - "global_controls_tests"
Cohesion: 0.24
Nodes (6): global_controls_tests(), config(), decide(), fill(), send(), set_mid()

### Community 38 - "test_core_network_and_global_controls.py"
Cohesion: 0.36
Nodes (5): check(), last_json(), main(), network_tests(), run_py()

### Community 39 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 40 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 42 - "Certification (Build 3 Repair)"
Cohesion: 0.40
Nodes (4): Certification (Build 3 Repair), Read order for an agent starting here, Regenerating, Rules

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fnum()` connect `fnum` to `run_self_test`, `build_live_integrity_status`, `._process_leader_fill`, `Any`, `HL_Live_Copy_Service_Core.py`, `ConfigManager`, `utc_now_ms`, `LeaderFill`, `canonical_coin_key`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09409701928696669 - nodes in this community are weakly interconnected._
- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `utc_now_iso`, `load_json`, `self_test`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07800511508951406 - nodes in this community are weakly interconnected._
- **Why does `SenderGateway` connect `Any` to `run_self_test`, `HL_Live_Copy_Service_Core.py`, `fnum`, `._process_leader_fill`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07564102564102564 - nodes in this community are weakly interconnected._
- **Should `self_test` be split into smaller, more focused modules?**
  _Cohesion score 0.09247311827956989 - nodes in this community are weakly interconnected._