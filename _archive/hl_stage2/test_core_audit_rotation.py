#!/usr/bin/env python3
"""Audit CSV rotation: all four append-only files rotate at HL_LIVE_AUDIT_ROTATE_MB,
keep newest HL_LIVE_AUDIT_KEEP, header preserved, readers see history across rotation.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_audit_rotation.py"""
import os, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="audit_rot_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(tmp),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LIVE_AUDIT_ROTATE_MB": "1",      # 1 MB threshold for fast test
    "HL_LIVE_AUDIT_KEEP": "3",           # keep 3 rotated files
})
import HL_Live_Copy_Service_Core as c
R = []
def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

# ---- 1. order_intents.csv rotates at threshold, header preserved, keep-N works
c.ensure_csv_header(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS)
pad = "x" * 200
for i in range(6000):
    c.append_csv(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS, {
        "intent_id": "i%d" % i, "leader_fill_id": "f%d" % i, "leader_wallet": "0x" + "1" * 40,
        "coin": "BTC", "leader_side": "BUY", "copy_side": "BUY", "leader_price": "100",
        "leader_size": "1", "leader_notional": "100", "copy_size": "1", "copy_notional": "100",
        "wallet_mode": "LIVE", "copy_mode": "fixed", "decision": "ENTRY_ALLOWED", "reason": "",
        "sleeve_id": "s%d" % i, "position_id": "p%d" % i, "position_direction_before": "FLAT",
        "wallet_position_before": "0", "coin_net_before": "0", "reduce_only_intended": "False",
        "reduce_only_sent_planned": "False", "marketable_bps": "", "max_close_adverse_diff_pct": "",
        "min_notional": "", "notes": pad,
    })
rot = c.rotated_audit_paths(c.ORDER_INTENTS_CSV)
check("ORDER_INTENTS_ROTATED_AT_LIMIT", len(rot) >= 1 and c.ORDER_INTENTS_CSV.stat().st_size < 2 * 1024 * 1024, [p.name for p in rot])
check("ORDER_INTENTS_KEEP_N", len(rot) <= 3, len(rot))
check("ORDER_INTENTS_FRESH_HAS_HEADER", c.ORDER_INTENTS_CSV.read_text().splitlines()[0].startswith("created_at"))
# history reader spans rotated + current
seen = [r["intent_id"] for r in c.iter_audit_history(c.ORDER_INTENTS_CSV)]
check("ORDER_INTENTS_HISTORY_SPANS_ROTATED", len(seen) == 6000 and seen[0] == "i0" and seen[-1] == "i5999", len(seen))

# ---- 2. reconciliation.csv rotates at threshold, header preserved, keep-N works
c.ensure_csv_header(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)
for i in range(6000):
    c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS, {
        "event": "E", "status": "S%d" % i, "leader_wallet": "0x" + "1" * 40,
        "leader_fill_id": "f%d" % i, "intent_id": "i%d" % i, "copy_fill_id": "",
        "coin": "BTC", "manual_net": "0", "exchange_net": "0", "action": "",
        "reject_category": "", "terminal_state": "", "exchange_order_id": "",
        "engine_can_close": "", "engine_can_send": "", "notes": pad,
    })
rot = c.rotated_audit_paths(c.RECONCILIATION_CSV)
check("RECONCILIATION_ROTATED_AT_LIMIT", len(rot) >= 1 and c.RECONCILIATION_CSV.stat().st_size < 2 * 1024 * 1024, [p.name for p in rot])
check("RECONCILIATION_KEEP_N", len(rot) <= 3, len(rot))
check("RECONCILIATION_FRESH_HAS_HEADER", c.RECONCILIATION_CSV.read_text().splitlines()[0].startswith("created_at"))
seen = [r["status"] for r in c.iter_audit_history(c.RECONCILIATION_CSV)]
check("RECONCILIATION_HISTORY_SPANS_ROTATED", len(seen) == 6000 and seen[0] == "S0" and seen[-1] == "S5999", len(seen))

