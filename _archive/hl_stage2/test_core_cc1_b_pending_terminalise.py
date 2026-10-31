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

def rows_for(aid):
    if not c.SEND_ATTEMPTS_CSV.exists():
        return []
    c._close_audit_handle(c.SEND_ATTEMPTS_CSV)
    with c.SEND_ATTEMPTS_CSV.open(newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("attempt_id") == aid]

def latest(aid):
    rows = rows_for(aid)
    return rows[-1] if rows else {}

def durable_owed(fid):
    # Independent disk readback: a stubbed append or in-memory flag cannot pass.
    rows = json.loads(c.CLOSE_ESCALATIONS_FILE.read_text(encoding="utf-8-sig")) if c.CLOSE_ESCALATIONS_FILE.exists() else {}
    return next((dict(r) for r in rows.values() if isinstance(r, dict)
                 and r.get("leader_fill_id") == fid and r.get("state") == "OPEN"), {})

def fixture(label, defect, is_exit=True):
    aid = "attempt-" + label
    cloid = c.generate_cloid("cloid-" + label)
    original_updater, original_rows, original_lease = c.update_send_attempt_row, c.send_attempt_rows, c._sender_lease_owned
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
        if defect == "POST_WAIT_MODE" and len(master_calls) == 2:
            return "MASTER_REAL_ORDERS_OFF"
        return ""
    def proof(*args, **kw):
        proof_calls.append(1)
        if defect in {"NET", "LATE_EXCEPTION_FALSE", "LATE_EXCEPTION_READ"} and len(proof_calls) == 2:
            raise RuntimeError("fresh_exchange_net exploded")
        if defect == "POST_WAIT_PROOF" and len(proof_calls) == 1:
            return "CLOSE_PROOF_HOLD_NET_UNKNOWN"
        if defect.startswith("LATE_BLOCK_") and len(proof_calls) == 2:
            return "CLOSE_PROOF_HOLD_NET_UNKNOWN"
        return ""
    gw._master_gate_reason, gw._final_close_proof = master, proof
    def pre_send():
        hooks.append(1)
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "created_at": c.utc_now_iso(), "attempt_id": aid,
            "intent_id": intent.intent_id, "leader_wallet": WALLET,
            "leader_fill_id": fill.leader_fill_id,
            "status": "pending_send", "terminal_state": "PENDING_SEND",
            "cloid": cloid,
        }, durable=True)
        if defect in {"LATE_BLOCK_RAISE", "LATE_EXCEPTION_RAISE"}:
            c.update_send_attempt_row = lambda *a, **kw: (_ for _ in ()).throw(OSError("isolated terminal append fault"))
        if defect in {"LATE_BLOCK_FALSE", "LATE_EXCEPTION_FALSE"}:
            c.update_send_attempt_row = lambda *a, **kw: False
        if defect == "LATE_EXCEPTION_READ":
            c.send_attempt_rows = lambda: (_ for _ in ()).throw(OSError("isolated terminal read fault"))
        if defect == "LATE_BLOCK_PARTIAL":
            def partial_write_then_fault(*a, **kw):
                original_updater(*a, **kw)
                raise OSError("isolated after-append acknowledgement lost")
            c.update_send_attempt_row = partial_write_then_fault
        return aid
    if defect == "POST_WAIT_LEASE":
        c._sender_lease_owned = lambda: False
    fault, response = None, None
    try:
        response = gw._place_order(spy, "BTC", False, 0.08, 100.0, "Ioc", True,
                                   timing={"send_attempt_id": aid}, intent=intent,
                                   cloid=cloid, path="b-negative-" + label, pre_send=pre_send)
    except Exception as exc:
        fault = exc
    finally:
        c.update_send_attempt_row = original_updater
        c.send_attempt_rows = original_rows
        c._sender_lease_owned = original_lease
    pending = latest(aid) if hooks else {}
    owed = durable_owed(fill.leader_fill_id)
    return spy.calls, hooks, fault, pending, owed, response


