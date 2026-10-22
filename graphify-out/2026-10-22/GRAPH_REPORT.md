# Graph Report - hl-build3-restart-95b02fa-20261022  (2026-10-22)

## Corpus Check
- 290 files · ~571,413 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3555 nodes · 9603 edges · 155 communities (127 shown, 28 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 849 edges (avg confidence: 0.87)
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
- DedupeStore
- HL_Live_Copy_Service_Core.py
- HL_Copy_App_SSOT.py
- RHC_RESIDUAL_harness_2a269ad.py
- pathlib
- sys
- HeadroomMonitor
- build_live_integrity_status
- UI_harness_fa9d9f55ff.py
- HEALTH_CORRECTION_harness_fefc2b04.py
- inum
- _fetch_user_realized_pnl_snapshot
- Any
- UI_CORRECTION_harness_2d29211.py
- CTRL_probe_t_967fad56.py
- run_report.py
- _replay_audit_fallback
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- LiveCopyCore
- self_test
- run_self_test
- _row_time_ms
- ORDER_CORRECTION_harness_fefc2b04.py
- utc_now_iso
- re
- test_core_audit_append_never_drops.py
- ENG-015-016-TNF17_harness.py
- IntentBuilder
- load_json
- plan_catchup
- AuditLogWriter
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
- bench_memory_profile.py
- main
- probe_reearn.py
- main
- exchange_truth.py
- census_inv_06_09.py
- Master Product Invariants and Certification Contract
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- main
- Detail
- main
- main
- main
- rowbound_oracle.py
- json
- FakeExchange
- HTMLElement
- _record_core_fatal
- NLS_RESIDUAL_harness_2a269ad.py
- Rows
- main
- main
- fnum
- block_num
- Any
- test_core_ws_pool_and_slots.py
- Path
- fnum
- time
- main
- ENG-015 / ENG-016 / TN-F17 Certification Report
- cert_memory_scan.py
- run
- math
- main
- get
- Inject
- PartialWriteThenFail
- card_hygiene.py
- test_core_reduce_only_repair.py
- run_engine_checks
- TimedLock
- .wallets
- test_http_keepalive.py
- ENG-INV-03-05_oracle_t_ff1af604.py
- cert_common.py
- cert_liq_parity_offline.py
- csv
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- test_exchange_truth_retry.py
- main
- PartialThenFull
- test_core_warm_dex_clients.py
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- main
- Probe
- ENG-INV-06..09 Non-Vacuous Static Census Report
- J2 Local Rejects - Proposed Patch Diffs
- test_core_queue_timing_stamps.py
- main
- main
- _lock_for
- main
- _LatestStatusWriteWorker
- claim_network_stamp
- test_core_audit_header_cache.py
- argparse
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- test_core_liq_isolated.py
- tempfile
- shutil
- Certification run status
- NetworkConfigError
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- Config
- main
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- FakeExchange
- cert_disk_guard.py
- H
- render_chart
- FakeExchange
- AppendFail
- Led
- append_csv
- test_eng012_low_latency
- http_post
- verify_js_reference
- verify_api_endpoint
- main
- acquire_global_instance_lock
- ast

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 156 edges
2. `SenderGateway` - 112 edges
3. `utc_now_ms()` - 102 edges
4. `LiveCopyCore` - 82 edges
5. `fnum()` - 76 edges
6. `log_error()` - 73 edges
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

## Communities (155 total, 28 thin omitted)

### Community 0 - "utc_now_ms"
Cohesion: 0.07
Nodes (25): request_lane(), _adoptable_intent_rows(), canonical_copy_fill_id(), claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs() (+17 more)

### Community 1 - "HTMLElement"
Cohesion: 0.13
Nodes (3): extract_table_headers(), HTMLElement, SimpleHTMLParser

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.13
Nodes (10): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, executable_price_from_fill_payload(), FixedModeAuthorityConflict (+2 more)

### Community 3 - "HL_Live_Copy_Service.py"
Cohesion: 0.08
Nodes (28): append_send_attempt(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema(), ensure_dirs(), fixed_notional_buffered_cap(), floor_decimal_to_places(), get_wallet_live_config() (+20 more)

### Community 4 - "Any"
Cohesion: 0.04
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
Cohesion: 0.11
Nodes (26): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test(), _build_intent(), check() (+18 more)

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
Cohesion: 0.10
Nodes (11): adverse_diff_pct(), append_csv(), audit_notes_for_fill(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, LeaderFill, LiveWalletConfig (+3 more)

### Community 13 - "DedupeStore"
Cohesion: 0.17
Nodes (3): CycleSummary, DedupeStore, ServiceStateWriter

### Community 14 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.04
Nodes (10): install_session_counter(), scan_foreign_ws(), _check(), load_existing_intents(), project_isolated_liquidation_px(), reject_category_from_text(), send_terminal_state(), _short() (+2 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+31 more)

### Community 16 - "RHC_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.07
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 17 - "pathlib"
Cohesion: 0.04
Nodes (11): check(), main(), slow_append(), check(), main(), hold_shared_lock(), slow_shared_lock_holder_for_diag(), RecordingSenderGateway (+3 more)

### Community 18 - "sys"
Cohesion: 0.06
Nodes (12): check(), finish(), main(), WarmPool, check(), main(), check(), main() (+4 more)

### Community 19 - "HeadroomMonitor"
Cohesion: 0.11
Nodes (8): CountingRequests, current_request_lane(), HeadroomMonitor, _run(), info_weight(), counted_request(), level_for(), scanner()

### Community 20 - "build_live_integrity_status"
Cohesion: 0.11
Nodes (12): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row() (+4 more)

### Community 21 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.11
Nodes (25): blocked(), check(), main(), neg_test(), parse_html(), setup_test_env(), test_engine_integrity(), test_inc() (+17 more)

### Community 22 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 23 - "inum"
Cohesion: 0.08
Nodes (38): _account_card_lines(), active_wallet(), active_wallet_row(), avg(), core_missing(), core_td(), css_class(), dash_td() (+30 more)

### Community 24 - "_fetch_user_realized_pnl_snapshot"
Cohesion: 0.13
Nodes (18): _account_reconciliation_baseline_timestamp(), _build_account_reconciliation(), _build_health_summary(), _build_pnl_tally(), _earliest_real_order_filled_ms(), _engine_run_key(), _fetch_exchange_account_snapshot(), _fetch_user_realized_pnl_snapshot() (+10 more)

### Community 25 - "Any"
Cohesion: 0.08
Nodes (51): _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_top_status(), _build_live_wallet_derived(), _build_live_wallet_rows(), _build_manual_reconciliation_rows(), _build_real_copy_positions() (+43 more)

### Community 26 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.12
Nodes (23): blocked(), check(), main(), neg_test(), parse_html(), parse_ssot_home_table_headers(), parse_ssot_table_headers(), setup_test_env() (+15 more)

### Community 27 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 28 - "run_report.py"
Cohesion: 0.10
Nodes (22): check(), main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), build_report(), _f() (+14 more)

### Community 29 - "_replay_audit_fallback"
Cohesion: 0.21
Nodes (12): _append_spill_journal(), _audit_fallback_remains(), _audit_row_data(), _audit_row_payload(), _fallback_path(), _read_spill_journal(), replay_audit_fallback(), _replay_audit_fallback() (+4 more)

### Community 30 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 31 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.11
Nodes (17): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+9 more)

### Community 32 - "LiveCopyCore"
Cohesion: 0.04
Nodes (35): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+27 more)

