# CALL_MAP_7d865e5.md

> Graph: commit 7d865e5; graphify-out built 2026-10-31T16:28:45Z (age ~minutes at post time). Produced via graphify (C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe -m graphify update .) plus AST cross-check.

Caller -> callee map for Core's top-level functions (callee names invoked in body).

## load_env_file (line 79)
- calls: exists, get, len, partition, read_text, splitlines, startswith, strip

## _rebind_exchange_truth (line 123)
- calls: globals, guarded

## _rebind_follower_volume (line 130)
- calls: globals, guarded

## learn_follower_dex (line 228)
- calls: add, lower, split, str, strip

## _follower_dex_names (line 241)
- calls: acquire, get, list_perp_dexes, log_error, lower, release, set, str, strip, utc_now_ms

## follower_dex_scope (line 267)
- calls: RuntimeError, _follower_dex_names, add, getenv, log_error, lower, set, sorted, split, str, strip

## mids_dex_key (line 284)
- calls: str, upper

## follower_mid (line 300)
- calls: fnum, follower_dex_scope, get, getenv, int, isfinite, isinstance, items, mids_dex_key, post_many, stale, str, upper, utc_now_ms, zip

## follower_position_mark (line 329)
- calls: abs, canonical_coin_key, fnum, follower_dex_scope, get, items, master_exposure, normalise_wallet, sum

## _open_orders_cache_clear_locked (line 348)
- calls: pop

## invalidate_open_orders_cache (line 353)
- calls: _open_orders_cache_clear_locked

## _open_orders_send_begin (line 358)
- calls: _open_orders_cache_clear_locked

## _open_orders_send_end (line 363)
- calls: _open_orders_cache_clear_locked

## periodic_open_orders (line 368)
- calls: enumerate, fnum, get, getenv, int, isinstance, len, max, post_many, utc_now_ms, zip

## leader_mid (line 404)
- calls: fnum, get, getenv, int, isfinite, isinstance, items, lower, mids_dex_key, post_many, set, sorted, split, str, strip, upper, utc_now_ms, zip

## missed_entry_decision (line 432)
- calls: max, str, upper

## already_closed_late_entries (line 452)
- calls: abs, append, canonical_coin_key, enumerate, fnum, get, getenv, int, max, normalise_wallet, setdefault, sorted, str, strip, values

## _chain_sorted (line 480)
- calls: abs, all, append, extend, fnum, get, int, len, list, max, min, next, remove, sorted

## collapse_stale_runs (line 509)
- calls: LeaderFill, _chain_sorted, abs, append, bval, canonical_coin_key, close_run, dict, extend, fnum, get, getenv, handled, int, len, list, max, normalise_wallet, setdefault, sort, str, sum, values

## _short (line 583)
- calls: len, str

## sender_key_check (line 588)
- calls: _short, from_key, get, getenv, isinstance, lower, normalise_wallet, post_many, str, strip

## prof_take (line 660)
- calls: clear, int, items, sorted

## read_pair_start_anchor_ms (line 714)
- calls: Path, get, int, loads, max, read_text

## leader_poll_start_ms (line 729)
- calls: int, max

## _lock_for (line 755)
- calls: (none)

## _note_lock_contention (line 769)
- calls: _current_frames, append, basename, dumps, enumerate, extract_stack, get, get_ident, int, items, monotonic, open, str, utc_now_ms, write

## stamp_fill (line 837)
- calls: get, isinstance, max, utc_now_ms, values

## utc_now_ms (line 868)
- calls: int, time

## utc_now_iso (line 872)
- calls: isoformat, now

## fnum (line 876)
- calls: float, isfinite

## bval (line 886)
- calls: isinstance, lower, str, strip

## _response_text (line 894)
- calls: dumps, isinstance, str

## classify_rate_limit_kind (line 907)
- calls: getattr, isinstance

## classify_reject_category (line 920)
- calls: _response_text, lower

## reject_category_from_text (line 945)
- calls: classify_reject_category

## classify_send_lifecycle (line 949)
- calls: abs, fnum, getattr, signed_delta, split, str, strip, upper

## deferred_truth_max_seconds (line 977)
- calls: fnum, getenv

## classify_terminal_state (line 982)
- calls: get, str, upper

## classify_operator_action (line 1065)
- calls: classify_terminal_state, startswith

## send_status_reaches_catchall (line 1183)
- calls: startswith

