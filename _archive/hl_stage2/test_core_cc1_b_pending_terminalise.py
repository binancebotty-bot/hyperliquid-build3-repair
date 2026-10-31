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


def sender_path_case(label, scenario):
    """Exercise production _send_real -> _place_order and both per-attempt pending rows.
    All exchange/credential objects are isolated fakes; no SDK or account is contacted.
    """
    old = {k: getattr(c, k) for k in (
        "HLAccount", "HLExchange", "classify_reject_category",
        "update_send_attempt_row", "wait_intent_durable")}
    saved_secret = os.environ.get("HL_LIVE_HL_PRIVATE_KEY")
    c.HLAccount = object()
    c.HLExchange = object()
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "ISOLATED_FAKE_MARKER_NOT_A_KEY"
    c.wait_intent_durable = lambda *a, **kw: None
    if scenario == "two-attempt":
        c.classify_reject_category = lambda *a: "REDUCE_ONLY_REJECTED"
    if scenario == "terminal-write-raised":
        c.update_send_attempt_row = lambda *a, **kw: (_ for _ in ()).throw(OSError("isolated append/read failed"))
    fill = SimpleNamespace(leader_wallet=WALLET, leader_fill_id="event-e2e-" + label,
                           coin="BTC", price=100.0, raw={})
    intent = SimpleNamespace(fill=fill, intent_id="intent-e2e-" + label,
                             notes="lifecycle=EXIT", copy_side="SELL",
                             copy_size=0.08, copy_notional=8.0, reduce_only_intended=True,
                             wallet_position_before=0.08, coin_net_before=0.08,
                             sleeve_id="sleeve-" + label, position_id="pos-" + label)
    class FakeExchange:
        def __init__(self):
            self.calls = []
        def order(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return {"status": "err", "response": "REDUCE_ONLY_REJECTED"}
    spy = FakeExchange()
    gw = object.__new__(c.SenderGateway)
    gw.audit = c.AuditLogWriter()
    gw.cfg = SimpleNamespace(marketable_bps=lambda: 20.0,
                             max_close_adverse_diff_pct=lambda: 0.0,
                             min_notional=lambda: 1.0,
                             max_order_notional=lambda: 1000.0)
    gw._resolve_coin = lambda *_: {"ok": True, "sdk_coin": "BTC", "sz_decimals": 4,
                                   "price_max_decimals": 2, "min_order_value_usd": 1.0}
    gw._format_limit_px = lambda v, dec: round(v, dec)
    gw._floor_wire_size = lambda v, dec: round(v, dec)
    gw._pre_exchange_asset_safety = lambda *a: (True, {})
    gw._get_exchange_client = lambda *a: spy
    gw._exchange_client_has_symbol = lambda *a: True
    gw._withdraw_standing_close = lambda exchange, i, sz, dec, timing: (sz, None)
    gw._ensure_margin_mode = lambda *a: None
    gw._close_wire_plan = lambda i, size, dec, *a, **kw: (True, size, "")
    gw._ceiling_split_plan = lambda *a: (0.0, "")
    gw._effective_symbol_min_notional = lambda *a: 1.0
    gw._validate_final_wire_order = lambda *a: (True, {})
    gw._reserve_exchange_order_slot = lambda **kw: c.utc_now_ms()
    gw._reduce_only_for_intent = lambda i: True
    gw._reduce_only_on_wire = lambda *a: False
    gw._note_sender_key_rejection = lambda *a: None
    gw._gate_refusal_row = lambda *a: None
    gw._parse_hl_response = lambda response: (False, "ORDER_REJECTED", "", "REDUCE_ONLY_REJECTED")
    owed = []
    gw._journal_authorised_close_refusal = lambda i, reason: owed.append((i.intent_id, reason))
    checks = []
    def master(*a):
        checks.append(1)
        at = 6 if scenario == "two-attempt" else 3
        if len(checks) == at:
            raise ValueError("INVALID_CONFIG_READ: isolated final guard")
        return ""
    gw._master_gate_reason = master
    gw._final_close_proof = lambda *a: ""
    timing = {"send_attempt_id": "attempt-e2e-" + label, "send_cloid": c.generate_cloid("e2e-" + label)}
    try:
        outcome = gw._send_real(intent, timing)
        first_id = "attempt-e2e-" + label
        last_id = str(timing.get("send_attempt_id") or "")
        first = latest(first_id)
        last = latest(last_id) if last_id != first_id else first
        return outcome, list(spy.calls), first_id, last_id, first, last, owed
    finally:
        for key, val in old.items():
            setattr(c, key, val)
        if saved_secret is None:
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        else:
            os.environ["HL_LIVE_HL_PRIVATE_KEY"] = saved_secret

def sender_e2e_witnesses():
    for label, scenario in (
        ("one-fault", "single"),
        ("write-fault", "terminal-write-raised"),
        ("prior-call", "two-attempt"),
    ):
        try:
            (ok, status, result), calls, first_id, last_id, first, last, owed = sender_path_case(label, scenario)
            check(label + "-PARENT_TRUTH",
                  bool(result.get("exchange_called")) == (scenario == "two-attempt")
                  and ((status == "ORDER_REJECTED") if scenario == "two-attempt"
                       else status == ("PRE_WIRE_TERMINAL_WRITE_FAILED" if scenario == "terminal-write-raised"
                                      else "PRE_WIRE_FAULT_NO_EXCHANGE_CALL")),
                  (status, result))
            check(label + "-SDK_COUNT", len(calls) == (1 if scenario == "two-attempt" else 0), calls)
            check(label + "-OWED_RETAINED", bool(owed), owed)
            if scenario == "two-attempt":
                check(label + "-TWO_DISTINCT_ATTEMPTS",
                      first_id != last_id and first.get("cloid") and last.get("cloid")
                      and first["cloid"] != last["cloid"]
                      and first.get("status") == "ORDER_REJECTED"
                      and last.get("terminal_state") == "PRE_WIRE_FAULT_NO_EXCHANGE_CALL"
                      and result["timing"]["send_attempt_id"] == first_id
                      and result["timing"]["send_cloid"] == first["cloid"], (first, last, result))
            elif scenario == "terminal-write-raised":
                check(label + "-ORIGINAL_PENDING_UNMODIFIED",
                      first.get("status") == "pending_send" and first.get("cloid")
                      and first.get("terminal_state") == "PENDING_SEND", first)
            else:
                check(label + "-PENDING_DURABLY_TERMINALISED",
                      first.get("terminal_state") == "PRE_WIRE_FAULT_NO_EXCHANGE_CALL"
                      and first.get("status") != "pending_send", first)
        except Exception as exc:
            check(label + "-EXCEPTION", False, repr(exc))

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
    sender_e2e_witnesses()
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(not x for x in RESULTS)))
    return 1 if not all(RESULTS) else 0

if __name__ == "__main__":
    sys.exit(main())
