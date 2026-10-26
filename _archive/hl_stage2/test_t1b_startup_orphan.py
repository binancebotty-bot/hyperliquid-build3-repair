#!/usr/bin/env python3
"""T1b: startup orphan-order check (orphan-order invariant, part b).

Before arming, the sender reads the follower's open orders on every dex the engine reads. Each order is matched
to an engine send row / resting entry (by cloid or order id): a match is adopted as a resting engine order; no
match is cancelled and audited as `orphan_order_cancelled`. A failed read fails closed (refuses to arm). The
check never runs on a mainnet follower without --confirm-mainnet-follower.

Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_t1b_startup_orphan.py   # RESULT:: markers, exit 0/1.
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
    tmp = Path(tempfile.mkdtemp(prefix="t1b_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.ConfigManager.auto_send_enabled = property(lambda self: True)  # real sending configured (the check is skipped otherwise)
    c.follower_dex_scope = lambda: [""]          # one dex scope, deterministic
    c._LEARNED_DEXES = set()

    class FakeExchange:
        def __init__(self):
            self.cancels = []

        def cancel(self, coin, oid):
            self.cancels.append((coin, oid))
            return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}

    def recon_rows():
        return c.read_csv_rows(c.RECONCILIATION_CSV)

    def run(orders=None, raise_read=False, known_cloid="", pending_attempt=""):
        # fresh state per scenario
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
        c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
        c.ensure_csv_header(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)
        if known_cloid:
            c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS,
                         {"attempt_id": pending_attempt or "pend1", "intent_id": "i1", "coin": "BTC", "side": "BUY",
                          "status": "pending_send", "cloid": known_cloid, "copy_size": "1", "limit_price": "100"})
        if raise_read:
            def fetcher(p):
                raise RuntimeError("boom")
        else:
            def fetcher(p):
                return list(orders or [])
        c.OPEN_ORDERS_FETCHER = fetcher
        fake = FakeExchange()
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        res = gw.startup_orphan_order_check()
        return res, fake, gw

    # ---- B1: a matched order (by cloid) is adopted, not cancelled -----------------------------------
    cl = c.generate_cloid("i1")
    res, fake, gw = run(orders=[{"oid": 555, "coin": "BTC", "side": "B", "sz": "1.0", "limitPx": "100", "cloid": cl}],
                        known_cloid=cl, pending_attempt="pend1")
    check("B1_MATCHED_ADOPTED", res["ok"] and not fake.cancels and len(res["adopted"]) == 1, str(res))
    reg = c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {}) or {}
    check("B2_MATCHED_RECORDED_AS_RESTING", "555" in reg and reg["555"]["cloid"] == cl and reg["555"]["side"] == "BUY", str(reg))
    adopted = [r for r in recon_rows() if r.get("event") == "STARTUP_ORPHAN" and r.get("status") == "ORPHAN_ORDER_ADOPTED"]
    check("B3_ADOPTION_AUDITED", len(adopted) == 1 and adopted[0].get("exchange_order_id") == "555", str(adopted)[:300])
    promoted = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("attempt_id") == "pend1"]
    check("B4_PENDING_ROW_PROMOTED_TO_ORDER_RESTING", promoted and promoted[-1]["status"] == "ORDER_RESTING"
          and promoted[-1]["exchange_order_id"] == "555", str(promoted)[:300])

    # ---- B5: an unknown order is cancelled and audited ----------------------------------------------
    res, fake, gw = run(orders=[{"oid": 777, "coin": "BTC", "side": "A", "sz": "2.0", "limitPx": "99",
                                 "cloid": "0x" + "f" * 32}])
    check("B5_UNMATCHED_CANCELLED", res["ok"] and fake.cancels == [("BTC", 777)] and len(res["cancelled"]) == 1, str(res))
    cancelled = [r for r in recon_rows() if r.get("event") == "STARTUP_ORPHAN" and r.get("status") == "ORPHAN_ORDER_CANCELLED"]
    check("B6_CANCEL_AUDITED", len(cancelled) == 1 and cancelled[0].get("exchange_order_id") == "777", str(cancelled)[:300])

    # ---- B7: an order with no cloid but an oid we already hold is adopted ----------------------------
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {"888": {"oid": "888", "coin": "BTC", "side": "BUY",
                                                              "size": 1.0, "limit_px": 100.0, "cloid": ""}})
    c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS,
                 {"attempt_id": "own", "coin": "BTC", "status": "ORDER_RESTING", "exchange_order_id": "888"})
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 888, "coin": "BTC", "side": "B", "sz": "1.0", "limitPx": "100"}]
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    res = gw.startup_orphan_order_check()
    check("B7_MATCHED_BY_ORDER_ID_ADOPTED", res["ok"] and not fake.cancels and len(res["adopted"]) == 1, str(res))

    # ---- B8: empty open orders is a no-op -----------------------------------------------------------
    res, fake, _ = run(orders=[])
    check("B8_EMPTY_LIST_NOOP", res["ok"] and not res["adopted"] and not res["cancelled"] and not fake.cancels, str(res))

    # ---- B9: read failure fails closed (refuses to arm, touches nothing) -----------------------------
    res, fake, _ = run(raise_read=True)
    check("B9_READ_FAILURE_FAILS_CLOSED", (not res["ok"]) and "fail closed" in res.get("detail", "") and not fake.cancels, str(res))

    # ---- B10: mainnet follower without confirmation is skipped ---------------------------------------
    saved_net, saved_conf = c.FOLLOWER_NETWORK, c.MAINNET_ORDERS_CONFIRMED
    c.FOLLOWER_NETWORK, c.MAINNET_ORDERS_CONFIRMED = "mainnet", False
    try:
        res, fake, _ = run(orders=[{"oid": 999, "coin": "BTC", "side": "B", "sz": "1", "limitPx": "1"}])
    finally:
        c.FOLLOWER_NETWORK, c.MAINNET_ORDERS_CONFIRMED = saved_net, saved_conf
    check("B10_MAINNET_UNCONFIRMED_SKIPPED", res["ok"] and res.get("skipped") and not fake.cancels, str(res))

    # ---- G1..G6: USER-OWNED orders are never cancelled (gap 1, 2026-10-26) --------------------------
    class _LedgerStub:
        """A manual ledger holding ONE wallet's sleeves. Default wallet is the USER sleeve wallet, because
        only that wallet may shield an order (controller 6420098503); leader wallet ids hold the engine's own
        copy sleeves and must NOT shield anything."""

        def __init__(self, coins, wallet=None, unreadable=False):
            w = wallet or c.USER_SLEEVE_WALLET
            self.data = {"by_wallet": {w: {cn: {"coin": cn, "signed_size": 1.0} for cn in coins}},
                         "by_coin_net": {}}
            self.unreadable = unreadable
            self.path = Path(tempfile.mkdtemp(prefix="t1b_ledger_")) / "manual_live_positions.json"
            self.path.write_text("{not json" if unreadable else "{}", encoding="utf-8")

        def nonflat_wallets_from_disk(self):
            return None if self.unreadable else {}

    def user_owned_rows(oid):
        return [r for r in recon_rows()
                if r.get("status") == "ORPHAN_ORDER_USER_OWNED" and r.get("exchange_order_id") == str(oid)]

    # G1: an order carrying NO cloid cannot be the engine's -> left untouched and named
    res, fake, gw = run(orders=[{"oid": 1001, "coin": "HYPE", "side": "B", "sz": "5", "limitPx": "10"}])
    check("G1_CLOID_NONE_NOT_CANCELLED",
          res["ok"] and not fake.cancels and len(res.get("user_owned") or []) == 1
          and res["user_owned"][0]["oid"] == "1001" and not res["cancelled"], str(res))
    check("G1B_CLOID_NONE_AUDITED_BY_NAME", len(user_owned_rows(1001)) == 1,
          str(recon_rows())[:400])

    # G2/G6: USER sleeve wallet + NO cloid -> survives and the row names the sleeve
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 1002, "coin": "BTC", "side": "A", "sz": "1", "limitPx": "99",
                                        "cloid": "0x" + "a" * 40}]
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw.ledger = _LedgerStub(["BTC"])
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    res = gw.startup_orphan_order_check()
    check("G2_USER_SLEEVE_NO_CLOID_NOT_CANCELLED",
          res["ok"] and not fake.cancels and len(res.get("user_owned") or []) == 1 and not res["cancelled"], str(res))
    rows = user_owned_rows(1002)
    check("G6_SLEEVE_REASON_NAMED", len(rows) == 1 and "manual ledger" in str(rows[0].get("notes") or ""),
          str(rows)[:400])

    # G2B: the SAME user sleeve coin WITH an engine-style cloid -> still cancelled as an orphan (unchanged)
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 1006, "coin": "BTC", "side": "A", "sz": "1", "limitPx": "99",
                                        "cloid": "0x" + "a" * 32}]
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw.ledger = _LedgerStub(["BTC"])
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    res = gw.startup_orphan_order_check()
    check("G2B_USER_SLEEVE_WITH_ENGINE_CLOID_STILL_CANCELLED",
          res["ok"] and [tuple(map(str, t)) for t in fake.cancels] == [("BTC", "1006")]
          and len(res["cancelled"]) == 1 and not (res.get("user_owned") or []), str(res))

    # G2C: an ENGINE sleeve on the same coin (leader wallet id) + cloid None -> survives, but for the NO-CLOID
    # reason only; the sleeve itself must NOT be the shield.
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 1007, "coin": "BTC", "side": "B", "sz": "1", "limitPx": "99"}]
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw.ledger = _LedgerStub(["BTC"], wallet=FOLLOWER)
    check("G2D_ENGINE_SLEEVE_NOT_IN_SLEEVED_SET", gw._sleeved_coins() == (set(), True), "%r" % (gw._sleeved_coins(),))
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    res = gw.startup_orphan_order_check()
    check("G2C_ENGINE_SLEEVE_CLOID_NONE_SURVIVES_BY_CLOID_RULE",
          res["ok"] and not fake.cancels and len(res.get("user_owned") or []) == 1
          and "no cloid" in str(res["user_owned"][0].get("reason") or ""), str(res))

    # G3: engine-style cloid absent from the journal, coin has NO sleeve -> cancelled exactly as before
    # NOTE: the cancel path uses the SDK coin the exchange client reports (the run() helper stubs it to "BTC"),
    # so the coin under test must be BTC for the cancel to be observable here - that is B5's proven shape.
    res, fake, gw = run(orders=[{"oid": 1003, "coin": "BTC", "side": "A", "sz": "2", "limitPx": "50",
                                 "cloid": "0x" + "b" * 32}])
    check("G3_ENGINE_CLOID_ORPHAN_STILL_CANCELLED",
          res["ok"] and [tuple(map(str, t)) for t in fake.cancels] == [("BTC", "1003")]
          and len(res["cancelled"]) == 1 and not (res.get("user_owned") or []), str(res))

    # G5: a sender with NO ledger must not raise and must not protect anything (explicit None)
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 1005, "coin": "BTC", "side": "B", "sz": "1", "limitPx": "20",
                                        "cloid": "0x" + "c" * 32}]
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw.ledger = None
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    check("G5A_SLEEVED_COINS_NONE_LEDGER_IS_EMPTY", gw._sleeved_coins() == (set(), True), "sleeved=%r" % (gw._sleeved_coins(),))
    res = gw.startup_orphan_order_check()
    check("G5_LEDGER_NONE_SAFE",
          res["ok"] and [tuple(map(str, t)) for t in fake.cancels] == [("BTC", "1005")]
          and not (res.get("user_owned") or []), str(res))

    # G7: an UNREADABLE ledger cancels nothing - unknown is not zero, and cancelling is the unsafe direction
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 1008, "coin": "BTC", "side": "A", "sz": "1", "limitPx": "77",
                                        "cloid": "0x" + "d" * 40}]
    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw.ledger = _LedgerStub([], unreadable=True)
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    check("G7_SLEEVED_COINS_UNREADABLE_IS_UNKNOWN", gw._sleeved_coins() == (set(), False),
          "sleeved=%r" % (gw._sleeved_coins(),))
    res = gw.startup_orphan_order_check()
    check("G7_UNREADABLE_LEDGER_CANCELS_NOTHING",
          res["ok"] and not fake.cancels and len(res.get("user_owned") or []) == 1
          and not res["cancelled"] and len(user_owned_rows(1008)) == 1, str(res))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
