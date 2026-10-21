# Graph Report - hl-build3-dust-retest-20261021  (2026-10-21)

## Corpus Check
- 284 files · ~569,199 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3499 nodes · 9486 edges · 152 communities (125 shown, 27 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 845 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2674a9d5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- sleeve_from_leader_event_position
- main
- SenderGateway
- Architecture Contract — Hyperliquid Build 3 Repair
- load_ui_state
- Operating Protocol
- headroom.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- Path
- LiveCopyCore
- HL_Live_Copy_Service_Core.py
- HL_Copy_App_SSOT.py
- WSManager
- threading
- sys
- DedupeStore
- build_live_integrity_status
- UI_harness_fa9d9f55ff.py
- tempfile
- HEALTH_CORRECTION_harness_fefc2b04.py
- cert_liq_parity_offline.py
- json
- UI_CORRECTION_harness_2d29211.py
- Any
- outage_classify.py
- fnum
- Any
- _live_audit_summary_full
- run_self_test
- self_test
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- time
- main
- main
- csv
- test_core_audit_append_never_drops.py
- test_core_ws_pool_and_slots.py
- IntentBuilder
- _load_live_copy_config
- ORDER_CORRECTION_harness_fefc2b04.py
- read_csv_rows
- ENG-015-016-TNF17_harness.py
- utc_now_iso
- tools_memory_profile.py
- run
- plan_catchup
- ENG-001-004_harness_43731b4f.py
- render_chart
- NLS_RESIDUAL_harness_2a269ad_v4.py
- ConfigManager
- main
- collections
- NLS_RESIDUAL_harness_2a269ad_v2.py
- NLS_RESIDUAL_harness_2a269ad_v3.py
- probe_reearn.py
- exchange_truth.py
- shutil
- Master Product Invariants and Certification Contract
- ENGINE_RESIDUAL_harness_2a269ad.py
- test_core_slot_reservation_pacing.py
- Detail
- main
- RISK_harness_fa9d9f55ff.py
- census_inv_06_09.py
- pathlib
- Inject
- main
- main
- test_http_keepalive.py
- subprocess
- main
- main
- main
- UI_FP_FAIL_harness_09e1258003.py
- test_core_audit_reduce_only_matches_wire.py
- main
- global_controls_tests
- test_screen_run4.py
- math
- CTRL_probe_t_967fad56.py
- test_g2_copy_correctness.py
- ENG-015 / ENG-016 / TN-F17 Certification Report
- main
- main
- DONE10_CORRECTION_harness_4fb8255.py
- test_core_reduce_only_repair.py
- hashlib
- TimedLock
- main
- test_cert_scripts.py
- test_exchange_truth_retry.py
- main
- Rows
- argparse
- PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)
- test_core_queue_timing_stamps.py
- main
- main
- _model_dashboard_response
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- _post
- _LatestStatusWriteWorker
- main
- test_core_liq_isolated.py
- main
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- os
- PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)
- J2 Local Rejects - Proposed Patch Diffs
- list_perp_dexes
- AppendFail
- test_core_clo_dispatch_prefilter.py
- tools/cert — offline halves of the J4 certification gaps (task K2)
- test_core_append_truncate.py
- test_core_audit_header_cache.py
- test_core_run5_converge.py
- test_core_tail_read_off_lock.py
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- test_j2_local_rejects.py
- .test_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders
- Certification (Build 3 Repair)
- Certification run status
- probe_ui_routes_t_cfcad924.py
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- test_ui_incremental_summary.py
- test_single_exchange_order_callsite.py
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- _Half
- test_core_outage_replay.py
- test_g4_order_cap.py
- convergence_shadow.py
- test_core_standing_close_guard.py
- test_spot_gate_refusal.py
- test_g4_fixed_slices.py
- Gap2MemoryScan
- valid_address
- fnum
- test_core_send_mode_fails_closed.py
- FakeExchange

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 158 edges
2. `SenderGateway` - 113 edges
3. `utc_now_ms()` - 103 edges
4. `LiveCopyCore` - 83 edges
5. `fnum()` - 76 edges
6. `log_error()` - 72 edges
7. `Intent` - 66 edges
8. `ConfigManager` - 63 edges
9. `self_test()` - 62 edges
10. `canonical_coin_key()` - 62 edges

