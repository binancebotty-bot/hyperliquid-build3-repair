# BASE_RED_TRIAGE_B raw probe

commit a1acc28 | dir _archive/hl_stage2 | files 167 | timeout 120s
interpreter C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe

| file | exit | TOTAL= | RESULT:: | first stderr line |
|---|---|---|---|---|
| test_catchup_plan.py | 0 | Y | Y |  |
| test_catchup_re3_fixture.py | 0 | Y | Y |  |
| test_core_account_history_sampler.py | 0 | Y | Y |  |
| test_core_adl.py | 0 | Y | Y |  |
| test_core_adopt_oid.py | 0 | Y | Y |  |
| test_core_all_mids_dex_isolation.py | 0 | N | N |  |
| test_core_all_mids_dex_keys.py | 0 | N | N |  |
| test_core_ambiguous_startup_alert.py | 0 | Y | Y |  |
| test_core_append_permission_retry.py | 0 | Y | Y |  |
| test_core_append_truncate.py | 1 | Y | Y |  |
| test_core_audit_append_never_drops.py | 0 | Y | Y |  |
| test_core_audit_header_cache.py | 0 | Y | Y |  |
| test_core_audit_reduce_only_matches_wire.py | 1 | Y | Y |  |
| test_core_batch_parallel.py | 0 | Y | Y |  |
| test_core_cap_journal_fields.py | 0 | Y | Y |  |
| test_core_cap_size_down.py | 0 | Y | Y |  |
| test_core_catchup_collapse.py | 0 | Y | Y |  |
| test_core_catchup_window_rows.py | 0 | Y | Y |  |
| test_core_clo_dispatch_prefilter.py | 0 | Y | Y |  |
| test_core_close_to_target.py | 0 | Y | Y |  |
| test_core_csv_field_limit.py | 0 | N | Y |  |
| test_core_deferred_entry_refusal.py | 1 | N | Y |  |
| test_core_dex_scope_and_ui_truth.py | 0 | Y | Y |  |
| test_core_disk_full.py | 1 | Y | Y | [audit_write_failure] order_intents.csv: TimeoutError('order_intents row for intent_id=int-b (seq None) is NOT on disk before the exchange call: an earlier order_intents row of wallet 0xaaaaaaaaaaaaaa |
| test_core_dispatch_block_remedy.py | 0 | Y | Y |  |
| test_core_dispatch_guards.py | 0 | Y | Y |  |
| test_core_dust_rules.py | 0 | Y | Y |  |
| test_core_dynamic_lanes.py | 0 | Y | Y |  |
| test_core_engine_gaps.py | 1 | Y | Y | C:\Users\wigmore\AppData\Local\Programs\Python\Python311\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx |
| test_core_exclusion_contract.py | 0 | Y | Y |  |
| test_core_exclusion_not_active_red.py | 0 | Y | Y |  |
| test_core_exposure_fail_cache.py | 0 | Y | Y |  |
| test_core_exposure_pending.py | 0 | Y | Y |  |
| test_core_fill_lag.py | 1 | Y | Y | [status_write_failure:live-integrity-status] TimeoutError |
| test_core_fill_trace_buffering.py | 0 | N | Y |  |
| test_core_fill_trace_concurrency.py | 0 | N | Y |  |
| test_core_fill_trace_retry.py | 0 | N | Y |  |
| test_core_fill_trace_status_context.py | 0 | N | Y |  |
| test_core_follower_dex_exists.py | 0 | Y | Y |  |
| test_core_follower_entry_exclusions.py | 0 | Y | Y |  |
| test_core_follower_mid_dex_keys.py | 0 | N | N |  |
| test_core_follower_volume_payload.py | 0 | N | Y |  |
| test_core_gates_alert_only.py | 0 | Y | Y |  |
| test_core_headroom.py | 0 | Y | Y |  |
| test_core_headroom_foreign_ws.py | 0 | Y | Y |  |
| test_core_held_past_limit.py | 0 | Y | Y |  |
| test_core_http_post_headroom.py | 0 | Y | Y |  |
| test_core_intent_durable_barrier.py | 0 | Y | Y |  |
| test_core_intent_failed_status_retained.py | 0 | Y | Y |  |
| test_core_intent_outside_lock.py | 0 | Y | Y |  |
| test_core_intent_write_behind.py | 0 | Y | Y |  |
| test_core_latency_trace_details.py | 0 | N | N |  |
| test_core_ledger_repair.py | 0 | Y | Y |  |
| test_core_liq_isolated.py | 0 | Y | Y |  |
| test_core_liq_parity.py | 0 | Y | Y |  |
| test_core_liq_parity_one_terminal_row.py | 0 | Y | Y |  |
| test_core_liq_projection.py | 0 | Y | Y |  |
| test_core_liquidation.py | 0 | Y | Y |  |
| test_core_live_only_stream_cap.py | 0 | Y | Y |  |
| test_core_local_first.py | 0 | Y | Y |  |
| test_core_margin_gate_and_single_terminal.py | 0 | Y | Y |  |
| test_core_margin_mode_background.py | 0 | Y | Y |  |
| test_core_master_gate.py | 0 | Y | Y |  |
| test_core_memory_bounds.py | 0 | Y | Y |  |
| test_core_merged_rows.py | 0 | Y | Y |  |
| test_core_missed_entry_reject_fields.py | 0 | Y | Y |  |
| test_core_missed_entry_rule.py | 0 | Y | Y |  |
| test_core_network_and_global_controls.py | 1 | Y | Y | C:\Users\wigmore\AppData\Local\Programs\Python\Python311\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx |
| test_core_nmp_terminal.py | 0 | Y | Y |  |
| test_core_no_silent_fill.py | 0 | Y | Y |  |
| test_core_observability_part1.py | 0 | Y | Y |  |
| test_core_off_path_skip.py | 0 | Y | Y |  |
| test_core_oid_bounds.py | 0 | Y | Y |  |
| test_core_open_orders_cache.py | 1 | N | Y | Traceback (most recent call last): |
| test_core_orphan_attempt_sweep.py | 0 | Y | Y |  |
| test_core_outage_defer.py | 0 | Y | Y |  |
| test_core_outage_paging.py | 0 | N | N |  |
| test_core_outage_replay.py | 0 | Y | Y |  |
| test_core_pair_anchor_clamp.py | 0 | Y | Y |  |
| test_core_poll_fallback.py | 0 | Y | Y |  |
| test_core_poll_overlap_scaling.py | 0 | Y | Y |  |
| test_core_queue_timing_stamps.py | 1 | N | N | Traceback (most recent call last): |
| test_core_r0_ws_resubscribe.py | 0 | Y | Y |  |
| test_core_r1_cursor.py | 1 | N | Y | Traceback (most recent call last): |
| test_core_reduce_only_repair.py | 0 | Y | Y |  |
| test_core_refusal_remedy_ownership.py | 0 | Y | Y |  |
| test_core_release_send_guards.py | 1 | N | N | Traceback (most recent call last): |
| test_core_retry_send_integrity.py | 0 | Y | Y |  |
| test_core_run3_fixes.py | 1 | Y | Y |  |
| test_core_run4_fixes.py | 1 | Y | Y |  |
| test_core_run5_converge.py | 0 | Y | Y |  |
| test_core_rw10_margin_symbol.py | 0 | Y | Y |  |
| test_core_rw11_meta_fetch_retry.py | 0 | Y | Y |  |
| test_core_rw12_eol_consistency.py | 0 | Y | Y |  |
| test_core_rw12_mode_at_send.py | 1 | Y | Y |  |
| test_core_rw12_retry_cloid.py | 1 | N | N | Traceback (most recent call last): |
| test_core_rw13_recovery_reconcile.py | 0 | Y | Y |  |
| test_core_rw13_universe_refresh.py | 0 | Y | Y |  |
| test_core_rw14_snapshot_failclosed.py | 0 | Y | Y |  |
| test_core_rw15_builder_empty.py | 0 | Y | Y |  |
| test_core_rw7b_review_fixes.py | 0 | Y | Y |  |
| test_core_rw9_timeout_vs_429.py | 1 | N | N | Traceback (most recent call last): |
| test_core_s9_held_position_closable.py | 0 | Y | Y |  |
| test_core_s9_unlisted_named.py | 0 | Y | Y |  |
| test_core_scope_sweep_resilience.py | 0 | Y | Y |  |
| test_core_send_lock_isolation.py | 0 | Y | Y |  |
| test_core_send_mode_fails_closed.py | 0 | Y | N |  |
| test_core_send_stage_stamps2.py | 0 | Y | Y |  |
| test_core_sender_key.py | 1 | N | Y | Traceback (most recent call last): |
| test_core_slot_reservation_pacing.py | 1 | N | N | ALERT: the gate refused an order (MISSING_INTENT_CONTEXT) but could not journal it: AttributeError("'RecordingSenderGateway' object has no attribute 'audit'") |
| test_core_snapshot_reads_every_dex.py | 0 | N | N |  |
| test_core_stage_stamps.py | 0 | Y | Y |  |
| test_core_standing_close_guard.py | 0 | Y | Y |  |
| test_core_state_bound_dedupe.py | 0 | Y | Y |  |
| test_core_stop_sentinel.py | 0 | Y | N |  |
| test_core_summary_account_value_sign.py | 0 | N | N |  |
| test_core_switch_states.py | 0 | Y | Y |  |
| test_core_tail_read_off_lock.py | 0 | Y | Y |  |
| test_core_trace_rotation.py | 0 | N | Y |  |
| test_core_trace_stamps.py | 1 | Y | Y |  |
| test_core_volume_warm_and_pending.py | 0 | Y | Y |  |
| test_core_warm_dex_clients.py | 0 | Y | Y |  |
| test_core_ws_pool_and_slots.py | 0 | Y | Y |  |
| test_core_ws_resubscribe.py | 0 | Y | Y |  |
| test_core_ws_startup_grace.py | 0 | Y | Y |  |
| test_core_xyz_equity_not_double_source.py | 0 | N | N |  |
| test_csv_field_limit.py | 0 | N | Y |  |
| test_db_exit_gate.py | 0 | Y | Y |  |
| test_exchange_truth_retry.py | 0 | Y | Y |  |
| test_g2_copy_correctness.py | 0 | N | Y |  |
| test_g3_exchange_truth.py | 0 | N | Y |  |
| test_g4_fixed_slices.py | 0 | Y | Y |  |
| test_g4_intake_sleeves.py | 0 | Y | Y |  |
| test_g4_order_cap.py | 0 | Y | Y |  |
| test_g4_ui_controls.py | 0 | Y | Y |  |
| test_hotpath_replay_bench.py | 0 | Y | Y |  |
| test_hotswap_seam.py | 0 | Y | Y |  |
| test_http_keepalive.py | 0 | Y | Y |  |
| test_info_weight_routes.py | 0 | Y | Y |  |
| test_j2_local_rejects.py | 0 | Y | Y |  |
| test_j4_pc_run_specs.py | 0 | Y | Y |  |
| test_leader_equity_singleflight.py | 0 | N | N |  |
| test_live_screen_truth.py | 1 | Y | Y | C:\Users\wigmore\AppData\Local\Programs\Python\Python311\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx |
| test_outage_classify.py | 0 | Y | Y |  |
| test_outage_classify_deferred.py | 0 | N | N |  |
| test_readiness1_ambiguous_timeout_no_blind_resend.py | 1 | Y | Y |  |
| test_request_weight_followup.py | 1 | N | N | .ALERT: the gate refused an order (MISSING_INTENT_CONTEXT) but could not journal it: AttributeError("'SenderGateway' object has no attribute 'audit'") |
| test_run_report.py | 0 | Y | Y |  |
| test_run_report_paging.py | 0 | N | Y |  |
| test_screen_run4.py | 1 | Y | Y | C:\Users\wigmore\AppData\Local\Programs\Python\Python311\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx |
| test_single_exchange_order_callsite.py | 0 | N | N |  |
| test_spot_classification_xyz.py | 0 | Y | N |  |
| test_spot_gate_refusal.py | 0 | Y | Y |  |
| test_t1a_cloid_pending_row.py | 1 | Y | Y |  |
| test_t1b_startup_orphan.py | 0 | Y | Y |  |
| test_t1c_stop_cancel.py | 0 | Y | Y |  |
| test_ui_account_basis.py | 0 | Y | Y |  |
| test_ui_account_tile_all_dexes.py | 0 | N | Y |  |
| test_ui_audit_summary_size.py | 0 | Y | Y |  |
| test_ui_exchange_age_unknown.py | 0 | Y | Y |  |
| test_ui_expected_rejections.py | 0 | Y | Y |  |
| test_ui_global_controls_preserve_unowned.py | 0 | N | Y |  |
| test_ui_incremental_edges.py | 0 | Y | Y |  |
| test_ui_incremental_summary.py | 0 | Y | Y |  |
| test_ui_partial_read_marker.py | 0 | Y | Y |  |
| test_ui_send_attempts_dedupe.py | 0 | Y | Y |  |
| test_ui_send_mode_survives.py | 0 | Y | Y |  |

files=167 with_TOTAL=133 no_TOTAL=34
exit_nonzero=24 timeouts=0

## no-TOTAL files

- test_core_all_mids_dex_isolation.py exit=0 RESULT=N tail=PASS the dex after the failing one is still read
- test_core_all_mids_dex_keys.py exit=0 RESULT=N tail=PASS named DEX bare mid is namespaced
- test_core_csv_field_limit.py exit=0 RESULT=Y tail=RESULT::core_csv_field_limit_PASS | True True True
- test_core_deferred_entry_refusal.py exit=1 RESULT=Y tail=RESULT::R1_STALE_THEN_FRESH_WITHIN_TOLERANCE_TAKES_FAIL | {'cause': 'FOLLOWER_PRICE_FRESHNESS_GATE', 'intent_id': '84f99
- test_core_fill_trace_buffering.py exit=0 RESULT=Y tail=RESULT::FILL_TRACE_30K_30MIB_PASS rows=30002 drops=0
- test_core_fill_trace_concurrency.py exit=0 RESULT=Y tail=RESULT::FILL_TRACE_100_PRODUCER_PASS rows=50000 drops=0 elapsed_ms=139.2
- test_core_fill_trace_retry.py exit=0 RESULT=Y tail=RESULT::FILL_TRACE_APPEND_RETRY_PASS rows=[{'ts': 1793313935437, 'k': 'fill_trace_drop', 'count': 2}, {'k': 'queued', 's
- test_core_fill_trace_status_context.py exit=0 RESULT=Y tail=RESULT::FILL_TRACE_STATUS_CONTEXT_PASS
- test_core_follower_mid_dex_keys.py exit=0 RESULT=N tail=PASS follower_mid resolves a namespaced xyz coin
- test_core_follower_volume_payload.py exit=0 RESULT=Y tail=RESULT::FOLLOWER_VOLUME_UNWRAPS_XNET_DATA_PASS
- test_core_latency_trace_details.py exit=0 RESULT=N tail=PASS: proc_end records rejection details, real replies, stage stamps, and blocked/exception outcomes
- test_core_open_orders_cache.py exit=1 RESULT=Y tail=PASS TWO_SWEEPS_ONE_CALL_INSIDE_TTL 1
- test_core_outage_paging.py exit=0 RESULT=N tail=PASS retained=3333/14000 dense=14000/14000 pages=8
- test_core_queue_timing_stamps.py exit=1 RESULT=N tail=
- test_core_r1_cursor.py exit=1 RESULT=Y tail=RESULT::nothing_pending_cursor_moves_PASS
- test_core_release_send_guards.py exit=1 RESULT=N tail=
- test_core_rw12_retry_cloid.py exit=1 RESULT=N tail=
- test_core_rw9_timeout_vs_429.py exit=1 RESULT=N tail=
- test_core_sender_key.py exit=1 RESULT=Y tail=RESULT::K1_SIGNER_UNKNOWN_HAS_ITS_OWN_CATEGORY_PASS
- test_core_slot_reservation_pacing.py exit=1 RESULT=N tail=
- test_core_snapshot_reads_every_dex.py exit=0 RESULT=N tail=PASS fetch returned SNAPSHOT_OK
- test_core_summary_account_value_sign.py exit=0 RESULT=N tail=PASS opposite signs -> conservative (negative) value
- test_core_trace_rotation.py exit=0 RESULT=Y tail=RESULT::trace_rotation_PASS | ['t.jsonl.1', 't.jsonl.2', 't.jsonl.3']
- test_core_xyz_equity_not_double_source.py exit=0 RESULT=N tail=PASS xyz snapshot is recorded (not dropped as zero account)
- test_csv_field_limit.py exit=0 RESULT=Y tail=RESULT::csv_field_limit_PASS
- test_g2_copy_correctness.py exit=0 RESULT=Y tail==== t1) repeated genuine ADDs -> event-authorised desired, delta-sized ===
- test_g3_exchange_truth.py exit=0 RESULT=Y tail==== A) MASTER truth drives ACTUAL; signer state cannot ===
- test_leader_equity_singleflight.py exit=0 RESULT=N tail=
- test_outage_classify_deferred.py exit=0 RESULT=N tail=PASS test_outage_classify_deferred
- test_request_weight_followup.py exit=1 RESULT=N tail=
- test_run_report_paging.py exit=0 RESULT=Y tail=RESULT::paging_PASS | got=4500 calls=3
- test_single_exchange_order_callsite.py exit=0 RESULT=N tail=
- test_ui_account_tile_all_dexes.py exit=0 RESULT=Y tail=RESULT::THE_TILE_HELPER_EXISTS_PASS
- test_ui_global_controls_preserve_unowned.py exit=0 RESULT=Y tail=RESULT::save_succeeded_PASS
