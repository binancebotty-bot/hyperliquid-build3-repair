# Graph Report - hlb3-timeout-recovery-fix-20261020  (2026-10-20)

## Corpus Check
- 276 files · ~561,703 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 13 file(s) not represented in the graph (top: .csv 11, (none) 1, .jsonl 1)

## Summary
- 3407 nodes · 9290 edges · 136 communities (114 shown, 22 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 843 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ba903de8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- sleeve_from_leader_event_position
- main
- Any
- Architecture Contract — Hyperliquid Build 3 Repair
- load_ui_state
- Operating Protocol
- convergence_shadow.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- load_json
- LiveCopyCore
- HL_Live_Copy_Service_Core.py
- HL_Copy_App_SSOT.py
- test_g4_order_cap.py
- utc_now_ms
- sys
- run_self_test
- fnum
- tempfile
- UI_harness_fa9d9f55ff.py
- test_g4_fixed_slices.py
- threading
- json
- Any
- UI_CORRECTION_harness_2d29211.py
- subprocess
- re
- inum
- self_test
- test_core_disk_full.py
- run_report.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- collections
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- test_core_ws_pool_and_slots.py
- tools_memory_profile.py
- pathlib
- HEALTH_CORRECTION_harness_fefc2b04.py
- csv
- ORDER_CORRECTION_harness_fefc2b04.py
- get
- ENG-015-016-TNF17_harness.py
- utc_now_iso
- argparse
- test_cert_scripts.py
- math
- plan_catchup
- main
- test_core_slot_reservation_pacing.py
- ENG-001-004_harness_43731b4f.py
- NLS_RESIDUAL_harness_2a269ad_v4.py
- _fetch_user_realized_pnl_snapshot
- test_screen_run4.py
- NLS_RESIDUAL_harness_2a269ad_v2.py
- NLS_RESIDUAL_harness_2a269ad_v3.py
- probe_reearn.py
- main
- global_controls_tests
- shutil
- Master Product Invariants and Certification Contract
- main
- Detail
- cert_disk_guard.py
- census_inv_06_09.py
- exchange_truth.py
- ConfigManager
- ._decision
- main
- time
- main
- main
- _model_dashboard_response
- IntentBuilder
- main
- test_core_reduce_only_repair.py
- main
- UI_FP_FAIL_harness_09e1258003.py
- HeadroomMonitor
- test_http_keepalive.py
- main
- ENG-INV-06..09 Non-Vacuous Static Census Report
- _row_time_ms
- CTRL_probe_t_967fad56.py
- ENG-015 / ENG-016 / TN-F17 Certification Report
- RISK_harness_fa9d9f55ff.py
- PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)
- TimedLock
- Rows
- test_core_sender_key.py
- test_core_standing_close_guard.py
- test_exchange_truth_retry.py
- test_j2_local_rejects.py
- main
- .wallet_mode
- main
- main
- test_core_tail_read_off_lock.py
- main
- main
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- block_num
- main
- test_core_liq_isolated.py
- test_core_run5_converge.py
- main
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- valid_address
- list_perp_dexes
- Any
- render_chart
- J2 Local Rejects - Proposed Patch Diffs
- main
- test_core_audit_header_cache.py
- test_ui_incremental_summary.py
- test_core_catchup_collapse.py
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- tools/cert — offline halves of the J4 certification gaps (task K2)
- test_core_cap_size_down.py
- Certification (Build 3 Repair)
- Certification run status
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- http_post
- headroom.py
- ENG-005 through ENG-009 Certification Report
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 160 edges
2. `SenderGateway` - 121 edges
3. `utc_now_ms()` - 102 edges
4. `LiveCopyCore` - 81 edges
5. `fnum()` - 76 edges
6. `log_error()` - 73 edges
7. `Intent` - 71 edges
8. `canonical_coin_key()` - 64 edges
9. `self_test()` - 62 edges
10. `ConfigManager` - 61 edges

## Surprising Connections (you probably didn't know these)
- `Evidence from building this (2026-10-11, offline, on this host)` --references--> `read_csv_rows()`  [INFERRED]
  tools/cert/README.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `7. Send path: idempotency, cloid` --references--> `DedupeStore`  [INFERRED]
  process/PORT_VS_REBUILD.crosscheck-hermes.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Row 2 — switch states OFF / CLOSE ONLY / ON` --references--> `_build_live_wallet_rows()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Row 7 — send path (idempotency, cloid)` --references--> `_row_client_id()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py

## Import Cycles
- None detected.

## Communities (136 total, 22 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (45): append_send_attempt(), executable_price_from_fill_payload(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places(), force_fetch_hl_perp_meta() (+37 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.07
Nodes (10): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill (+2 more)

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 3 - "main"
Cohesion: 0.13
Nodes (13): attach_send_result(), clear_unresolved_send(), _mut(), configure_paths(), persist_unresolved_send(), _mut(), _state_write(), check() (+5 more)

