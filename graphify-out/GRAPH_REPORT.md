# Graph Report - hl-build3-xyz-recovery-6329934384  (2026-10-22)

## Corpus Check
- 290 files · ~571,882 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3563 nodes · 9614 edges · 154 communities (125 shown, 29 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 845 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `95b02fa9`
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
- .__init__
- _load_live_copy_config
- HL_Copy_App_SSOT.py
- RHC_RESIDUAL_harness_2a269ad.py
- threading
- sys
- HeadroomMonitor
- AuditLogWriter
- UI_harness_fa9d9f55ff.py
- tempfile
- fnum
- _live_audit_summary_full
- Any
- UI_CORRECTION_harness_2d29211.py
- hashlib
- run_report.py
- HL_Live_Copy_Service_Core.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- time
- LiveCopyCore
- self_test
- run_self_test
- csv
- ORDER_CORRECTION_harness_fefc2b04.py
- utc_now_iso
- re
- test_core_queue_timing_stamps.py
- ENG-015-016-TNF17_harness.py
- IntentBuilder
- Path
- plan_catchup
- read_csv_rows
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
- test_core_reduce_only_repair.py
- test_http_keepalive.py
- probe_reearn.py
- main
- exchange_truth.py
- census_inv_06_09.py
- Master Product Invariants and Certification Contract
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- main
- Detail
- main
- math
- test_core_clo_dispatch_prefilter.py
- pathlib
- subprocess
- test_core_slot_reservation_pacing.py
- HTMLElement
- test_screen_run4.py
- shutil
- Rows
- main
- main
- fnum
- headroom.py
- _BoundedRaw
- test_core_ws_pool_and_slots.py
- test_cert_scripts.py
- main
- json
- main
- ENG-015 / ENG-016 / TN-F17 Certification Report
- cert_memory_scan.py
- run
- test_core_xyz_recovery_safety.py
- main
- _model_dashboard_response
- .wallets
- test_core_fill_trace_retry.py
- card_hygiene.py
- test_core_headroom_foreign_ws.py
- RISK_harness_fa9d9f55ff.py
- TimedLock
- test_g2_copy_correctness.py
- main
- .test_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders
- collections
- argparse
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
- test_core_audit_reduce_only_matches_wire.py
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
- requests
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- test_core_append_truncate.py
- test_core_run5_converge.py
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- Inject
- cert_disk_guard.py
- valid_address
- render_chart
- _Half
- test_core_audit_append_never_drops.py
- test_g4_fixed_slices.py
- FakeExchange
- Gap2MemoryScan
- _post
- PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)
- verify_api_endpoint
- test_spot_gate_refusal.py
- test_single_exchange_order_callsite.py

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 156 edges
2. `SenderGateway` - 113 edges
3. `utc_now_ms()` - 102 edges
4. `LiveCopyCore` - 82 edges
5. `fnum()` - 76 edges
6. `log_error()` - 73 edges
7. `Intent` - 65 edges
8. `canonical_coin_key()` - 64 edges
9. `ConfigManager` - 64 edges
10. `self_test()` - 62 edges

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

## Communities (154 total, 29 thin omitted)

### Community 0 - "utc_now_ms"
Cohesion: 0.07
Nodes (25): request_lane(), _adoptable_intent_rows(), canonical_copy_fill_id(), claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs() (+17 more)

### Community 1 - "HTMLElement"
Cohesion: 0.13
Nodes (3): extract_table_headers(), HTMLElement, SimpleHTMLParser

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 3 - "HL_Live_Copy_Service.py"
Cohesion: 0.09
Nodes (47): append_send_attempt(), executable_price_from_fill_payload(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), fixed_notional_buffered_cap(), floor_decimal_to_places(), force_fetch_hl_perp_meta() (+39 more)

