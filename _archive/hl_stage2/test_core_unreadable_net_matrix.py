#!/usr/bin/env python3
"""H2: unreadable exchange net must not be mistaken for a confirmed position.

TABLE: 4 read faults x 6 risk contexts x {ENTRY,CLOSE} = 48 cells.
Calls the PINNED Core's real _fresh_exchange_net, _pre_send_ownership_gate,
send_if_allowed and _close_wire_plan; never replaces their decision code.
Fake exposure HTTP, fake order sender, fake ledgers, no key access, no sockets.
RED means a requirement is NOT met by the pinned Core; this file changes no engine code.

Run (from _archive/hl_stage2):
  python test_core_unreadable_net_matrix.py
Expected until engine fixes: nonzero with CASE::...::RED output; do NOT repair Core.
"""
import os
import socket
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_OFFLINE_DIR = Path(tempfile.mkdtemp(prefix="h2-net-matrix-"))
os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(_OFFLINE_DIR / "offline.lock")
os.environ["HL_LIVE_ENV_FILE"] = str(_OFFLINE_DIR / "nonexistent.env")
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ["HL_LIVE_UNEXPLAINED_WAIT_SEC"] = "0"
# Deny every outbound TCP connection, including accidental SDK fallthrough.
_ORIGINAL_CONNECT = socket.socket.connect
def _deny_connect(sock, address):
    raise AssertionError("OFFLINE_SOCKET_DENIED")
socket.socket.connect = _deny_connect

import HL_Live_Copy_Service_Core as C  # noqa: E402

WALLET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40
LEADER = "0x" + "c" * 40
COIN = "BTC"
NOW = C.utc_now_ms()
READ_FAULTS = ("malformed_wallet", "not_ok", "throws", "malformed_exposure")
CONTEXTS = (
    "normal",
    "global_close_only",
    "missing_ownership",
    "missing_fills",
    "wrong_account",
    "foreign_exposure",
)
ALL_RESULTS = []
SOCKET_ATTEMPTS = []
# Keep the socket denial as a negative proof: no simulator may call real network.
def note(label, phase, read, context, ok, actual, required):
    safe = str(actual).replace("\n", " ").replace("\r", " ")[:370]
    state = "PASS" if ok else "RED"
    print("CASE::%s::%s::%s::%s::%s::actual=%s::required=%s" %
          (label, phase, read, context, state, safe, required))
    ALL_RESULTS.append((label, bool(ok), phase, read, context))


def fill(phase, cid):
    direction = "Open Long" if phase == "entry" else "Close Long"
    side = "BUY" if phase == "entry" else "SELL"
    f = types.SimpleNamespace(
        raw={"dir": direction, "created_at_ms": NOW},
        coin=COIN, side="B" if phase == "entry" else "A",
        leader_wallet=LEADER, leader_fill_id="h2-%s-%s" % (phase, cid),
        timestamp_ms=NOW, price=100.0, size=1.0)
    return types.SimpleNamespace(
        fill=f, intent_id="intent-h2-%s-%s" % (phase, cid), reason="",
        notes="lifecycle=%s" % ("ENTRY" if phase == "entry" else "EXIT"),
        copy_side=side, copy_size=1.0, decision="SEND_ALLOWED", cap_detail=None,
        send_allowed=True, wallet_mode="ON", reduce_only_intended=(phase == "close"),
        wallet_position_before=1.0 if phase == "close" else 0.0, coin_net_before=1.0)