## classify_terminal_row (line 1202)
- calls: str, strip, upper

## margin_unresolved_label (line 1213)
- calls: get, str, strip, upper

## missed_entry_skip_name (line 1226)
- calls: str, strip, upper

## classify_integrity_severity (line 1243)
- calls: startswith, str, upper

## send_terminal_state (line 1274)
- calls: classify_terminal_state

## stale_snapshot_replay_reason (line 1278)
- calls: any, fnum, get, getattr, int, isinstance, max, str, upper

## ensure_dirs (line 1291)
- calls: mkdir

## _attribution_json_safe (line 1297)
- calls: isinstance, items, str

## _write_attribution_json (line 1309)
- calls: _attribution_json_safe, dumps, get_ident, getattr, getpid, mkdir, replace, time_ns, unlink, with_name, write_text

## _append_core_fatal_row (line 1327)
- calls: DictWriter, exists, get, mkdir, open, stat, writeheader, writerow

## _process_identity (line 1341)
- calls: cwd, getpid, getppid, hasattr, list, loaded_sha, str

## _scan_interrupted_core_temps (line 1355)
- calls: _process_identity, _write_attribution_json, append, exists, fromtimestamp, getpid, glob, isoformat, sorted, stat, str, utc_now_iso

## record_core_phase (line 1377)
- calls: _process_identity, _write_attribution_json, str, utc_now_iso, utc_now_ms

## _write_core_start_record (line 1390)
- calls: _process_identity, _scan_interrupted_core_temps, _write_attribution_json, get, len, str, utc_now_iso

## _write_core_shutdown_record (line 1401)
- calls: _process_identity, _write_attribution_json, utc_now_iso, utc_now_ms

## _record_core_fatal (line 1412)
- calls: _append_core_fatal_row, _process_identity, _write_attribution_json, format_exception, getattr, getpid, getppid, hasattr, join, str, utc_now_iso, utc_now_ms

## install_core_attribution_hooks (line 1428)
- calls: SystemExit, _drain_status_write_workers, _record_core_fatal, _write_core_shutdown_record, _write_core_start_record, bool, callable, ensure_dirs, flush_intent_writer, getattr, getsignal, hasattr, int, previous, previous_sys_hook, previous_thread_hook, register, signal

## atomic_write_json (line 1485)
- calls: OSError, acquire, dumps, exists, get_ident, getpid, len, mkdir, note_audit_write_failure, prof, range, record_core_phase, release, replace, repr, sleep, str, time_ns, unlink, with_name, write_text

## load_json (line 1532)
- calls: exists, loads, read_text

## _close_audit_handle (line 1553)
- calls: close, pop, str

## _header_checked (line 1562)
- calls: get, stat, str, tuple

## _remember_header (line 1574)
- calls: pop, stat, str, tuple

## _note_append (line 1582)
- calls: get, pop, stat, str, tuple

## ensure_csv_header (line 1598)
- calls: DictReader, DictWriter, _close_audit_handle, _header_checked, _lock_for, _remember_header, all, exists, get, getpid, list, log_error, mkdir, open, pop, replace, stat, str, time_ns, with_suffix, writeheader, writerow

## rotated_audit_paths (line 1639)
- calls: fullmatch, glob, int, len, sorted, split

## audit_history_paths (line 1648)
- calls: exists, rotated_audit_paths

## _rotate_audit_file (line 1656)
- calls: DictWriter, _close_audit_handle, get, int, len, log_error, max, now, open, pop, replace, rotated_audit_paths, split, str, strftime, unlink, with_name, writeheader

## _owned_note (line 1682)
- calls: _normalize_oid, abs, fnum, get, str, strip

## note_audit_write_failure (line 1694)
- calls: get, getpid, int, open, utc_now_iso, write

## audit_write_failure_count (line 1711)
- calls: get, int, max, open, sum

## _fallback_path (line 1722)
- calls: (none)

## _spill_journal_path (line 1727)
- calls: _fallback_path, with_name

## _audit_row_data (line 1731)
- calls: get, str

## _audit_row_payload (line 1735)
- calls: DictWriter, StringIO, _audit_row_data, getvalue, writerow

## _append_spill_journal (line 1741)
- calls: OSError, _spill_journal_path, dumps, exists, fileno, flush, fsync, len, mkdir, open, stat, truncate, write

## _read_spill_journal (line 1761)
- calls: OSError, _spill_journal_path, enumerate, exists, get, isinstance, loads, open, stat, str, type

