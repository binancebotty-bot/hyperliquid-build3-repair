#!/usr/bin/env python3
"""CS-I4 / I05 / I06: no-call after durable pre_send; isolated/testnet-only. NOT EXECUTED by GitHub-only writer."""
from __future__ import annotations
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(tempfile.mkdtemp(prefix="cc1_b_nocall_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(ROOT), "HL_LIVE_ENV_FILE": str(ROOT / "missing.env"),
    "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_GLOBAL_LOCK_FILE": str(ROOT / "isolated-global.lock"),
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

c.SEND_ATTEMPTS_CSV = ROOT / "send_attempts.csv"
c.RECONCILIATION_CSV = ROOT / "reconciliation.csv"
c.CLOSE_ESCALATIONS_FILE = ROOT / "close_escalations.json"
c._sender_lease_owned = lambda: True  # Isolate B; lease enforcement has its own physical test.
RESULTS = []
WALLET = "0x" + "a" * 40

def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
          " | " + str(detail)[:180] if not ok else ""), flush=True)

def latest(aid):
    c._close_audit_handle(c.SEND_ATTEMPTS_CSV)
    with c.SEND_ATTEMPTS_CSV.open(newline="", encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("attempt_id") == aid]
    return rows[-1] if rows else {}

def fixture(label, defect, is_exit=True):
    aid = "attempt-" + label
    fill = SimpleNamespace(leader_wallet=WALLET, leader_fill_id="event-" + label, coin="BTC")
    intent = SimpleNamespace(fill=fill, intent_id="intent-" + label, copy_side="SELL",
                             copy_size=0.08, reduce_only_intended=is_exit)
    class Spy:
        def __init__(self):
            self.calls = []
        def order(self, *args, **kw):
            self.calls.append((args, kw))
            return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": "0.08", "oid": 1}}]}}}
    spy = Spy()
    gw = object.__new__(c.SenderGateway)
    gw.audit = c.AuditLogWriter()
    gw._reserve_exchange_order_slot = lambda **kw: c.utc_now_ms()
    gw._reduce_only_for_intent = lambda i: is_exit
    gw._note_sender_key_rejection = lambda x: None
    gw._gate_refusal_row = lambda *a: None
    master_calls, proof_calls, hooks = [], [], []
    def master(*args):
        master_calls.append(1)
        if defect == "CONFIG" and len(master_calls) == 3:
            raise ValueError("INVALID_CONFIG_READ:JSONDecodeError")
        if defect == "FIRST" and len(master_calls) == 1:
            raise ValueError("INVALID_CONFIG_READ:JSONDecodeError")
        return ""
    def proof(*args, **kw):
        proof_calls.append(1)
        if defect == "NET" and len(proof_calls) == 2:
            raise RuntimeError("fresh_exchange_net exploded")
        return ""
    gw._master_gate_reason, gw._final_close_proof = master, proof
    def pre_send():
        hooks.append(1)
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "created_at": c.utc_now_iso(), "attempt_id": aid,
            "intent_id": intent.intent_id, "leader_wallet": WALLET,
            "leader_fill_id": fill.leader_fill_id,
            "status": "pending_send", "terminal_state": "PENDING_SEND",
        }, durable=True)
        return aid
    fault = None
    try:
        gw._place_order(spy, "BTC", False, 0.08, 100.0, "Ioc", True,
                        timing={"send_attempt_id": aid}, intent=intent,
                        path="b-negative-" + label, pre_send=pre_send)
    except Exception as exc:
        fault = exc
    pending = latest(aid) if hooks else {}
    open_rows = json.loads(c.CLOSE_ESCALATIONS_FILE.read_text()) if c.CLOSE_ESCALATIONS_FILE.exists() else {}
    owed = any(isinstance(r, dict) and r.get("leader_fill_id") == fill.leader_fill_id
              and r.get("state") == "OPEN" for r in open_rows.values())
    return spy.calls, hooks, fault, pending, owed

def main():
    for label, kind in (("config-after-pending", "CONFIG"),
                        ("net-after-pending", "NET"),
                        ("config-first-gate", "FIRST")):
        try:
            calls, hooks, fault, row, owed = fixture(label, kind)
            check(label + "-ZERO_SDK", not calls, calls)
            check(label + "-TYPED_NO_CALL", isinstance(fault, c.PreWireNoCallFault), repr(fault))
            if kind == "FIRST":
                check(label + "-NO_PHANTOM_PENDING", not hooks and not row)
            else:
                check(label + "-EXACT_TERMINAL_CSV",
                      len(hooks) == 1 and row.get("terminal_state") == "PRE_WIRE_FAULT_NO_EXCHANGE_CALL"
                      and row.get("status") != "pending_send" and row.get("operator_action") == "NO_EXCHANGE_CALL", row)
            check(label + "-DURABLE_OPEN_OWED_CLOSE", owed)
        except Exception as exc:
            check(label + "-UNEXPECTED_EXCEPTION", False, repr(exc))
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(not x for x in RESULTS)))
    return 1 if not all(RESULTS) else 0

if __name__ == "__main__":
    sys.exit(main())