def stub_gateway(context, read_fault):
    sends, audit_rows, escalations, reads = [], [], [], []
    global_close = context == "global_close_only"
    missing_sleeve = context == "missing_ownership"
    missing_fills = context == "missing_fills"
    foreign = context == "foreign_exposure"
    account = OTHER if context == "wrong_account" else WALLET
    ledger_size = 0.0 if missing_sleeve else 1.0
    # Persisted background snapshot is independent of the requested fresh
    # exposure. Its validity must NEVER legitimize an unreadable fresh read.
    persisted_size = 5.0 if foreign else ledger_size
    ledger = types.SimpleNamespace(
        data={"by_wallet": {} if missing_sleeve else
              {LEADER: {COIN: {"signed_size": 1.0}}}},
        coin_net=lambda coin: ledger_size)
    cfg = types.SimpleNamespace(
        master_switch_now=lambda: True,
        send_mode_now=lambda: "CLOSE" if global_close else "ON",
        wallet_over_stream_cap=lambda wallet: False,
        wallet_mode=lambda wallet: "ON",
        wallet_enabled=lambda wallet: True,
        liq_parity_enabled=lambda: False,
    )
    gw = types.SimpleNamespace(
        cfg=cfg, ledger=ledger, sender_key_invalid=False, truth_refresh=None,
        _market_halted_until_ms={}, _ioc_no_match_until_ms={},
        _margin_reject_until_ms={}, _pending_exit_lock=None,
        _audit_proof_block_reason=lambda: "missing_fills" if missing_fills else "",
        _persisted_exchange_positions=lambda: ({COIN: persisted_size}, ""),
        _manual_sleeves_for_coin=lambda coin: (
            [] if missing_sleeve else [(LEADER, {"signed_size": 1.0})]),
        _ownership_gate_block=lambda intent, status, reason, *a: {
            "status": status, "terminal_state": status, "error": reason,
            "operator_action": "NO_SEND_OWNERSHIP_BLOCK", "exchange_called": False},
        _append_local_block_reconciliation=lambda intent, status, row:
            audit_rows.append(("OWNERSHIP_GATE", status, dict(row))),
        audit=types.SimpleNamespace(append_reconciliation=lambda *a, **kw:
            audit_rows.append(("RECONCILIATION", str(a[:2]), dict(kw)))),
        leader_reduced_since=lambda f: False,
        _base_timing=lambda i: {},
        _send_time_wallet_mode_block=lambda intent, lifecycle: None,
        _floor_wire_size=lambda amount, decimals: round(amount, decimals),
        _proven_owned_for_sleeve=lambda w, coin: (
            (0.0, "fills_unreadable") if missing_fills or missing_sleeve
            else (1.0, "fills")),
        _open_close_escalation=lambda intent, why: escalations.append(why),
    )
    gw._follower_order_account_for_proof = lambda: account
    gw._close_proof_account_ok = lambda: C.SenderGateway._close_proof_account_ok()
    gw._reduce_only_for_intent = C.SenderGateway._reduce_only_for_intent
    gw._pre_send_ownership_gate = lambda intent: C.SenderGateway._pre_send_ownership_gate(gw, intent)
    def _fresh(coin):
        reads.append((coin, read_fault))
        return C.SenderGateway._fresh_exchange_net(gw, coin)
    gw._fresh_exchange_net = _fresh
    def _send(intent, timing=None):
        sends.append({"id": intent.intent_id, "copy_side": intent.copy_side})
        return False, "HARNESS_SEND_INTERCEPTED", {"exchange_called": False, "reject_category": ""}
    gw._send_real = _send
    return gw, sends, audit_rows, escalations, reads, account


def fake_exposure(read_fault):
    def read(*args, **kwargs):
        if read_fault == "throws":
            raise RuntimeError("synthetic exposure failure")
        if read_fault == "not_ok":
            return {"ok": False, "by_coin": {COIN: {"net": "3"}}}
        if read_fault == "malformed_exposure":
            return {"ok": True, "by_coin": {COIN: {"net": "NOT_A_NUMBER"}}}
        # malformed wallet must be rejected before this fetcher is invoked.
        raise AssertionError("malformed wallet unexpectedly attempted fetch")
    return read


