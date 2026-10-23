# Graph Report - hl-build3-weight-singleflight-followup-6330860304  (2026-10-22)

## Corpus Check
- 292 files · ~573,673 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3600 nodes · 9712 edges · 163 communities (132 shown, 31 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 860 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `47270874`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- utc_now_ms
- HTMLElement
- sleeve_from_leader_event_position
- HL_Live_Copy_Service.py
- Any
- Architecture Contract — Hyperliquid Build 3 Repair
- load_ui_state
- Operating Protocol
- ENGINE_RESIDUAL_harness_2a269ad.py
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- DryRunLiveCopyService
- DedupeStore
- time
- HL_Copy_App_SSOT.py
- tempfile
- sys
- pathlib
- test_http_keepalive.py
- build_live_integrity_status
- UI_harness_fa9d9f55ff.py
- HEALTH_CORRECTION_harness_fefc2b04.py
- fnum
- _live_audit_summary_full
- Any
- UI_CORRECTION_harness_2d29211.py
- hashlib
- run_report.py
- HL_Live_Copy_Service_Core.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- LiveCopyCore
- self_test
- run_self_test
- Path
- AuditLogWriter
- utc_now_iso
- test_screen_run4.py
- test_core_audit_append_never_drops.py
- ENG-015-016-TNF17_harness.py
- bval
- Path
- plan_catchup
- HeadroomMonitor
- main
- NLS_RESIDUAL_harness_2a269ad_v4.py
- tools_memory_profile.py
- NLS_RESIDUAL_harness_2a269ad_v2.py
- NLS_RESIDUAL_harness_2a269ad_v3.py
- ENG-001-004_harness_43731b4f.py
- main
- global_controls_tests
- ConfigManager
- main
- _load_live_copy_config
- main
- probe_reearn.py
- main
- exchange_truth.py
- census_inv_06_09.py
- Master Product Invariants and Certification Contract
- cert_disk_guard.py
- main
- Detail
- main
- math
- main
- ast
- DONE10_CORRECTION_harness_4fb8255.py
- test_core_slot_reservation_pacing.py
- HTMLElement
- test_core_clo_dispatch_prefilter.py
- shutil
- Rows
- main
- main
- CTRL_probe_t_967fad56.py
- UI_FP_FAIL_harness_09e1258003.py
- subprocess
- test_core_ws_pool_and_slots.py
- bench_memory_profile.py
- main
- json
- main
- ENG-015 / ENG-016 / TN-F17 Certification Report
- argparse
- run
- append_csv
- main
- _model_dashboard_response
- main
- PartialWriteThenFail
- headroom.py
- Any
- RISK_harness_fa9d9f55ff.py
- TimedLock
- LeaderEquitySingleflightTests
- main
- main
- collections
- cert_liq_parity_offline.py
- test_ui_incremental_summary.py
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- test_core_standing_close_guard.py
- test_exchange_truth_retry.py
- main
- test_core_outage_replay.py
- test_core_warm_dex_clients.py
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- main
- outage_classify.py
- ENG-INV-06..09 Non-Vacuous Static Census Report
- J2 Local Rejects - Proposed Patch Diffs
- test_core_tail_read_off_lock.py
- main
- Config
- tools/cert — offline halves of the J4 certification gaps (task K2)
- main
- _LatestStatusWriteWorker
- test_core_outage_paging.py
- test_core_audit_header_cache.py
- main
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- test_core_liq_isolated.py
- test_core_live_only_stream_cap.py
- Certification (Build 3 Repair)
- Certification run status
- test_core_headroom.py
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- test_core_queue_timing_stamps.py
- test_core_run5_converge.py
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- test_core_append_truncate.py
- csv
- valid_address
- render_chart
- main
- _close_audit_handle
- probe_ui_routes_t_cfcad924.py
- note_audit_write_failure
- _rotate_audit_file
- http_post
- ENG-001/002/004 Certification Report
- verify_api_endpoint
- acquire_global_instance_lock
- test_spot_gate_refusal.py
- test_core_headroom_foreign_ws.py
- test_g4_fixed_slices.py
- append_csv
- _header_checked
- _note_append
- _note_lock_contention
- verify_js_reference
- test_core_send_mode_fails_closed.py
- resolve_settlement

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 157 edges
2. `SenderGateway` - 113 edges
3. `utc_now_ms()` - 103 edges
4. `LiveCopyCore` - 83 edges
5. `fnum()` - 76 edges
6. `log_error()` - 73 edges
7. `Intent` - 66 edges
8. `ConfigManager` - 64 edges
9. `self_test()` - 62 edges
10. `canonical_coin_key()` - 62 edges

## Surprising Connections (you probably didn't know these)
- `Evidence from building this (2026-10-11, offline, on this host)` --references--> `read_csv_rows()`  [INFERRED]
  tools/cert/README.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `7. Send path: idempotency, cloid` --references--> `DedupeStore`  [INFERRED]
  process/PORT_VS_REBUILD.crosscheck-hermes.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Sources & method` --references--> `_live_audit_summary()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Row 2 — switch states OFF / CLOSE ONLY / ON` --references--> `_build_live_wallet_rows()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py

## Import Cycles
- None detected.

## Communities (163 total, 31 thin omitted)

### Community 0 - "utc_now_ms"
Cohesion: 0.07
Nodes (25): request_lane(), canonical_copy_fill_id(), claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs(), iter_audit_history() (+17 more)

### Community 1 - "HTMLElement"
Cohesion: 0.13
Nodes (3): extract_table_headers(), HTMLElement, SimpleHTMLParser

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 3 - "HL_Live_Copy_Service.py"
Cohesion: 0.07
Nodes (57): append_send_attempt(), atomic_write_json(), attach_send_result(), clear_unresolved_send(), _mut(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema() (+49 more)

### Community 4 - "Any"
Cohesion: 0.04
Nodes (24): post_many(), atomic_write_json(), canonical_coin_key(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), fnum() (+16 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.09
Nodes (37): admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics(), api_model_cache_status(), api_norm(), api_set_ui_state(), api_trades() (+29 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.07
Nodes (24): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test(), check(), main() (+16 more)

### Community 9 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 10 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 11 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 12 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (10): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), executable_price_from_fill_payload(), fnum(), LeaderFill (+2 more)

### Community 14 - "time"
Cohesion: 0.15
Nodes (5): CaptureAudit, make_intent(), wait_for_trace_rows(), main(), one()

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), avg(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure() (+31 more)

### Community 16 - "tempfile"
Cohesion: 0.07
Nodes (33): main(), check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive() (+25 more)

### Community 17 - "sys"
Cohesion: 0.04
Nodes (18): check(), main(), check(), injected_open(), slow_append(), check(), main(), slow() (+10 more)

### Community 18 - "pathlib"
Cohesion: 0.03
Nodes (17): gw(), check(), wallets(), check(), check(), check(), main(), sections() (+9 more)

### Community 19 - "test_http_keepalive.py"
Cohesion: 0.13
Nodes (3): _Flaky, H, Mon

### Community 20 - "build_live_integrity_status"
Cohesion: 0.05
Nodes (31): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row() (+23 more)

### Community 21 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.11
Nodes (25): blocked(), check(), main(), neg_test(), parse_html(), setup_test_env(), test_engine_integrity(), test_inc() (+17 more)

### Community 22 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 23 - "fnum"
Cohesion: 0.08
Nodes (47): _account_card_lines(), active_wallet(), _append_exchange_history(), block_num(), core_missing(), core_td(), css_class(), dd_current() (+39 more)

### Community 24 - "_live_audit_summary_full"
Cohesion: 0.06
Nodes (42): _account_reconciliation_baseline_timestamp(), active_wallet_row(), _build_account_reconciliation(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_health_summary(), _build_live_top_status(), _build_live_wallet_rows() (+34 more)

### Community 25 - "Any"
Cohesion: 0.09
Nodes (40): _build_live_leader_performance(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), build_portfolio_history(), _build_real_copy_positions(), _classify_owned_exchange_net(), compact_history(), contract_money_equal() (+32 more)

### Community 26 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.12
Nodes (23): blocked(), check(), main(), neg_test(), parse_html(), parse_ssot_home_table_headers(), parse_ssot_table_headers(), setup_test_env() (+15 more)

### Community 27 - "hashlib"
Cohesion: 0.09
Nodes (11): sha(), _sha256(), _sha256(), _sha256(), _sha256(), check(), _load_committed_engine(), main() (+3 more)

### Community 28 - "run_report.py"
Cohesion: 0.13
Nodes (16): build_report(), fetch_leader_fills(), _fmt_durs(), _fmt_stamps(), leader_fill_ids(), load_live_config_wallets(), load_outage_classify(), main() (+8 more)

### Community 29 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.04
Nodes (42): _append_core_fatal_row(), _attribution_json_safe(), _BoundedRaw, canonical_coin_resolved(), _chain_sorted(), _check(), collapse_stale_runs(), close_run() (+34 more)

### Community 30 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (19): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source(), main(), run_negative_mutations() (+11 more)

### Community 31 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 32 - "LiveCopyCore"
Cohesion: 0.03
Nodes (42): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+34 more)

### Community 33 - "self_test"
Cohesion: 0.08
Nodes (20): audit_notes_for_fill(), classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), is_benign_ws_error(), _is_reduce_only_full_close_bypass(), is_ws_abnf_frame(), parse_hl_order_status() (+12 more)

### Community 34 - "run_self_test"
Cohesion: 0.05
Nodes (18): _adoptable_intent_rows(), is_valid_wallet(), LeaderFillIngestor, ManualLedger, normalise_wallet(), prof, read_csv_rows(), repair_adopt_oids() (+10 more)

### Community 35 - "Path"
Cohesion: 0.19
Nodes (9): acquire_instance_lock(), _append_spill_journal(), _audit_fallback_remains(), load_env_file(), _read_spill_journal(), _remember_header(), replay_audit_fallback(), _spill_journal_path() (+1 more)

### Community 36 - "AuditLogWriter"
Cohesion: 0.06
Nodes (33): AuditLogWriter, check(), FakeExchange, Led, make_intent(), run(), _build_intent(), _cfg() (+25 more)

### Community 37 - "utc_now_iso"
Cohesion: 0.16
Nodes (17): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+9 more)

### Community 38 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 39 - "test_core_audit_append_never_drops.py"
Cohesion: 0.07
Nodes (4): fill(), run(), Audit, fill()

### Community 40 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.13
Nodes (16): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+8 more)

### Community 41 - "bval"
Cohesion: 0.05
Nodes (14): list_perp_dexes(), master_exposure(), _post(), rolling_day_pnl(), bval(), _follower_dex_names(), follower_dex_scope(), follower_mid() (+6 more)

### Community 42 - "Path"
Cohesion: 0.13
Nodes (24): _account_orphan_signed_size(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key(), invalidate_model_cache() (+16 more)

### Community 43 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 45 - "main"
Cohesion: 0.10
Nodes (5): main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 46 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.15
Nodes (15): _addr(), _avail_mb(), build_intents(), build_matcher_stub(), gen_csv(), _hash(), main(), make_row() (+7 more)

### Community 48 - "NLS_RESIDUAL_harness_2a269ad_v2.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 49 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 50 - "ENG-001-004_harness_43731b4f.py"
Cohesion: 0.11
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 51 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 52 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 54 - "main"
Cohesion: 0.13
Nodes (4): main(), _note_read_on_current(), slow(), fetch()

### Community 55 - "_load_live_copy_config"
Cohesion: 0.13
Nodes (28): _active_live_copy_wallet_count(), add_live_config_wallet(), api_state(), _enforce_live_copy_cap(), _engine_wallet_summary(), _execution_guards_info(), ev(), get_global_controls() (+20 more)

### Community 56 - "main"
Cohesion: 0.14
Nodes (4): main(), _note_read_on_current(), slow(), fetch()

### Community 57 - "probe_reearn.py"
Cohesion: 0.17
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 58 - "main"
Cohesion: 0.08
Nodes (9): check(), FakeExchange, _Half, Inject, main(), error_contexts(), errors(), hold_runtime_state_lock() (+1 more)

### Community 59 - "exchange_truth.py"
Cohesion: 0.16
Nodes (8): claim_network_stamp(), env_with_file(), network_endpoints(), NetworkConfigError, resolve_networks(), stamp_state_refusal(), state_present(), terminal_reject_evidence()

### Community 60 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (17): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+9 more)

### Community 62 - "cert_disk_guard.py"
Cohesion: 0.17
Nodes (15): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later) (+7 more)

### Community 63 - "main"
Cohesion: 0.07
Nodes (11): check(), main(), engine_order(), land(), load_run(), producer(), poll_copy_account_fills(), Audit (+3 more)

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "main"
Cohesion: 0.18
Nodes (7): main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 66 - "math"
Cohesion: 0.08
Nodes (10): p90(), Ledger, plan(), p90(), check(), main(), _note_read_on_current(), slow() (+2 more)

### Community 67 - "main"
Cohesion: 0.14
Nodes (3): main(), __init__(), order()

### Community 68 - "ast"
Cohesion: 0.20
Nodes (18): exchange_order_calls(), SingleExchangeOrderCallsiteTest, baseline_deps(), closure(), dyn_imports(), git_show(), imports_of(), is_b4() (+10 more)

### Community 69 - "DONE10_CORRECTION_harness_4fb8255.py"
Cohesion: 0.18
Nodes (10): check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live(), main(), neg_test(), run_check() (+2 more)

### Community 70 - "test_core_slot_reservation_pacing.py"
Cohesion: 0.12
Nodes (7): FakeExchange, RecordingSenderGateway, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order(), VirtualClock

### Community 71 - "HTMLElement"
Cohesion: 0.12
Nodes (3): HTMLElement, SimpleHTMLParser, verify_html_element()

### Community 72 - "test_core_clo_dispatch_prefilter.py"
Cohesion: 0.09
Nodes (8): WarmPool, check(), main(), check(), main(), check(), main(), check()

### Community 73 - "shutil"
Cohesion: 0.31
Nodes (14): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+6 more)