## _spill_rows (line 1799)
- calls: DictReader, OSError, _audit_row_data, _fallback_path, exists, open, read, seek, stat

## _spill_pending (line 1814)
- calls: _read_spill_journal, any, values

## _replay_payload_present (line 1818)
- calls: OSError, audit_history_paths, exists, len, open, read, seek, stat

## _spill_row (line 1833)
- calls: DictWriter, OSError, StringIO, _append_spill_journal, _audit_row_data, _fallback_path, _lock_for, _spill_rows, add, exists, fileno, flush, fsync, get, getvalue, len, mkdir, note_audit_write_failure, open, stat, str, truncate, uuid4, write, writeheader, writerow

## _replay_audit_fallback (line 1884)
- calls: OSError, _append_spill_journal, _audit_row_data, _audit_row_payload, _fallback_path, _lock_for, _read_spill_journal, _replay_payload_present, _spill_journal_path, _spill_rows, all, any, append_csv, discard, encode, ensure_csv_header, enumerate, exists, fileno, flush, fsync, get, hexdigest, int, isinstance, items, len, log_error, open, pop, set, sha256, stat, str, uuid4, values

## replay_audit_fallback (line 1980)
- calls: _replay_audit_fallback

## _audit_fallback_remains (line 1985)
- calls: _fallback_path, _spill_journal_path, any, exists, stat

## _audit_flush_worker (line 1989)
- calls: _audit_fallback_remains, _lock_for, clear, list, note_audit_write_failure, pop, replay_audit_fallback, str, values, wait

## _schedule_audit_flush (line 2015)
- calls: Thread, is_alive, list, note_audit_write_failure, set, start, str

## append_csv (line 2029)
- calls: OSError, _audit_row_payload, _close_audit_handle, _fallback_path, _is_owned, _lock_for, _note_append, _note_lock_contention, _owned_note, _rotate_audit_file, _schedule_audit_flush, _spill_row, acquire, ensure_csv_header, exists, fileno, flush, fsync, get, int, isinstance, len, log_error, min, monotonic, note_audit_write_failure, open, prof, release, sleep, stat, str, truncate, write

## update_send_attempt_row (line 2138)
- calls: append_csv, dict, get, reversed, send_attempt_rows, update

## enqueue_intent_row (line 2184)
- calls: Thread, append, append_csv, bval, fnum, get, getenv, int, is_alive, items, len, notify_all, pop, register, start

## _intent_writer_loop (line 2217)
- calls: add, append_csv, discard, fnum, get, getenv, int, len, log_error, max, min, notify_all, pop, popleft, range, set, setdefault, sleep, str, wait

## intent_seq_for (line 2256)
- calls: get, str

## wait_intent_durable (line 2262)
- calls: Thread, TimeoutError, discard, float, fnum, get, getenv, int, is_alive, items, monotonic, note_audit_write_failure, pop, set, setdefault, sorted, start, wait

## flush_intent_writer (line 2330)
- calls: TimeoutError, float, get, int, len, log_error, monotonic, note_audit_write_failure, wait

## intent_writer_status (line 2357)
- calls: bool, get, int, len

## _flush_intents_before_read (line 2363)
- calls: flush_intent_writer

## iter_csv_rows (line 2368)
- calls: BufferedReader, DictReader, TextIOWrapper, _BoundedRaw, _flush_intents_before_read, _lock_for, detach, exists, log_error, next, open, stat

## iter_audit_history (line 2398)
- calls: audit_history_paths, iter_csv_rows

## alert_unresolved_ambiguous_sends (line 2407)
- calls: add, append_reconciliation, get, iter_audit_history, lower, partition, set, split, str, strip, update_send_attempt_row, upper

## read_csv_tail_rows (line 2444)
- calls: DictReader, StringIO, _flush_intents_before_read, _lock_for, close, decode, exists, fileno, find, fstat, list, open, read, readline, rstrip, seek

## read_csv_rows (line 2473)
- calls: DictReader, StringIO, _flush_intents_before_read, _lock_for, close, decode, exists, fileno, fstat, list, open, prof, read, stat

## _slim_send_row (line 2502)
- calls: get

## _send_cache_reset (line 2506)
- calls: OrderedDict, deque, get, update

## _send_cache_add (line 2514)
- calls: _normalize_oid, _slim_send_row, append, len, move_to_end, popitem, upper

