#!/usr/bin/env python3
"""T1a: cloid and the pending send row (orphan-order invariant, part a).

Every order carries a deterministic 128-bit hex cloid, and the send row is written with status `pending_send`
BEFORE the one physical exchange call, then replaced in place (same attempt_id) after the reply. A crash
between the two writes therefore leaves exactly one row naming the order, and no send ever leaves two rows.

Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_t1a_cloid_pending_row.py   # RESULT:: markers, exit 0/1.
Offline: fake exchange, no network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="t1a_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    mid = {"f": 100.0, "l": 100.0}
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mid["f"])} if mid["f"] else {})
    c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mid["l"])} if mid["l"] else {})

    # ---- helpers ---------------------------------------------------------------------------------
    e = c.generate_cloid("i1")
    check("A1_CLOID_IS_0X32HEX", e.startswith("0x") and len(e) == 34 and all(ch in "0123456789abcdef" for ch in e[2:]), e)
    check("A2_CLOID_DETERMINISTIC", c.generate_cloid("i1") == e and c.generate_cloid("i2") != e)
    check("A3_ATTEMPT_ID_DETERMINISTIC", c.generate_attempt_id("i1") == c.generate_attempt_id("i1")
          and c.generate_attempt_id("i1") != c.generate_attempt_id("i2"))
    check("A4_CLOID_FIELD_BEFORE_STAGE_STAMPS", "cloid" in c.SEND_ATTEMPT_FIELDS
          and c.SEND_ATTEMPT_FIELDS[-len(c.STAGE_STAMP_KEYS):] == list(c.STAGE_STAMP_KEYS), str(c.SEND_ATTEMPT_FIELDS[-8:]))

    # ---- update_send_attempt_row: replace in place, never duplicate --------------------------------
    p = tmp / "rows.csv"
    c.append_csv(p, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "a1", "coin": "BTC", "status": "pending_send", "cloid": "0x" + "1" * 32})
    c.append_csv(p, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "a2", "coin": "ETH", "status": "pending_send", "cloid": "0x" + "2" * 32})
    saved_csv = c.SEND_ATTEMPTS_CSV
    c.SEND_ATTEMPTS_CSV = p
    try:
        upd = c.update_send_attempt_row("a1", {"status": "ORDER_FILLED", "exchange_order_id": "77"})
        rows = list(c.csv.DictReader(p.open(newline="", encoding="utf-8-sig")))
        unknown = c.update_send_attempt_row("nope", {"status": "X"})
    finally:
        c.SEND_ATTEMPTS_CSV = saved_csv
    check("A5_UPDATE_IS_APPEND_ONLY", upd and len(rows) == 3 and rows[0]["status"] == "pending_send"
          and rows[2]["attempt_id"] == "a1" and rows[2]["status"] == "ORDER_FILLED"
          and rows[2]["exchange_order_id"] == "77" and rows[2]["coin"] == "BTC" and rows[1]["status"] == "pending_send", str(rows)[:300])
    check("A6_UPDATE_UNKNOWN_ID_RETURNS_FALSE", unknown is False)
    c.SEND_ATTEMPTS_CSV = p
    try:
        before = [r.get("status") for r in c.send_attempt_rows()]
        c.update_send_attempt_row("a2", {"status": "ORDER_REJECTED"})
        after = [r.get("status") for r in c.send_attempt_rows()]
    finally:
        c.SEND_ATTEMPTS_CSV = saved_csv
    check("A6B_INCREMENTAL_READER_SEES_THE_UPDATE", before == ["pending_send", "pending_send", "ORDER_FILLED"]
          and after == ["pending_send", "pending_send", "ORDER_FILLED", "ORDER_REJECTED"], f"{before} -> {after}")

    # ---- wire harness (fake exchange, no network) --------------------------------------------------
    class FakeExchange:
        def __init__(self, replies=None):
            self.calls, self.replies = [], list(replies or [])

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size,
                               "reduce_only": reduce_only, "cloid": (str(cloid) if cloid is not None else None)})
            if self.replies:
                return self.replies.pop(0)
            if tif["limit"]["tif"] == "Gtc":
                return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 4242}}]}}}
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(fake):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        return gw

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON",
                                                                  "copy_mode": "fixed", "fixed_notional": 1000}}})
    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"t{seq[0]}", LEADER, "BTC", side, price, size, c.utc_now_ms() + seq[0], "TEST", 0, {})

    def send(fake, follower=100.0):
        mid["f"], mid["l"] = follower, 100.0
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        led = c.ManualLedger(path=tmp / f"l{seq[0]}.json")
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill())
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            ok, status, res = gw._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        return ok, status, res, intent

    # ---- A7: filled IOC send: pending row written first, cloid on the wire, replaced in place ------
    fake = FakeExchange()
    gw = gateway(fake)
    ok, status, res, intent = send(fake, follower=100.0)
    expected_cloid = c.generate_cloid(intent.intent_id)
    expected_attempt = c.generate_attempt_id(intent.intent_id)
    rows = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
    check("A7_FILLED_IOC_OK", ok and status == "ORDER_FILLED", f"{ok} {status}")
    check("A8_CLOID_ON_THE_PHYSICAL_CALL", fake.calls and fake.calls[0]["cloid"] == expected_cloid, str(fake.calls))
    check("A9_ONE_PENDING_ROW_BEFORE_REPLY", len(rows) == 1 and rows[0]["status"] == "pending_send"
          and rows[0]["cloid"] == expected_cloid and rows[0]["attempt_id"] == expected_attempt, str(rows)[:400])
    gw._append_real_attempt(intent, status, res)
    rows = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
    check("A10_FINAL_ROW_APPENDED_SAME_ATTEMPT_ID",
          len(rows) == 2 and rows[0]["status"] == "pending_send" and rows[1]["status"] == "ORDER_FILLED"
          and rows[1]["attempt_id"] == expected_attempt and rows[1]["cloid"] == expected_cloid and rows[1]["exchange_order_id"], str(rows)[:400])

    # ---- A11: crash between the two writes (resting limit accepted, engine dies) --------------------
    fake2 = FakeExchange()
    gw2 = gateway(fake2)
    ok, status, res, intent2 = send(fake2, follower=101.0)   # beyond tolerance -> GTC rests at leader price
    rows = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
    pend = [r for r in rows if r.get("intent_id") == intent2.intent_id]
    check("A11_CRASH_LEAVES_ONE_PENDING_ROW_WITH_CLOID",
          len(pend) == 1 and pend[0]["status"] == "pending_send"
          and pend[0]["cloid"] == c.generate_cloid(intent2.intent_id), str(pend)[:400])

    # ---- A12: a pending_send row that has an oid is engine-owned for the matcher --------------------
    p2 = tmp / "owned.csv"
    c.append_csv(p2, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "own1", "intent_id": "iown", "leader_wallet": LEADER,
                                             "coin": "BTC", "side": "BUY", "status": "pending_send",
                                             "exchange_order_id": "9090", "copy_size": "1", "limit_price": "100"})
    saved_csv = c.SEND_ATTEMPTS_CSV
    c.SEND_ATTEMPTS_CSV = p2
    try:
        matcher = c.CopyFillMatcher(c.ManualLedger(path=tmp / "m.json"), c.AuditLogWriter())
    finally:
        c.SEND_ATTEMPTS_CSV = saved_csv
    check("A12_READERS_TREAT_PENDING_SEND_AS_OWNED", "9090" in matcher.sent_oid_index
          and matcher.sent_oid_index["9090"]["status"] == "pending_send", str(list(matcher.sent_oid_index)))

    # ---- A13: pending-row write failure -> fail closed: no exchange call, a not-attempted result ---------
    fake3 = FakeExchange()
    gw = gateway(fake3)
    def boom(*a, **k):
        raise OSError("disk full")
    gw._begin_pending_send = boom
    ok3, status3, res3, intent3 = send(fake3, follower=100.0)
    check("A13_PENDING_WRITE_FAILURE_SENDS_NOTHING", (not ok3) and not fake3.calls
          and "AUDIT_WRITE_FAILED" in str(status3), f"{ok3} {status3} {fake3.calls}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
