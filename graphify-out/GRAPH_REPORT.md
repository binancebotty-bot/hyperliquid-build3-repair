# Graph Report - hyperliquid-build3-repair  (2026-10-14)

## Corpus Check
- 100 files · ~383,104 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: .csv 7, .jsonl 5, (none) 3)

## Summary
- 1708 nodes · 5223 edges · 68 communities (60 shown, 8 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 440 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d829fce8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- FixedModeAuthorityConflict
- exchange_truth.py
- self_test
- Architecture Contract — Hyperliquid Build 3 Repair
- load_ui_state
- Operating Protocol
- ENGINE_RESIDUAL_harness_2a269ad.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- atomic_write_json
- HL_Copy_App_SSOT.py
- SenderGateway
- fnum
- main
- utc_now_iso
- load_json
- test_g2_copy_correctness.py
- main
- json
- shutil
- tempfile
- G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)
- HL_Live_Copy_Service_Core.py
- Master Product Invariants and Certification Contract
- fnum
- utc_now_ms
- IntentBuilder
- run_self_test
- Any
- log_error
- get_model_state_cached
- build_live_integrity_status
- main
- UI_harness_fa9d9f55ff.py
- subprocess
- UI_CORRECTION_harness_2d29211.py
- RHC_RESIDUAL_harness_2a269ad.py
- Testnet run handover — 2026-10-09
- ._shared_thread
- Certification (Build 3 Repair)
- time
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- ORDER_CORRECTION_harness_fefc2b04.py
- ENG-015-016-TNF17_harness.py
- hashlib
- census_inv_06_09.py
- DONE10_CORRECTION_harness_4fb8255.py
- main
- ENG-INV-06..09 Non-Vacuous Static Census Report
- ENG-015 / ENG-016 / TN-F17 Certification Report
- RISK_harness_fa9d9f55ff.py
- datetime
- check_fexc016_negative
- check_inc01_positive
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- Project essentials — always in force
- Decisions awaiting the operator
- ENG-005 through ENG-009 Certification Report
- resolve_settlement
- FailingIngestor
- SuccessIngestor
- PRICING_CORRECTION_2d29211148_report.md

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 88 edges
2. `fnum()` - 62 edges
3. `self_test()` - 61 edges
4. `SenderGateway` - 60 edges
5. `run_self_test()` - 60 edges
6. `DryRunLiveCopyService` - 57 edges
7. `utc_now_ms()` - 56 edges
8. `ConfigManager` - 51 edges
9. `ManualLedger` - 46 edges
10. `Intent` - 42 edges

## Surprising Connections (you probably didn't know these)
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `ENG-INV-09: Exchange truth outranks local replay` --references--> `ExchangeReconciler`  [INFERRED]
  certification/results/ENG-INV-06-09_43731b4.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `ENG-INV-08: Startup/recovery truth includes all perp DEX scopes` --references--> `master_userfills_all_dexes()`  [INFERRED]
  certification/results/ENG-INV-06-09_43731b4.md → _archive/hl_stage2/exchange_truth.py
- `ENG-INV-09: Exchange truth outranks local replay` --references--> `resolve_settlement()`  [INFERRED]
  certification/results/ENG-INV-06-09_43731b4.md → _archive/hl_stage2/exchange_truth.py
- `Precise blocker for Architect ruling` --references--> `executable_price_from_fill_payload()`  [INFERRED]
  _archive/hl_stage2/evidence/G4_C2A_MARK_SOURCE_INVENTORY.md → _archive/hl_stage2/HL_Live_Copy_Service.py

## Import Cycles
- None detected.

## Communities (68 total, 8 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (42): append_send_attempt(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places() (+34 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.07
Nodes (15): Trace table, adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), executable_price_from_fill_payload() (+7 more)

### Community 3 - "exchange_truth.py"
Cohesion: 0.13
Nodes (9): apply_env_name_aliases(), claim_network_stamp(), env_with_file(), identity_ok(), network_endpoints(), NetworkConfigError, resolve_networks(), runtime_master_identity() (+1 more)