## Surprising Connections (you probably didn't know these)
- `Evidence from building this (2026-10-11, offline, on this host)` --references--> `read_csv_rows()`  [INFERRED]
  tools/cert/README.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `Row 6 — ledger repair / ownership` --references--> `_has_pending_exit_guard_proof()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `7. Send path: idempotency, cloid` --references--> `DedupeStore`  [INFERRED]
  process/PORT_VS_REBUILD.crosscheck-hermes.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Sources & method` --references--> `_live_audit_summary()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py

## Import Cycles
- None detected.

## Communities (152 total, 27 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (47): append_send_attempt(), executable_price_from_fill_payload(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places(), force_fetch_hl_perp_meta() (+39 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.07
Nodes (11): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill (+3 more)

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 3 - "main"
Cohesion: 0.13
Nodes (13): attach_send_result(), clear_unresolved_send(), _mut(), configure_paths(), persist_unresolved_send(), _mut(), _state_write(), check() (+5 more)

### Community 4 - "SenderGateway"
Cohesion: 0.03
Nodes (27): post_many(), atomic_write_json(), bval(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), generate_attempt_id() (+19 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.09
Nodes (37): admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics(), api_model_cache_status(), api_norm(), api_set_ui_state(), api_trades() (+29 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "headroom.py"
Cohesion: 0.08
Nodes (9): CountingRequests, HeadroomMonitor, _run(), info_weight(), level_for(), Clock, events(), scanner() (+1 more)

### Community 9 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 12 - "Path"
Cohesion: 0.13
Nodes (24): _account_orphan_signed_size(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key(), invalidate_model_cache() (+16 more)

### Community 13 - "LiveCopyCore"
Cohesion: 0.04
Nodes (36): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+28 more)

### Community 14 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.04
Nodes (67): scan_foreign_ws(), acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _append_spill_journal(), _attribution_json_safe(), audit_history_paths() (+59 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), avg(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure() (+31 more)

### Community 16 - "WSManager"
Cohesion: 0.11
Nodes (4): LeaderFillIngestor, WSManager, on_message(), on_open()

### Community 17 - "threading"
Cohesion: 0.05
Nodes (15): check(), main(), check(), slow_append(), slow(), Audit, me(), w() (+7 more)

### Community 18 - "sys"
Cohesion: 0.04
Nodes (16): check(), main(), check(), finish(), main(), check(), main(), check() (+8 more)

### Community 20 - "build_live_integrity_status"
Cohesion: 0.10
Nodes (12): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row() (+4 more)

### Community 21 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.06
Nodes (30): blocked(), check(), HTMLElement, main(), neg_test(), parse_html(), setup_test_env(), SimpleHTMLParser (+22 more)

### Community 22 - "tempfile"
Cohesion: 0.07
Nodes (33): main(), check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive() (+25 more)

### Community 23 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 24 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 25 - "json"
Cohesion: 0.09
Nodes (16): Clock, events(), fake_urlopen(), Resp, main(), main(), main(), route_present() (+8 more)

### Community 26 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.07
Nodes (26): blocked(), check(), extract_table_headers(), HTMLElement, main(), neg_test(), parse_html(), parse_ssot_home_table_headers() (+18 more)

### Community 27 - "Any"
Cohesion: 0.07
Nodes (23): _adoptable_intent_rows(), canonical_copy_fill_id(), claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs(), normalise_copy_fill_side() (+15 more)

### Community 28 - "outage_classify.py"
Cohesion: 0.14
Nodes (6): block_reasons(), classify(), main(), missing_detail(), _rows(), Audit

### Community 29 - "fnum"
Cohesion: 0.08
Nodes (47): _account_card_lines(), active_wallet(), _append_exchange_history(), block_num(), core_missing(), core_td(), css_class(), dd_current() (+39 more)

### Community 30 - "Any"
Cohesion: 0.09
Nodes (40): _build_live_leader_performance(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), build_portfolio_history(), _build_real_copy_positions(), _classify_owned_exchange_net(), compact_history(), contract_money_equal() (+32 more)

### Community 31 - "_live_audit_summary_full"
Cohesion: 0.06
Nodes (42): _account_reconciliation_baseline_timestamp(), active_wallet_row(), _build_account_reconciliation(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_health_summary(), _build_live_top_status(), _build_live_wallet_rows() (+34 more)

### Community 32 - "run_self_test"
Cohesion: 0.07
Nodes (17): AuditLogWriter, _coin_key_map(), _exchange_accepts_cloid(), load_json(), ManualLedger, run_self_test(), _clean_account_fixture(), order() (+9 more)

### Community 33 - "self_test"
Cohesion: 0.07
Nodes (24): append_csv(), atomic_write_json(), classify_ignored_ws_message(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), extract_ws_fills() (+16 more)

### Community 34 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (21): _match(), resolve_settlement(), add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source() (+13 more)

### Community 35 - "time"
Cohesion: 0.11
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 36 - "main"
Cohesion: 0.17
Nodes (6): check(), main(), error_contexts(), errors(), hold_runtime_state_lock(), wait_for_json_file()

### Community 37 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 38 - "csv"
Cohesion: 0.06
Nodes (23): _durable_row(), _fixed_intents(), w(), check(), fake_fetcher(), w(), build_report(), _f() (+15 more)

### Community 39 - "test_core_audit_append_never_drops.py"
Cohesion: 0.07
Nodes (4): fill(), run(), Audit, fill()

### Community 40 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.06
Nodes (19): main(), config(), gate(), wallets(), cfg(), check(), main(), WebSocketApp() (+11 more)

### Community 41 - "IntentBuilder"
Cohesion: 0.11
Nodes (11): IntentBuilder, is_spot_pair(), Conclusion, ENG-001/002/004 Certification Report, ENG-001 Negative Tests, ENG-001: Repeated leader ADDs converge to target, ENG-002 Negative Tests, ENG-004 Negative Tests (+3 more)

### Community 42 - "_load_live_copy_config"
Cohesion: 0.13
Nodes (28): _active_live_copy_wallet_count(), add_live_config_wallet(), api_state(), _enforce_live_copy_cap(), _engine_wallet_summary(), _execution_guards_info(), ev(), get_global_controls() (+20 more)

### Community 43 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 44 - "read_csv_rows"
Cohesion: 0.10
Nodes (14): prof, read_csv_rows(), _market_fixture(), send_attempt_rows(), update_send_attempt_row(), 2. Top tracemalloc allocation lines (`f37b9c1`, 50 MB synthetic CSV), 3. Verdict per suspect (prove / disprove), 4. Interpretation - ranking by contribution to the observed 4.5 GB (+6 more)

### Community 45 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.13
Nodes (16): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+8 more)

### Community 46 - "utc_now_iso"
Cohesion: 0.17
Nodes (16): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+8 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.09
Nodes (19): main(), make_csv(), measure(), rss_mb(), _addr(), _avail_mb(), build_intents(), build_matcher_stub() (+11 more)

### Community 48 - "run"
Cohesion: 0.23
Nodes (3): Gap1OutageClassifier, Gap3LiqParity, run()

### Community 49 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 50 - "ENG-001-004_harness_43731b4f.py"
Cohesion: 0.13
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 51 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 52 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 54 - "main"
Cohesion: 0.10
Nodes (5): main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 55 - "collections"
Cohesion: 0.10
Nodes (15): main(), pick_lane(), as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows() (+7 more)

### Community 56 - "NLS_RESIDUAL_harness_2a269ad_v2.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 57 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 58 - "probe_reearn.py"
Cohesion: 0.18
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 59 - "exchange_truth.py"
Cohesion: 0.15
Nodes (8): claim_network_stamp(), env_with_file(), network_endpoints(), NetworkConfigError, resolve_networks(), stamp_state_refusal(), state_present(), terminal_reject_evidence()

### Community 60 - "shutil"
Cohesion: 0.31
Nodes (14): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+6 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (17): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+9 more)

### Community 62 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.42
Nodes (12): _build_intent(), check(), main(), _make_config(), _make_ledger(), neg_test(), _now_ms(), test_eng_val_01() (+4 more)

### Community 63 - "test_core_slot_reservation_pacing.py"
Cohesion: 0.16
Nodes (6): FakeExchange, RecordingSenderGateway, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order()

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 66 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 67 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 68 - "pathlib"
Cohesion: 0.16
Nodes (24): imports_of(), is_b4(), main(), mutate(), prod_files(), scan(), baseline_deps(), closure() (+16 more)

### Community 70 - "main"
Cohesion: 0.15
Nodes (5): main(), engine_order(), land(), load_run(), producer()

### Community 71 - "main"
Cohesion: 0.10
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 72 - "test_http_keepalive.py"
Cohesion: 0.12
Nodes (6): cand(), cand(), _Flaky, H, Mon, stub()

### Community 73 - "subprocess"
Cohesion: 0.08
Nodes (16): main(), git(), load(), main(), record(), check(), _load_committed_engine(), main() (+8 more)

### Community 74 - "main"
Cohesion: 0.13
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 75 - "main"
Cohesion: 0.18
Nodes (7): main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 76 - "main"
Cohesion: 0.13
Nodes (4): check(), main(), startup_orphan_order_check(), wait_for_json_file()

### Community 77 - "UI_FP_FAIL_harness_09e1258003.py"
Cohesion: 0.23
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 78 - "test_core_audit_reduce_only_matches_wire.py"
Cohesion: 0.15
Nodes (7): check(), FakeExchange, Led, make_intent(), run(), main(), one()

### Community 79 - "main"
Cohesion: 0.12
Nodes (4): check(), main(), __init__(), order()

### Community 80 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 81 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 82 - "math"
Cohesion: 0.21
Nodes (3): p90(), Ledger, plan()

### Community 83 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 84 - "test_g2_copy_correctness.py"
Cohesion: 0.28
Nodes (4): check(), main(), fresh(), wire_account_net()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 87 - "main"
Cohesion: 0.13
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 88 - "DONE10_CORRECTION_harness_4fb8255.py"
Cohesion: 0.18
Nodes (10): check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live(), main(), neg_test(), run_check() (+2 more)

### Community 89 - "test_core_reduce_only_repair.py"
Cohesion: 0.14
Nodes (5): poll_copy_account_fills(), Audit, Ledger, run(), rows()

### Community 90 - "hashlib"
Cohesion: 0.15
Nodes (5): sha(), _sha256(), _sha256(), _sha256(), _sha256()

### Community 92 - "main"
Cohesion: 0.18
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 93 - "test_cert_scripts.py"
Cohesion: 0.21
Nodes (3): ExportLeaderFills, Gap5DiskGuard, load_module()

### Community 94 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 95 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 96 - "Rows"
Cohesion: 0.15
Nodes (11): 6. Open decisions register, 3. Convergence, 4. Dust close, 5. Liquidation parity (+ cross 3x), 6. Ledger repair / ownership, 7. Send path: idempotency, cloid, 9. Audit-write / disk-full, Bottom line for the Boss condition (+3 more)

### Community 97 - "argparse"
Cohesion: 0.14
Nodes (15): core_import(), decide(), deny_write(), icacls_available(), main(), restore_write(), _run(), whoami() (+7 more)

### Community 98 - "PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)"
Cohesion: 0.25
Nodes (7): Common preamble (applies to every gap), GAP-1 · outage recovery, GAP-3 · liquidation parity vs the exchange `liquidationPx`, GAP-4 · realistic-load latency (Phase R), GAP-5 · disk-full robustness, PC run specs for the five certification-matrix gaps (job J4, 2026-10-11), What this job does NOT do

### Community 100 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 101 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 102 - "_model_dashboard_response"
Cohesion: 0.18
Nodes (10): _kick_model_cache_refresh_background(), _refresh(), _model_cache_snapshot_nonblocking(), model_dashboard(), _model_dashboard_html_cache_get(), _model_dashboard_html_cache_latest_get(), _model_dashboard_html_cache_store(), _model_dashboard_last_good_html_disk_get() (+2 more)

### Community 103 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 104 - "_post"
Cohesion: 0.29
Nodes (4): http_post(), _post(), start_keepalive(), loop()

### Community 107 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 109 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 110 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 111 - "J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)"
Cohesion: 0.22
Nodes (8): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

### Community 112 - "os"
Cohesion: 0.05
Nodes (16): check(), check(), main(), config(), intent(), send(), write_cfg(), check() (+8 more)

### Community 113 - "PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)"
Cohesion: 0.40
Nodes (4): Evidence-thinness (honest), Headline (3 lines), Model used (named per part), PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 115 - "list_perp_dexes"
Cohesion: 0.18
Nodes (9): list_perp_dexes(), master_account_net(), _state_payloads(), ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-08: Startup/recovery truth includes all perp DEX scopes, File Hashes, Mutation Test Summary (+1 more)

### Community 117 - "test_core_clo_dispatch_prefilter.py"
Cohesion: 0.17
Nodes (3): Config, fill(), WarmPool

### Community 118 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.29
Nodes (6): Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 124 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 125 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 128 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 129 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 130 - "probe_ui_routes_t_cfcad924.py"
Cohesion: 0.47
Nodes (3): fetch(), main(), markers()

### Community 131 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 132 - "test_ui_incremental_summary.py"
Cohesion: 0.43
Nodes (4): check(), main(), _payload_check(), row()

### Community 134 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

### Community 135 - "Mainnet crash and ambiguous-send recovery"
Cohesion: 0.50
Nodes (3): After a crash or uncertain send, Mainnet crash and ambiguous-send recovery, Wallet-roster changes

### Community 142 - "test_g4_order_cap.py"
Cohesion: 0.22
Nodes (3): check(), main(), engine()

### Community 143 - "convergence_shadow.py"
Cohesion: 0.35
Nodes (6): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test()

### Community 144 - "test_core_standing_close_guard.py"
Cohesion: 0.24
Nodes (4): Audit, guard(), Ledger, plan()

### Community 145 - "test_spot_gate_refusal.py"
Cohesion: 0.38
Nodes (4): check(), main(), decide(), fill()

### Community 148 - "valid_address"
Cohesion: 0.15
Nodes (8): _fill_key(), identity_ok(), master_userfills(), master_userfills_all_dexes(), rolling_day_pnl(), runtime_master_identity(), valid_address(), ENG-INV-09: Exchange truth outranks local replay

### Community 149 - "fnum"
Cohesion: 0.05
Nodes (25): master_exposure(), _manual_sleeve_exists(), canonical_coin_key(), _chain_sorted(), collapse_stale_runs(), close_run(), ExchangeReconciler, fnum() (+17 more)

### Community 150 - "test_core_send_mode_fails_closed.py"
Cohesion: 0.60
Nodes (4): check(), main(), fresh(), write()

## Knowledge Gaps
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fnum()` connect `fnum` to `Rows`, `run_self_test`, `SenderGateway`, `IntentBuilder`, `LiveCopyCore`, `HL_Live_Copy_Service_Core.py`, `WSManager`, `DedupeStore`, `build_live_integrity_status`, `ConfigManager`, `Any`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08524590163934426 - nodes in this community are weakly interconnected._
- **Why does `SenderGateway` connect `SenderGateway` to `run_self_test`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `time`, `ORDER_CORRECTION_harness_fefc2b04.py`, `read_csv_rows`, `LiveCopyCore`, `HL_Live_Copy_Service_Core.py`, `test_core_audit_reduce_only_matches_wire.py`, `WSManager`, `fnum`, `Any`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07081377151799687 - nodes in this community are weakly interconnected._
- **Why does `main()` connect `main` to `sys`, `tempfile`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `main` be split into smaller, more focused modules?**
  _Cohesion score 0.12648221343873517 - nodes in this community are weakly interconnected._