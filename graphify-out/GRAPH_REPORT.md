# Graph Report - hl-build3-startup-script-6370312203  (2026-10-23)

## Corpus Check
- 280 files · ~562,931 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3446 nodes · 9385 edges · 145 communities (123 shown, 22 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 834 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `88ce5c67`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pathlib
- Any
- HL_Live_Copy_Service_Core.py
- DryRunLiveCopyService
- HL_Copy_App_SSOT.py
- tempfile
- UI_FP_FAIL_harness_09e1258003.py
- HL_Live_Copy_Service.py
- re
- utc_now_ms
- testnet_startup.py
- LiveCopyCore
- ENGINE_RESIDUAL_harness_2a269ad.py
- Intent
- build_live_integrity_status
- IntentBuilder
- json
- fnum
- main
- UI_harness_fa9d9f55ff.py
- render_home
- Any
- _live_audit_summary_full
- load_ui_state
- UI_CORRECTION_harness_2d29211.py
- read_csv_rows
- Any
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- test_core_ws_pool_and_slots.py
- subprocess
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- HEALTH_CORRECTION_harness_fefc2b04.py
- _load_live_copy_config
- run_self_test
- test_core_standing_close_guard.py
- ORDER_CORRECTION_harness_fefc2b04.py
- ENG-015-016-TNF17_harness.py
- utc_now_ms
- utc_now_iso
- threading
- test_screen_run4.py
- run_report.py
- plan_catchup
- _fetch_paged_cached
- DONE10_CORRECTION_harness_4fb8255.py
- PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)
- main
- tools_memory_profile.py
- ENG-001-004_harness_43731b4f.py
- Path
- fnum
- NLS_RESIDUAL_harness_2a269ad_v4.py
- main
- probe_reearn.py
- collections
- main
- ast
- NLS_RESIDUAL_harness_2a269ad_v2.py
- NLS_RESIDUAL_harness_2a269ad_v3.py
- main
- shutil
- Detail
- census_inv_06_09.py
- exchange_truth.py
- main
- FakeExchange
- cert_liq_parity_offline.py
- Master Product Invariants and Certification Contract
- HTMLElement
- main
- main
- time
- HTMLElement
- Architecture Contract — Hyperliquid Build 3 Repair
- sleeve_from_leader_event_position
- main
- main
- main
- argparse
- main
- CTRL_probe_t_967fad56.py
- test_cert_scripts.py
- ENG-015 / ENG-016 / TN-F17 Certification Report
- _LatestStatusWriteWorker
- PRICING_CORRECTION_harness_2f57dba50f.py
- _model_dashboard_response
- TimedLock
- math
- global_controls_tests
- csv
- Operating Protocol
- hashlib
- test_exchange_truth_retry.py
- main
- cert_disk_guard.py
- test_core_append_truncate.py
- main
- main
- main
- test_j2_local_rejects.py
- main
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- main
- main
- test_core_liq_isolated.py
- test_core_sender_key.py
- sys
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)
- test_g4_fixed_slices.py
- J2 Local Rejects - Proposed Patch Diffs
- main
- test_core_audit_header_cache.py
- test_g4_ui_controls.py
- test_g4_order_cap.py
- test_ui_incremental_summary.py
- card_hygiene.py
- test_core_outage_replay.py
- test_core_tail_read_off_lock.py
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Testnet run handover — 2026-10-09
- tools/cert — offline halves of the J4 certification gaps (task K2)
- CTRL_probe3_t_967fad56.py
- test_core_run5_converge.py
- test_core_send_lock_isolation.py
- Bootstrap
- Certification (Build 3 Repair)
- test_core_send_mode_fails_closed.py
- Certification run status
- verify_js_reference
- Hyperliquid Build 3 Repair
- PRIOR_ART.md
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- verify_api_endpoint
- STARTUP.md

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 156 edges
2. `SenderGateway` - 111 edges
3. `utc_now_ms()` - 100 edges
4. `LiveCopyCore` - 80 edges
5. `fnum()` - 76 edges
6. `log_error()` - 70 edges
7. `Intent` - 64 edges
8. `self_test()` - 62 edges
9. `canonical_coin_key()` - 62 edges
10. `ConfigManager` - 61 edges