def sender_path_case(label, scenario):
    """Exercise production _send_real -> _place_order and both per-attempt pending rows.
    All exchange/credential objects are isolated fakes; no SDK or account is contacted.
    """
    old = {k: getattr(c, k) for k in (
        "HLAccount", "HLExchange", "classify_reject_category",
        "update_send_attempt_row", "send_attempt_rows",
        "_sender_lease_owned", "wait_intent_durable")}
    saved_secret = os.environ.get("HL_LIVE_HL_PRIVATE_KEY")
    c.HLAccount = object()
    c.HLExchange = object()
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "ISOLATED_FAKE_MARKER_NOT_A_KEY"
    c.wait_intent_durable = lambda *a, **kw: None
    if scenario == "two-attempt":
        c.classify_reject_category = lambda *a: "REDUCE_ONLY_REJECTED"
    if scenario in {"terminal-write-raised", "late-block-raised"}:
        c.update_send_attempt_row = lambda *a, **kw: (_ for _ in ()).throw(OSError("isolated append/read failed"))
    if scenario in {"terminal-write-false", "late-block-false"}:
        c.update_send_attempt_row = lambda *a, **kw: False
    if scenario == "terminal-read-raised":
        c.send_attempt_rows = lambda: (_ for _ in ()).throw(OSError("isolated CSV read failed")
                                     )
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
    checks, proofs = [], []
    def master(*a):
        checks.append(1)
        if scenario == "post-wait-mode" and len(checks) == 2:
            return "MASTER_REAL_ORDERS_OFF"
        if scenario == "two-attempt" and len(checks) == 6:
            raise ValueError("INVALID_CONFIG_READ: isolated retry final guard")
        if scenario not in {"two-attempt", "post-wait-mode", "post-wait-proof",
                            "post-wait-lease", "late-block-raised", "late-block-false"} and len(checks) == 3:
            raise ValueError("INVALID_CONFIG_READ: isolated final guard")
        return ""
    def proof(*a):
        proofs.append(1)
        if scenario == "post-wait-proof" and len(proofs) == 1:
            return "CLOSE_PROOF_HOLD_NET_UNKNOWN"
        if scenario in {"late-block-raised", "late-block-false"} and len(proofs) == 2:
            return "CLOSE_PROOF_HOLD_NET_UNKNOWN"
        return ""
    gw._master_gate_reason = master
    gw._final_close_proof = proof
    if scenario == "post-wait-lease":
        c._sender_lease_owned = lambda: False
    timing = {"send_attempt_id": "attempt-e2e-" + label, "send_cloid": c.generate_cloid("e2e-" + label)}
    try:
        outcome = gw._send_real(intent, timing)
        first_id = "attempt-e2e-" + label
        last_id = str(timing.get("send_attempt_id") or "")
        first = latest(first_id)
        last = latest(last_id) if last_id != first_id else first
        owed = durable_owed(fill.leader_fill_id)
        return outcome, list(spy.calls), first_id, last_id, first, last, owed
    finally:
        for key, val in old.items():
            setattr(c, key, val)
        if saved_secret is None:
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        else:
            os.environ["HL_LIVE_HL_PRIVATE_KEY"] = saved_secret

def sender_e2e_witnesses():
    scenarios = (
        ("one-fault", "single"),
        ("write-fault", "terminal-write-raised"),
        ("write-false", "terminal-write-false"),
        ("read-fault", "terminal-read-raised"),
        ("late-raised", "late-block-raised"),
        ("late-false", "late-block-false"),
        ("prior-call", "two-attempt"),
        ("post-mode", "post-wait-mode"),
        ("post-proof", "post-wait-proof"),
        ("post-lease", "post-wait-lease"),
    )
    no_pending = {"post-wait-mode", "post-wait-proof", "post-wait-lease"}
    durable_failure = {"terminal-write-raised", "terminal-write-false",
                       "terminal-read-raised", "late-block-raised", "late-block-false"}
    for label, scenario in scenarios:
        try:
            (ok, status, result), calls, first_id, last_id, first, last, owed = sender_path_case(label, scenario)
            if scenario == "two-attempt":
                expected_status = "ORDER_REJECTED"
            elif scenario in no_pending:
                expected_status = "ORDER_REJECTED"
            elif scenario in durable_failure:
                expected_status = "PRE_WIRE_TERMINAL_WRITE_FAILED"
            else:
                expected_status = "PRE_WIRE_FAULT_NO_EXCHANGE_CALL"
            valid_terminal = (
                result.get("terminal_state") in {"BLOCKED_AT_PLACE_ORDER",
                    "CLOSE_PROOF_HOLD_AT_WIRE", "SEND_BLOCKED_NO_SENDER_LEASE"}
                if scenario in no_pending else
                result.get("terminal_state", expected_status) == expected_status
            )
            check(label + "-PARENT_TRUTH",
                  not ok and bool(result.get("exchange_called")) == (scenario == "two-attempt")
                  and status == expected_status and valid_terminal,
                  (status, result))
            check(label + "-SDK_COUNT", len(calls) == (1 if scenario == "two-attempt" else 0), calls)
            check(label + "-DURABLE_OPEN_OWED",
                  owed.get("state") == "OPEN" and owed.get("leader_fill_id") == "event-e2e-" + label
                  and owed.get("intent_id") == "intent-e2e-" + label, owed)
            if scenario == "two-attempt":
                check(label + "-TWO_DISTINCT_ATTEMPTS",
                      first_id != last_id and first.get("cloid") and last.get("cloid")
                      and first["cloid"] != last["cloid"]
                      and first.get("status") == "ORDER_REJECTED"
                      and last.get("terminal_state") == "PRE_WIRE_FAULT_NO_EXCHANGE_CALL"
                      and result["timing"]["send_attempt_id"] == first_id
                      and result["timing"]["send_cloid"] == first["cloid"]
                      and len(rows_for(first_id)) >= 2 and rows_for(first_id)[0].get("status") == "pending_send",
                      (first, last, result))
            elif scenario in no_pending:
                check(label + "-NO_PHANTOM_PENDING",
                      not first and not last and not rows_for(first_id), (first, last))
            elif scenario in durable_failure:
                check(label + "-ORIGINAL_PENDING_UNMODIFIED",
                      first.get("status") == "pending_send" and first.get("cloid")
                      and first.get("terminal_state") == "PENDING_SEND"
                      and len(rows_for(first_id)) == 1 and rows_for(first_id)[0]["status"] == "pending_send", first)
            else:
                check(label + "-PENDING_DURABLY_TERMINALISED",
                      first.get("terminal_state") == "PRE_WIRE_FAULT_NO_EXCHANGE_CALL"
                      and first.get("status") != "pending_send"
                      and len(rows_for(first_id)) >= 2
                      and rows_for(first_id)[0]["status"] == "pending_send"
                      and rows_for(first_id)[0]["cloid"] == first["cloid"], first)
        except Exception as exc:
            check(label + "-EXCEPTION", False, repr(exc))