## _send_cache_refresh (line 2530)
- calls: DictReader, StringIO, _send_cache_add, _send_cache_reset, decode, exists, len, list, lstrip, open, read, rfind, seek, stat, str, update

## send_attempt_rows (line 2575)
- calls: _send_cache_refresh, list

## send_attempt_by_oid (line 2581)
- calls: _send_cache_refresh, get

## send_attempt_recovery_rows (line 2586)
- calls: _send_cache_refresh, list

## _coin_key_map (line 2600)
- calls: get, isinstance, items, load_json, stat, str, strip, upper

## canonical_coin_key (line 2628)
- calls: _coin_key_map, get, str, strip, upper

## is_spot_pair (line 2641)
- calls: bool, endswith, match, startswith, str, strip, upper

## canonical_coin_resolved (line 2647)
- calls: bool, canonical_coin_key, startswith, str, strip

## row_exchange_order_id (line 2656)
- calls: get, split, str, strip

## signed_from_side_size (line 2669)
- calls: abs, fnum, str, upper

## xyz_fill_after_position (line 2679)
- calls: abs, canonical_coin_key, fnum, get, isinstance, startswith, str, upper

## xyz_observation_preferred (line 2704)
- calls: abs, fnum, get, int, lower, str

## update_xyz_position_state_from_fills (line 2719)
- calls: abs, append, atomic_write_json, canonical_coin_key, dict, fnum, get, int, isinstance, items, load_json, setdefault, startswith, str, utc_now_iso, utc_now_ms, xyz_fill_after_position, xyz_observation_preferred

## load_xyz_position_state (line 2787)
- calls: isinstance, load_json, setdefault

## xyz_state_positions (line 2796)
- calls: abs, canonical_coin_key, fnum, get, isinstance, items, load_xyz_position_state

## service_position_evidence_by_coin (line 2809)
- calls: add, append, canonical_coin_key, fnum, get, int, read_csv_rows, row_exchange_order_id, set, setdefault, signed_from_side_size, sorted, str, upper, values

## build_live_integrity_status (line 2851)
- calls: _close_recovery_terminal, _exclusion_terminal_classification, _has_entry_safety_block_proof, _has_no_manual_position_terminal_proof, _has_ownership_gate_terminal_proof, _has_pending_exit_guard_proof, _intent_wallet, _leader_lifecycle, _local_terminal_classification, _manual_sleeve_exists, _raw_index_price_domain_terminal, abs, all, any, append, audit_write_failure_count, bool, canonical_coin_key, classify_integrity_severity, classify_reject_category, classify_terminal_row, dict, exists, findall, fnum, fromisoformat, get, getenv, int, is_current_core_row, is_historical_core_row, is_known_historical_terminal, isinstance, items, join, keys, len, load_json, load_xyz_position_state, lower, max, normalise_wallet, read_csv_rows, read_csv_tail_rows, replace, row_ms, set, setdefault, sorted, split, startswith, stat, str, strip, sum, timestamp, update, upper, utc_now_iso, utc_now_ms, values, xyz_state_positions

## _drain_status_write_workers (line 3743)
- calls: join_until, list, monotonic, report_shutdown_timeout

## write_live_integrity_status (line 3754)
- calls: atomic_write_json, build_live_integrity_status, monotonic, update

## log_error (line 3766)
- calls: append_csv, ensure_dirs, format_exc, isinstance, str, type, utc_now_iso, utc_now_ms, write

## normalise_wallet (line 3784)
- calls: lower, str, strip

## is_valid_wallet (line 3788)
- calls: all, len, startswith

## stable_hash (line 3792)
- calls: encode, hexdigest, join, sha256, str

## generate_cloid (line 3797)
- calls: encode, hexdigest, sha256, str

## is_engine_cloid (line 3804)
- calls: all, len, lower, startswith, str, strip

## generate_attempt_id (line 3811)
- calls: stable_hash

## _sdk_cloid (line 3822)
- calls: from_str

## _exchange_accepts_cloid (line 3837)
- calls: any, get, getattr, signature, type, values

## normalise_copy_fill_side (line 3856)
- calls: lower, str, strip

## _fill_dir (line 3892)
- calls: get, lower, str, strip

## mergeable_fills (line 3896)
- calls: _fill_dir, canonical_coin_key

## merge_leader_fills (line 3907)
- calls: LeaderFill, abs, dict, fnum, get, int, len, max, min, str, sum

## _safe_marker_name (line 4252)
- calls: str, sub

