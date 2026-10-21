# Graph Report - hl-build3-liq-parity-floor-cap-20261021  (2026-10-21)

## Corpus Check
- 282 files · ~567,498 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3486 nodes · 9445 edges · 141 communities (125 shown, 16 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 837 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7173ef65`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HL_Live_Copy_Service.py
- DryRunLiveCopyService
- dry_run_intent_audit_decision
- main
- SenderGateway
- Architecture Contract — Hyperliquid Build 3 Repair
- load_ui_state
- Operating Protocol
- HeadroomMonitor
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Bootstrap
- Hyperliquid Build 3 Repair
- load_json
- LiveCopyCore
- HL_Live_Copy_Service_Core.py
- HL_Copy_App_SSOT.py
- test_http_keepalive.py
- threading
- sys
- Any
- AuditLogWriter
- UI_harness_fa9d9f55ff.py
- tempfile
- HEALTH_CORRECTION_harness_fefc2b04.py
- cert_liq_parity_offline.py
- json
- UI_CORRECTION_harness_2d29211.py
- utc_now_ms
- outage_classify.py
- inum
- Any
- _fetch_user_realized_pnl_snapshot
- run_self_test
- self_test
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- main
- main
- run_report.py
- test_core_audit_append_never_drops.py
- test_core_ws_pool_and_slots.py
- ._decision
- get
- ORDER_CORRECTION_harness_fefc2b04.py
- _row_time_ms
- ENG-015-016-TNF17_harness.py
- utc_now_iso
- tools_memory_profile.py
- run
- plan_catchup
- ManualLedger
- render_chart
- NLS_RESIDUAL_harness_2a269ad_v4.py
- fnum
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
- convergence_shadow.py
- ast
- main
- main
- main
- bench_memory_profile.py
- hashlib
- math
- main
- main
- headroom.py
- test_core_audit_reduce_only_matches_wire.py
- main
- global_controls_tests
- test_screen_run4.py
- block_num
- main
- main
- ENG-015 / ENG-016 / TN-F17 Certification Report
- master_account_net
- main
- csv
- test_spot_gate_refusal.py
- TimedLock
- cert_disk_guard.py
- test_cert_scripts.py
- test_exchange_truth_retry.py
- main
- PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)
- cert_memory_scan.py
- ENG-INV-06..09 Non-Vacuous Static Census Report
- main
- main
- main
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- http_post
- _LatestStatusWriteWorker
- subprocess
- test_core_liq_isolated.py
- main
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- re
- ConfigManager
- J2 Local Rejects - Proposed Patch Diffs
- AppendFail
- card_hygiene.py
- tools/cert — offline halves of the J4 certification gaps (task K2)
- main
- test_core_tail_read_off_lock.py
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Testnet run handover — 2026-10-09
- test_j2_local_rejects.py
- .test_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders
- Certification (Build 3 Repair)
- Certification run status
- time
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- test_ui_incremental_summary.py
- test_single_exchange_order_callsite.py
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- test_core_outage_replay.py
- main
- Gap2MemoryScan
- _post
- test_core_send_lock_isolation.py

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 156 edges
2. `SenderGateway` - 112 edges
3. `utc_now_ms()` - 101 edges
4. `LiveCopyCore` - 81 edges
5. `fnum()` - 76 edges
6. `log_error()` - 72 edges
7. `Intent` - 65 edges
8. `self_test()` - 62 edges
9. `canonical_coin_key()` - 62 edges
10. `ConfigManager` - 62 edges

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

## Communities (141 total, 16 thin omitted)

### Community 0 - "HL_Live_Copy_Service.py"
Cohesion: 0.07
Nodes (57): append_send_attempt(), atomic_write_json(), attach_send_result(), clear_unresolved_send(), _mut(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema() (+49 more)

### Community 1 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (7): append_csv(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill, LiveWalletConfig, side_from_signed()

### Community 2 - "dry_run_intent_audit_decision"
Cohesion: 0.11
Nodes (13): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, adverse_diff_pct(), audit_reason_for_fill() (+5 more)

### Community 3 - "main"
Cohesion: 0.21
Nodes (7): configure_paths(), check(), Fixture, fresh(), main(), reset_master(), with_master()

### Community 4 - "SenderGateway"
Cohesion: 0.03
Nodes (17): post_many(), atomic_write_json(), bval(), classify_reject_category(), follower_dex_scope(), generate_attempt_id(), generate_cloid(), Intent (+9 more)

### Community 5 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 6 - "load_ui_state"
Cohesion: 0.10
Nodes (47): _active_live_copy_wallet_count(), add_live_config_wallet(), admin_purge_wallet(), api_equity(), api_metrics(), api_model_cache_status(), api_norm(), api_set_ui_state() (+39 more)

### Community 7 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 8 - "HeadroomMonitor"
Cohesion: 0.13
Nodes (6): CountingRequests, HeadroomMonitor, _run(), info_weight(), level_for(), scanner()

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
Cohesion: 0.04
Nodes (37): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+29 more)

### Community 14 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.03
Nodes (72): acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _append_spill_journal(), _attribution_json_safe(), audit_history_paths(), _audit_row_data() (+64 more)

### Community 15 - "HL_Copy_App_SSOT.py"
Cohesion: 0.08
Nodes (39): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+31 more)

### Community 16 - "test_http_keepalive.py"
Cohesion: 0.13
Nodes (3): _Flaky, H, Mon

### Community 17 - "threading"
Cohesion: 0.04
Nodes (19): CountingReader, writer(), check(), main(), check(), check(), slow_append(), Audit (+11 more)

### Community 18 - "sys"
Cohesion: 0.03
Nodes (30): check(), main(), check(), main(), check(), main(), check(), main() (+22 more)

### Community 19 - "Any"
Cohesion: 0.05
Nodes (21): canonical_coin_key(), canonical_coin_resolved(), classify_operator_action(), classify_send_lifecycle(), classify_terminal_state(), follower_position_mark(), normalise_wallet(), project_liquidation_px() (+13 more)

### Community 20 - "AuditLogWriter"
Cohesion: 0.04
Nodes (39): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings), Two-run control (instrument, not product), scan_foreign_ws(), audit_write_failure_count(), AuditLogWriter, build_live_integrity_status() (+31 more)

### Community 21 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.06
Nodes (30): blocked(), check(), HTMLElement, main(), neg_test(), parse_html(), setup_test_env(), SimpleHTMLParser (+22 more)

### Community 22 - "tempfile"
Cohesion: 0.08
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 23 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.07
Nodes (17): main(), check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative() (+9 more)

### Community 24 - "cert_liq_parity_offline.py"
Cohesion: 0.30
Nodes (8): check_positions(), collect_leader_distances(), count_liq_parity_blocked_rows(), first_follower_positions(), load_json(), main(), position_distance(), to_float()

### Community 25 - "json"
Cohesion: 0.06
Nodes (30): Clock, events(), check(), main(), fresh(), write(), check(), main() (+22 more)

### Community 26 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.07
Nodes (26): blocked(), check(), extract_table_headers(), HTMLElement, main(), neg_test(), parse_html(), parse_ssot_home_table_headers() (+18 more)

### Community 27 - "utc_now_ms"
Cohesion: 0.08
Nodes (21): _adoptable_intent_rows(), canonical_copy_fill_id(), claim_copy_fill_process_marker(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs(), normalise_copy_fill_side(), prof (+13 more)

### Community 28 - "outage_classify.py"
Cohesion: 0.14
Nodes (6): block_reasons(), classify(), main(), missing_detail(), _rows(), Audit

### Community 29 - "inum"
Cohesion: 0.08
Nodes (38): _account_card_lines(), active_wallet(), active_wallet_row(), avg(), core_missing(), core_td(), css_class(), dash_td() (+30 more)

### Community 30 - "Any"
Cohesion: 0.08
Nodes (51): _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_leader_performance(), _build_live_top_status(), _build_live_wallet_derived(), _build_live_wallet_rows(), _build_manual_reconciliation_rows(), _build_real_copy_positions() (+43 more)

### Community 31 - "_fetch_user_realized_pnl_snapshot"
Cohesion: 0.13
Nodes (18): _account_reconciliation_baseline_timestamp(), _build_account_reconciliation(), _build_health_summary(), _build_pnl_tally(), _earliest_real_order_filled_ms(), _engine_run_key(), _fetch_exchange_account_snapshot(), _fetch_user_realized_pnl_snapshot() (+10 more)

### Community 32 - "run_self_test"
Cohesion: 0.07
Nodes (10): _exchange_accepts_cloid(), is_valid_wallet(), LeaderFillIngestor, run_self_test(), _clean_account_fixture(), _market_fixture(), order(), WSManager (+2 more)

### Community 33 - "self_test"
Cohesion: 0.07
Nodes (23): audit_notes_for_fill(), classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), is_benign_ws_error(), _is_reduce_only_full_close_bypass(), is_ws_abnf_frame(), load_local_env_file() (+15 more)

### Community 34 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (19): resolve_settlement(), add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source(), main() (+11 more)

### Community 35 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 36 - "main"
Cohesion: 0.06
Nodes (11): fake_open(), PartialThenFull, check(), FakeExchange, _Half, Inject, main(), error_contexts() (+3 more)

### Community 37 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 38 - "run_report.py"
Cohesion: 0.13
Nodes (16): build_report(), fetch_leader_fills(), _fmt_durs(), _fmt_stamps(), leader_fill_ids(), load_live_config_wallets(), load_outage_classify(), main() (+8 more)

### Community 39 - "test_core_audit_append_never_drops.py"
Cohesion: 0.05
Nodes (7): fill(), run(), Audit, fill(), Config, fill(), WarmPool

### Community 40 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.12
Nodes (11): WebSocketApp(), build_cfg(), check(), FakeApp, FakeResp, FakeWS, main(), active_wallets() (+3 more)

### Community 41 - "._decision"
Cohesion: 0.08
Nodes (12): guarded(), is_spot_pair(), leader_mid(), Conclusion, ENG-001/002/004 Certification Report, ENG-001 Negative Tests, ENG-001: Repeated leader ADDs converge to target, ENG-002 Negative Tests (+4 more)

### Community 42 - "get"
Cohesion: 0.06
Nodes (28): api_get_ui_state(), api_state(), ev(), get_live_audit_summary(), get_live_copy_summary(), get_wallet_meta(), home(), _kick_model_cache_refresh_background() (+20 more)

### Community 43 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (18): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent_cfg() (+10 more)

### Community 44 - "_row_time_ms"
Cohesion: 0.21
Nodes (11): _fetch_user_fills_by_time(), _fetch_user_fills_cached(), _fetch_user_fills_paged(), _fetch_user_funding_cached(), _fetch_user_funding_paged(), _fill_dedupe_key(), _funding_dedupe_key(), _funding_usdc() (+3 more)

### Community 45 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.13
Nodes (16): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+8 more)

### Community 46 - "utc_now_iso"
Cohesion: 0.17
Nodes (16): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+8 more)

### Community 47 - "tools_memory_profile.py"
Cohesion: 0.15
Nodes (15): _addr(), _avail_mb(), build_intents(), build_matcher_stub(), gen_csv(), _hash(), main(), make_row() (+7 more)

### Community 48 - "run"
Cohesion: 0.23
Nodes (3): Gap1OutageClassifier, Gap3LiqParity, run()

### Community 49 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 50 - "ManualLedger"
Cohesion: 0.10
Nodes (14): IntentBuilder, ManualLedger, main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test() (+6 more)

### Community 51 - "render_chart"
Cohesion: 0.36
Nodes (6): render_chart(), compress_points(), poly(), x_at(), x_for_t(), y_at()

### Community 52 - "NLS_RESIDUAL_harness_2a269ad_v4.py"
Cohesion: 0.25
Nodes (16): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+8 more)

### Community 53 - "fnum"
Cohesion: 0.05
Nodes (14): list_perp_dexes(), master_exposure(), _chain_sorted(), collapse_stale_runs(), close_run(), DedupeStore, fnum(), _follower_dex_names() (+6 more)

### Community 54 - "main"
Cohesion: 0.10
Nodes (5): main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 55 - "collections"
Cohesion: 0.14
Nodes (11): as_float(), as_int_ms(), audit_files(), load_json(), load_rows(), rows(), classify(), decide() (+3 more)

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
Cohesion: 0.14
Nodes (9): claim_network_stamp(), env_with_file(), _match(), network_endpoints(), NetworkConfigError, resolve_networks(), stamp_state_refusal(), state_present() (+1 more)

### Community 60 - "shutil"
Cohesion: 0.31
Nodes (14): certify_tn_f09(), certify_tn_f10(), certify_tn_f11(), certify_tn_f12(), certify_tn_f18(), certify_tn_f19(), _check(), main() (+6 more)

### Community 61 - "Master Product Invariants and Certification Contract"
Cohesion: 0.10
Nodes (19): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+11 more)

### Community 62 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.38
Nodes (12): _build_intent(), check(), main(), _make_config(), _make_ledger(), neg_test(), _now_ms(), test_eng_val_01() (+4 more)

### Community 63 - "test_core_slot_reservation_pacing.py"
Cohesion: 0.16
Nodes (6): FakeExchange, RecordingSenderGateway, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order()

### Community 64 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 65 - "main"
Cohesion: 0.11
Nodes (11): check(), _find_projection(), main(), follower_liq(), gateway(), leader_fetcher(), mk_intent(), parity_entry() (+3 more)

### Community 66 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 67 - "convergence_shadow.py"
Cohesion: 0.40
Nodes (6): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test()

### Community 68 - "ast"
Cohesion: 0.12
Nodes (27): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+19 more)

### Community 69 - "main"
Cohesion: 0.22
Nodes (3): main(), config(), gate()

### Community 70 - "main"
Cohesion: 0.09
Nodes (10): main(), engine_order(), land(), load_run(), producer(), poll_copy_account_fills(), Audit, Ledger (+2 more)

### Community 71 - "main"
Cohesion: 0.12
Nodes (5): check(), main(), _note_read_on_current(), slow(), fetch()

### Community 72 - "bench_memory_profile.py"
Cohesion: 0.21
Nodes (4): main(), make_csv(), measure(), rss_mb()

### Community 73 - "hashlib"
Cohesion: 0.05
Nodes (14): sha(), _sha256(), _sha256(), _sha256(), _sha256(), check(), _load_committed_engine(), main() (+6 more)

### Community 74 - "math"
Cohesion: 0.08
Nodes (9): check(), main(), _note_read_on_current(), slow(), fetch(), p90(), Ledger, plan() (+1 more)

### Community 75 - "main"
Cohesion: 0.18
Nodes (7): main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 76 - "main"
Cohesion: 0.15
Nodes (4): check(), main(), startup_orphan_order_check(), wait_for_json_file()

### Community 77 - "headroom.py"
Cohesion: 0.10
Nodes (11): Clock, events(), settle(), build_payloads(), check(), flat(), main(), mutate_and_render() (+3 more)

### Community 78 - "test_core_audit_reduce_only_matches_wire.py"
Cohesion: 0.23
Nodes (5): check(), FakeExchange, Led, make_intent(), run()

### Community 79 - "main"
Cohesion: 0.14
Nodes (3): main(), __init__(), order()

### Community 80 - "global_controls_tests"
Cohesion: 0.24
Nodes (6): global_controls_tests(), config(), decide(), fill(), send(), set_mid()

### Community 81 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 82 - "block_num"
Cohesion: 0.31
Nodes (7): block_num(), dd_current(), dd_max(), latest_history_block_dd(), max_history_block_dd(), sorted_rows(), key()

### Community 83 - "main"
Cohesion: 0.28
Nodes (3): check(), finish(), main()

### Community 84 - "main"
Cohesion: 0.28
Nodes (6): main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), _f()

### Community 85 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 86 - "master_account_net"
Cohesion: 0.25
Nodes (5): _fill_key(), master_account_net(), master_userfills_all_dexes(), _state_payloads(), ENG-INV-08: Startup/recovery truth includes all perp DEX scopes

### Community 87 - "main"
Cohesion: 0.13
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 88 - "csv"
Cohesion: 0.24
Nodes (4): w(), check(), fake_fetcher(), w()

### Community 89 - "test_spot_gate_refusal.py"
Cohesion: 0.38
Nodes (4): check(), main(), decide(), fill()

### Community 92 - "cert_disk_guard.py"
Cohesion: 0.47
Nodes (7): decide(), deny_write(), icacls_available(), main(), restore_write(), _run(), whoami()

### Community 93 - "test_cert_scripts.py"
Cohesion: 0.21
Nodes (3): ExportLeaderFills, Gap5DiskGuard, load_module()

### Community 94 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 95 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 96 - "PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)"
Cohesion: 0.50
Nodes (3): Bottom line for the Boss condition, Headline, PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)

### Community 97 - "cert_memory_scan.py"
Cohesion: 0.21
Nodes (6): core_import(), emit(), decide(), main(), measure(), rss_mb()

### Community 98 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.29
Nodes (6): ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-07: Leader mutable state isolated by (wallet, coin), File Hashes, Mutation Test Summary, Results Summary

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

### Community 104 - "http_post"
Cohesion: 0.40
Nodes (3): http_post(), start_keepalive(), loop()

### Community 106 - "subprocess"
Cohesion: 0.07
Nodes (20): check(), wallets(), check(), main(), check(), last_json(), main(), network_tests() (+12 more)

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

### Community 112 - "re"
Cohesion: 0.05
Nodes (20): check(), main(), config(), intent(), send(), write_cfg(), sections(), check() (+12 more)

### Community 113 - "ConfigManager"
Cohesion: 0.20
Nodes (4): ConfigManager, gw(), make_gateway(), 2. Switch states OFF / CLOSE ONLY / ON

### Community 114 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 117 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 118 - "tools/cert — offline halves of the J4 certification gaps (task K2)"
Cohesion: 0.25
Nodes (7): Evidence from building this (2026-10-11, offline, on this host), Input layouts, Model split, Safety (all scripts), Scripts, tools/cert — offline halves of the J4 certification gaps (task K2), Which J4 gaps still need the live engine

### Community 122 - "test_core_tail_read_off_lock.py"
Cohesion: 0.13
Nodes (4): Probe, probing_open(), fake_urlopen(), Resp

### Community 124 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 125 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 126 - "test_j2_local_rejects.py"
Cohesion: 0.13
Nodes (4): clear_resting_entries(), FakeExchange, main(), one()

### Community 128 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 129 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 130 - "time"
Cohesion: 0.31
Nodes (4): main(), fetch(), main(), markers()

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

### Community 142 - "main"
Cohesion: 0.25
Nodes (3): check(), main(), engine()

### Community 148 - "_post"
Cohesion: 0.18
Nodes (7): identity_ok(), master_userfills(), _post(), rolling_day_pnl(), runtime_master_identity(), valid_address(), ENG-INV-09: Exchange truth outranks local replay

## Knowledge Gaps
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fnum()` connect `fnum` to `run_self_test`, `SenderGateway`, `._decision`, `LiveCopyCore`, `HL_Live_Copy_Service_Core.py`, `ManualLedger`, `Any`, `AuditLogWriter`, `utc_now_ms`, `Master Product Invariants and Certification Contract`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Should `HL_Live_Copy_Service.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06912280701754386 - nodes in this community are weakly interconnected._
- **Why does `main()` connect `main` to `sys`, `tempfile`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Should `DryRunLiveCopyService` be split into smaller, more focused modules?**
  _Cohesion score 0.07672634271099744 - nodes in this community are weakly interconnected._
- **Why does `SenderGateway` connect `SenderGateway` to `run_self_test`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`, `ORDER_CORRECTION_harness_fefc2b04.py`, `test_core_audit_reduce_only_matches_wire.py`, `HL_Live_Copy_Service_Core.py`, `ConfigManager`, `Any`, `AuditLogWriter`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `dry_run_intent_audit_decision` be split into smaller, more focused modules?**
  _Cohesion score 0.11052631578947368 - nodes in this community are weakly interconnected._
- **Should `SenderGateway` be split into smaller, more focused modules?**
  _Cohesion score 0.032992930086410056 - nodes in this community are weakly interconnected._