### Community 74 - "Rows"
Cohesion: 0.15
Nodes (11): 6. Open decisions register, 3. Convergence, 4. Dust close, 5. Liquidation parity (+ cross 3x), 6. Ledger repair / ownership, 7. Send path: idempotency, cloid, 9. Audit-write / disk-full, Bottom line for the Boss condition (+3 more)

### Community 75 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 76 - "main"
Cohesion: 0.13
Nodes (4): check(), main(), startup_orphan_order_check(), wait_for_json_file()

### Community 77 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 78 - "UI_FP_FAIL_harness_09e1258003.py"
Cohesion: 0.23
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 79 - "subprocess"
Cohesion: 0.09
Nodes (15): git(), load(), main(), record(), check(), _load_committed_engine(), main(), neg() (+7 more)

### Community 80 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.05
Nodes (17): cfg(), WebSocketApp(), build_cfg(), check(), FakeApp, FakeResp, FakeWS, main() (+9 more)

### Community 81 - "bench_memory_profile.py"
Cohesion: 0.21
Nodes (4): main(), make_csv(), measure(), rss_mb()

### Community 82 - "main"
Cohesion: 0.21
Nodes (7): configure_paths(), check(), Fixture, fresh(), main(), reset_master(), with_master()

### Community 83 - "json"
Cohesion: 0.18
Nodes (12): main(), main(), main(), route_present(), check_hwm(), check_i1(), check_i3(), git() (+4 more)