### Community 4 - "Any"
Cohesion: 0.03
Nodes (24): post_many(), atomic_write_json(), bval(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), follower_dex_scope() (+16 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.11
Nodes (40): _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_norm(), api_set_ui_state(), api_wallet_meta(), _clean_wallet_config(), _clean_wallet_include() (+32 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "convergence_shadow.py"
Cohesion: 0.40
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

### Community 12 - "load_json"
Cohesion: 0.11
Nodes (28): _account_orphan_signed_size(), _append_exchange_history(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key() (+20 more)

### Community 13 - "LiveCopyCore"
Cohesion: 0.03
Nodes (41): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+33 more)

### Community 14 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.03
Nodes (62): scan_foreign_ws(), acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _attribution_json_safe(), audit_history_paths(), AuditLogWriter (+54 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+31 more)

### Community 16 - "test_g4_order_cap.py"
Cohesion: 0.20
Nodes (3): check(), main(), engine()

### Community 17 - "utc_now_ms"
Cohesion: 0.05
Nodes (35): _adoptable_intent_rows(), alert_unresolved_ambiguous_sends(), canonical_copy_fill_id(), claim_copy_fill_process_marker(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs(), iter_audit_history() (+27 more)

### Community 18 - "sys"
Cohesion: 0.04
Nodes (16): check(), finish(), main(), check(), main(), check(), main(), check() (+8 more)

### Community 19 - "run_self_test"
Cohesion: 0.05
Nodes (17): master_exposure(), follower_position_mark(), guarded(), is_valid_wallet(), LeaderFillIngestor, _read(), ManualLedger, normalise_wallet() (+9 more)

### Community 20 - "fnum"
Cohesion: 0.05
Nodes (33): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row(), is_current_core_row() (+25 more)

### Community 21 - "tempfile"
Cohesion: 0.08
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 22 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.07
Nodes (29): blocked(), check(), HTMLElement, main(), neg_test(), parse_html(), setup_test_env(), SimpleHTMLParser (+21 more)

### Community 24 - "threading"
Cohesion: 0.04
Nodes (16): check(), main(), check(), main(), AlreadyRunning, Audit, slow_append(), Audit (+8 more)

### Community 25 - "json"
Cohesion: 0.06
Nodes (22): Clock, events(), Clock, events(), settle(), check(), main(), main() (+14 more)

### Community 26 - "Any"
Cohesion: 0.08
Nodes (51): _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_top_status(), _build_live_wallet_derived(), _build_live_wallet_rows(), _build_manual_reconciliation_rows(), _build_real_copy_positions() (+43 more)

### Community 27 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.07
Nodes (26): blocked(), check(), extract_table_headers(), HTMLElement, main(), neg_test(), parse_html(), parse_ssot_home_table_headers() (+18 more)

### Community 28 - "subprocess"
Cohesion: 0.06
Nodes (22): git(), load(), main(), record(), sha(), _sha256(), _sha256(), _sha256() (+14 more)

### Community 29 - "re"
Cohesion: 0.06
Nodes (15): sections(), check(), main(), check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live() (+7 more)

### Community 30 - "inum"
Cohesion: 0.08
Nodes (38): _account_card_lines(), active_wallet(), active_wallet_row(), avg(), core_missing(), core_td(), css_class(), dash_td() (+30 more)

### Community 31 - "self_test"
Cohesion: 0.07
Nodes (26): append_csv(), atomic_write_json(), classify_ignored_ws_message(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), extract_ws_fills() (+18 more)

### Community 32 - "test_core_disk_full.py"
Cohesion: 0.06
Nodes (9): fake_open(), PartialThenFull, check(), FakeExchange, _Half, Inject, main(), error_contexts() (+1 more)

### Community 33 - "run_report.py"
Cohesion: 0.08
Nodes (23): check(), main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), build_report(), _f() (+15 more)

### Community 34 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.09
Nodes (20): _match(), resolve_settlement(), add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main() (+12 more)

### Community 35 - "collections"
Cohesion: 0.07
Nodes (17): check(), main(), main(), pick_lane(), as_float(), as_int_ms(), audit_files(), emit() (+9 more)

### Community 36 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (19): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source(), main(), run_negative_mutations() (+11 more)

### Community 37 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.07
Nodes (17): check(), main(), config(), gate(), wallets(), cfg(), WebSocketApp(), build_cfg() (+9 more)

### Community 38 - "tools_memory_profile.py"
Cohesion: 0.09
Nodes (19): main(), make_csv(), measure(), rss_mb(), _addr(), _avail_mb(), build_intents(), build_matcher_stub() (+11 more)

### Community 39 - "pathlib"
Cohesion: 0.13
Nodes (26): exchange_order_calls(), SingleExchangeOrderCallsiteTest, imports_of(), is_b4(), main(), mutate(), prod_files(), scan() (+18 more)

### Community 40 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 41 - "csv"
Cohesion: 0.09
Nodes (10): block_reasons(), classify(), main(), missing_detail(), _rows(), w(), check(), fake_fetcher() (+2 more)

### Community 42 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 43 - "get"
Cohesion: 0.08
Nodes (22): api_equity(), api_get_ui_state(), api_metrics(), api_model_cache_status(), api_state(), api_trades(), ev(), get_live_audit_summary() (+14 more)

### Community 44 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.13
Nodes (16): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+8 more)

### Community 45 - "utc_now_iso"
Cohesion: 0.17
Nodes (16): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+8 more)

