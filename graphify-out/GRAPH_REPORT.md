# Graph Report - hl-build3-no-sub-minimum-rebase-20261021  (2026-10-21)

## Corpus Check
- 279 files · ~564,889 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .csv 11, (none) 2, .jsonl 1)

## Summary
- 3453 nodes · 9388 edges · 146 communities (117 shown, 29 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 850 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7e9e1600`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SenderGateway
- LiveCopyCore
- shutil
- HL_Live_Copy_Service_Core.py
- sys
- fnum
- Any
- HL_Live_Copy_Service.py
- HL_Copy_App_SSOT.py
- DryRunLiveCopyService
- csv
- tempfile
- threading
- json
- ConfigManager
- test_core_audit_append_never_drops.py
- UI_harness_fa9d9f55ff.py
- render_home
- Any
- re
- inum
- IntentBuilder
- load_ui_state
- UI_CORRECTION_harness_2d29211.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py
- headroom.py
- test_core_ws_pool_and_slots.py
- ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py
- HEALTH_CORRECTION_harness_fefc2b04.py
- self_test
- _load_live_copy_config
- run_self_test
- ORDER_CORRECTION_harness_fefc2b04.py
- build_live_integrity_status
- utc_now_iso
- ENG-015-016-TNF17_harness.py
- hashlib
- pathlib
- plan_catchup
- math
- tools_memory_profile.py
- Path
- fnum
- probe_reearn.py
- collections
- read_csv_rows
- main
- DedupeStore
- main
- global_controls_tests
- dry_run_intent_audit_decision
- Master Product Invariants and Certification Contract
- Detail
- census_inv_06_09.py
- exchange_truth.py
- test_core_slot_reservation_pacing.py
- HTMLElement
- test_core_reduce_only_repair.py
- main
- main
- HTMLElement
- UI_FP_FAIL_harness_09e1258003.py
- Architecture Contract — Hyperliquid Build 3 Repair
- main
- main
- main
- test_run_report.py
- test_screen_run4.py
- argparse
- ENGINE_RESIDUAL_harness_2a269ad.py
- subprocess
- ENG-INV-06..09 Non-Vacuous Static Census Report
- main
- main
- test_core_sender_key.py
- test_http_keepalive.py
- CTRL_probe_t_967fad56.py
- main
- run
- ENG-015 / ENG-016 / TN-F17 Certification Report
- main
- PRICING_CORRECTION_harness_2f57dba50f.py
- time
- RISK_harness_fa9d9f55ff.py
- bench_memory_profile.py
- TimedLock
- main
- Operating Protocol
- test_cert_scripts.py
- test_core_append_truncate.py
- test_exchange_truth_retry.py
- test_j2_local_rejects.py
- main
- cert_disk_guard.py
- Inject
- main
- main
- main
- main
- UI CERT ARTIFACT SCHEMA — required shape for every UI certification card
- _LatestStatusWriteWorker
- main
- test_core_liq_isolated.py
- test_core_run5_converge.py
- main
- ENG-INV-03-05 CORRECTED Census Report
- ENG-INV-07-09 Runtime Chain Correction
- J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)
- valid_address
- J2 Local Rejects - Proposed Patch Diffs
- main
- AppendFail
- test_core_audit_header_cache.py
- .test_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders
- main
- PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)
- card_hygiene.py
- _Half
- test_core_outage_replay.py
- Probe
- test_core_warm_dex_clients.py
- Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)
- Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)
- Testnet run handover — 2026-10-09
- test_single_exchange_order_callsite.py
- Bootstrap
- Certification (Build 3 Repair)
- CTRL_probe3_t_967fad56.py
- Certification run status
- Build 3 Repair — Certification Matrix (Boss invariants / controls)
- http_post
- test_core_local_first.py
- test_core_send_lock_isolation.py
- Hyperliquid Build 3 Repair
- FakeExchange
- ENG-005 through ENG-009 Certification Report
- Mainnet crash and ambiguous-send recovery
- PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)
- Gap2MemoryScan
- resolve_settlement
- MATRIX_WALK_2026-10-10.md
- DONE10_GATE_d829fce8ff.md
- PRICING_CORRECTION_2d29211148_report.md
- verify_api_endpoint

## God Nodes (most connected - your core abstractions)
1. `fnum()` - 158 edges
2. `SenderGateway` - 112 edges
3. `utc_now_ms()` - 102 edges
4. `LiveCopyCore` - 82 edges
5. `fnum()` - 76 edges
6. `log_error()` - 72 edges
7. `Intent` - 65 edges
8. `self_test()` - 62 edges
9. `canonical_coin_key()` - 62 edges
10. `ConfigManager` - 62 edges

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

## Communities (146 total, 29 thin omitted)

### Community 0 - "SenderGateway"
Cohesion: 0.03
Nodes (31): post_many(), atomic_write_json(), classify_operator_action(), classify_reject_category(), classify_send_lifecycle(), classify_terminal_state(), follower_dex_scope(), follower_mid() (+23 more)

### Community 1 - "LiveCopyCore"
Cohesion: 0.03
Nodes (40): E2 comparison: net catch-up plan vs the engine's current merge (HL_Live_Copy_Service_Core.py), 0. What was read (evidence base), 1. What the net planner is, 2. Where it would plug in, 3. Invariants the Core imposes on any net planner, 4. Exact risks (with severity), 5. Test evidence (this job's deliverable), 6. GO / NO-GO (+32 more)

### Community 2 - "shutil"
Cohesion: 0.05
Nodes (72): main(), make_leader_fill(), make_testnet_fetcher(), _mutate_engine_file(), test_eng001_convergence(), test_eng001_negative_test(), test_eng002_negative_test(), test_eng002_proportional_mode() (+64 more)

### Community 3 - "HL_Live_Copy_Service_Core.py"
Cohesion: 0.04
Nodes (61): acquire_global_instance_lock(), acquire_instance_lock(), _append_core_fatal_row(), append_csv(), _append_spill_journal(), _attribution_json_safe(), audit_history_paths(), _audit_row_data() (+53 more)

### Community 4 - "sys"
Cohesion: 0.03
Nodes (21): check(), finish(), main(), check(), main(), check(), main(), check() (+13 more)

### Community 5 - "fnum"
Cohesion: 0.05
Nodes (28): _adoptable_intent_rows(), _manual_sleeve_exists(), canonical_coin_key(), _chain_sorted(), _coin_key_map(), collapse_stale_runs(), close_run(), ExchangeReconciler (+20 more)

### Community 6 - "Any"
Cohesion: 0.07
Nodes (22): AuditLogWriter, canonical_copy_fill_id(), claim_copy_fill_process_marker(), copy_cursor_ms(), CopyAccountIngestor, CopyFillMatcher, ensure_dirs(), normalise_copy_fill_side() (+14 more)

### Community 7 - "HL_Live_Copy_Service.py"
Cohesion: 0.07
Nodes (57): append_send_attempt(), atomic_write_json(), attach_send_result(), clear_unresolved_send(), _mut(), count_csv_data_rows(), ensure_csv_header(), ensure_csv_schema() (+49 more)

### Community 8 - "HL_Copy_App_SSOT.py"
Cohesion: 0.06
Nodes (55): alignment_status_for_key(), _apply_price_model(), block(), bps_fee(), build_model_state(), append_expected_fill(), copy_wallet_exposure(), record_copy_exposure() (+47 more)

### Community 9 - "DryRunLiveCopyService"
Cohesion: 0.08
Nodes (7): append_csv(), DryRunLiveCopyService, event_authorised_desired_net(), fnum(), LeaderFill, LiveWalletConfig, side_from_signed()

### Community 10 - "csv"
Cohesion: 0.05
Nodes (36): main(), _durable_row(), _fixed_intents(), fresh(), wire_account_net(), w(), check(), main() (+28 more)

### Community 11 - "tempfile"
Cohesion: 0.08
Nodes (32): check(), check_done10_negative(), check_done10_positive(), check_fexc016_negative(), check_fexc016_positive(), check_fui001_negative(), check_fui001_positive(), check_fui002_negative() (+24 more)

### Community 12 - "threading"
Cohesion: 0.04
Nodes (18): check(), main(), check(), slow_append(), Audit, me(), w(), check() (+10 more)

### Community 13 - "json"
Cohesion: 0.05
Nodes (26): Clock, events(), Clock, events(), settle(), check(), main(), fresh() (+18 more)

### Community 14 - "ConfigManager"
Cohesion: 0.07
Nodes (9): scan_foreign_ws(), bval(), ConfigManager, is_valid_wallet(), ServiceStateWriter, make_gateway(), 2. Switch states OFF / CLOSE ONLY / ON, Headline (3 lines) (+1 more)

### Community 15 - "test_core_audit_append_never_drops.py"
Cohesion: 0.04
Nodes (12): fill(), run(), Audit, fill(), Ledger, plan(), Audit, builder() (+4 more)

### Community 16 - "UI_harness_fa9d9f55ff.py"
Cohesion: 0.11
Nodes (25): blocked(), check(), main(), neg_test(), parse_html(), setup_test_env(), test_engine_integrity(), test_inc() (+17 more)

### Community 17 - "render_home"
Cohesion: 0.08
Nodes (39): _account_card_lines(), _append_exchange_history(), avg(), block_num(), css_class(), dash_td(), dd_current(), dd_max() (+31 more)

### Community 18 - "Any"
Cohesion: 0.08
Nodes (39): active_wallet(), active_wallet_row(), _build_execution_quality_rows(), _build_execution_quality_summary(), _build_live_top_status(), _build_live_wallet_rows(), _build_recent_send_warning_groups(), contract_money_equal() (+31 more)

### Community 19 - "re"
Cohesion: 0.06
Nodes (10): block_reasons(), classify(), main(), missing_detail(), _rows(), sections(), check(), main() (+2 more)

### Community 20 - "inum"
Cohesion: 0.08
Nodes (35): _account_reconciliation_baseline_timestamp(), _build_account_reconciliation(), _build_health_summary(), _build_pnl_tally(), _earliest_real_order_filled_ms(), _engine_alert(), _engine_run_key(), _fetch_exchange_account_snapshot() (+27 more)

### Community 21 - "IntentBuilder"
Cohesion: 0.06
Nodes (16): list_perp_dexes(), master_exposure(), _post(), rolling_day_pnl(), _follower_dex_names(), IntentBuilder, guarded(), _read() (+8 more)

### Community 22 - "load_ui_state"
Cohesion: 0.10
Nodes (34): admin_purge_wallet(), api_equity(), api_get_ui_state(), api_metrics(), api_model_cache_status(), api_norm(), api_set_ui_state(), api_trades() (+26 more)

### Community 23 - "UI_CORRECTION_harness_2d29211.py"
Cohesion: 0.12
Nodes (23): blocked(), check(), main(), neg_test(), parse_html(), parse_ssot_home_table_headers(), parse_ssot_table_headers(), setup_test_env() (+15 more)

### Community 24 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py"
Cohesion: 0.09
Nodes (19): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), get_function_source(), main(), run_negative_mutations() (+11 more)

### Community 25 - "headroom.py"
Cohesion: 0.09
Nodes (12): _check(), compute_convergence_order(), ConvergenceOrder, _expect(), _none(), run_self_test(), CountingRequests, HeadroomMonitor (+4 more)

### Community 26 - "test_core_ws_pool_and_slots.py"
Cohesion: 0.07
Nodes (17): check(), main(), config(), gate(), wallets(), cfg(), WebSocketApp(), build_cfg() (+9 more)

### Community 27 - "ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py"
Cohesion: 0.10
Nodes (18): add_check(), add_negative(), ast_parse_file(), count_order_call_sites(), count_process_spawns(), main(), run_negative_mutations(), test_eng010_account_net_truth() (+10 more)

### Community 28 - "HEALTH_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.11
Nodes (16): check_age_in_write_path_negative(), check_age_in_write_path_positive(), check_age_threshold_negative(), check_age_threshold_positive(), check_freshness_budget_negative(), check_freshness_budget_positive(), check_network_errors_negative(), check_network_errors_positive() (+8 more)

### Community 29 - "self_test"
Cohesion: 0.07
Nodes (23): audit_notes_for_fill(), classify_ignored_ws_message(), extract_ws_fills(), extract_ws_fills_with_meta(), is_benign_ws_error(), _is_reduce_only_full_close_bypass(), is_ws_abnf_frame(), load_local_env_file() (+15 more)

### Community 30 - "_load_live_copy_config"
Cohesion: 0.12
Nodes (29): _active_live_copy_wallet_count(), add_live_config_wallet(), api_state(), _enforce_live_copy_cap(), _engine_wallet_summary(), _execution_guards_info(), ev(), get_global_controls() (+21 more)

### Community 31 - "run_self_test"
Cohesion: 0.08
Nodes (7): _exchange_accepts_cloid(), LeaderFillIngestor, run_self_test(), order(), WSManager, on_message(), on_open()

### Community 32 - "ORDER_CORRECTION_harness_fefc2b04.py"
Cohesion: 0.14
Nodes (19): _build_intent(), _cfg(), _check(), FakeExchange, _fresh_ledger(), _git_head(), main(), _make_intent() (+11 more)

### Community 33 - "build_live_integrity_status"
Cohesion: 0.07
Nodes (19): J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89), Proposed patch (engine thread applies it; no Core edit was made here), Two-run control (instrument, not product), audit_write_failure_count(), build_live_integrity_status(), _has_pending_exit_guard_proof(), is_active_row(), is_current_core_row() (+11 more)

### Community 34 - "utc_now_iso"
Cohesion: 0.17
Nodes (16): build_ws_health_snapshot(), DedicatedLiveWSManager, on_close(), on_error(), on_message(), on_open(), on_ping(), on_pong() (+8 more)

### Community 35 - "ENG-015-016-TNF17_harness.py"
Cohesion: 0.14
Nodes (15): check(), line_count(), main(), mutate_file(), negative_eng015(), negative_eng016(), negative_tnf17(), positive_eng015() (+7 more)

### Community 36 - "hashlib"
Cohesion: 0.10
Nodes (15): check(), check_done10_blocked(), check_engine_sha256(), check_mailbox_transport(), check_no_auto_live(), main(), neg_test(), run_check() (+7 more)

### Community 37 - "pathlib"
Cohesion: 0.20
Nodes (22): imports_of(), is_b4(), main(), mutate(), prod_files(), scan(), baseline_deps(), closure() (+14 more)

### Community 38 - "plan_catchup"
Cohesion: 0.15
Nodes (17): _g(), _num(), plan_catchup(), _side_of(), _signed(), _start(), acts(), check() (+9 more)

### Community 39 - "math"
Cohesion: 0.09
Nodes (8): check(), main(), _note_read_on_current(), slow(), fetch(), p90(), p90(), p90()

### Community 40 - "tools_memory_profile.py"
Cohesion: 0.15
Nodes (15): _addr(), _avail_mb(), build_intents(), build_matcher_stub(), gen_csv(), _hash(), main(), make_row() (+7 more)

### Community 41 - "Path"
Cohesion: 0.16
Nodes (20): _account_orphan_signed_size(), atomic_write_csv(), atomic_write_json(), _atomic_write_json(), backup_purge_files(), _build_account_orphan_registry(), _csv_cache_key(), invalidate_model_cache() (+12 more)

### Community 42 - "fnum"
Cohesion: 0.16
Nodes (21): _build_live_leader_performance(), _build_live_wallet_derived(), _build_manual_reconciliation_rows(), _build_real_copy_positions(), _classify_owned_exchange_net(), _exchange_field(), _exchange_signed_size(), fnum() (+13 more)

### Community 43 - "probe_reearn.py"
Cohesion: 0.17
Nodes (15): builder(), decide(), fill(), Ledger, r1(), r14(), r14r(), r2() (+7 more)

### Community 44 - "collections"
Cohesion: 0.14
Nodes (12): as_float(), as_int_ms(), audit_files(), emit(), load_json(), load_rows(), rows(), classify() (+4 more)

### Community 45 - "read_csv_rows"
Cohesion: 0.12
Nodes (13): prof, read_csv_rows(), _market_fixture(), send_attempt_rows(), 2. Top tracemalloc allocation lines (`f37b9c1`, 50 MB synthetic CSV), 3. Verdict per suspect (prove / disprove), 4. Interpretation - ranking by contribution to the observed 4.5 GB, 5. Fix verification on current `main` (`06435bf`) (+5 more)

### Community 46 - "main"
Cohesion: 0.10
Nodes (5): main(), catch_up(), exit_intent(), fill(), snapshot()

### Community 47 - "DedupeStore"
Cohesion: 0.12
Nodes (8): DedupeStore, 3. Convergence, 4. Dust close, 5. Liquidation parity (+ cross 3x), 6. Ledger repair / ownership, 7. Send path: idempotency, cloid, 9. Audit-write / disk-full, Rows

### Community 48 - "main"
Cohesion: 0.12
Nodes (8): check(), _find_projection(), main(), gateway(), leader_fetcher(), mk_intent(), parity_entry(), _probe_leverage()

### Community 49 - "global_controls_tests"
Cohesion: 0.16
Nodes (11): check(), global_controls_tests(), config(), decide(), fill(), send(), set_mid(), last_json() (+3 more)

### Community 50 - "dry_run_intent_audit_decision"
Cohesion: 0.11
Nodes (13): Answer, Consequences, G4-C2A — READ-ONLY MARK SOURCE INVENTORY (Architect F3), Precise blocker for Architect ruling, Question, Trace table, adverse_diff_pct(), audit_reason_for_fill() (+5 more)

### Community 51 - "Master Product Invariants and Certification Contract"
Cohesion: 0.11
Nodes (18): 10. Rulings after v0.4, 1. Purpose, 2. Provenance, 3.1 Record fields (matrix schema `hl_certification_matrix_v1`), 3.2 Evidence rules ("everything proven, nothing assumed"), 3.3 What "certified for mainnet" means, 3. How to use this contract, 4.1 Precedence (highest first) (+10 more)

### Community 52 - "Detail"
Cohesion: 0.10
Nodes (19): Addendum - independent re-run by `hermes:implementation-owner` (deepseek-flash), Corrections, Detail, `hermes/e1` (`84223ce0b0`) -> MERGE (flaky baseline test appeared), `hermes/e2` (`4128499ac4`) -> MERGE, `hermes/f1` (`55430af3ec`) -> RESOLVE first, `hermes/f2` (`0152bcdedc`) -> RESOLVE first, `hermes/j1-diskfull` (`537088cffb`) -> RESOLVE first (+11 more)

### Community 53 - "census_inv_06_09.py"
Cohesion: 0.23
Nodes (9): all_py_files(), check_inv06(), check_inv07(), check_inv08(), check_inv09(), file_lines(), main(), run_mutation_tests() (+1 more)

### Community 54 - "exchange_truth.py"
Cohesion: 0.15
Nodes (8): claim_network_stamp(), env_with_file(), network_endpoints(), NetworkConfigError, resolve_networks(), stamp_state_refusal(), state_present(), terminal_reject_evidence()

### Community 55 - "test_core_slot_reservation_pacing.py"
Cohesion: 0.16
Nodes (6): FakeExchange, RecordingSenderGateway, sender_gateway(), SlotReservationPacingTests, place_order(), cancel_order()

### Community 56 - "HTMLElement"
Cohesion: 0.12
Nodes (3): HTMLElement, SimpleHTMLParser, verify_html_element()

### Community 57 - "test_core_reduce_only_repair.py"
Cohesion: 0.14
Nodes (5): poll_copy_account_fills(), Audit, Ledger, run(), rows()

### Community 58 - "main"
Cohesion: 0.13
Nodes (4): main(), _note_read_on_current(), slow(), fetch()

### Community 59 - "main"
Cohesion: 0.15
Nodes (6): check(), main(), _note_read_on_current(), slow(), fetch(), p90()

### Community 60 - "HTMLElement"
Cohesion: 0.13
Nodes (3): extract_table_headers(), HTMLElement, SimpleHTMLParser

### Community 61 - "UI_FP_FAIL_harness_09e1258003.py"
Cohesion: 0.23
Nodes (8): build_payloads(), check(), flat(), main(), mutate_and_render(), neg(), raw_state(), run_dom()

### Community 62 - "Architecture Contract — Hyperliquid Build 3 Repair"
Cohesion: 0.13
Nodes (14): Architect's job, Architecture Contract — Hyperliquid Build 3 Repair, Automatic Architect escalation, Build 4 requirements source set, Chosen repair, Completion definition, Conflict rule, Full project acceptance scope (+6 more)

### Community 63 - "main"
Cohesion: 0.17
Nodes (6): check(), main(), error_contexts(), errors(), hold_runtime_state_lock(), wait_for_json_file()

### Community 64 - "main"
Cohesion: 0.15
Nodes (5): main(), engine_order(), land(), load_run(), producer()

### Community 65 - "main"
Cohesion: 0.18
Nodes (7): main(), config(), fill(), gateway(), order(), send(), set_mids()

### Community 66 - "test_run_report.py"
Cohesion: 0.15
Nodes (5): check(), fake_fetcher(), fake_urlopen(), Resp, w()

### Community 67 - "test_screen_run4.py"
Cohesion: 0.17
Nodes (5): check(), fake_urlopen(), FakeResp, main(), write_csv()

### Community 68 - "argparse"
Cohesion: 0.21
Nodes (7): decide(), main(), measure(), rss_mb(), main(), post(), wallets()

### Community 69 - "ENGINE_RESIDUAL_harness_2a269ad.py"
Cohesion: 0.42
Nodes (12): _build_intent(), check(), main(), _make_config(), _make_ledger(), neg_test(), _now_ms(), test_eng_val_01() (+4 more)

### Community 70 - "subprocess"
Cohesion: 0.22
Nodes (7): g(), blob(), census(), blob(), calls_in(), head(), main()

### Community 71 - "ENG-INV-06..09 Non-Vacuous Static Census Report"
Cohesion: 0.15
Nodes (10): _fill_key(), master_userfills(), master_userfills_all_dexes(), ENG-INV-06..09 Non-Vacuous Static Census Report, ENG-INV-06: No new engine/runtime around Build 3, ENG-INV-08: Startup/recovery truth includes all perp DEX scopes, ENG-INV-09: Exchange truth outranks local replay, File Hashes (+2 more)

### Community 72 - "main"
Cohesion: 0.21
Nodes (7): configure_paths(), check(), Fixture, fresh(), main(), reset_master(), with_master()

### Community 73 - "main"
Cohesion: 0.14
Nodes (3): main(), __init__(), order()

### Community 74 - "test_core_sender_key.py"
Cohesion: 0.16
Nodes (3): check(), main(), wait_for_json_file()

### Community 75 - "test_http_keepalive.py"
Cohesion: 0.14
Nodes (3): _Flaky, H, Mon

### Community 76 - "CTRL_probe_t_967fad56.py"
Cohesion: 0.24
Nodes (7): expect_error(), load_module(), main(), record(), run_checks(), run_mailbox_census(), sha256_file()

### Community 77 - "main"
Cohesion: 0.18
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 78 - "run"
Cohesion: 0.23
Nodes (3): Gap1OutageClassifier, Gap3LiqParity, run()

### Community 79 - "ENG-015 / ENG-016 / TN-F17 Certification Report"
Cohesion: 0.15
Nodes (11): reconcile_sleeve(), Conclusion, ENG-015 / ENG-016 / TN-F17 Certification Report, ENG-015: Sign flip handling, ENG-016: Build 4 leftovers on the shared follower account, File Hashes (Tested Commit), Harness, Mutations Applied (Negative Tests) (+3 more)

### Community 81 - "PRICING_CORRECTION_harness_2f57dba50f.py"
Cohesion: 0.19
Nodes (4): check(), _load_committed_engine(), main(), neg()

### Community 82 - "time"
Cohesion: 0.26
Nodes (5): fetch(), main(), markers(), main(), one()

### Community 83 - "RISK_harness_fa9d9f55ff.py"
Cohesion: 0.22
Nodes (7): check(), main(), neg_test(), run_engine_checks(), config(), decide(), fill()

### Community 84 - "bench_memory_profile.py"
Cohesion: 0.21
Nodes (4): main(), make_csv(), measure(), rss_mb()

### Community 86 - "main"
Cohesion: 0.18
Nodes (4): main(), _note_read_on_current(), slow(), fetch()

### Community 87 - "Operating Protocol"
Cohesion: 0.17
Nodes (11): Architect, Architectural interrupt, Control model, Controller, Evidence discipline, GitHub discipline, Hermes, Hermes reporting convention — Richard instruction, October 2026 (+3 more)

### Community 88 - "test_cert_scripts.py"
Cohesion: 0.21
Nodes (3): ExportLeaderFills, Gap5DiskGuard, load_module()

### Community 90 - "test_exchange_truth_retry.py"
Cohesion: 0.22
Nodes (4): ReadTimeout, Resp, run(), slow()

### Community 92 - "main"
Cohesion: 0.22
Nodes (4): check(), main(), fill(), send()

### Community 93 - "cert_disk_guard.py"
Cohesion: 0.35
Nodes (8): core_import(), decide(), deny_write(), icacls_available(), main(), restore_write(), _run(), whoami()

### Community 95 - "main"
Cohesion: 0.24
Nodes (3): check(), main(), wait_for()

### Community 96 - "main"
Cohesion: 0.27
Nodes (6): check(), main(), config(), intent(), send(), write_cfg()

### Community 97 - "main"
Cohesion: 0.27
Nodes (5): check(), main(), authority_for(), fresh(), wire_account_net()

### Community 98 - "main"
Cohesion: 0.22
Nodes (3): check(), main(), run()

### Community 99 - "UI CERT ARTIFACT SCHEMA — required shape for every UI certification card"
Cohesion: 0.20
Nodes (9): A tool failure is not a product gap, Control-write rows: the authorised isolated write-test (controller ruling), Environment (verified — get this wrong and the probe fails while the product is fine), Hard requirements (each has already caused a FAIL), Required artifact shape, THE PROCESS RULE — bind to the build the RUNNING PROCESS loads, not the disk HEAD, The rule that governs all of it, The two review rules (controller-confirmed additions) (+1 more)

### Community 102 - "test_core_liq_isolated.py"
Cohesion: 0.22
Nodes (3): Fake, leader(), post()

### Community 105 - "ENG-INV-03-05 CORRECTED Census Report"
Cohesion: 0.22
Nodes (8): Artifacts, ENG-INV-03-05 CORRECTED Census Report, Internal Imports (correctly classified as INTERNAL, not third-party), Invariants Checked, Method, Non-Vacuous Negative Test, Summary, Target Files

### Community 106 - "ENG-INV-07-09 Runtime Chain Correction"
Cohesion: 0.22
Nodes (8): Correction Summary, ENG-INV-07-09 Runtime Chain Correction, Engine Self-Test (Supporting Evidence — DRY RUN), Invariant Results, Negative Tests (Dry-Run), Real Testnet Order/Fill (NOT_ESTABLISHED), Rules Followed, What Was Done

### Community 107 - "J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)"
Cohesion: 0.22
Nodes (8): 0. Common preamble (every gap), 1. Outage recovery (gap 1), 2. Memory flat on new main (gap 2), 3. Liquidation parity vs exchange liquidationPx (gap 3), 4. Realistic-load latency, Phase R (gap 4), 5. Disk-full robustness (gap 5), 6. Batch plan (one PC session), J4 - PC run scripts for the five certification gaps (main 5e88e89 or later)

### Community 108 - "valid_address"
Cohesion: 0.25
Nodes (5): identity_ok(), master_account_net(), runtime_master_identity(), _state_payloads(), valid_address()

### Community 109 - "J2 Local Rejects - Proposed Patch Diffs"
Cohesion: 0.25
Nodes (7): Implementation Notes, J2 Local Rejects - Proposed Patch Diffs, Patch 1: Enhance Resting-Order Churn Check, Patch 2: Local Reject for Price Outside 0.2% Band, Patch 3: Add Terminal State Classification for New Reject, Patch 4: Add Operator Action for New Reject, Test Results Summary

### Community 114 - "main"
Cohesion: 0.25
Nodes (3): check(), main(), engine()

### Community 115 - "PC run specs for the five certification-matrix gaps (job J4, 2026-10-11)"
Cohesion: 0.25
Nodes (7): Common preamble (applies to every gap), GAP-1 · outage recovery, GAP-3 · liquidation parity vs the exchange `liquidationPx`, GAP-4 · realistic-load latency (Phase R), GAP-5 · disk-full robustness, PC run specs for the five certification-matrix gaps (job J4, 2026-10-11), What this job does NOT do

### Community 116 - "card_hygiene.py"
Cohesion: 0.36
Nodes (3): main(), pick_lane(), main()

### Community 121 - "Merge instruction — ENG-INV-01..06 rebuild (t_7366969c)"
Cohesion: 0.29
Nodes (6): Branch and base, Changed files vs origin/main, Merge instruction — ENG-INV-01..06 rebuild (t_7366969c), Register accounting (832-row origin/main base), Schema preservation, Suggested review checks (do not merge without approval)

### Community 122 - "Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)"
Cohesion: 0.29
Nodes (6): 1. Preserved product behaviour (must survive the repair), 2. Trading-authority model (the frozen semantics), 3. Explicit non-goals, 4. Measurable downstream DONE (project completion), 5. Open items this freeze does NOT resolve (carried forward, not silently merged), Build 3 — Product Semantics, Non-Goals and Measurable DONE (Gate 1 freeze)

### Community 123 - "Testnet run handover — 2026-10-09"
Cohesion: 0.29
Nodes (6): 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z), 2. Testnet run status: IN PROGRESS, no trade placed yet, 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch, 4. Things the Controller/Architect should reconcile, 5. What's left next, Testnet run handover — 2026-10-09

### Community 125 - "Bootstrap"
Cohesion: 0.33
Nodes (5): Architect bootstrap, Bootstrap, Controller bootstrap, Current first gate: BUILD3_SOURCE_BASELINE_IMPORT_1, Hermes bootstrap

### Community 126 - "Certification (Build 3 Repair)"
Cohesion: 0.33
Nodes (5): Certification (Build 3 Repair), Read order for an agent starting here, Recording a run, Regenerating the matrix, Rules

### Community 127 - "CTRL_probe3_t_967fad56.py"
Cohesion: 0.53
Nodes (4): git(), load(), main(), record()

### Community 128 - "Certification run status"
Cohesion: 0.33
Nodes (5): By area, Certification run status, Requirements that need mainnet proof, Requirements with a recorded result, Runs

### Community 129 - "Build 3 Repair — Certification Matrix (Boss invariants / controls)"
Cohesion: 0.33
Nodes (5): Build 3 Repair — Certification Matrix (Boss invariants / controls), Matrix, Models used (per part), Reproduce, Test-suite health (how "mock-proven" was established)

### Community 130 - "http_post"
Cohesion: 0.40
Nodes (3): http_post(), start_keepalive(), loop()

### Community 133 - "Hyperliquid Build 3 Repair"
Cohesion: 0.40
Nodes (4): Hyperliquid Build 3 Repair, Immediate state, Read order, Roles

### Community 135 - "ENG-005 through ENG-009 Certification Report"
Cohesion: 0.50
Nodes (3): Checks, ENG-005 through ENG-009 Certification Report, Non-Vacuous Negative Tests

### Community 136 - "Mainnet crash and ambiguous-send recovery"
Cohesion: 0.50
Nodes (3): After a crash or uncertain send, Mainnet crash and ambiguous-send recovery, Wallet-roster changes

### Community 137 - "PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)"
Cohesion: 0.50
Nodes (3): Bottom line for the Boss condition, Headline, PORT_VS_REBUILD - old (May) build vs this week's rebuild, row by row (REVIEW ONLY, advisory)

## Knowledge Gaps
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SenderGateway` connect `SenderGateway` to `ORDER_CORRECTION_harness_fefc2b04.py`, `LiveCopyCore`, `HL_Live_Copy_Service_Core.py`, `fnum`, `Any`, `read_csv_rows`, `ConfigManager`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_43731b4f.py`, `ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py`, `run_self_test`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Should `SenderGateway` be split into smaller, more focused modules?**
  _Cohesion score 0.03128594432942259 - nodes in this community are weakly interconnected._
- **Why does `fnum()` connect `fnum` to `SenderGateway`, `LiveCopyCore`, `build_live_integrity_status`, `HL_Live_Copy_Service_Core.py`, `Any`, `ConfigManager`, `DedupeStore`, `Master Product Invariants and Certification Contract`, `IntentBuilder`, `run_self_test`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Should `LiveCopyCore` be split into smaller, more focused modules?**
  _Cohesion score 0.034954407294832825 - nodes in this community are weakly interconnected._
- **Why does `LiveCopyCore` connect `LiveCopyCore` to `shutil`, `HL_Live_Copy_Service_Core.py`, `Any`, `ConfigManager`, `IntentBuilder`, `run_self_test`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Should `shutil` be split into smaller, more focused modules?**
  _Cohesion score 0.05128205128205128 - nodes in this community are weakly interconnected._
- **Should `HL_Live_Copy_Service_Core.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04038050863909921 - nodes in this community are weakly interconnected._