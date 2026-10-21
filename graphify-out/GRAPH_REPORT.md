# Graph Report - jobA-latency  (2026-10-21)

## Corpus Check
- 283 files · ~569,048 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3507 nodes · 9498 edges · 157 communities (135 shown, 22 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 844 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ff5abc21`
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
- ENGINE_RESIDUAL_harness_2a269ad.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- load_json
- utc_now_ms
- HL_Live_Copy_Service_Core.py
- HL_Copy_App_SSOT.py
- run_self_test
- threading
- sys
- test_core_clo_dispatch_prefilter.py
- build_live_integrity_status
- UI_harness_fa9d9f55ff.py
- tempfile
- HEALTH_CORRECTION_harness_fefc2b04.py
- cert_liq_parity_offline.py
- _row_time_ms
- UI_CORRECTION_harness_2d29211.py
- CopyFillMatcher
- csv
- inum
- Any
- _fetch_user_realized_pnl_snapshot
- fnum
- self_test
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- main
- main
- run_report.py
- test_core_audit_append_never_drops.py
- test_core_ws_pool_and_slots.py
- IntentBuilder
- CTRL_probe_t_967fad56.py
- ORDER_CORRECTION_harness_fefc2b04.py
- PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)
- ENG-015-016-TNF17_harness.py
- utc_now_iso
- tools_memory_profile.py
- run
- plan_catchup
- shutil
- render_chart
- NLS_RESIDUAL_harness_2a269ad_v4.py
- ConfigManager
- main
- collections
- NLS_RESIDUAL_harness_2a269ad_v2.py
- NLS_RESIDUAL_harness_2a269ad_v3.py
- probe_reearn.py
- exchange_truth.py
- NLS_RESIDUAL_harness_2a269ad.py
- Master Product Invariants and Certification Contract
- main
- test_core_slot_reservation_pacing.py
- Detail
- main
- RISK_harness_fa9d9f55ff.py
- census_inv_06_09.py
- pathlib
- DONE10_CORRECTION_harness_4fb8255.py
- main
- main
- test_core_queue_timing_stamps.py
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
- json
- bench_memory_profile.py
- ENG-015 / ENG-016 / TN-F17 Certification Report
- test_core_reduce_only_repair.py
- main
- ._merge_fresh_disk_before_save
- test_http_keepalive.py
- cert_memory_scan.py
- TimedLock
- hashlib
- test_cert_scripts.py
- test_exchange_truth_retry.py
- main
- .__init__
- main
- main
- get
- main
- main
- main
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- _post
- _LatestStatusWriteWorker
- main
- test_core_liq_isolated.py
- Inject
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- PRICING_CORRECTION_harness_2f57dba50f.py
- re
- valid_address
- J2 Local Rejects - Proposed Patch Diffs
- block_num
- AppendFail
- main
- tools/cert — offline halves of the J4 certification gaps (task K2)
- test_core_append_truncate.py
- test_core_audit_header_cache.py
- test_core_run5_converge.py
- test_core_live_only_stream_cap.py
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- test_j2_local_rejects.py
- .test_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders
- Certification (Build 3 Repair)
- Certification run status
- time
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- main
- test_single_exchange_order_callsite.py
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- test_spot_gate_refusal.py
- master_exposure
- main
- test_g4_fixed_slices.py
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- cert_disk_guard.py
- test_ui_incremental_summary.py
- Gap2MemoryScan
- resolve_settlement
- card_hygiene.py
- _Half
- Probe
- argparse
- write_live_integrity_status
- CTRL_probe3_t_967fad56.py
- fetch_leader_fills
- FakeExchange

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 156 edges
2. `SenderGateway` - 113 edges
3. `utc_now_ms()` - 102 edges
4. `LiveCopyCore` - 82 edges
5. `fnum()` - 76 edges
6. `log_error()` - 72 edges
7. `Intent` - 65 edges
8. `ConfigManager` - 64 edges
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

## Communities (157 total, 22 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.10
Nodes (43): append_send_attempt(), extract_ws_fills(), extract_ws_fills_with_meta(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places() (+35 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.07
Nodes (11): adverse_diff_pct(), append_csv(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), executable_price_from_fill_payload(), fnum() (+3 more)

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 3 - "main"
Cohesion: 0.09
Nodes (19): attach_send_result(), clear_unresolved_send(), _mut(), configure_paths(), ensure_dirs(), load_auto_send_attempt_ids(), load_csv_ids(), load_json() (+11 more)

### Community 4 - "Any"
Cohesion: 0.03
Nodes (22): atomic_write_json(), bval(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), generate_attempt_id(), generate_cloid() (+14 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.10
Nodes (47): _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_metrics(), api_model_cache_status(), api_norm(), api_set_ui_state() (+39 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.07
Nodes (25): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test(), CountingRequests, HeadroomMonitor (+17 more)

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

### Community 13 - "utc_now_ms"
Cohesion: 0.03
Nodes (41): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+33 more)

### Community 14 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.04
Nodes (64): acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _append_spill_journal(), _attribution_json_safe(), _audit_fallback_remains(), _audit_flush_worker() (+56 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+31 more)

### Community 16 - "run_self_test"
Cohesion: 0.08
Nodes (10): _exchange_accepts_cloid(), is_valid_wallet(), LeaderFillIngestor, run_self_test(), _clean_account_fixture(), _market_fixture(), order(), WSManager (+2 more)

### Community 17 - "threading"
Cohesion: 0.05
Nodes (15): check(), main(), check(), slow_append(), slow(), Audit, me(), w() (+7 more)

### Community 18 - "sys"
Cohesion: 0.03
Nodes (15): check(), finish(), main(), check(), main(), check(), check(), main() (+7 more)

### Community 19 - "test_core_clo_dispatch_prefilter.py"
Cohesion: 0.07
Nodes (10): Config, fill(), WarmPool, check(), main(), check(), main(), check() (+2 more)

### Community 20 - "build_live_integrity_status"
Cohesion: 0.10
Nodes (13): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row() (+5 more)

### Community 21 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.06
Nodes (30): blocked(), check(), HTMLElement, main(), neg_test(), parse_html(), setup_test_env(), SimpleHTMLParser (+22 more)

### Community 22 - "tempfile"
Cohesion: 0.08
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 23 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 24 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 25 - "_row_time_ms"
Cohesion: 0.21
Nodes (11): _fetch_user_fills_by_time(), _fetch_user_fills_cached(), _fetch_user_fills_paged(), _fetch_user_funding_cached(), _fetch_user_funding_paged(), _fill_dedupe_key(), _funding_dedupe_key(), _funding_usdc() (+3 more)

### Community 26 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.07
Nodes (26): blocked(), check(), extract_table_headers(), HTMLElement, main(), neg_test(), parse_html(), parse_ssot_home_table_headers() (+18 more)

### Community 27 - "CopyFillMatcher"
Cohesion: 0.05
Nodes (30): _adoptable_intent_rows(), AuditLogWriter, canonical_copy_fill_id(), claim_copy_fill_process_marker(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs(), normalise_copy_fill_side() (+22 more)

### Community 28 - "csv"
Cohesion: 0.19
Nodes (5): w(), check(), fake_fetcher(), w(), main()

### Community 29 - "inum"
Cohesion: 0.08
Nodes (38): _account_card_lines(), active_wallet(), active_wallet_row(), avg(), core_missing(), core_td(), css_class(), dash_td() (+30 more)

### Community 30 - "Any"
Cohesion: 0.08
Nodes (51): _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_top_status(), _build_live_wallet_derived(), _build_live_wallet_rows(), _build_manual_reconciliation_rows(), _build_real_copy_positions() (+43 more)

### Community 31 - "_fetch_user_realized_pnl_snapshot"
Cohesion: 0.13
Nodes (18): _account_reconciliation_baseline_timestamp(), _build_account_reconciliation(), _build_health_summary(), _build_pnl_tally(), _earliest_real_order_filled_ms(), _engine_run_key(), _fetch_exchange_account_snapshot(), _fetch_user_realized_pnl_snapshot() (+10 more)

### Community 32 - "fnum"
Cohesion: 0.06
Nodes (26): canonical_coin_key(), canonical_coin_resolved(), _chain_sorted(), _coin_key_map(), collapse_stale_runs(), close_run(), copy_cursor_ms(), ExchangeReconciler (+18 more)

### Community 33 - "self_test"
Cohesion: 0.07
Nodes (25): atomic_write_json(), audit_notes_for_fill(), classify_ignored_ws_message(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), _is_reduce_only_full_close_bypass(), last_csv_row() (+17 more)

### Community 34 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (19): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source(), main(), run_negative_mutations() (+11 more)

### Community 35 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 36 - "main"
Cohesion: 0.17
Nodes (6): check(), main(), error_contexts(), errors(), hold_runtime_state_lock(), wait_for_json_file()

### Community 37 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 38 - "run_report.py"
Cohesion: 0.17
Nodes (13): build_report(), _fmt_durs(), _fmt_stamps(), load_live_config_wallets(), load_outage_classify(), main(), outage_outcomes(), read_rows() (+5 more)

### Community 39 - "test_core_audit_append_never_drops.py"
Cohesion: 0.05
Nodes (9): fill(), run(), Audit, fill(), Audit, Audit, guard(), Ledger (+1 more)

### Community 40 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.11
Nodes (12): cfg(), WebSocketApp(), build_cfg(), check(), FakeApp, FakeResp, FakeWS, main() (+4 more)

### Community 41 - "IntentBuilder"
Cohesion: 0.05
Nodes (19): post_many(), follower_dex_scope(), follower_mid(), stale(), IntentBuilder, guarded(), is_spot_pair(), leader_mid() (+11 more)

### Community 42 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 43 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 44 - "PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)"
Cohesion: 0.25
Nodes (7): Common preamble (applies to every gap), GAP-1 · outage recovery, GAP-3 · liquidation parity vs the exchange `liquidationPx`, GAP-4 · realistic-load latency (Phase R), GAP-5 · disk-full robustness, PC run specs for the five certification-matrix gaps (job J4, 2026-10-11), What this job does NOT do

### Community 45 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.14
Nodes (15): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+7 more)

### Community 46 - "utc_now_iso"
Cohesion: 0.13
Nodes (22): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+14 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.15
Nodes (15): _addr(), _avail_mb(), build_intents(), build_matcher_stub(), gen_csv(), _hash(), main(), make_row() (+7 more)

### Community 48 - "run"
Cohesion: 0.23
Nodes (3): Gap1OutageClassifier, Gap3LiqParity, run()

### Community 49 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 50 - "shutil"
Cohesion: 0.13
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 51 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 52 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 53 - "ConfigManager"
Cohesion: 0.09
Nodes (4): ConfigManager, 6. Open decisions register, 2. Switch states OFF / CLOSE ONLY / ON, 4. Dust close

### Community 54 - "main"
Cohesion: 0.10
Nodes (5): main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 55 - "collections"
Cohesion: 0.14
Nodes (12): as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows(), rows(), classify() (+4 more)

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

### Community 60 - "NLS_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.29
Nodes (15): utc_now_iso(), certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check() (+7 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (17): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+9 more)

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

### Community 69 - "DONE10_CORRECTION_harness_4fb8255.py"
Cohesion: 0.18
Nodes (10): check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live(), main(), neg_test(), run_check() (+2 more)

### Community 70 - "main"
Cohesion: 0.15
Nodes (5): main(), engine_order(), land(), load_run(), producer()

### Community 71 - "main"
Cohesion: 0.10
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 72 - "test_core_queue_timing_stamps.py"
Cohesion: 0.11
Nodes (3): StopAfterOneSample, fake_urlopen(), Resp

### Community 73 - "subprocess"
Cohesion: 0.22
Nodes (7): g(), blob(), census(), blob(), calls_in(), head(), main()

### Community 74 - "main"
Cohesion: 0.11
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 75 - "main"
Cohesion: 0.18
Nodes (7): main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 76 - "main"
Cohesion: 0.14
Nodes (4): check(), main(), startup_orphan_order_check(), wait_for_json_file()

### Community 77 - "UI_FP_FAIL_harness_09e1258003.py"
Cohesion: 0.23
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 78 - "test_core_audit_reduce_only_matches_wire.py"
Cohesion: 0.23
Nodes (5): check(), FakeExchange, Led, make_intent(), run()

### Community 79 - "main"
Cohesion: 0.14
Nodes (3): main(), __init__(), order()

### Community 80 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 81 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 83 - "json"
Cohesion: 0.05
Nodes (26): check(), main(), Clock, events(), Clock, events(), settle(), check() (+18 more)

### Community 84 - "bench_memory_profile.py"
Cohesion: 0.21
Nodes (4): main(), make_csv(), measure(), rss_mb()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 86 - "test_core_reduce_only_repair.py"
Cohesion: 0.14
Nodes (5): poll_copy_account_fills(), Audit, Ledger, run(), rows()

### Community 87 - "main"
Cohesion: 0.13
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 88 - "._merge_fresh_disk_before_save"
Cohesion: 0.18
Nodes (9): 3. Convergence, 5. Liquidation parity (+ cross 3x), 6. Ledger repair / ownership, 7. Send path: idempotency, cloid, 9. Audit-write / disk-full, Bottom line for the Boss condition, Headline, PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory) (+1 more)

### Community 89 - "test_http_keepalive.py"
Cohesion: 0.13
Nodes (3): _Flaky, H, Mon

### Community 90 - "cert_memory_scan.py"
Cohesion: 0.25
Nodes (5): core_import(), decide(), main(), measure(), rss_mb()

### Community 92 - "hashlib"
Cohesion: 0.22
Nodes (5): sha(), _sha256(), _sha256(), _sha256(), _sha256()

### Community 93 - "test_cert_scripts.py"
Cohesion: 0.21
Nodes (3): ExportLeaderFills, Gap5DiskGuard, load_module()

### Community 94 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 95 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 96 - ".__init__"
Cohesion: 0.10
Nodes (5): _check(), DedupeStore, ServiceStateWriter, TestFailure, 8. Hot-path latency / prewarm

### Community 97 - "main"
Cohesion: 0.18
Nodes (5): check(), main(), config(), gate(), wallets()

### Community 98 - "main"
Cohesion: 0.18
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 99 - "get"
Cohesion: 0.06
Nodes (28): api_get_ui_state(), api_state(), ev(), get_live_audit_summary(), get_live_copy_summary(), get_wallet_meta(), home(), _kick_model_cache_refresh_background() (+20 more)

### Community 100 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 101 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 102 - "main"
Cohesion: 0.24
Nodes (3): check(), main(), wait_for()

### Community 103 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 104 - "_post"
Cohesion: 0.22
Nodes (5): http_post(), _post(), rolling_day_pnl(), start_keepalive(), loop()

### Community 107 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 109 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 110 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 111 - "PRICING_CORRECTION_harness_2f57dba50f.py"
Cohesion: 0.19
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 112 - "re"
Cohesion: 0.06
Nodes (9): block_reasons(), classify(), main(), missing_detail(), _rows(), sections(), check(), main() (+1 more)

### Community 113 - "valid_address"
Cohesion: 0.20
Nodes (6): _fill_key(), identity_ok(), master_userfills(), master_userfills_all_dexes(), runtime_master_identity(), valid_address()

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 115 - "block_num"
Cohesion: 0.31
Nodes (7): block_num(), dd_current(), dd_max(), latest_history_block_dd(), max_history_block_dd(), sorted_rows(), key()

### Community 117 - "main"
Cohesion: 0.27
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 118 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.25
Nodes (7): Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), Scripts, tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 119 - "test_core_append_truncate.py"
Cohesion: 0.18
Nodes (3): fake_open(), PartialThenFull, Row 9 — audit-write / disk-full

### Community 122 - "test_core_live_only_stream_cap.py"
Cohesion: 0.28
Nodes (3): check(), main(), wallets()

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

### Community 130 - "time"
Cohesion: 0.20
Nodes (6): main(), fetch(), main(), markers(), main(), one()

### Community 131 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 132 - "main"
Cohesion: 0.28
Nodes (6): main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), _f()

### Community 134 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

### Community 135 - "Mainnet crash and ambiguous-send recovery"
Cohesion: 0.50
Nodes (3): After a crash or uncertain send, Mainnet crash and ambiguous-send recovery, Wallet-roster changes

### Community 140 - "test_spot_gate_refusal.py"
Cohesion: 0.38
Nodes (4): check(), main(), decide(), fill()

### Community 141 - "master_exposure"
Cohesion: 0.27
Nodes (5): list_perp_dexes(), master_account_net(), master_exposure(), _state_payloads(), ENG-INV-08: Startup/recovery truth includes all perp DEX scopes

### Community 142 - "main"
Cohesion: 0.25
Nodes (3): check(), main(), engine()

### Community 144 - "J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)"
Cohesion: 0.22
Nodes (8): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

### Community 145 - "cert_disk_guard.py"
Cohesion: 0.47
Nodes (7): decide(), deny_write(), icacls_available(), main(), restore_write(), _run(), whoami()

### Community 146 - "test_ui_incremental_summary.py"
Cohesion: 0.43
Nodes (4): check(), main(), _payload_check(), row()

### Community 148 - "resolve_settlement"
Cohesion: 0.50
Nodes (3): _match(), resolve_settlement(), ENG-INV-09: Exchange truth outranks local replay

### Community 149 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 152 - "argparse"
Cohesion: 0.53
Nodes (3): main(), post(), wallets()

### Community 153 - "write_live_integrity_status"
Cohesion: 0.33
Nodes (4): write_live_integrity_status(), Findings (FAILS on main) and the fix in the patch, J1 — disk-full robustness: findings and proposed patch, What already holds on main (no change needed)

### Community 154 - "CTRL_probe3_t_967fad56.py"
Cohesion: 0.53
Nodes (4): git(), load(), main(), record()

### Community 155 - "fetch_leader_fills"
Cohesion: 0.40
Nodes (3): fetch_leader_fills(), leader_fill_ids(), _stable_hash()

## Knowledge Gaps
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `Any` to `.__init__`, `fnum`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`, `IntentBuilder`, `ORDER_CORRECTION_harness_fefc2b04.py`, `utc_now_ms`, `HL_Live_Copy_Service_Core.py`, `test_core_audit_reduce_only_matches_wire.py`, `run_self_test`, `CopyFillMatcher`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09966329966329966 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `fnum` to `.__init__`, `Any`, `IntentBuilder`, `utc_now_ms`, `HL_Live_Copy_Service_Core.py`, `master_exposure`, `run_self_test`, `build_live_integrity_status`, `ConfigManager`, `CopyFillMatcher`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.0744466800804829 - nodes in this community are weakly interconnected._
- **Why does `ConfigManager` connect `ConfigManager` to `.__init__`, `fnum`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`, `Any`, `ENGINE_RESIDUAL_harness_2a269ad.py`, `IntentBuilder`, `ORDER_CORRECTION_harness_fefc2b04.py`, `utc_now_ms`, `HL_Live_Copy_Service_Core.py`, `test_core_audit_reduce_only_matches_wire.py`, `run_self_test`, `shutil`, `CopyFillMatcher`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `main` be split into smaller, more focused modules?**
  _Cohesion score 0.0855614973262032 - nodes in this community are weakly interconnected._