## Surprising Connections (you probably didn't know these)
- `Evidence from building this (2026-10-11, offline, on this host)` --references--> `read_csv_rows()`  [INFERRED]
  tools/cert/README.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `Row 6 — ledger repair / ownership` --references--> `_has_pending_exit_guard_proof()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Sources & method` --references--> `_live_audit_summary()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Row 2 — switch states OFF / CLOSE ONLY / ON` --references--> `_build_live_wallet_rows()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py

## Import Cycles
- None detected.

## Communities (145 total, 22 thin omitted)

### Community 0 - "pathlib"
Cohesion: 0.05
Nodes (14): check(), check(), check(), check(), main(), imports_of(), is_b4(), main() (+6 more)

### Community 1 - "Any"
Cohesion: 0.03
Nodes (18): post_many(), atomic_write_json(), bval(), classify_reject_category(), _exchange_accepts_cloid(), follower_dex_scope(), generate_attempt_id(), generate_cloid() (+10 more)

### Community 2 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.03
Nodes (73): scan_foreign_ws(), acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _attribution_json_safe(), audit_history_paths(), _BoundedRaw (+65 more)

### Community 3 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (10): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill (+2 more)

### Community 4 - "HL_Copy_App_SSOT.py"
Cohesion: 0.06
Nodes (54): alignment_status_for_key(), _apply_price_model(), avg(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure() (+46 more)

### Community 5 - "tempfile"
Cohesion: 0.08
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 6 - "UI_FP_FAIL_harness_09e1258003.py"
Cohesion: 0.23
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 7 - "HL_Live_Copy_Service.py"
Cohesion: 0.07
Nodes (31): atomic_write_json(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), fixed_notional_buffered_cap(), floor_decimal_to_places(), get_wallet_live_config() (+23 more)

### Community 8 - "re"
Cohesion: 0.07
Nodes (11): block_reasons(), classify(), main(), missing_detail(), _rows(), check(), sections(), check() (+3 more)

### Community 9 - "utc_now_ms"
Cohesion: 0.11
Nodes (11): claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, normalise_copy_fill_side(), repair_recovery_copy_fills(), utc_now_ms(), 3. Verdict per suspect (prove / disprove) (+3 more)

### Community 10 - "testnet_startup.py"
Cohesion: 0.15
Nodes (36): acquire_supervisor_lock(), check_source(), coin_key(), collect(), collect_core_only(), core_running(), evaluate(), evaluate_core() (+28 more)

### Community 11 - "LiveCopyCore"
Cohesion: 0.04
Nodes (40): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+32 more)

### Community 12 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.05
Nodes (27): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test(), CountingRequests, HeadroomMonitor (+19 more)

### Community 13 - "Intent"
Cohesion: 0.08
Nodes (12): canonical_coin_key(), classify_operator_action(), classify_send_lifecycle(), classify_terminal_state(), Intent, send_terminal_state(), stable_hash(), intent() (+4 more)

### Community 14 - "build_live_integrity_status"
Cohesion: 0.10
Nodes (14): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row(), is_current_core_row() (+6 more)

### Community 15 - "IntentBuilder"
Cohesion: 0.06
Nodes (20): list_perp_dexes(), master_exposure(), _follower_dex_names(), follower_mid(), stale(), follower_position_mark(), IntentBuilder, guarded() (+12 more)

### Community 16 - "json"
Cohesion: 0.14
Nodes (13): Clock, events(), main(), main(), route_present(), check_hwm(), check_i1(), check_i3() (+5 more)

### Community 17 - "fnum"
Cohesion: 0.07
Nodes (10): _chain_sorted(), collapse_stale_runs(), close_run(), ConfigManager, fnum(), load_json(), ServiceStateWriter, 2. Switch states OFF / CLOSE ONLY / ON (+2 more)

### Community 18 - "main"
Cohesion: 0.08
Nodes (9): check(), FakeExchange, _Half, Inject, main(), error_contexts(), errors(), hold_runtime_state_lock() (+1 more)

### Community 19 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.11
Nodes (25): blocked(), check(), main(), neg_test(), parse_html(), setup_test_env(), test_engine_integrity(), test_inc() (+17 more)

### Community 20 - "render_home"
Cohesion: 0.13
Nodes (23): _account_card_lines(), css_class(), dash_td(), dual(), fmt_dual_or_dash(), fmt_money_or_dash(), fmt_x_or_dash(), format_dd() (+15 more)

### Community 21 - "Any"
Cohesion: 0.08
Nodes (39): active_wallet(), active_wallet_row(), block_num(), _build_execution_quality_rows(), _build_live_top_status(), _build_live_wallet_rows(), core_missing(), core_td() (+31 more)

### Community 22 - "_live_audit_summary_full"
Cohesion: 0.08
Nodes (35): _account_orphan_signed_size(), _account_reconciliation_baseline_timestamp(), _append_exchange_history(), atomic_write_json(), _build_account_orphan_registry(), _build_account_reconciliation(), _build_execution_quality_summary(), _build_health_summary() (+27 more)

### Community 23 - "load_ui_state"
Cohesion: 0.11
Nodes (31): admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics(), api_model_cache_status(), api_norm(), api_set_ui_state(), api_trades() (+23 more)

### Community 24 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.12
Nodes (23): blocked(), check(), main(), neg_test(), parse_html(), parse_ssot_home_table_headers(), parse_ssot_table_headers(), setup_test_env() (+15 more)

### Community 25 - "read_csv_rows"
Cohesion: 0.07
Nodes (16): _adoptable_intent_rows(), ExchangeReconciler, _owned_note(), prof, read_csv_rows(), _market_fixture(), send_attempt_rows(), update_send_attempt_row() (+8 more)

### Community 26 - "Any"
Cohesion: 0.08
Nodes (33): classify_ignored_ws_message(), executable_price_from_fill_payload(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_public_executable_quote(), force_fetch_hl_perp_meta(), get_hl_perp_meta_by_coin(), inum() (+25 more)

### Community 27 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (19): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source(), main(), run_negative_mutations() (+11 more)

### Community 28 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.07
Nodes (16): main(), config(), gate(), wallets(), cfg(), WebSocketApp(), build_cfg(), check() (+8 more)

### Community 29 - "subprocess"
Cohesion: 0.22
Nodes (7): g(), blob(), census(), blob(), calls_in(), head(), main()

### Community 30 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 31 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 32 - "_load_live_copy_config"
Cohesion: 0.14
Nodes (27): _active_live_copy_wallet_count(), add_live_config_wallet(), api_state(), _enforce_live_copy_cap(), _engine_wallet_summary(), _execution_guards_info(), ev(), get_global_controls() (+19 more)

### Community 33 - "run_self_test"
Cohesion: 0.06
Nodes (20): AuditLogWriter, canonical_copy_fill_id(), ensure_dirs(), ManualLedger, normalise_wallet(), _read_all_copy_fills(), repair_adopt_oids(), repair_flat_ledger_only_positions() (+12 more)

### Community 34 - "test_core_standing_close_guard.py"
Cohesion: 0.24
Nodes (4): Audit, guard(), Ledger, plan()

### Community 35 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 36 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.14
Nodes (15): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+7 more)

### Community 37 - "utc_now_ms"
Cohesion: 0.13
Nodes (19): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+11 more)

### Community 38 - "utc_now_iso"
Cohesion: 0.16
Nodes (12): append_csv(), append_send_attempt(), fetch_live_fills_range(), fetch_live_fills_since(), load_json(), load_manual_live_positions(), safe_atomic_write_json(), save_manual_live_positions() (+4 more)

### Community 39 - "threading"
Cohesion: 0.06
Nodes (12): check(), main(), slow_append(), slow(), Audit, me(), w(), check() (+4 more)

### Community 40 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 41 - "run_report.py"
Cohesion: 0.07
Nodes (29): main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), check(), main(), neg_test() (+21 more)

### Community 42 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 43 - "_fetch_paged_cached"
Cohesion: 0.18
Nodes (13): _fetch_paged_cached(), _fetch_user_fills_by_time(), _fetch_user_fills_cached(), _fetch_user_fills_paged(), _fetch_user_funding_cached(), _fetch_user_funding_paged(), _fill_dedupe_key(), _funding_dedupe_key() (+5 more)

### Community 44 - "DONE10_CORRECTION_harness_4fb8255.py"
Cohesion: 0.18
Nodes (10): check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live(), main(), neg_test(), run_check() (+2 more)

### Community 45 - "PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)"
Cohesion: 0.50
Nodes (3): Bottom line for the Boss condition, Headline, PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)

### Community 46 - "main"
Cohesion: 0.04
Nodes (16): fill(), run(), Audit, fill(), check(), main(), engine_order(), land() (+8 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.09
Nodes (19): main(), make_csv(), measure(), rss_mb(), _addr(), _avail_mb(), build_intents(), build_matcher_stub() (+11 more)

### Community 48 - "ENG-001-004_harness_43731b4f.py"
Cohesion: 0.13
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 49 - "Path"
Cohesion: 0.17
Nodes (18): atomic_write_csv(), _atomic_write_json(), backup_purge_files(), _csv_cache_key(), invalidate_model_cache(), _live_order_intents_path(), load_local_env_file(), _model_dashboard_html_cache_store() (+10 more)

### Community 50 - "fnum"
Cohesion: 0.13
Nodes (23): _build_live_leader_performance(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), _classify_owned_exchange_net(), _exchange_field(), _exchange_signed_size(), fnum() (+15 more)

### Community 51 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 52 - "main"
Cohesion: 0.11
Nodes (14): attach_send_result(), clear_unresolved_send(), _mut(), configure_paths(), load_unresolved_sends(), persist_unresolved_send(), _mut(), reconcile_unresolved_send() (+6 more)

### Community 53 - "probe_reearn.py"
Cohesion: 0.17
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 54 - "collections"
Cohesion: 0.14
Nodes (12): as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows(), rows(), classify() (+4 more)

### Community 55 - "main"
Cohesion: 0.10
Nodes (5): main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 56 - "ast"
Cohesion: 0.13
Nodes (21): RecordingSenderGateway, exchange_order_calls(), SingleExchangeOrderCallsiteTest, baseline_deps(), closure(), dyn_imports(), git_show(), imports_of() (+13 more)

### Community 57 - "NLS_RESIDUAL_harness_2a269ad_v2.py"
Cohesion: 0.26
Nodes (16): utc_now_iso(), certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check() (+8 more)

### Community 58 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 59 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 60 - "shutil"
Cohesion: 0.31
Nodes (14): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+6 more)

### Community 61 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 62 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 63 - "exchange_truth.py"
Cohesion: 0.07
Nodes (24): claim_network_stamp(), env_with_file(), _fill_key(), http_post(), identity_ok(), master_account_net(), master_userfills(), master_userfills_all_dexes() (+16 more)

### Community 64 - "main"
Cohesion: 0.15
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 65 - "FakeExchange"
Cohesion: 0.13
Nodes (6): FakeExchange, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order(), VirtualClock

### Community 66 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 67 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (18): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+10 more)

### Community 68 - "HTMLElement"
Cohesion: 0.12
Nodes (3): HTMLElement, SimpleHTMLParser, verify_html_element()

### Community 69 - "main"
Cohesion: 0.13
Nodes (4): main(), _note_read_on_current(), slow(), fetch()

### Community 70 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 71 - "time"
Cohesion: 0.12
Nodes (9): Clock, events(), settle(), main(), fetch(), main(), markers(), main() (+1 more)

### Community 72 - "HTMLElement"
Cohesion: 0.13
Nodes (3): extract_table_headers(), HTMLElement, SimpleHTMLParser

### Community 73 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 74 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 75 - "main"
Cohesion: 0.14
Nodes (4): main(), _note_read_on_current(), slow(), fetch()

### Community 76 - "main"
Cohesion: 0.18
Nodes (7): main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 77 - "main"
Cohesion: 0.18
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 78 - "argparse"
Cohesion: 0.21
Nodes (7): decide(), main(), measure(), rss_mb(), main(), post(), wallets()

### Community 79 - "main"
Cohesion: 0.14
Nodes (3): main(), __init__(), order()

### Community 80 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 81 - "test_cert_scripts.py"
Cohesion: 0.11
Nodes (7): ExportLeaderFills, Gap1OutageClassifier, Gap2MemoryScan, Gap3LiqParity, Gap5DiskGuard, load_module(), run()

### Community 82 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 84 - "PRICING_CORRECTION_harness_2f57dba50f.py"
Cohesion: 0.19
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 85 - "_model_dashboard_response"
Cohesion: 0.20
Nodes (9): _kick_model_cache_refresh_background(), _refresh(), _model_cache_snapshot_nonblocking(), model_dashboard(), _model_dashboard_html_cache_get(), _model_dashboard_html_cache_latest_get(), _model_dashboard_last_good_html_disk_get(), _model_dashboard_response() (+1 more)

### Community 87 - "math"
Cohesion: 0.16
Nodes (5): p90(), Ledger, plan(), p90(), p90()

### Community 88 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 89 - "csv"
Cohesion: 0.21
Nodes (4): check(), fake_fetcher(), w(), main()

### Community 90 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 91 - "hashlib"
Cohesion: 0.18
Nodes (5): sha(), _sha256(), _sha256(), _sha256(), _sha256()

### Community 92 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 93 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 94 - "cert_disk_guard.py"
Cohesion: 0.15
Nodes (16): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later) (+8 more)

### Community 97 - "main"
Cohesion: 0.24
Nodes (3): check(), main(), wait_for()

### Community 98 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 100 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 101 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 102 - "main"
Cohesion: 0.27
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 104 - "main"
Cohesion: 0.28
Nodes (3): check(), finish(), main()

### Community 105 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 106 - "test_core_sender_key.py"
Cohesion: 0.18
Nodes (3): check(), main(), wait_for_json_file()

### Community 107 - "sys"
Cohesion: 0.05
Nodes (15): check(), main(), check(), main(), check(), main(), check(), main() (+7 more)

### Community 108 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 109 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 110 - "PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)"
Cohesion: 0.25
Nodes (7): Common preamble (applies to every gap), GAP-1 · outage recovery, GAP-3 · liquidation parity vs the exchange `liquidationPx`, GAP-4 · realistic-load latency (Phase R), GAP-5 · disk-full robustness, PC run specs for the five certification-matrix gaps (job J4, 2026-10-11), What this job does NOT do

### Community 112 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 116 - "test_g4_order_cap.py"
Cohesion: 0.20
Nodes (3): check(), main(), engine()

### Community 117 - "test_ui_incremental_summary.py"
Cohesion: 0.43
Nodes (4): check(), main(), _payload_check(), row()

### Community 118 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 120 - "test_core_tail_read_off_lock.py"
Cohesion: 0.11
Nodes (4): Probe, probing_open(), fake_urlopen(), Resp

### Community 122 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 123 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 124 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 125 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 126 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.29
Nodes (6): Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 127 - "CTRL_probe3_t_967fad56.py"
Cohesion: 0.53
Nodes (4): git(), load(), main(), record()

### Community 130 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 131 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 132 - "test_core_send_mode_fails_closed.py"
Cohesion: 0.60
Nodes (4): check(), main(), fresh(), write()

### Community 133 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 135 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 137 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

### Community 138 - "Mainnet crash and ambiguous-send recovery"
Cohesion: 0.50
Nodes (3): After a crash or uncertain send, Mainnet crash and ambiguous-send recovery, Wallet-roster changes

## Knowledge Gaps
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `Any` to `run_self_test`, `HL_Live_Copy_Service_Core.py`, `ORDER_CORRECTION_harness_fefc2b04.py`, `Intent`, `fnum`, `read_csv_rows`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Should `pathlib` be split into smaller, more focused modules?**
  _Cohesion score 0.0480225988700565 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `fnum` to `run_self_test`, `HL_Live_Copy_Service_Core.py`, `Master Product Invariants and Certification Contract`, `Any`, `utc_now_ms`, `LiveCopyCore`, `Intent`, `build_live_integrity_status`, `IntentBuilder`, `read_csv_rows`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Should `Any` be split into smaller, more focused modules?**
  _Cohesion score 0.03430299238869774 - nodes in this community are weakly interconnected._
- **Why does `LiveCopyCore` connect `LiveCopyCore` to `run_self_test`, `HL_Live_Copy_Service_Core.py`, `utc_now_ms`, `Intent`, `fnum`, `NLS_RESIDUAL_harness_2a269ad_v4.py`, `NLS_RESIDUAL_harness_2a269ad_v2.py`, `NLS_RESIDUAL_harness_2a269ad_v3.py`, `shutil`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service_Core.py` be split into smaller, more focused modules?**
  _Cohesion score 0.025810795645830994 - nodes in this community are weakly interconnected._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.08408249603384453 - nodes in this community are weakly interconnected._