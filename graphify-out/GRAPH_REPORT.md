# Graph Report - hl-build3-ui-4139c198-20261021  (2026-10-22)

## Corpus Check
- 289 files · ~572,598 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3554 nodes · 9596 edges · 150 communities (123 shown, 27 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 844 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4139c198`
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
- HeadroomMonitor
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- Path
- LiveCopyCore
- Path
- HL_Copy_App_SSOT.py
- run_self_test
- time
- sys
- CTRL_probe_t_967fad56.py
- build_live_integrity_status
- main
- tempfile
- HEALTH_CORRECTION_harness_fefc2b04.py
- main
- Inject
- UI_CORRECTION_harness_2d29211.py
- CopyFillMatcher
- cert_liq_parity_offline.py
- Any
- fnum
- _live_audit_summary_full
- HL_Live_Copy_Service_Core.py
- self_test
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- main
- main
- run_report.py
- test_core_audit_append_never_drops.py
- main
- utc_now_ms
- get
- ORDER_CORRECTION_harness_fefc2b04.py
- NLS_RESIDUAL_harness_2a269ad_v4.py
- subprocess
- utc_now_iso
- NLS_RESIDUAL_harness_2a269ad.py
- run
- plan_catchup
- shutil
- Any
- IntentBuilder
- fnum
- main
- collections
- _record_core_fatal
- NLS_RESIDUAL_harness_2a269ad_v3.py
- probe_reearn.py
- exchange_truth.py
- ENGINE_RESIDUAL_harness_2a269ad.py
- Master Product Invariants and Certification Contract
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- FakeExchange
- Detail
- main
- run_engine_checks
- census_inv_06_09.py
- rowbound_oracle.py
- HTMLElement
- main
- main
- Probe
- make_order_census_artifact.py
- main
- main
- main
- headroom.py
- ast
- main
- global_controls_tests
- test_core_append_truncate.py
- test_core_save_preserves_send_mode.py
- json
- cert_memory_scan.py
- ENG-015 / ENG-016 / TN-F17 Certification Report
- test_core_reduce_only_repair.py
- main
- StopAfterOneSample
- H
- convergence_shadow.py
- TimedLock
- test_ui_scoped_account_values.py
- card_hygiene.py
- test_exchange_truth_retry.py
- main
- DedupeStore
- main
- cert_disk_guard.py
- _model_dashboard_response
- main
- main
- main
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- http_post
- _LatestStatusWriteWorker
- test_core_network_and_global_controls.py
- test_core_liq_isolated.py
- main
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- run_negative_mutations
- re
- ENG-INV-03-05_oracle_t_ff1af604.py
- J2 Local Rejects - Proposed Patch Diffs
- test_core_standing_close_guard.py
- _rotate_audit_file
- main
- acquire_global_instance_lock
- Sink
- CountingReader
- main
- test_core_live_only_stream_cap.py
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- argparse
- append_csv
- Certification (Build 3 Repair)
- Certification run status
- test_j2_local_rejects.py
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- _BoundedRaw
- Config
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- main
- test_core_dust_rules.py
- main
- J1 — disk-full robustness: findings and proposed patch
- PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)
- WarmPool
- Clock
- Clock
- _Flaky
- Mon

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 156 edges
2. `SenderGateway` - 112 edges
3. `utc_now_ms()` - 101 edges
4. `LiveCopyCore` - 81 edges
5. `fnum()` - 76 edges
6. `log_error()` - 72 edges
7. `Intent` - 65 edges
8. `ConfigManager` - 64 edges
9. `self_test()` - 62 edges
10. `canonical_coin_key()` - 62 edges

## Surprising Connections (you probably didn't know these)
- `Row 6 — ledger repair / ownership` --references--> `_has_pending_exit_guard_proof()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `7. Send path: idempotency, cloid` --references--> `DedupeStore`  [INFERRED]
  process/PORT_VS_REBUILD.crosscheck-hermes.md → _archive/hl_stage2/HL_Live_Copy_Service_Core.py
- `6. Open decisions register` --references--> `purge_wallet_everywhere()`  [INFERRED]
  certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Sources & method` --references--> `_live_audit_summary()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py
- `Row 7 — send path (idempotency, cloid)` --references--> `_row_client_id()`  [INFERRED]
  process/PORT_VS_REBUILD.md → _archive/hl_stage2/HL_Copy_App_SSOT.py

## Import Cycles
- None detected.

## Communities (150 total, 27 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.07
Nodes (57): append_send_attempt(), atomic_write_json(), attach_send_result(), clear_unresolved_send(), _mut(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema() (+49 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (10): adverse_diff_pct(), audit_reason_for_fill(), dry_run_intent_audit_decision(), DryRunLiveCopyService, event_authorised_desired_net(), executable_price_from_fill_payload(), fnum(), LeaderFill (+2 more)

### Community 2 - "sleeve_from_leader_event_position"
Cohesion: 0.14
Nodes (9): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, FixedModeAuthorityConflict, proportional_sleeve_scale() (+1 more)

### Community 3 - "main"
Cohesion: 0.21
Nodes (7): configure_paths(), check(), Fixture, fresh(), main(), reset_master(), with_master()

### Community 4 - "SenderGateway"
Cohesion: 0.05
Nodes (17): bval(), canonical_coin_key(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), generate_attempt_id(), Intent (+9 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.11
Nodes (40): _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_norm(), api_set_ui_state(), api_wallet_meta(), _clean_wallet_config(), _clean_wallet_include() (+32 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "HeadroomMonitor"
Cohesion: 0.12
Nodes (7): CountingRequests, HeadroomMonitor, _run(), info_weight(), level_for(), scan_foreign_ws(), scanner()

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
Cohesion: 0.14
Nodes (21): _account_orphan_signed_size(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key(), invalidate_model_cache() (+13 more)

### Community 13 - "LiveCopyCore"
Cohesion: 0.04
Nodes (31): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+23 more)

### Community 14 - "Path"
Cohesion: 0.09
Nodes (27): append_csv(), _append_spill_journal(), _audit_fallback_remains(), _audit_flush_worker(), audit_history_paths(), _audit_row_data(), _audit_row_payload(), ensure_csv_header() (+19 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (42): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+34 more)

### Community 16 - "run_self_test"
Cohesion: 0.07
Nodes (21): _exchange_accepts_cloid(), ManualLedger, run_self_test(), _clean_account_fixture(), order(), make_gateway(), ENG-002: Proportional mode end-to-end, ENG-INV-06..09 Non-Vacuous Static Census Report (+13 more)

### Community 17 - "time"
Cohesion: 0.03
Nodes (31): check(), main(), p90(), events(), settle(), slow_append(), slow(), p90() (+23 more)

### Community 18 - "sys"
Cohesion: 0.02
Nodes (29): check(), finish(), main(), writer(), check(), main(), check(), main() (+21 more)

### Community 19 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 20 - "build_live_integrity_status"
Cohesion: 0.10
Nodes (12): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row() (+4 more)

### Community 21 - "main"
Cohesion: 0.06
Nodes (27): blocked(), check(), HTMLElement, main(), neg_test(), parse_html(), setup_test_env(), SimpleHTMLParser (+19 more)

### Community 22 - "tempfile"
Cohesion: 0.08
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 23 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 26 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.10
Nodes (24): blocked(), check(), extract_table_headers(), main(), neg_test(), parse_html(), parse_ssot_home_table_headers(), parse_ssot_table_headers() (+16 more)

### Community 27 - "CopyFillMatcher"
Cohesion: 0.07
Nodes (22): _adoptable_intent_rows(), AuditLogWriter, canonical_copy_fill_id(), claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs() (+14 more)

### Community 28 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 29 - "Any"
Cohesion: 0.06
Nodes (66): _account_card_lines(), active_wallet(), active_wallet_row(), avg(), block_num(), contract_money_equal(), core_missing(), core_td() (+58 more)

### Community 30 - "fnum"
Cohesion: 0.11
Nodes (27): _build_live_leader_performance(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), _classify_owned_exchange_net(), _exchange_field(), _exchange_signed_size(), fnum() (+19 more)

### Community 31 - "_live_audit_summary_full"
Cohesion: 0.07
Nodes (43): _account_reconciliation_baseline_timestamp(), _append_exchange_history(), _build_account_reconciliation(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_health_summary(), _build_live_top_status(), _build_pnl_tally() (+35 more)

### Community 32 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.06
Nodes (19): acquire_instance_lock(), generate_cloid(), is_spot_pair(), load_env_file(), load_existing_intents(), missed_entry_decision(), _owned_note(), project_isolated_liquidation_px() (+11 more)

### Community 33 - "self_test"
Cohesion: 0.08
Nodes (20): audit_notes_for_fill(), classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), is_benign_ws_error(), _is_reduce_only_full_close_bypass(), is_ws_abnf_frame(), parse_hl_order_status() (+12 more)

### Community 34 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 35 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.13
Nodes (14): add_check(), ast_parse_file(), main(), test_eng010_account_net_truth(), test_eng011_in_flight_suppression(), test_eng012_low_latency(), test_eng013_audit_trail(), test_eng014_event_disorders() (+6 more)

### Community 36 - "main"
Cohesion: 0.09
Nodes (9): check(), FakeExchange, main(), error_contexts(), errors(), hold_runtime_state_lock(), wait_for_json_file(), fake_urlopen() (+1 more)

### Community 37 - "main"
Cohesion: 0.18
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 38 - "run_report.py"
Cohesion: 0.10
Nodes (22): check(), main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), build_report(), _f() (+14 more)

### Community 39 - "test_core_audit_append_never_drops.py"
Cohesion: 0.05
Nodes (10): fill(), run(), Audit, fill(), Ledger, plan(), Audit, Audit (+2 more)

### Community 40 - "main"
Cohesion: 0.13
Nodes (5): check(), main(), WebSocketApp(), FakeApp, FakeWS

### Community 41 - "utc_now_ms"
Cohesion: 0.03
Nodes (30): list_perp_dexes(), master_account_net(), master_exposure(), master_userfills(), master_userfills_all_dexes(), _post(), post_many(), rolling_day_pnl() (+22 more)

### Community 42 - "get"
Cohesion: 0.07
Nodes (23): api_equity(), api_get_ui_state(), api_metrics(), api_model_cache_status(), api_state(), api_trades(), _build_live_wallet_rows(), get_live_audit_summary() (+15 more)

### Community 43 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.09
Nodes (22): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+14 more)

### Community 44 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.05
Nodes (48): read_csv_rows(), _market_fixture(), send_attempt_rows(), 2. Top tracemalloc allocation lines (`f37b9c1`, 50 MB synthetic CSV), 3. Verdict per suspect (prove / disprove), 4. Interpretation - ranking by contribution to the observed 4.5 GB, 5. Fix verification on current `main` (`06435bf`), Engine memory profile - HL_Live_Copy_Service_Core.py (+40 more)

### Community 45 - "subprocess"
Cohesion: 0.04
Nodes (31): git(), load(), main(), record(), check(), line_count(), main(), mutate_file() (+23 more)

### Community 46 - "utc_now_iso"
Cohesion: 0.16
Nodes (17): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+9 more)

### Community 47 - "NLS_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.07
Nodes (34): main(), make_csv(), measure(), rss_mb(), _addr(), _avail_mb(), build_intents(), build_matcher_stub() (+26 more)

### Community 48 - "run"
Cohesion: 0.11
Nodes (7): ExportLeaderFills, Gap1OutageClassifier, Gap2MemoryScan, Gap3LiqParity, Gap5DiskGuard, load_module(), run()

### Community 49 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 50 - "shutil"
Cohesion: 0.11
Nodes (25): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+17 more)

### Community 51 - "Any"
Cohesion: 0.06
Nodes (19): atomic_write_json(), canonical_coin_resolved(), _coin_key_map(), ExchangeReconciler, load_json(), load_xyz_position_state(), record_core_phase(), repair_flat_ledger_only_positions() (+11 more)

### Community 52 - "IntentBuilder"
Cohesion: 0.11
Nodes (10): IntentBuilder, Conclusion, ENG-001/002/004 Certification Report, ENG-001 Negative Tests, ENG-001: Repeated leader ADDs converge to target, ENG-002 Negative Tests, ENG-004 Negative Tests, Negative Tests (non-vacuous proof) (+2 more)

### Community 53 - "fnum"
Cohesion: 0.06
Nodes (13): _manual_sleeve_exists(), _chain_sorted(), collapse_stale_runs(), close_run(), ConfigManager, fnum(), is_valid_wallet(), learn_follower_dex() (+5 more)

### Community 54 - "main"
Cohesion: 0.09
Nodes (6): check(), main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 55 - "collections"
Cohesion: 0.14
Nodes (12): as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows(), rows(), classify() (+4 more)

### Community 56 - "_record_core_fatal"
Cohesion: 0.21
Nodes (14): _append_core_fatal_row(), _attribution_json_safe(), _drain_status_write_workers(), install_core_attribution_hooks(), _atexit_marker(), _handler(), _sys_excepthook(), _thread_excepthook() (+6 more)

### Community 57 - "NLS_RESIDUAL_harness_2a269ad_v3.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 58 - "probe_reearn.py"
Cohesion: 0.18
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 59 - "exchange_truth.py"
Cohesion: 0.09
Nodes (13): claim_network_stamp(), env_with_file(), _fill_key(), identity_ok(), _match(), network_endpoints(), NetworkConfigError, resolve_networks() (+5 more)

### Community 60 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.42
Nodes (12): _build_intent(), check(), main(), _make_config(), _make_ledger(), neg_test(), _now_ms(), test_eng_val_01() (+4 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (18): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+10 more)

### Community 62 - "J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)"
Cohesion: 0.22
Nodes (8): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

### Community 63 - "FakeExchange"
Cohesion: 0.13
Nodes (6): FakeExchange, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order(), VirtualClock

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 66 - "run_engine_checks"
Cohesion: 0.24
Nodes (6): check(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 67 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 68 - "rowbound_oracle.py"
Cohesion: 0.29
Nodes (16): baseline_deps(), closure(), dyn_imports(), git_show(), imports_of(), is_b4(), list_prod(), load_approved() (+8 more)

### Community 70 - "main"
Cohesion: 0.13
Nodes (7): check(), main(), engine_order(), land(), load_run(), producer(), poll_copy_account_fills()

### Community 71 - "main"
Cohesion: 0.12
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 73 - "make_order_census_artifact.py"
Cohesion: 0.53
Nodes (4): blob(), calls_in(), head(), main()

### Community 74 - "main"
Cohesion: 0.13
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 75 - "main"
Cohesion: 0.17
Nodes (8): check(), main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 76 - "main"
Cohesion: 0.14
Nodes (4): check(), main(), startup_orphan_order_check(), wait_for_json_file()

### Community 77 - "headroom.py"
Cohesion: 0.12
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 78 - "ast"
Cohesion: 0.23
Nodes (5): exchange_order_calls(), SingleExchangeOrderCallsiteTest, get_function_source(), blob(), census()

### Community 79 - "main"
Cohesion: 0.13
Nodes (4): check(), main(), __init__(), order()

### Community 80 - "global_controls_tests"
Cohesion: 0.24
Nodes (6): global_controls_tests(), config(), decide(), fill(), send(), set_mid()

### Community 82 - "test_core_save_preserves_send_mode.py"
Cohesion: 0.27
Nodes (4): check(), main(), simulate_save_handler(), write_cfg()

### Community 83 - "json"
Cohesion: 0.05
Nodes (31): check(), main(), check(), main(), write_cfg(), events(), check(), main() (+23 more)

### Community 84 - "cert_memory_scan.py"
Cohesion: 0.25
Nodes (5): core_import(), decide(), main(), measure(), rss_mb()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 86 - "test_core_reduce_only_repair.py"
Cohesion: 0.15
Nodes (4): Audit, Ledger, run(), rows()

### Community 87 - "main"
Cohesion: 0.17
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 90 - "convergence_shadow.py"
Cohesion: 0.40
Nodes (6): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test()

### Community 92 - "test_ui_scoped_account_values.py"
Cohesion: 0.33
Nodes (6): audit_fixture(), check(), load_ui_without_environment(), main(), render_headless(), write_json()

### Community 93 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 94 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 95 - "main"
Cohesion: 0.25
Nodes (4): check(), main(), fill(), send()

### Community 97 - "main"
Cohesion: 0.18
Nodes (5): check(), main(), config(), gate(), wallets()

### Community 98 - "cert_disk_guard.py"
Cohesion: 0.47
Nodes (7): decide(), deny_write(), icacls_available(), main(), restore_write(), _run(), whoami()

### Community 99 - "_model_dashboard_response"
Cohesion: 0.13
Nodes (13): get_wallet_meta(), _kick_model_cache_refresh_background(), _refresh(), _model_cache_snapshot_nonblocking(), model_dashboard(), _model_dashboard_html_cache_get(), _model_dashboard_html_cache_latest_get(), _model_dashboard_html_cache_store() (+5 more)

### Community 100 - "main"
Cohesion: 0.32
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 101 - "main"
Cohesion: 0.25
Nodes (3): check(), main(), run()

### Community 103 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 104 - "http_post"
Cohesion: 0.40
Nodes (3): http_post(), start_keepalive(), loop()

### Community 105 - "_LatestStatusWriteWorker"
Cohesion: 0.21
Nodes (3): _check(), _LatestStatusWriteWorker, TestFailure

### Community 106 - "test_core_network_and_global_controls.py"
Cohesion: 0.14
Nodes (7): check(), main(), check(), last_json(), main(), network_tests(), run_py()

### Community 107 - "test_core_liq_isolated.py"
Cohesion: 0.20
Nodes (4): Fake, leader(), post(), mk()

### Community 109 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 110 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 111 - "run_negative_mutations"
Cohesion: 0.25
Nodes (4): add_negative(), count_order_call_sites(), count_process_spawns(), run_negative_mutations()

### Community 112 - "re"
Cohesion: 0.04
Nodes (24): block_reasons(), classify(), main(), missing_detail(), _rows(), sections(), check(), main() (+16 more)

### Community 113 - "ENG-INV-03-05_oracle_t_ff1af604.py"
Cohesion: 0.46
Nodes (6): imports_of(), is_b4(), main(), mutate(), prod_files(), scan()

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 115 - "test_core_standing_close_guard.py"
Cohesion: 0.24
Nodes (4): Audit, guard(), Ledger, plan()

### Community 116 - "_rotate_audit_file"
Cohesion: 0.15
Nodes (4): _close_audit_handle(), _rotate_audit_file(), rotated_audit_paths(), AppendFail

### Community 117 - "main"
Cohesion: 0.32
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 118 - "acquire_global_instance_lock"
Cohesion: 0.33
Nodes (3): acquire_global_instance_lock(), _global_holder_path(), _global_instance_lock_path()

### Community 122 - "test_core_live_only_stream_cap.py"
Cohesion: 0.28
Nodes (3): check(), main(), wallets()

### Community 124 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 125 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 126 - "argparse"
Cohesion: 0.53
Nodes (3): main(), post(), wallets()

### Community 127 - "append_csv"
Cohesion: 0.60
Nodes (3): append_csv(), stage_auto_row(), should_write_would_send()

### Community 128 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 129 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 130 - "test_j2_local_rejects.py"
Cohesion: 0.12
Nodes (4): clear_resting_entries(), FakeExchange, main(), one()

### Community 131 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 134 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

### Community 135 - "Mainnet crash and ambiguous-send recovery"
Cohesion: 0.50
Nodes (3): After a crash or uncertain send, Mainnet crash and ambiguous-send recovery, Wallet-roster changes

### Community 140 - "main"
Cohesion: 0.50
Nodes (4): check(), main(), decide(), fill()

### Community 142 - "main"
Cohesion: 0.25
Nodes (3): check(), main(), engine()

### Community 143 - "J1 — disk-full robustness: findings and proposed patch"
Cohesion: 0.50
Nodes (3): Findings (FAILS on main) and the fix in the patch, J1 — disk-full robustness: findings and proposed patch, What already holds on main (no change needed)

### Community 144 - "PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)"
Cohesion: 0.50
Nodes (3): Bottom line for the Boss condition, Headline, PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)

## Knowledge Gaps
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `SenderGateway` to `HL_Live_Copy_Service_Core.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`, `utc_now_ms`, `ORDER_CORRECTION_harness_fefc2b04.py`, `NLS_RESIDUAL_harness_2a269ad_v4.py`, `Path`, `run_self_test`, `Any`, `fnum`, `CopyFillMatcher`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06523855890944498 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `fnum` to `HL_Live_Copy_Service_Core.py`, `DedupeStore`, `SenderGateway`, `utc_now_ms`, `LiveCopyCore`, `run_self_test`, `Any`, `build_live_integrity_status`, `IntentBuilder`, `CopyFillMatcher`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07544757033248081 - nodes in this community are weakly interconnected._
- **Why does `utc_now_ms()` connect `utc_now_ms` to `HL_Live_Copy_Service_Core.py`, `DedupeStore`, `SenderGateway`, `test_core_liq_isolated.py`, `LiveCopyCore`, `Path`, `test_core_dust_rules.py`, `run_self_test`, `Any`, `build_live_integrity_status`, `IntentBuilder`, `fnum`, `test_core_standing_close_guard.py`, `_record_core_fatal`, `CopyFillMatcher`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Should `sleeve_from_leader_event_position` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `SenderGateway` be split into smaller, more focused modules?**
  _Cohesion score 0.04683447749809306 - nodes in this community are weakly interconnected._