### Community 84 - "main"
Cohesion: 0.22
Nodes (3): main(), config(), gate()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 86 - "argparse"
Cohesion: 0.14
Nodes (11): core_import(), decide(), main(), measure(), rss_mb(), main(), post(), wallets() (+3 more)

### Community 87 - "run"
Cohesion: 0.11
Nodes (7): ExportLeaderFills, Gap1OutageClassifier, Gap2MemoryScan, Gap3LiqParity, Gap5DiskGuard, load_module(), run()

### Community 88 - "append_csv"
Cohesion: 0.35
Nodes (9): append_csv(), _audit_row_data(), _audit_row_payload(), ensure_csv_header(), _fallback_path(), _lock_for(), _replay_audit_fallback(), _spill_row() (+1 more)

### Community 90 - "_model_dashboard_response"
Cohesion: 0.18
Nodes (10): _kick_model_cache_refresh_background(), _refresh(), _model_cache_snapshot_nonblocking(), model_dashboard(), _model_dashboard_html_cache_get(), _model_dashboard_html_cache_latest_get(), _model_dashboard_html_cache_store(), _model_dashboard_last_good_html_disk_get() (+2 more)

### Community 91 - "main"
Cohesion: 0.24
Nodes (3): check(), main(), wait_for()

### Community 93 - "headroom.py"
Cohesion: 0.20
Nodes (4): current_request_lane(), install_session_counter(), counted_request(), level_for()