### Community 4 - "self_test"
Cohesion: 0.11
Nodes (13): append_csv(), classify_ignored_ws_message(), is_benign_ws_error(), is_ws_abnf_frame(), self_test(), fake_fetch(), fake_public_quote(), make_auto_intent() (+5 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.12
Nodes (40): _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_norm(), api_set_ui_state(), api_wallet_meta(), _clean_wallet_config(), _clean_wallet_include() (+32 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.20
Nodes (18): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test(), _build_intent(), check() (+10 more)

### Community 9 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 12 - "atomic_write_json"
Cohesion: 0.21
Nodes (17): atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), invalidate_model_cache(), _live_order_intents_path(), load_local_env_file(), normalise_wallet_for_purge() (+9 more)

### Community 13 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (42): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+34 more)

### Community 14 - "SenderGateway"
Cohesion: 0.07
Nodes (11): classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), Intent, SenderGateway, signed_from_side_size(), stable_hash() (+3 more)

### Community 15 - "fnum"
Cohesion: 0.07
Nodes (54): _append_exchange_history(), avg(), block_num(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), core_missing(), core_td(), css_class() (+46 more)

### Community 16 - "main"
Cohesion: 0.29
Nodes (3): check(), main(), engine()

### Community 17 - "utc_now_iso"
Cohesion: 0.17
Nodes (15): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+7 more)

### Community 18 - "load_json"
Cohesion: 0.12
Nodes (13): atomic_write_json(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), last_csv_row(), load_auto_send_attempt_ids(), load_csv_ids() (+5 more)

### Community 19 - "test_g2_copy_correctness.py"
Cohesion: 0.22
Nodes (4): check(), main(), fresh(), wire_account_net()

### Community 20 - "main"
Cohesion: 0.12
Nodes (14): attach_send_result(), clear_unresolved_send(), _mut(), configure_paths(), persist_unresolved_send(), _mut(), reconcile_unresolved_send(), _state_write() (+6 more)

### Community 21 - "json"
Cohesion: 0.09
Nodes (10): check(), main(), check(), main(), authority_for(), fresh(), wire_account_net(), check() (+2 more)

### Community 22 - "shutil"
Cohesion: 0.06
Nodes (71): LiveCopyCore, main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test() (+63 more)

### Community 23 - "tempfile"
Cohesion: 0.15
Nodes (14): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+6 more)

### Community 24 - "G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3)"
Cohesion: 0.33
Nodes (5): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question

### Community 25 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.06
Nodes (40): acquire_instance_lock(), _append_core_fatal_row(), append_csv(), atomic_write_json(), _attribution_json_safe(), AuditLogWriter, _check(), ensure_dirs() (+32 more)

### Community 26 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (17): 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first), 4.2 Applicability values (+9 more)

### Community 27 - "fnum"
Cohesion: 0.13
Nodes (6): bval(), ConfigManager, CycleSummary, DedupeStore, fnum(), is_valid_wallet()

### Community 28 - "utc_now_ms"
Cohesion: 0.17
Nodes (8): claim_copy_fill_process_marker(), CopyAccountIngestor, CopyFillMatcher, normalise_copy_fill_side(), read_csv_rows(), repair_recovery_copy_fills(), _market_fixture(), utc_now_ms()

### Community 29 - "IntentBuilder"
Cohesion: 0.08
Nodes (19): list_perp_dexes(), master_account_net(), master_exposure(), _post(), rolling_day_pnl(), valid_address(), follower_mid(), IntentBuilder (+11 more)

### Community 30 - "run_self_test"
Cohesion: 0.08
Nodes (11): _manual_sleeve_exists(), canonical_coin_key(), canonical_coin_resolved(), follower_position_mark(), ManualLedger, normalise_wallet(), run_self_test(), _clean_account_fixture() (+3 more)