## claim_copy_fill_process_marker (line 4256)
- calls: _safe_marker_name, count, exists, fdopen, getpid, log_error, mkdir, open, rsplit, str, utc_now_iso, write

## _ledger_locked (line 4789)
- calls: fn, get

## project_liquidation_px (line 5507)
- calls: abs, max

## project_isolated_liquidation_px (line 5526)
- calls: (none)

## rotate_trace_file (line 10676)
- calls: exists, log_error, range, replace, stat, str, unlink, with_name

## _summary_account_value (line 11905)
- calls: append, float, fnum, get, isinstance, max, min

## _unified_account_value (line 11929)
- calls: _summary_account_value, any, extend, fnum, follower_dex_scope, get, isinstance, len, next, post_many, str, upper

## append_account_history_point (line 11962)
- calls: _summary_account_value, _unified_account_value, abs, append, atomic_write_json, fnum, fromisoformat, get, int, isinstance, len, load_json, log_error, str, timestamp, utc_now_iso, utc_now_ms

## load_existing_intents (line 12406)
- calls: (none)

## _populate_vol_cache (line 12421)
- calls: add, float, get, isfinite, isinstance, len, set, str, strip, update, utc_now_ms, zip

## warm_follower_volumes (line 12445)
- calls: float, follower_volumes_24h, log_error, utc_now_ms

## follower_volumes_24h (line 12465)
- calls: dict, float, follower_dex_scope, log_error, post_many, read_24h_volumes, set, time, update

## min_24h_notional_usd (line 12495)
- calls: float, get, isfinite, isinstance, loads, read_text, stat, update

## follower_entry_exclusion (line 12530)
- calls: follower_volumes_24h, get, min_24h_notional_usd, str, strip, upper

## _check (line 15188)
- calls: TestFailure, print

## _write_csv (line 15194)
- calls: DictWriter, append, keys, mkdir, open, writeheader, writerow

## run_self_test (line 15208)
- calls: AuditLogWriter, ConfigManager, CopyFillMatcher, DedupeStore, Event, ExchangeReconciler, FakeCopyIngestor, Intent, IntentBuilder, LeaderFill, LeaderFillIngestor, LiveCopyCore, ManualLedger, Path, SenderGateway, SimpleNamespace, TemporaryDirectory, Thread, WSManager, _FakeExchange, _RecordingApp, _check, _format_limit_px, _journal_authorised_close_refusal, _on_message, _recompute_net, _reduce_only_for_intent, _resolve_coin, _send_real, _write_csv, abs, any, append, append_csv, atomic_write_json, bool, build, build_live_integrity_status, claim_copy_fill_process_marker, classify_leader_side_for_wallet, classify_send_lifecycle, clear, clear_close_escalations, close, coin_net, compare_snapshot, copy_fill_id, dict, dumps, empty, ensure_csv_header, ensure_dirs, exists, floor, fnum, get, globals, is_valid_wallet, isinstance, items, join, len, load_env_file, load_json, loads, match_and_apply, mkstemp, normalise_copy_fill_side, pop, print, put_nowait, range, read_csv_rows, run_cycle, run_scope_sweep, save, set, setdefault, sleep, sleeve, sleeve_id, start, stop, str, sum, type, unlink, update, upper, utc_now_iso, utc_now_ms, wallet_coin_position, write_health, write_text

## repair_flat_ledger_only_positions (line 16510)
- calls: AuditLogWriter, ConfigManager, ExchangeReconciler, ManualLedger, RuntimeError, _exchange_signed_size, abs, append, append_live_fill_repair_close, append_reconciliation, canonical_coin_key, close_sleeve_as_exchange_flat, ensure_dirs, fetch_snapshot, fnum, get, isinstance, items, keys, load_xyz_position_state, normalise_wallet, sorted, startswith, str, wallets, write_live_integrity_status

## repair_recovery_copy_fills (line 16604)
- calls: AuditLogWriter, CopyAccountIngestor, CopyFillMatcher, ManualLedger, _copy_fill_oid, _normalize_oid, append, canonical_coin_key, copy_fill_id, ensure_dirs, fnum, get, int, keys, len, match_and_apply, normalise_copy_fill_side, poll_copy_account_fills, set, utc_now_ms, write_live_integrity_status

## copy_cursor_ms (line 16679)
- calls: fnum, get, int, isinstance, load_json