### Community 94 - "Any"
Cohesion: 0.24
Nodes (3): CountingRequests, info_weight(), scan_foreign_ws()

### Community 95 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 97 - "LeaderEquitySingleflightTests"
Cohesion: 0.24
Nodes (5): LeaderEquitySingleflightTests, read_equity(), result(), call(), result()

### Community 99 - "main"
Cohesion: 0.28
Nodes (6): main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), _f()

### Community 100 - "collections"
Cohesion: 0.09
Nodes (15): main(), pick_lane(), as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows() (+7 more)

### Community 101 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 102 - "test_ui_incremental_summary.py"
Cohesion: 0.43
Nodes (4): check(), main(), _payload_check(), row()

### Community 103 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 104 - "test_core_standing_close_guard.py"
Cohesion: 0.24
Nodes (4): Audit, guard(), Ledger, plan()

### Community 105 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 106 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 109 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 110 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 111 - "main"
Cohesion: 0.27
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 112 - "outage_classify.py"
Cohesion: 0.11
Nodes (9): block_reasons(), classify(), main(), missing_detail(), _rows(), Audit, Audit, me() (+1 more)

### Community 113 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.33
Nodes (5): ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, File Hashes, Mutation Test Summary, Results Summary

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 115 - "test_core_tail_read_off_lock.py"
Cohesion: 0.09
Nodes (7): Probe, probing_open(), check(), fake_fetcher(), fake_urlopen(), Resp, w()