# ---- 3. send_attempts.csv rotates at threshold, header preserved, keep-N works
c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
for i in range(6000):
    c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
        "attempt_id": "a%d" % i, "intent_id": "i%d" % i, "leader_fill_id": "f%d" % i,
        "leader_wallet": "0x" + "1" * 40, "coin": "BTC", "side": "BUY", "order_type": "LIMIT",
        "limit_price": "100", "copy_size": "1", "copy_notional": "100", "reduce_only_sent": "False",
        "sleeve_id": "s%d" % i, "position_id": "p%d" % i, "wallet_position_before": "0",
        "wallet_position_after_expected": "1", "coin_net_before": "0", "coin_net_after_expected": "1",
        "status": "ORDER_FILLED", "exchange_response": "{}", "exchange_order_id": str(1000000 + i),
        "error": "", "reject_category": "", "terminal_state": "FILLED_AWAITING_COPY_POLL",
        "operator_action": "WAIT_FOR_COPY_POLL", "latency_classification": "", "ws_received_ms": "0",
        "leader_fill_timestamp_ms": "0", "intent_created_at_ms": "0", "send_decision_started_ms": "0",
        "send_real_started_ms": "0", "symbol_resolve_started_ms": "0", "symbol_resolve_finished_ms": "0",
        "sdk_client_started_ms": "0", "sdk_client_finished_ms": "0", "exchange_call_started_ms": "0",
        "exchange_call_finished_ms": "0", "send_attempt_written_ms": "0", "queue_wait_ms": "0",
        "leader_to_intent_ms": "0", "intent_to_send_start_ms": "0", "symbol_resolve_ms": "0",
        "sdk_client_ms": "0", "exchange_call_ms": "0", "send_total_ms": "0", "leader_to_send_attempt_ms": "0",
        "notes": pad, "cloid": "", "enqueued_ms": "0", "picked_up_ms": "0", "process_started_ms": "0",
        "prewarm_done_ms": "0", "lock_acquired_ms": "0", "intent_written_ms": "0",
    })
rot = c.rotated_audit_paths(c.SEND_ATTEMPTS_CSV)
check("SEND_ATTEMPTS_ROTATED_AT_LIMIT", len(rot) >= 1 and c.SEND_ATTEMPTS_CSV.stat().st_size < 2 * 1024 * 1024, [p.name for p in rot])
check("SEND_ATTEMPTS_KEEP_N", len(rot) <= 3, len(rot))
check("SEND_ATTEMPTS_FRESH_HAS_HEADER", c.SEND_ATTEMPTS_CSV.read_text().splitlines()[0].startswith("created_at"))
# send_attempts cache handles rotation via inode change - it resets and reads new file only
# (bounded window cache for recent data; history reader spans rotated files)
c.send_attempt_rows()  # refresh cache
check("SEND_ATTEMPTS_CACHE_RESET_AFTER_ROTATION", c.send_attempt_by_oid("1059999") is None)
# history reader spans rotated + current
seen = [r["attempt_id"] for r in c.iter_audit_history(c.SEND_ATTEMPTS_CSV)]
check("SEND_ATTEMPTS_HISTORY_SPANS_ROTATED", len(seen) == 6000 and seen[0] == "a0" and seen[-1] == "a5999", len(seen))

# ---- 4. live_fills.csv rotates at threshold, header preserved, keep-N works
c.ensure_csv_header(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS)
for i in range(6000):
    c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, {
        "copy_fill_id": "cf%d" % i, "intent_id": "i%d" % i, "leader_fill_id": "f%d" % i,
        "leader_wallet": "0x" + "1" * 40, "sleeve_id": "s%d" % i, "position_id": "p%d" % i,
        "coin": "BTC", "side": "BUY", "fill_price": "100", "fill_size": "1", "fill_notional": "100",
        "fee": "0", "source": "COPY_POLL", "exchange_hash": "h%d" % i, "exchange_order_id": str(1000000 + i),
        "ledger_action": "UPDATED", "wallet_position_before": "0", "wallet_position_after": "1",
        "coin_net_after": "1", "notes": pad,
    })
rot = c.rotated_audit_paths(c.LIVE_FILLS_CSV)
check("LIVE_FILLS_ROTATED_AT_LIMIT", len(rot) >= 1 and c.LIVE_FILLS_CSV.stat().st_size < 2 * 1024 * 1024, [p.name for p in rot])
check("LIVE_FILLS_KEEP_N", len(rot) <= 3, len(rot))
check("LIVE_FILLS_FRESH_HAS_HEADER", c.LIVE_FILLS_CSV.read_text().splitlines()[0].startswith("created_at"))
seen = [r["copy_fill_id"] for r in c.iter_audit_history(c.LIVE_FILLS_CSV)]
check("LIVE_FILLS_HISTORY_SPANS_ROTATED", len(seen) == 6000 and seen[0] == "cf0" and seen[-1] == "cf5999", len(seen))