### Community 31 - "Any"
Cohesion: 0.09
Nodes (46): _account_reconciliation_baseline_timestamp(), active_wallet(), active_wallet_row(), _archive_manual_reconciliation_ledger_row(), _build_account_reconciliation(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance() (+38 more)

### Community 32 - "log_error"
Cohesion: 0.25
Nodes (3): ensure_csv_header(), LeaderFillIngestor, log_error()

### Community 33 - "get_model_state_cached"
Cohesion: 0.18
Nodes (13): api_equity(), api_get_ui_state(), api_metrics(), api_state(), api_trades(), get_live_audit_summary(), get_model_state_cached(), get_wallet_meta() (+5 more)

### Community 34 - "build_live_integrity_status"
Cohesion: 0.14
Nodes (8): build_live_integrity_status(), is_active_row(), is_current_core_row(), is_historical_core_row(), row_ms(), classify_integrity_severity(), load_xyz_position_state(), xyz_state_positions()

### Community 35 - "main"
Cohesion: 0.18
Nodes (5): check(), main(), config(), gate(), wallets()

### Community 36 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.06
Nodes (30): blocked(), check(), HTMLElement, main(), neg_test(), parse_html(), setup_test_env(), SimpleHTMLParser (+22 more)

### Community 37 - "subprocess"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 38 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.07
Nodes (26): blocked(), check(), extract_table_headers(), HTMLElement, main(), neg_test(), parse_html(), parse_ssot_home_table_headers() (+18 more)

### Community 39 - "RHC_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.11
Nodes (20): check(), check_done10_negative(), check_done10_positive(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_positive(), check_fui003_negative() (+12 more)

### Community 40 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 42 - "Certification (Build 3 Repair)"
Cohesion: 0.40
Nodes (4): Certification (Build 3 Repair), Read order for an agent starting here, Regenerating, Rules

### Community 43 - "time"
Cohesion: 0.11
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 44 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 45 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 46 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.13
Nodes (16): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+8 more)

### Community 47 - "hashlib"
Cohesion: 0.11
Nodes (9): sha(), _sha256(), _sha256(), _sha256(), _sha256(), check(), _load_committed_engine(), main() (+1 more)

### Community 48 - "census_inv_06_09.py"
Cohesion: 0.19
Nodes (10): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+2 more)

### Community 49 - "DONE10_CORRECTION_harness_4fb8255.py"
Cohesion: 0.18
Nodes (10): check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live(), main(), neg_test(), run_check() (+2 more)

### Community 50 - "main"
Cohesion: 0.18
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 51 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.15
Nodes (9): _fill_key(), master_userfills(), master_userfills_all_dexes(), ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-09: Exchange truth outranks local replay, File Hashes, Mutation Test Summary (+1 more)

### Community 52 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 53 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 54 - "datetime"
Cohesion: 0.22
Nodes (4): classify(), main(), netloc_ok(), probe_clearinghouse_state()

### Community 55 - "check_fexc016_negative"
Cohesion: 0.21
Nodes (6): check_fexc016_negative(), check_fui002_negative(), check_health001_negative(), check_health001_positive(), mock_ws_summary(), restore_ws_summary()

### Community 56 - "check_inc01_positive"
Cohesion: 0.18
Nodes (6): check_inc01_negative(), check_inc01_positive(), check_inc03_negative(), check_inc03_positive(), mock_exchange_reconciler(), restore_exchange_reconciler()

### Community 57 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 58 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 59 - "Project essentials — always in force"
Cohesion: 0.25
Nodes (7): Controller arrangement — DECLARED, Durable identity, Establish state BEFORE answering, Project essentials — always in force, The rules, This is an EXISTING ACTIVE project, Your ROLE — coordinator, NOT implementer

### Community 60 - "Decisions awaiting the operator"
Cohesion: 0.33
Nodes (5): CLOSED, D-001 — Testnet credentials for physical-fill certification, D-002 — Physical-fill signer does not exist on testnet (credential/account mismatch), Decisions awaiting the operator, OPEN

### Community 62 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DryRunLiveCopyService` connect `DryRunLiveCopyService` to `HL_Live_Copy_Service.py`, `self_test`, `time`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `utc_now_iso`, `load_json`, `main`, `.wallet_gate`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0925589836660617 - nodes in this community are weakly interconnected._
- **Why does `ConfigManager` connect `fnum` to `ENGINE_RESIDUAL_harness_2a269ad.py`, `time`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ORDER_CORRECTION_harness_fefc2b04.py`, `SenderGateway`, `shutil`, `HL_Live_Copy_Service_Core.py`, `Master Product Invariants and Certification Contract`, `run_self_test`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07287784679089027 - nodes in this community are weakly interconnected._
- **Why does `ManualLedger` connect `run_self_test` to `ENGINE_RESIDUAL_harness_2a269ad.py`, `time`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ORDER_CORRECTION_harness_fefc2b04.py`, `SenderGateway`, `shutil`, `HL_Live_Copy_Service_Core.py`, `utc_now_ms`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `exchange_truth.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12631578947368421 - nodes in this community are weakly interconnected._
- **Should `self_test` be split into smaller, more focused modules?**
  _Cohesion score 0.11067193675889328 - nodes in this community are weakly interconnected._