def late_gate_direct_witnesses():
    for label, kind in (
        ("post-mode-direct", "POST_WAIT_MODE"),
        ("post-proof-direct", "POST_WAIT_PROOF"),
        ("post-lease-direct", "POST_WAIT_LEASE"),
        ("late-block-raised-direct", "LATE_BLOCK_RAISE"),
        ("late-block-false-direct", "LATE_BLOCK_FALSE"),
        ("late-block-partial-direct", "LATE_BLOCK_PARTIAL"),
        ("late-exception-false-direct", "LATE_EXCEPTION_FALSE"),
        ("late-exception-read-direct", "LATE_EXCEPTION_READ"),
    ):
        try:
            calls, hooks, fault, row, owed, response = fixture(label, kind)
            aid = "attempt-" + label
            no_pending = kind.startswith("POST_WAIT")
            terminal_failed = kind in {"LATE_BLOCK_RAISE", "LATE_BLOCK_FALSE",
                                      "LATE_BLOCK_PARTIAL", "LATE_EXCEPTION_FALSE", "LATE_EXCEPTION_READ"}
            check(label + "-NO_SDK", len(calls) == 0, calls)
            check(label + "-DURABLE_OWED",
                  owed.get("state") == "OPEN" and owed.get("leader_fill_id") == "event-" + label
                  and owed.get("intent_id") == "intent-" + label, owed)
            check(label + "-RESPONSE_TYPED",
                  ((fault is None and isinstance(response, dict)
                    and response.get("exchange_called") is False) if no_pending else
                   isinstance(fault, c.PendingSendTerminalWriteFailed)), repr(fault or response))
            if no_pending:
                check(label + "-NO_PHANTOM",
                      not hooks and not row and not rows_for(aid), row)
            elif terminal_failed:
                hist = rows_for(aid)
                check(label + "-ORIGINAL_DURABLE_ROW",
                      len(hooks) == 1 and len(hist) >= 1 and hist[0].get("status") == "pending_send"
                      and hist[0].get("cloid") and all(h.get("cloid") == hist[0]["cloid"] for h in hist)
                      and ((len(hist) == 2 and row.get("terminal_state") == "CLOSE_PROOF_HOLD_AT_WIRE")
                           if kind == "LATE_BLOCK_PARTIAL" else len(hist) == 1 and row.get("status") == "pending_send"),
                      hist)
        except Exception as exc:
            check(label + "-EXCEPTION", False, repr(exc))

def main():
    for label, kind in (("config-after-pending", "CONFIG"),
                        ("net-after-pending", "NET"),
                        ("config-first-gate", "FIRST")):
        try:
            calls, hooks, fault, row, owed, response = fixture(label, kind)
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
    late_gate_direct_witnesses()
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(not x for x in RESULTS)))
    return 1 if not all(RESULTS) else 0

if __name__ == "__main__":
    sys.exit(main())