## canonical_copy_fill_id (line 16688)
- calls: join, len, pop, split, str

## _read_all_copy_fills (line 16699)
- calls: COPY_FILLS_FETCHER, copy_fill_id, dict, fnum, get, int, isinstance, json, len, list, max, post, range, request_lane, sorted, values

## repair_ledger_catch_up (line 16734)
- calls: AuditLogWriter, CopyFillMatcher, ManualLedger, _apply_oid_matched_copy_fill, _copy_fill_oid, _fresh_sent_row_for_oid, _intent_from_send_attempt, _is_liquidation_fill, _normalize_oid, _read_all_copy_fills, _safe_marker_name, _try_apply_liquidation, abs, all, any, append, append_reconciliation, canonical_coin_key, canonical_copy_fill_id, coin_net, copy_fill_id, dict, ensure_dirs, exists, fnum, follower_dex_scope, get, held, int, isinstance, items, len, lower, master_exposure, max, min, normalise_copy_fill_side, normalise_wallet, read_csv_rows, round, sent_row_for, set, setdefault, signed_delta, sorted, split, str, sum, tol, utc_now_ms, values, write_live_integrity_status

## _adoptable_intent_rows (line 16890)
- calls: abs, append, canonical_coin_key, fnum, get, max, normalise_copy_fill_side, read_csv_rows, str, strip, tol

## repair_adopt_oids (line 16914)
- calls: AuditLogWriter, CopyFillMatcher, Intent, LeaderFill, ManualLedger, _adoptable_intent_rows, _copy_fill_oid, _fresh_sent_row_for_oid, _normalize_oid, _read_all_copy_fills, abs, add, append, append_live_fill, append_reconciliation, apply_copy_fill, canonical_coin_key, canonical_copy_fill_id, claim_copy_fill_process_marker, coin_net, copy_fill_id, dict, ensure_dirs, fnum, get, int, len, min, normalise_copy_fill_side, normalise_wallet, read_csv_rows, setdefault, sleeve_id, sorted, str, strip, utc_now_iso, utc_now_ms, wallet_coin_position, write_live_integrity_status

## _sender_lease_owned (line 17070)
- calls: bool

## _global_instance_lock_path (line 17079)
- calls: Path, getenv, gettempdir, str, strip

## _global_holder_path (line 17088)
- calls: with_name

## release_global_instance_lock (line 17094)
- calls: close

## acquire_global_instance_lock (line 17103)
- calls: SystemExit, _global_holder_path, _global_instance_lock_path, close, dumps, fileno, flock, flush, get, getpid, isoformat, loads, locking, mkdir, now, open, read_text, seek, startswith, str, strip, truncate, write, write_text

## acquire_instance_lock (line 17155)
- calls: Path, SystemExit, close, fileno, flock, locking, mkdir, open, seek

## main (line 17174)
- calls: ArgumentParser, ConfigManager, CycleSummary, LiveCopyCore, Path, RuntimeError, SystemExit, _write_core_shutdown_record, acquire_global_instance_lock, acquire_instance_lock, add_argument, asdict, bool, bval, claim_network_stamp, dumps, exists, float, flush_intent_writer, fnum, get, getenv, install_core_attribution_hooks, int, len, live_over_stream_cap, live_wallets, log_error, max, min, monotonic, parse_args, print, print_help, repair_adopt_oids, repair_flat_ledger_only_positions, repair_ledger_catch_up, repair_recovery_copy_fills, replace, run_cycle, run_self_test, sender_key_check, sleep, stamp_state_refusal, start, start_convergence_thread, start_copy_poll_thread, startup_orphan_order_check, stat, stop, tick, time, unlink, wallet_mode_counts, warm_follower_volumes, write_startup, write_startup_status

## journal_sweeps_enabled (line 17400)
- calls: get, getenv, isinstance, loads, lower, read_text, str, strip

## close_orphan_attempt_rows (line 17421)
- calls: _close_orphan_attempt_rows_impl, acquire, float, get, globals, release, time

## _close_orphan_attempt_rows_impl (line 17443)
- calls: Decimal, InvalidOperation, Path, RuntimeError, _canon_oid, _is_close, abs, add, adjusted, append, append_csv, bool, dict, float, fnum, get, globals, int, is_finite, items, len, log_error, lower, quantize, read_csv_rows, repr, set, setdefault, sort, sorted, split, str, strip, to_integral_value, update, upper, utc_now_iso, utc_now_ms, values