# ---- 5. readers still find a send row written before rotation
# Write a specific row, then rotate, then verify it's findable via history reader
c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
    "attempt_id": "pre_rotate", "intent_id": "pre_intent", "leader_fill_id": "pre_fill",
    "leader_wallet": "0x" + "1" * 40, "coin": "BTC", "side": "BUY", "order_type": "LIMIT",
    "limit_price": "100", "copy_size": "1", "copy_notional": "100", "reduce_only_sent": "False",
    "sleeve_id": "pre_sleeve", "position_id": "pre_pos", "wallet_position_before": "0",
    "wallet_position_after_expected": "1", "coin_net_before": "0", "coin_net_after_expected": "1",
    "status": "ORDER_FILLED", "exchange_response": "{}", "exchange_order_id": "999999",
    "error": "", "reject_category": "", "terminal_state": "FILLED_AWAITING_COPY_POLL",
    "operator_action": "WAIT_FOR_COPY_POLL", "latency_classification": "", "ws_received_ms": "0",
    "leader_fill_timestamp_ms": "0", "intent_created_at_ms": "0", "send_decision_started_ms": "0",
    "send_real_started_ms": "0", "symbol_resolve_started_ms": "0", "symbol_resolve_finished_ms": "0",
    "sdk_client_started_ms": "0", "sdk_client_finished_ms": "0", "exchange_call_started_ms": "0",
    "exchange_call_finished_ms": "0", "send_attempt_written_ms": "0", "queue_wait_ms": "0",
    "leader_to_intent_ms": "0", "intent_to_send_start_ms": "0", "symbol_resolve_ms": "0",
    "sdk_client_ms": "0", "exchange_call_ms": "0", "send_total_ms": "0", "leader_to_send_attempt_ms": "0",
    "notes": "pre_rotation_test", "cloid": "", "enqueued_ms": "0", "picked_up_ms": "0", "process_started_ms": "0",
    "prewarm_done_ms": "0", "lock_acquired_ms": "0", "intent_written_ms": "0",
})
# Force rotation by writing enough data
for i in range(6000):
    c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
        "attempt_id": "post%d" % i, "intent_id": "post_intent%d" % i, "leader_fill_id": "post_fill%d" % i,
        "leader_wallet": "0x" + "1" * 40, "coin": "BTC", "side": "BUY", "order_type": "LIMIT",
        "limit_price": "100", "copy_size": "1", "copy_notional": "100", "reduce_only_sent": "False",
        "sleeve_id": "post_sleeve%d" % i, "position_id": "post_pos%d" % i, "wallet_position_before": "0",
        "wallet_position_after_expected": "1", "coin_net_before": "0", "coin_net_after_expected": "1",
        "status": "ORDER_FILLED", "exchange_response": "{}", "exchange_order_id": str(2000000 + i),
        "error": "", "reject_category": "", "terminal_state": "FILLED_AWAITING_COPY_POLL",
        "operator_action": "WAIT_FOR_COPY_POLL", "latency_classification": "", "ws_received_ms": "0",
        "leader_fill_timestamp_ms": "0", "intent_created_at_ms": "0", "send_decision_started_ms": "0",
        "send_real_started_ms": "0", "symbol_resolve_started_ms": "0", "symbol_resolve_finished_ms": "0",
        "sdk_client_started_ms": "0", "sdk_client_finished_ms": "0", "exchange_call_started_ms": "0",
        "exchange_call_finished_ms": "0", "send_attempt_written_ms": "0", "queue_wait_ms": "0",
        "leader_to_intent_ms": "0", "intent_to_send_start_ms": "0", "symbol_resolve_ms": "0",
        "sdk_client_ms": "0", "exchange_call_ms": "0", "send_total_ms": "0", "leader_to_send_attempt_ms": "0",
        "notes": pad, "cloid": "", "enqueued_ms": "0", "picked_up_ms": "0", "process_started_ms": "0",
        "prewarm_done_ms": "0", "lock_acquired_ms": "0", "intent_written_ms": "0",
    })
# Verify the pre-rotation row is still findable via history reader
found = False
for r in c.iter_audit_history(c.SEND_ATTEMPTS_CSV):
    if r.get("attempt_id") == "pre_rotate":
        found = True
        break
check("PRE_ROTATION_ROW_FINDABLE_IN_HISTORY", found)

# Also verify via send_attempt_by_oid (cache only has post-rotation data; history reader has all)
c.send_attempt_rows()  # refresh cache
check("PRE_ROTATION_OID_NOT_IN_CACHE_ONLY_HISTORY", c.send_attempt_by_oid("999999") is None)

# ---- 6. rotated file naming pattern: <name>.<UTCyyyymmdd>.<n>.csv
for p in c.rotated_audit_paths(c.ORDER_INTENTS_CSV):
    import re
    check("ROTATED_NAME_PATTERN", re.fullmatch(r"order_intents\.\d{8}\.\d+\.csv", p.name), p.name)

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)