### Community 116 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 118 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.20
Nodes (8): read_csv_tail_rows(), Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), Scripts, tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 119 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 123 - "main"
Cohesion: 0.12
Nodes (5): check(), finish(), main(), check(), main()

### Community 124 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 125 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 126 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 127 - "test_core_live_only_stream_cap.py"
Cohesion: 0.28
Nodes (3): check(), main(), wallets()

### Community 128 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 129 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 131 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 134 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

### Community 135 - "Mainnet crash and ambiguous-send recovery"
Cohesion: 0.50
Nodes (3): After a crash or uncertain send, Mainnet crash and ambiguous-send recovery, Wallet-roster changes

### Community 142 - "valid_address"
Cohesion: 0.14
Nodes (9): _fill_key(), identity_ok(), master_account_net(), master_userfills(), master_userfills_all_dexes(), runtime_master_identity(), _state_payloads(), valid_address() (+1 more)

### Community 143 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 146 - "probe_ui_routes_t_cfcad924.py"
Cohesion: 0.14
Nodes (3): fetch(), main(), markers()

### Community 147 - "note_audit_write_failure"
Cohesion: 0.25
Nodes (6): _audit_flush_worker(), note_audit_write_failure(), _schedule_audit_flush(), Findings (FAILS on main) and the fix in the patch, J1 — disk-full robustness: findings and proposed patch, What already holds on main (no change needed)

### Community 148 - "_rotate_audit_file"
Cohesion: 0.29
Nodes (4): audit_history_paths(), _replay_payload_present(), _rotate_audit_file(), rotated_audit_paths()

### Community 149 - "http_post"
Cohesion: 0.40
Nodes (3): http_post(), start_keepalive(), loop()

### Community 150 - "ENG-001/002/004 Certification Report"
Cohesion: 0.29
Nodes (6): Conclusion, ENG-001/002/004 Certification Report, ENG-002 Negative Tests, ENG-004 Negative Tests, Negative Tests (non-vacuous proof), Oracle: Hyperliquid Testnet API

### Community 152 - "acquire_global_instance_lock"
Cohesion: 0.33
Nodes (3): acquire_global_instance_lock(), _global_holder_path(), _global_instance_lock_path()

### Community 153 - "test_spot_gate_refusal.py"
Cohesion: 0.38
Nodes (4): check(), main(), decide(), fill()

### Community 154 - "test_core_headroom_foreign_ws.py"
Cohesion: 0.20
Nodes (5): _run(), Clock, events(), scanner(), settle()

### Community 156 - "append_csv"
Cohesion: 0.60
Nodes (3): append_csv(), stage_auto_row(), should_write_would_send()

### Community 161 - "test_core_send_mode_fails_closed.py"
Cohesion: 0.60
Nodes (4): check(), main(), fresh(), write()

## Knowledge Gaps
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `Any` to `utc_now_ms`, `LiveCopyCore`, `run_self_test`, `AuditLogWriter`, `ENGINE_RESIDUAL_harness_2a269ad.py`, `bval`, `pathlib`, `build_live_integrity_status`, `HL_Live_Copy_Service_Core.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Should `utc_now_ms` be split into smaller, more focused modules?**
  _Cohesion score 0.07370600414078675 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `Any` to `LiveCopyCore`, `utc_now_ms`, `run_self_test`, `bval`, `Rows`, `DedupeStore`, `build_live_integrity_status`, `ConfigManager`, `HL_Live_Copy_Service_Core.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `HTMLElement` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Why does `main()` connect `main` to `tempfile`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06523855890944498 - nodes in this community are weakly interconnected._