### Community 33 - "self_test"
Cohesion: 0.08
Nodes (20): classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), is_benign_ws_error(), _is_reduce_only_full_close_bypass(), is_ws_abnf_frame(), parse_hl_order_status(), parse_ws_leader_fill() (+12 more)

### Community 34 - "run_self_test"
Cohesion: 0.08
Nodes (8): _exchange_accepts_cloid(), LeaderFillIngestor, run_self_test(), order(), _write_csv(), WSManager, on_message(), on_open()

### Community 35 - "_row_time_ms"
Cohesion: 0.21
Nodes (11): _fetch_user_fills_by_time(), _fetch_user_fills_cached(), _fetch_user_fills_paged(), _fetch_user_funding_cached(), _fetch_user_funding_paged(), _fill_dedupe_key(), _funding_dedupe_key(), _funding_usdc() (+3 more)

### Community 36 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 37 - "utc_now_iso"
Cohesion: 0.17
Nodes (16): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+8 more)

### Community 38 - "re"
Cohesion: 0.05
Nodes (14): block_reasons(), classify(), main(), missing_detail(), _rows(), sections(), check(), main() (+6 more)

### Community 39 - "test_core_audit_append_never_drops.py"
Cohesion: 0.05
Nodes (9): fill(), run(), Audit, fill(), Audit, Audit, guard(), Ledger (+1 more)