def run_cell(read_fault, context, phase):
    gw, sends, audits, escalations, reads, account = stub_gateway(context, read_fault)
    intent = fill(phase, "%s-%s" % (read_fault, context))
    wallet = "not-a-wallet" if read_fault == "malformed_wallet" else WALLET
    # No private keys, live host state or real HTTP; fake account addresses ONLY.
    with mock.patch.object(C, "USER_WALLET", wallet), \
         mock.patch.object(C._XNET, "master_exposure", side_effect=fake_exposure(read_fault)), \
         mock.patch.object(C, "stale_snapshot_replay_reason", return_value=""), \
         mock.patch.dict(os.environ, {
             "HL_LIVE_HL_ACCOUNT_ADDRESS": account,
             "HL_LIVE_MOCK_SEND": "0",
             "HL_LIVE_NETTING_AWARE_REDUCE_ONLY": "1"}, clear=False):
        # The candidate method must differentiate malformed values; it currently
        # collapses invalid wallet, not-ok and exceptions to None, but malformed
        # *numbers* also collapse silently to 0.0 (fnum(..., 0.0)).
        raw = C.SenderGateway._fresh_exchange_net(gw, COIN)
        if not isinstance(raw, (int, float)) and raw is not None:
            raw_label = type(raw).__name__
        else:
            raw_label = repr(raw)
        note("FRESH_READER_CLASSIFIES", phase, read_fault, context,
             raw is None, "raw=%s" % raw_label,
             "typed unreadable; never guessed flat")
        if phase == "entry":
            # Real pre-send ownership logic / real send lane. All sends are fake.
            try:
                ok, status = C.SenderGateway.send_if_allowed(gw, intent)
                outcome = "ok=%r,status=%r" % (ok, status)
            except Exception as exc:
                ok, status = False, "EXCEPTION_" + type(exc).__name__
                outcome = "%s:%s" % (type(exc).__name__, str(exc)[:85])
            # A named unreadable-fresh-net refusal must exist. A global close-only
            # refusal alone is not a cause-specific exchange-net diagnosis.
            named = ("UNREADABLE" in str(status).upper() or
                     "MISSING_EXCHANGE_PROOF" in str(status).upper())
            owed = any("OWED" in repr(row) for row in audits)
            correct = (not sends and not ok and named and owed)
            note("ENTRY_NO_EXPOSURE_NAMED_FAILURE_AND_OWED",
                 phase, read_fault, context, correct,
                 "send_count=%d;%s;named=%s;owed_audit=%s;rows=%s" %
                 (len(sends), outcome, named, owed, len(audits)),
                 "zero sends + named read failure + durable owed evidence")
        else:
            timing = {}
            try:
                ro, amount, why = C.SenderGateway._close_wire_plan(
                    gw, intent, 1.0, 4, timing=timing)
                decision = timing.get("close_decision", "UNSET")
                error = ""
            except Exception as exc:
                ro, amount, why, decision = False, 0.0, type(exc).__name__, "EXCEPTION"
                error = "%s:%s" % (type(exc).__name__, str(exc)[:80])
            requires_hold = context in (
                "global_close_only", "missing_ownership", "missing_fills",
                "wrong_account", "foreign_exposure")
            # Close must read twice when it has usable ownership data and
            # precision; missing sleeve may legitimately hold before any read.
            reread_ok = len(reads) == (0 if context == "missing_ownership" else 2)
            # Direct fresh preflight above is independent; 2 reads inside close recheck.
            owned_send = (decision == "SEND" and abs(amount - 1.0) < 1e-10 and
                          ro is False and bool(escalations))
            safe_hold = (decision == "HOLD" and amount == 0 and ro is False and
                         bool(why) and bool(escalations))
            outcome = (safe_hold if requires_hold else owned_send)
            note("CLOSE_REVALIDATE_OWNED_RO_AND_RED", phase, read_fault, context,
                 reread_ok and outcome,
                 "decision=%s;size=%s;ro=%s;why=%s;reads=%d;RED=%s;error=%s" %
                 (decision, amount, ro, why, len(reads), escalations, error),
                 ("HOLD + named reason + RED owed" if requires_hold
                  else "one reread, SEND only fill-proven 1.0, RO false, RED owed"))

for _r in READ_FAULTS:
    for _ctx in CONTEXTS:
        for _phase in ("entry", "close"):
            run_cell(_r, _ctx, _phase)

expected = len(READ_FAULTS) * len(CONTEXTS) * 2 * 2
red = [r for r in ALL_RESULTS if not r[1]]
print("H2_SUMMARY::checks=%d::PASS=%d::RED=%d::cells=%d::socket_policy=DENY" %
      (len(ALL_RESULTS), len(ALL_RESULTS)-len(red), len(red), expected // 2))
if red:
    print("H2_RED_NAMES::" + ",".join("%s:%s:%s:%s" %
          (label, phase, rf, ctx) for label, _, phase, rf, ctx in red))
sys.exit(1 if red else 0)
