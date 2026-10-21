#!/usr/bin/env python3
"""Core engine: a copy-required intent that leaves the planner with no send attempt and no
terminal row must be recorded as INTENT_DROPPED_NO_SEND, never lost.

(a) an allowed perp intent whose send path raises   -> INTENT_DROPPED_NO_SEND written
(a2) an allowed perp intent whose symbol lookup fails -> its real reason stands, no dropped row
(b) a normal perp intent                            -> send attempt, no dropped row
(c) a spot intent                                   -> refused at the gate, not counted as dropped

Run: python test_intent_dropped_no_send.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

RESULTS = []
# literal, not imported: the test must measure behaviour, not the presence of the fix's own symbol
ALLOWED = {"ENTRY_ALLOWED", "ADD_ALLOWED", "SEND_ALLOWED", "EXIT_ALLOWED", "REDUCE_ALLOWED"}


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="coredrop_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_MOCK_SEND": "0",
        "HL_LIVE_PREWARM_SYMBOL_META": "0", "HL_LIVE_PREWARM_SDK_CLIENT": "0",
    })
    import HL_Live_Copy_Service_Core as c

    LEADER = "0x" + "d" * 40

    def fetcher(payload):
        t = payload.get("type")
        if t == "perpDexs":
            return []
        if t == "allMids":
            return {"BTC": "100"}
        return {"assetPositions": []}
    c.EXPOSURE_FETCHER = fetcher
    c.MIDS_FETCHER = fetcher

    # send mode ON: the send path is reachable, so a drop there is a real drop
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 100}}})

    c.USER_WALLET = "0x" + "c" * 40  # valid follower wallet: the exposure gates need one to read
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.dedupe.live_start_ms = 0  # nothing is excused as PRE_CUTOVER
    # ownership pre-send gate is a different invariant with its own terminal row; stub it out so
    # this test measures only whether a no-send intent is recorded or lost
    core.sender._pre_send_ownership_gate = lambda intent: (True, {})

    seq = [0]

    def fill(coin="BTC", side="BUY", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill("d%d" % seq[0], LEADER, coin, side, price, size, c.utc_now_ms(), "TEST")

    def rows_for(intent):
        if intent is None:
            return [], []
        recon = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("intent_id") == intent.intent_id]
        atts = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == intent.intent_id]
        return recon, atts

    # ---- (a) the allowed intent's send path raises: record the drop, do not lose it -----------
    def boom(*_a, **_k):
        raise RuntimeError("sender exploded")
    real_send = core.sender.send_if_allowed
    core.sender.send_if_allowed = boom
    raised = False
    try:
        core._process_leader_fill(fill())
    except RuntimeError:
        raised = True
    core.sender.send_if_allowed = real_send
    intent_a = list(core.intents_by_id.values())[-1]
    recon_a, att_a = rows_for(intent_a)
    check("A_INTENT_IS_COPY_REQUIRED", intent_a.decision in ALLOWED, intent_a.decision)
    check("A_EXCEPTION_PROPAGATES", raised, "send exception was swallowed")
    check("A_NO_SEND_ATTEMPT", not att_a, str(len(att_a)))
    check("A_DROPPED_ROW_WRITTEN",
          any(r.get("status") == "INTENT_DROPPED_NO_SEND" for r in recon_a),
          str([(r.get("event"), r.get("status")) for r in recon_a]))

    # ---- (a2) symbol resolution fails: the real reason stands, no dropped row ----------------
    core.sender._resolve_coin = lambda coin: {"ok": False, "raw_coin": coin,
                                              "status": "SYMBOL_UNRESOLVED",
                                              "error": "offline: not in meta cache",
                                              "exchange_called": False}
    _sent, status_a2, intent_a2 = core._process_leader_fill(fill())
    del core.sender._resolve_coin
    recon_a2, att_a2 = rows_for(intent_a2)
    check("A2_INTENT_ALLOWED", intent_a2.decision == "ENTRY_ALLOWED", intent_a2.decision)
    check("A2_REAL_REASON_WRITTEN", bool(recon_a2) or bool(att_a2), "no reason at all: status=%s" % status_a2)
    check("A2_NO_DROPPED_ROW",
          not any(r.get("status") == "INTENT_DROPPED_NO_SEND" for r in recon_a2),
          str([r.get("status") for r in recon_a2]))

    # ---- (b) a normal perp intent sends: attempt written, no dropped row ----------------------
    core.sender._send_real = lambda intent, timing=None: (True, "ORDER_FILLED", {
        "status": "ORDER_FILLED", "exchange_called": True, "exchange_response": {"mock": True},
        "oid": "7", "limit_px": 100.0, "wire_size": 1.0})
    sent_b, status_b, intent_b = core._process_leader_fill(fill())
    recon_b, att_b = rows_for(intent_b)
    check("B_SENT", bool(sent_b) and status_b == "ORDER_FILLED", "%s / %s" % (sent_b, status_b))
    check("B_SEND_ATTEMPT_WRITTEN", len(att_b) == 1, str(len(att_b)))
    check("B_NO_DROPPED_ROW", not any(r.get("status") == "INTENT_DROPPED_NO_SEND" for r in recon_b),
          str([r.get("status") for r in recon_b]))

    # ---- (c) a spot pair is refused at the gate: not sendable, not counted as dropped --------
    _sent_c, _status_c, intent_c = core._process_leader_fill(fill(coin="PURR", price=0.2))
    recon_c, att_c = rows_for(intent_c)
    # the spot gate is landed on its own branch (cf52cea); either way a spot pair is never sendable
    # and must never be recorded as a dropped copy-required intent
    check("C_NOT_A_COPY_REQUIRED_DECISION", intent_c.decision not in ALLOWED, intent_c.decision)
    check("C_NOT_SENDABLE", intent_c.send_allowed is False, str(intent_c.send_allowed))
    check("C_NO_SEND_ATTEMPT", not att_c, str(len(att_c)))
    check("C_NEVER_COUNTED_AS_DROPPED",
          not any(r.get("status") == "INTENT_DROPPED_NO_SEND" for r in recon_c),
          str([r.get("status") for r in recon_c]))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