### Community 40 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.14
Nodes (15): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+7 more)

### Community 41 - "IntentBuilder"
Cohesion: 0.03
Nodes (27): list_perp_dexes(), master_exposure(), _post(), post_many(), rolling_day_pnl(), _follower_dex_names(), follower_dex_scope(), follower_mid() (+19 more)

### Community 42 - "load_json"
Cohesion: 0.11
Nodes (28): _account_orphan_signed_size(), _append_exchange_history(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key() (+20 more)

### Community 43 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 44 - "AuditLogWriter"
Cohesion: 0.04
Nodes (36): AuditLogWriter, _BoundedRaw, iter_audit_history(), iter_csv_rows(), _owned_note(), prof, read_csv_rows(), _market_fixture() (+28 more)

### Community 45 - "main"
Cohesion: 0.09
Nodes (6): check(), main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 46 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.24
Nodes (17): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+9 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.13
Nodes (15): _addr(), _avail_mb(), build_intents(), build_matcher_stub(), gen_csv(), _hash(), main(), make_row() (+7 more)

### Community 48 - "NLS_RESIDUAL_harness_2a269ad_v2.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 49 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 50 - "ENG-001-004_harness_43731b4f.py"
Cohesion: 0.10
Nodes (10): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+2 more)

### Community 51 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 52 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 54 - "main"
Cohesion: 0.12
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 55 - "bench_memory_profile.py"
Cohesion: 0.27
Nodes (4): main(), make_csv(), measure(), rss_mb()

### Community 56 - "main"
Cohesion: 0.13
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 57 - "probe_reearn.py"
Cohesion: 0.17
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 58 - "main"
Cohesion: 0.07
Nodes (9): check(), FakeExchange, main(), error_contexts(), errors(), hold_runtime_state_lock(), wait_for_json_file(), fake_urlopen() (+1 more)

### Community 59 - "exchange_truth.py"
Cohesion: 0.14
Nodes (9): env_with_file(), identity_ok(), master_account_net(), _match(), resolve_settlement(), runtime_master_identity(), _state_payloads(), terminal_reject_evidence() (+1 more)

### Community 60 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.07
Nodes (24): LeaderEquitySingleflightTests, result(), 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means (+16 more)

### Community 62 - "J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)"
Cohesion: 0.22
Nodes (8): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

### Community 63 - "main"
Cohesion: 0.13
Nodes (7): check(), main(), engine_order(), land(), load_run(), producer(), poll_copy_account_fills()

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "main"
Cohesion: 0.17
Nodes (8): check(), main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 66 - "main"
Cohesion: 0.17
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 67 - "main"
Cohesion: 0.13
Nodes (4): check(), main(), __init__(), order()

### Community 68 - "rowbound_oracle.py"
Cohesion: 0.29
Nodes (16): baseline_deps(), closure(), dyn_imports(), git_show(), imports_of(), is_b4(), list_prod(), load_approved() (+8 more)

### Community 69 - "json"
Cohesion: 0.03
Nodes (44): check(), main(), main(), main(), route_present(), check_hwm(), check_i1(), check_i3() (+36 more)

### Community 70 - "FakeExchange"
Cohesion: 0.13
Nodes (5): FakeExchange, SlotReservationPacingTests, place_order(), cancel_order(), VirtualClock