### Community 4 - "Any"
Cohesion: 0.04
Nodes (18): bval(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), generate_attempt_id(), generate_cloid(), Intent (+10 more)

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
Cohesion: 0.07
Nodes (11): adverse_diff_pct(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill (+3 more)

### Community 13 - ".__init__"
Cohesion: 0.12
Nodes (3): scan_foreign_ws(), DedupeStore, ServiceStateWriter

### Community 14 - "_load_live_copy_config"
Cohesion: 0.13
Nodes (28): _active_live_copy_wallet_count(), add_live_config_wallet(), api_state(), _enforce_live_copy_cap(), _engine_wallet_summary(), _execution_guards_info(), ev(), get_global_controls() (+20 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), avg(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure() (+31 more)

### Community 16 - "RHC_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.07
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 17 - "threading"
Cohesion: 0.05
Nodes (12): check(), main(), slow_append(), Audit, me(), w(), check(), main() (+4 more)

### Community 18 - "sys"
Cohesion: 0.04
Nodes (17): check(), main(), check(), finish(), main(), check(), main(), check() (+9 more)

### Community 19 - "HeadroomMonitor"
Cohesion: 0.21
Nodes (3): HeadroomMonitor, info_weight(), level_for()

### Community 20 - "AuditLogWriter"
Cohesion: 0.08
Nodes (16): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), audit_write_failure_count(), AuditLogWriter, build_live_integrity_status(), _has_pending_exit_guard_proof() (+8 more)

### Community 21 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.11
Nodes (25): blocked(), check(), main(), neg_test(), parse_html(), setup_test_env(), test_engine_integrity(), test_inc() (+17 more)

### Community 22 - "tempfile"
Cohesion: 0.12
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
Cohesion: 0.08
Nodes (14): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file(), sha() (+6 more)

### Community 28 - "run_report.py"
Cohesion: 0.15
Nodes (15): build_report(), fetch_leader_fills(), _fmt_durs(), _fmt_stamps(), leader_fill_ids(), load_live_config_wallets(), load_outage_classify(), main() (+7 more)

### Community 29 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.05
Nodes (66): acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _append_spill_journal(), _attribution_json_safe(), _audit_fallback_remains(), _audit_flush_worker() (+58 more)

### Community 30 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (20): _match(), resolve_settlement(), add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main() (+12 more)

### Community 31 - "time"
Cohesion: 0.09
Nodes (21): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+13 more)

### Community 32 - "LiveCopyCore"
Cohesion: 0.04
Nodes (36): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+28 more)

### Community 33 - "self_test"
Cohesion: 0.07
Nodes (24): append_csv(), atomic_write_json(), classify_ignored_ws_message(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), extract_ws_fills() (+16 more)

### Community 34 - "run_self_test"
Cohesion: 0.07
Nodes (10): atomic_write_json(), _exchange_accepts_cloid(), learn_follower_dex(), run_self_test(), _clean_account_fixture(), order(), _write_csv(), WSManager (+2 more)

### Community 35 - "csv"
Cohesion: 0.12
Nodes (4): w(), check(), fake_fetcher(), w()

### Community 36 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.18
Nodes (16): _build_intent(), _cfg(), _check(), _fresh_ledger(), _git_head(), main(), _make_intent(), _make_intent_cfg() (+8 more)

### Community 37 - "utc_now_iso"
Cohesion: 0.17
Nodes (16): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+8 more)

### Community 38 - "re"
Cohesion: 0.06
Nodes (15): sections(), check(), main(), check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live() (+7 more)

### Community 39 - "test_core_queue_timing_stamps.py"
Cohesion: 0.06
Nodes (7): fill(), run(), Audit, fill(), Ledger, plan(), StopAfterOneSample

### Community 40 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.14
Nodes (15): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+7 more)

### Community 41 - "IntentBuilder"
Cohesion: 0.05
Nodes (23): list_perp_dexes(), master_exposure(), post_many(), _follower_dex_names(), follower_dex_scope(), follower_mid(), stale(), IntentBuilder (+15 more)

### Community 42 - "Path"
Cohesion: 0.13
Nodes (24): _account_orphan_signed_size(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key(), invalidate_model_cache() (+16 more)

### Community 43 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 44 - "read_csv_rows"
Cohesion: 0.06
Nodes (24): _owned_note(), prof, read_csv_rows(), _market_fixture(), _sdk_cloid(), send_attempt_rows(), 2. Top tracemalloc allocation lines (`f37b9c1`, 50 MB synthetic CSV), 4. Interpretation - ranking by contribution to the observed 4.5 GB (+16 more)

### Community 45 - "main"
Cohesion: 0.09
Nodes (6): check(), main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 46 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.09
Nodes (19): main(), make_csv(), measure(), rss_mb(), _addr(), _avail_mb(), build_intents(), build_matcher_stub() (+11 more)

### Community 48 - "NLS_RESIDUAL_harness_2a269ad_v2.py"
Cohesion: 0.26
Nodes (16): utc_now_iso(), certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check() (+8 more)

### Community 49 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.27
Nodes (15): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+7 more)