### Community 46 - "argparse"
Cohesion: 0.11
Nodes (15): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float() (+7 more)

### Community 47 - "test_cert_scripts.py"
Cohesion: 0.11
Nodes (7): ExportLeaderFills, Gap1OutageClassifier, Gap2MemoryScan, Gap3LiqParity, Gap5DiskGuard, load_module(), run()

### Community 48 - "math"
Cohesion: 0.08
Nodes (8): Ledger, plan(), check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 49 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 50 - "main"
Cohesion: 0.09
Nodes (6): check(), main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 51 - "test_core_slot_reservation_pacing.py"
Cohesion: 0.12
Nodes (7): FakeExchange, RecordingSenderGateway, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order(), VirtualClock

### Community 52 - "ENG-001-004_harness_43731b4f.py"
Cohesion: 0.13
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 53 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 54 - "_fetch_user_realized_pnl_snapshot"
Cohesion: 0.13
Nodes (18): _account_reconciliation_baseline_timestamp(), _build_account_reconciliation(), _build_health_summary(), _build_pnl_tally(), _earliest_real_order_filled_ms(), _engine_run_key(), _fetch_exchange_account_snapshot(), _fetch_user_realized_pnl_snapshot() (+10 more)

### Community 55 - "test_screen_run4.py"
Cohesion: 0.11
Nodes (7): fake_urlopen(), Resp, check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 56 - "NLS_RESIDUAL_harness_2a269ad_v2.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 57 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 58 - "probe_reearn.py"
Cohesion: 0.18
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 59 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 60 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 61 - "shutil"
Cohesion: 0.31
Nodes (14): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+6 more)

### Community 62 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (18): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+10 more)

### Community 63 - "main"
Cohesion: 0.11
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "cert_disk_guard.py"
Cohesion: 0.15
Nodes (16): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later) (+8 more)

### Community 66 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 67 - "exchange_truth.py"
Cohesion: 0.15
Nodes (8): claim_network_stamp(), env_with_file(), network_endpoints(), NetworkConfigError, resolve_networks(), stamp_state_refusal(), state_present(), terminal_reject_evidence()

### Community 69 - "._decision"
Cohesion: 0.13
Nodes (8): Conclusion, ENG-001/002/004 Certification Report, ENG-001 Negative Tests, ENG-002 Negative Tests, ENG-004 Negative Tests, Negative Tests (non-vacuous proof), Oracle: Hyperliquid Testnet API, Safety

### Community 70 - "main"
Cohesion: 0.13
Nodes (6): check(), main(), engine_order(), land(), load_run(), producer()

### Community 71 - "time"
Cohesion: 0.17
Nodes (6): slow(), fetch(), main(), markers(), main(), one()

### Community 72 - "main"
Cohesion: 0.15
Nodes (8): check(), main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 73 - "main"
Cohesion: 0.12
Nodes (6): check(), main(), __init__(), order(), order_status(), order_status_fetcher()

### Community 74 - "_model_dashboard_response"
Cohesion: 0.13
Nodes (13): get_wallet_meta(), _kick_model_cache_refresh_background(), _refresh(), _model_cache_snapshot_nonblocking(), model_dashboard(), _model_dashboard_html_cache_get(), _model_dashboard_html_cache_latest_get(), _model_dashboard_html_cache_store() (+5 more)

### Community 75 - "IntentBuilder"
Cohesion: 0.36
Nodes (13): IntentBuilder, _build_intent(), check(), main(), _make_config(), _make_ledger(), neg_test(), _now_ms() (+5 more)

### Community 76 - "main"
Cohesion: 0.13
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 77 - "test_core_reduce_only_repair.py"
Cohesion: 0.14
Nodes (5): poll_copy_account_fills(), Audit, Ledger, run(), rows()