### Community 71 - "HTMLElement"
Cohesion: 0.12
Nodes (3): HTMLElement, SimpleHTMLParser, verify_html_element()

### Community 72 - "_record_core_fatal"
Cohesion: 0.21
Nodes (14): _append_core_fatal_row(), _attribution_json_safe(), _drain_status_write_workers(), install_core_attribution_hooks(), _atexit_marker(), _handler(), _sys_excepthook(), _thread_excepthook() (+6 more)

### Community 73 - "NLS_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.26
Nodes (16): utc_now_iso(), certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check() (+8 more)

### Community 74 - "Rows"
Cohesion: 0.15
Nodes (11): 6. Open decisions register, 3. Convergence, 4. Dust close, 5. Liquidation parity (+ cross 3x), 6. Ledger repair / ownership, 7. Send path: idempotency, cloid, 9. Audit-write / disk-full, Bottom line for the Boss condition (+3 more)

### Community 75 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 76 - "main"
Cohesion: 0.14
Nodes (4): check(), main(), startup_orphan_order_check(), wait_for_json_file()

### Community 77 - "fnum"
Cohesion: 0.06
Nodes (28): _manual_sleeve_exists(), canonical_coin_key(), canonical_coin_resolved(), _chain_sorted(), _coin_key_map(), collapse_stale_runs(), close_run(), ExchangeReconciler (+20 more)

### Community 78 - "block_num"
Cohesion: 0.31
Nodes (7): block_num(), dd_current(), dd_max(), latest_history_block_dd(), max_history_block_dd(), sorted_rows(), key()

### Community 79 - "Any"
Cohesion: 0.09
Nodes (28): atomic_write_json(), attach_send_result(), clear_unresolved_send(), _mut(), fetch_live_fills_range(), fetch_live_fills_since(), fetch_public_executable_quote(), force_fetch_hl_perp_meta() (+20 more)

### Community 80 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.08
Nodes (15): cfg(), check(), main(), WebSocketApp(), wait_for(), build_cfg(), check(), FakeApp (+7 more)

### Community 81 - "Path"
Cohesion: 0.16
Nodes (10): acquire_instance_lock(), audit_history_paths(), _close_audit_handle(), ensure_csv_header(), _header_checked(), load_env_file(), _remember_header(), _replay_payload_present() (+2 more)

### Community 82 - "fnum"
Cohesion: 0.09
Nodes (10): configure_paths(), event_authorised_desired_net(), fnum(), reconcile_unresolved_send(), check(), Fixture, fresh(), main() (+2 more)

### Community 83 - "time"
Cohesion: 0.05
Nodes (15): Clock, events(), Clock, events(), settle(), slow(), check(), main() (+7 more)

### Community 84 - "main"
Cohesion: 0.18
Nodes (5): check(), main(), config(), gate(), wallets()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 86 - "cert_memory_scan.py"
Cohesion: 0.25
Nodes (5): core_import(), decide(), main(), measure(), rss_mb()

### Community 87 - "run"
Cohesion: 0.11
Nodes (7): ExportLeaderFills, Gap1OutageClassifier, Gap2MemoryScan, Gap3LiqParity, Gap5DiskGuard, load_module(), run()

### Community 88 - "math"
Cohesion: 0.16
Nodes (5): p90(), Ledger, plan(), p90(), p90()

### Community 90 - "get"
Cohesion: 0.06
Nodes (28): api_get_ui_state(), api_state(), ev(), get_live_audit_summary(), get_live_copy_summary(), get_wallet_meta(), home(), _kick_model_cache_refresh_background() (+20 more)

### Community 93 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 94 - "test_core_reduce_only_repair.py"
Cohesion: 0.15
Nodes (4): Audit, Ledger, run(), rows()