### Community 50 - "ENG-001-004_harness_43731b4f.py"
Cohesion: 0.12
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 51 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 52 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 54 - "main"
Cohesion: 0.10
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 55 - "test_core_reduce_only_repair.py"
Cohesion: 0.14
Nodes (5): poll_copy_account_fills(), Audit, Ledger, run(), rows()

### Community 56 - "test_http_keepalive.py"
Cohesion: 0.13
Nodes (3): _Flaky, H, Mon

### Community 57 - "probe_reearn.py"
Cohesion: 0.17
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 58 - "main"
Cohesion: 0.13
Nodes (7): check(), FakeExchange, main(), error_contexts(), errors(), hold_runtime_state_lock(), wait_for_json_file()

### Community 59 - "exchange_truth.py"
Cohesion: 0.16
Nodes (8): claim_network_stamp(), env_with_file(), network_endpoints(), NetworkConfigError, resolve_networks(), stamp_state_refusal(), state_present(), terminal_reject_evidence()

### Community 60 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (17): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+9 more)

### Community 62 - "J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)"
Cohesion: 0.22
Nodes (8): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

### Community 63 - "main"
Cohesion: 0.13
Nodes (6): check(), main(), engine_order(), land(), load_run(), producer()

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "main"
Cohesion: 0.15
Nodes (8): check(), main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 66 - "math"
Cohesion: 0.06
Nodes (12): check(), main(), _note_read_on_current(), slow(), fetch(), p90(), check(), main() (+4 more)

### Community 67 - "test_core_clo_dispatch_prefilter.py"
Cohesion: 0.06
Nodes (9): Config, fill(), WarmPool, check(), main(), check(), main(), __init__() (+1 more)

### Community 68 - "pathlib"
Cohesion: 0.18
Nodes (23): get_function_source(), imports_of(), is_b4(), main(), mutate(), prod_files(), scan(), baseline_deps() (+15 more)

### Community 69 - "subprocess"
Cohesion: 0.05
Nodes (27): git(), load(), main(), record(), check(), _load_committed_engine(), main(), neg() (+19 more)

### Community 70 - "test_core_slot_reservation_pacing.py"
Cohesion: 0.16
Nodes (6): FakeExchange, RecordingSenderGateway, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order()

### Community 71 - "HTMLElement"
Cohesion: 0.12
Nodes (3): HTMLElement, SimpleHTMLParser, verify_html_element()

### Community 72 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

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

### Community 77 - "fnum"
Cohesion: 0.06
Nodes (25): canonical_coin_key(), _chain_sorted(), _coin_key_map(), collapse_stale_runs(), close_run(), ExchangeReconciler, fnum(), follower_position_mark() (+17 more)

### Community 78 - "headroom.py"
Cohesion: 0.16
Nodes (4): CountingRequests, current_request_lane(), install_session_counter(), counted_request()

### Community 80 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.08
Nodes (15): cfg(), check(), main(), WebSocketApp(), wait_for(), build_cfg(), check(), FakeApp (+7 more)

### Community 81 - "test_cert_scripts.py"
Cohesion: 0.21
Nodes (3): ExportLeaderFills, Gap5DiskGuard, load_module()

### Community 82 - "main"
Cohesion: 0.13
Nodes (13): attach_send_result(), clear_unresolved_send(), _mut(), configure_paths(), persist_unresolved_send(), _mut(), _state_write(), check() (+5 more)

### Community 83 - "json"
Cohesion: 0.07
Nodes (22): Clock, events(), check(), main(), fresh(), write(), check(), main() (+14 more)

### Community 84 - "main"
Cohesion: 0.18
Nodes (5): check(), main(), config(), gate(), wallets()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 86 - "cert_memory_scan.py"
Cohesion: 0.19
Nodes (5): core_import(), decide(), main(), measure(), rss_mb()