### Community 78 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 79 - "UI_FP_FAIL_harness_09e1258003.py"
Cohesion: 0.23
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 80 - "HeadroomMonitor"
Cohesion: 0.19
Nodes (3): HeadroomMonitor, _run(), scanner()

### Community 81 - "test_http_keepalive.py"
Cohesion: 0.13
Nodes (3): _Flaky, H, Mon

### Community 82 - "main"
Cohesion: 0.17
Nodes (8): check(), main(), bind_recompute(), fail_recovery_queue(), fill(), gateway(), make_core(), send()

### Community 83 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.15
Nodes (10): _fill_key(), master_userfills(), master_userfills_all_dexes(), ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-08: Startup/recovery truth includes all perp DEX scopes, ENG-INV-09: Exchange truth outranks local replay, File Hashes (+2 more)

### Community 84 - "_row_time_ms"
Cohesion: 0.21
Nodes (11): _fetch_user_fills_by_time(), _fetch_user_fills_cached(), _fetch_user_fills_paged(), _fetch_user_funding_cached(), _fetch_user_funding_paged(), _fill_dedupe_key(), _funding_dedupe_key(), _funding_usdc() (+3 more)

### Community 85 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 86 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 87 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 88 - "PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)"
Cohesion: 0.17
Nodes (8): Common preamble (applies to every gap), GAP-1 · outage recovery, GAP-3 · liquidation parity vs the exchange `liquidationPx`, GAP-4 · realistic-load latency (Phase R), GAP-5 · disk-full robustness, PC run specs for the five certification-matrix gaps (job J4, 2026-10-11), What this job does NOT do, 8. Hot-path latency / prewarm

### Community 90 - "Rows"
Cohesion: 0.18
Nodes (9): 3. Convergence, 4. Dust close, 5. Liquidation parity (+ cross 3x), 6. Ledger repair / ownership, 7. Send path: idempotency, cloid, Bottom line for the Boss condition, Headline, PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory) (+1 more)

### Community 92 - "test_core_standing_close_guard.py"
Cohesion: 0.24
Nodes (4): Audit, guard(), Ledger, plan()

### Community 93 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 95 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 96 - ".wallet_mode"
Cohesion: 0.29
Nodes (6): 2. Switch states OFF / CLOSE ONLY / ON, Evidence-thinness (honest), Headline (3 lines), Model used (named per part), PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes), Row 2 — switch states OFF / CLOSE ONLY / ON

### Community 97 - "main"
Cohesion: 0.24
Nodes (3): check(), main(), wait_for()

### Community 98 - "main"
Cohesion: 0.27
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 100 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 101 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 102 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 103 - "block_num"
Cohesion: 0.31
Nodes (7): block_num(), dd_current(), dd_max(), latest_history_block_dd(), max_history_block_dd(), sorted_rows(), key()

### Community 105 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 108 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 109 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 110 - "valid_address"
Cohesion: 0.25
Nodes (5): identity_ok(), master_account_net(), runtime_master_identity(), _state_payloads(), valid_address()

### Community 111 - "list_perp_dexes"
Cohesion: 0.25
Nodes (4): list_perp_dexes(), _post(), rolling_day_pnl(), _follower_dex_names()

### Community 113 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 117 - "test_ui_incremental_summary.py"
Cohesion: 0.43
Nodes (4): check(), main(), _payload_check(), row()

### Community 122 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 123 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 124 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.29
Nodes (6): Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 126 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 127 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 128 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 129 - "http_post"
Cohesion: 0.40
Nodes (3): http_post(), start_keepalive(), loop()

### Community 131 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

## Knowledge Gaps
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fnum()` connect `fnum` to `Any`, `ConfigManager`, `._decision`, `LiveCopyCore`, `HL_Live_Copy_Service_Core.py`, `utc_now_ms`, `run_self_test`, `Rows`, `Master Product Invariants and Certification Contract`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08700564971751412 - nodes in this community are weakly interconnected._
- **Why does `SenderGateway` connect `Any` to `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ORDER_CORRECTION_harness_fefc2b04.py`, `HL_Live_Copy_Service_Core.py`, `utc_now_ms`, `run_self_test`, `fnum`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07329192546583851 - nodes in this community are weakly interconnected._
- **Why does `LiveCopyCore` connect `LiveCopyCore` to `HL_Live_Copy_Service_Core.py`, `utc_now_ms`, `run_self_test`, `fnum`, `NLS_RESIDUAL_harness_2a269ad_v4.py`, `NLS_RESIDUAL_harness_2a269ad_v2.py`, `NLS_RESIDUAL_harness_2a269ad_v3.py`, `shutil`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `main` be split into smaller, more focused modules?**
  _Cohesion score 0.12648221343873517 - nodes in this community are weakly interconnected._