### Community 95 - "run_engine_checks"
Cohesion: 0.24
Nodes (6): check(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 99 - "ENG-INV-03-05_oracle_t_ff1af604.py"
Cohesion: 0.46
Nodes (6): imports_of(), is_b4(), main(), mutate(), prod_files(), scan()

### Community 100 - "cert_common.py"
Cohesion: 0.14
Nodes (12): as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows(), rows(), classify() (+4 more)

### Community 101 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 102 - "csv"
Cohesion: 0.06
Nodes (12): Audit, me(), w(), w(), check(), fake_fetcher(), w(), check() (+4 more)

### Community 103 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 105 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 106 - "main"
Cohesion: 0.25
Nodes (4): check(), main(), fill(), send()

### Community 109 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 110 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 111 - "main"
Cohesion: 0.32
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 113 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.15
Nodes (10): _fill_key(), master_userfills(), master_userfills_all_dexes(), ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-08: Startup/recovery truth includes all perp DEX scopes, ENG-INV-09: Exchange truth outranks local replay, File Hashes (+2 more)

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 116 - "main"
Cohesion: 0.32
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 117 - "main"
Cohesion: 0.25
Nodes (3): check(), main(), engine()

### Community 118 - "_lock_for"
Cohesion: 0.18
Nodes (9): _lock_for(), read_csv_tail_rows(), Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), Scripts, tools/cert — offline halves of the J4 certification gaps (task K2) (+1 more)

### Community 119 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 121 - "claim_network_stamp"
Cohesion: 0.33
Nodes (3): claim_network_stamp(), stamp_state_refusal(), state_present()

### Community 123 - "argparse"
Cohesion: 0.53
Nodes (3): main(), post(), wallets()

### Community 124 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 125 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 126 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 127 - "tempfile"
Cohesion: 0.05
Nodes (19): check(), main(), check(), main(), check(), main(), wallets(), main() (+11 more)

### Community 128 - "shutil"
Cohesion: 0.53
Nodes (3): build(), find_dir(), main()

### Community 129 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 130 - "NetworkConfigError"
Cohesion: 0.50
Nodes (3): network_endpoints(), NetworkConfigError, resolve_networks()

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

### Community 143 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 147 - "append_csv"
Cohesion: 0.14
Nodes (10): append_csv(), _audit_flush_worker(), _note_append(), note_audit_write_failure(), _note_lock_contention(), _schedule_audit_flush(), Findings (FAILS on main) and the fix in the patch, J1 — disk-full robustness: findings and proposed patch (+2 more)

### Community 149 - "http_post"
Cohesion: 0.40
Nodes (3): http_post(), start_keepalive(), loop()

### Community 153 - "main"
Cohesion: 0.50
Nodes (4): check(), main(), decide(), fill()

### Community 154 - "acquire_global_instance_lock"
Cohesion: 0.33
Nodes (3): acquire_global_instance_lock(), _global_holder_path(), _global_instance_lock_path()

### Community 158 - "ast"
Cohesion: 0.23
Nodes (5): exchange_order_calls(), SingleExchangeOrderCallsiteTest, get_function_source(), blob(), census()

## Knowledge Gaps
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `Any` to `run_self_test`, `ORDER_CORRECTION_harness_fefc2b04.py`, `IntentBuilder`, `AuditLogWriter`, `fnum`, `HL_Live_Copy_Service_Core.py`, `test_eng012_low_latency`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Should `utc_now_ms` be split into smaller, more focused modules?**
  _Cohesion score 0.0715372907153729 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `fnum` to `utc_now_ms`, `LiveCopyCore`, `run_self_test`, `Any`, `IntentBuilder`, `Rows`, `AuditLogWriter`, `DedupeStore`, `HL_Live_Copy_Service_Core.py`, `build_live_integrity_status`, `ConfigManager`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Should `HTMLElement` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Why does `ConfigManager` connect `ConfigManager` to `LiveCopyCore`, `.wallets`, `run_self_test`, `ORDER_CORRECTION_harness_fefc2b04.py`, `.send_mode_now`, `ENGINE_RESIDUAL_harness_2a269ad.py`, `Rows`, `AuditLogWriter`, `fnum`, `HL_Live_Copy_Service_Core.py`, `ENG-001-004_harness_43731b4f.py`, `test_eng012_low_latency`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08416389811738649 - nodes in this community are weakly interconnected._