### Community 87 - "run"
Cohesion: 0.23
Nodes (3): Gap1OutageClassifier, Gap3LiqParity, run()

### Community 88 - "test_core_xyz_recovery_safety.py"
Cohesion: 0.15
Nodes (4): active_for_coin(), Audit, close_plan(), Ledger

### Community 90 - "_model_dashboard_response"
Cohesion: 0.18
Nodes (10): _kick_model_cache_refresh_background(), _refresh(), _model_cache_snapshot_nonblocking(), model_dashboard(), _model_dashboard_html_cache_get(), _model_dashboard_html_cache_latest_get(), _model_dashboard_html_cache_store(), _model_dashboard_last_good_html_disk_get() (+2 more)

### Community 93 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 94 - "test_core_headroom_foreign_ws.py"
Cohesion: 0.17
Nodes (5): _run(), Clock, events(), scanner(), settle()

### Community 95 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 97 - "test_g2_copy_correctness.py"
Cohesion: 0.18
Nodes (8): check(), main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), _f(), stage_stats()

### Community 100 - "collections"
Cohesion: 0.14
Nodes (12): as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows(), rows(), classify() (+4 more)

### Community 101 - "argparse"
Cohesion: 0.20
Nodes (11): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float() (+3 more)

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
Cohesion: 0.10
Nodes (8): block_reasons(), classify(), main(), missing_detail(), _rows(), Audit, fake_urlopen(), Resp

### Community 113 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.15
Nodes (10): _fill_key(), master_userfills(), master_userfills_all_dexes(), ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-08: Startup/recovery truth includes all perp DEX scopes, ENG-INV-09: Exchange truth outranks local replay, File Hashes (+2 more)

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 116 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 117 - "test_core_audit_reduce_only_matches_wire.py"
Cohesion: 0.23
Nodes (5): check(), FakeExchange, Led, make_intent(), run()

### Community 118 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.29
Nodes (6): Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 119 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

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

### Community 141 - "cert_disk_guard.py"
Cohesion: 0.47
Nodes (7): decide(), deny_write(), icacls_available(), main(), restore_write(), _run(), whoami()

### Community 142 - "valid_address"
Cohesion: 0.25
Nodes (5): identity_ok(), master_account_net(), runtime_master_identity(), _state_payloads(), valid_address()

### Community 143 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 147 - "FakeExchange"
Cohesion: 0.33
Nodes (3): FakeExchange, drive_send(), drive_send()

### Community 149 - "_post"
Cohesion: 0.22
Nodes (5): http_post(), _post(), rolling_day_pnl(), start_keepalive(), loop()

### Community 150 - "PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)"
Cohesion: 0.40
Nodes (4): Evidence-thinness (honest), Headline (3 lines), Model used (named per part), PORT_VS_REBUILD.md — port-vs-rebuild audit (REVIEW ONLY, advisory, no code changes)

### Community 153 - "test_spot_gate_refusal.py"
Cohesion: 0.38
Nodes (4): check(), main(), decide(), fill()

## Knowledge Gaps
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `Any` to `run_self_test`, `ORDER_CORRECTION_harness_fefc2b04.py`, `IntentBuilder`, `read_csv_rows`, `.__init__`, `fnum`, `AuditLogWriter`, `test_core_audit_reduce_only_matches_wire.py`, `HL_Live_Copy_Service_Core.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `time`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Should `utc_now_ms` be split into smaller, more focused modules?**
  _Cohesion score 0.06653683868873743 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `fnum` to `utc_now_ms`, `LiveCopyCore`, `run_self_test`, `Any`, `IntentBuilder`, `Rows`, `read_csv_rows`, `.__init__`, `AuditLogWriter`, `ConfigManager`, `HL_Live_Copy_Service_Core.py`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Should `HTMLElement` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Why does `DedupeStore` connect `.__init__` to `utc_now_ms`, `LiveCopyCore`, `run_self_test`, `ORDER_CORRECTION_harness_fefc2b04.py`, `shutil`, `Rows`, `NLS_RESIDUAL_harness_2a269ad_v4.py`, `NLS_RESIDUAL_harness_2a269ad_v2.py`, `NLS_RESIDUAL_harness_2a269ad_v3.py`, `HL_Live_Copy_Service_Core.py`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08524590163934426 - nodes in this community are weakly interconnected._