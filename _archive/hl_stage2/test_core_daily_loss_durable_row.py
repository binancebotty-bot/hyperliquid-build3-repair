#!/usr/bin/env python3
"""C7W20261029I2: daily-loss refusal leaves a restart-durable, named row per leader fill.

One process for the test, one fresh subprocess for restart verification. No Core edits, exchange
calls, wallet writes or orders. Run from _archive/hl_stage2:
    python test_core_daily_loss_durable_row.py
Targets the a1acc28 send-lane and reconciliation-writer APIs.
"""
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"

if len(sys.argv) > 1 and sys.argv[1] == "--restart-reader":
    import HL_Live_Copy_Service_Core as C
    fid = sys.argv[2]
    matches = [r for r in C.read_csv_rows(C.RECONCILIATION_CSV)
               if r.get("leader_fill_id") == fid
               and r.get("event") == "ENTRY_SAFETY_BLOCK"
               and r.get("status") == "ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED"
               and r.get("terminal_state") == "ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED"
               and "DAILY_LOSS_LIMIT_REACHED" in str(r.get("notes") or "")]
    sys.exit(0 if len(matches) == 1 else 1)

with tempfile.TemporaryDirectory(prefix="c7_daily_loss_") as tmp:
    os.environ["HL_LIVE_AUDIT_DIR"] = tmp
    import HL_Live_Copy_Service_Core as C

    results = []
    def check(label, ok, detail=""):
        results.append(bool(ok))
        print("RESULT::%s_%s%s" % (label, "PASS" if ok else "FAIL",
                                  (" | " + str(detail)[:200]) if not ok else ""))

    now = C.utc_now_ms()
    fid = "C7-DAILY-LOSS-FILL-001"
    cfg = types.SimpleNamespace(max_daily_loss=lambda: 100.0)
    core_gate = types.SimpleNamespace(cfg=cfg, _daily_pnl=(-125.0, now))
    gate = C.LiveCopyCore._daily_loss_block(core_gate)
    check("DAILY_LOSS_THRESHOLD_REACHED", gate == "DAILY_LOSS_LIMIT_REACHED", gate)

    core_gate._daily_pnl = (-99.0, C.utc_now_ms())
    check("BELOW_LIMIT_NOT_BLOCKED", C.LiveCopyCore._daily_loss_block(core_gate) == "")
    core_gate._daily_pnl = (-125.0, C.utc_now_ms())

    fill = types.SimpleNamespace(
        leader_fill_id=fid, leader_wallet="0xabc", coin="BTC", side="BUY", price=100.0, size=1.0,
        source="WS_CAPTURED", timestamp_ms=C.utc_now_ms(),
        raw={"dir": "Open Long", "created_at_ms": C.utc_now_ms()})
    intent = types.SimpleNamespace(
        fill=fill, intent_id="C7-DAILY-LOSS-INTENT-001", send_allowed=True,
        notes="lifecycle=ENTRY", reason="ENTRY", decision="SEND_ALLOWED",
        copy_side="BUY", copy_size=1.0, wallet_mode="LIVE")
    gateway = types.SimpleNamespace(
        cfg=types.SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON"),
        sender_key_invalid=False)
    sent, status = C.SenderGateway.send_if_allowed(gateway, intent, gate)
    check("ENTRY_REFUSED_WITH_NAMED_DAILY_LOSS_REASON",
          sent is False and status == "ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED", (sent, status))

    audit = C.AuditLogWriter()
    core_stub = types.SimpleNamespace(audit=audit)
    C.LiveCopyCore._append_send_terminal(core_stub, fill, intent, status)

    rows = [r for r in C.read_csv_rows(C.RECONCILIATION_CSV)
            if r.get("leader_fill_id") == fid]
    exact = [r for r in rows if r.get("event") == "ENTRY_SAFETY_BLOCK"
             and r.get("status") == "ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED"
             and r.get("terminal_state") == status
             and r.get("action") == "NO_SEND_ENTRY_SAFETY_BLOCK"
             and "block_reason=DAILY_LOSS_LIMIT_REACHED" in str(r.get("notes") or "")]
    check("DURABLE_NAMED_RECONCILIATION_ROW", len(exact) == 1, rows)
    check("ROW_IDENTIFIES_PRECISE_LEADER_FILL", len(rows) == 1 and rows[0].get("intent_id") == intent.intent_id, rows)
    check("IN_PROCESS_FILL_ROW_ACCOUNTED_FOR", audit.has_fill_row(fid))
    check("NO_EXCHANGE_SEND_ATTEMPT", not C.read_csv_rows(C.SEND_ATTEMPTS_CSV))

    # A separate Python interpreter must recover the row from disk, not a process-local set.
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            "--restart-reader", fid], capture_output=True, text=True,
                           env=os.environ.copy(), timeout=30)
    check("ROW_SURVIVES_FRESH_INTERPRETER_RESTART", child.returncode == 0,
          (child.returncode, child.stdout[-300:], child.stderr[-300:]))

    print("TOTAL=%d FAILED=%d" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)
