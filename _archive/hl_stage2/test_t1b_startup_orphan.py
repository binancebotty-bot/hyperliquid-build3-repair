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

    # ---- G1..G8: USER-OWNED orders are never cancelled (gap 1, simplified 6421004689) -------------------
    # The rule is cloid shape ONLY: no ledger is consulted, so an absent or unreadable ledger cannot change
    # any outcome.
    class _LedgerStub:
        """A manual ledger that USED to shield coins. It must now make no difference at all."""

        def __init__(self, coins, unreadable=False):
            self.data = {"by_wallet": {"user_owned": {cn: {"coin": cn, "signed_size": 1.0} for cn in coins},
                                       FOLLOWER: {cn: {"coin": cn, "signed_size": 1.0} for cn in coins}},
                         "by_coin_net": {}}
            self.unreadable = unreadable
            self.path = Path(tempfile.mkdtemp(prefix="t1b_ledger_")) / "manual_live_positions.json"
            self.path.write_text("{not json" if unreadable else "{}", encoding="utf-8")

        def nonflat_wallets_from_disk(self):
            return None if self.unreadable else {}

    def user_owned_rows(oid):
        return [r for r in recon_rows()
                if r.get("status") == "ORPHAN_ORDER_USER_OWNED" and r.get("exchange_order_id") == str(oid)]

    def one(order, ledger="absent"):
        """Run the check with ONE order and the given ledger state; return (res, fake, gw)."""
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        c.SEND_ATTEMPTS_CSV.write_text("", encoding="utf-8") if c.SEND_ATTEMPTS_CSV.exists() else None
        c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
        c.ensure_csv_header(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)
        c.OPEN_ORDERS_FETCHER = lambda p: [order]
        fake = FakeExchange()
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw.ledger = None if ledger == "absent" else _LedgerStub(["BTC"], unreadable=(ledger == "unreadable"))
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        return gw.startup_orphan_order_check(), fake, gw

    ENGINE_CLOID = "0x" + "a" * 32
    # G1: no cloid -> left alone and named, whatever the ledger says
    for ledger in ("absent", "unreadable", "normal"):
        res, fake, gw = one({"oid": 1001, "coin": "BTC", "side": "B", "sz": "1", "limitPx": "10"}, ledger)
        check("G1_CLOID_NONE_LEFT_ALONE__LEDGER_%s" % ledger.upper(),
              res["ok"] and not fake.cancels and not res["cancelled"]
              and len(res.get("user_owned") or []) == 1 and res["user_owned"][0]["oid"] == "1001", str(res))
        check("G1B_CLOID_NONE_AUDITED_BY_NAME__LEDGER_%s" % ledger.upper(),
              len(user_owned_rows(1001)) == 1 and "no cloid" in str(user_owned_rows(1001)[0].get("notes") or ""),
              str(user_owned_rows(1001))[:400])
    # G2: a 40-hex cloid is NOT engine-shaped (engine is exactly 32) -> left alone, ledger irrelevant
    for ledger in ("absent", "unreadable", "normal"):
        res, fake, gw = one({"oid": 1002, "coin": "BTC", "side": "A", "sz": "1", "limitPx": "99",
                             "cloid": "0x" + "a" * 40}, ledger)
        check("G2_40HEX_CLOID_LEFT_ALONE__LEDGER_%s" % ledger.upper(),
              res["ok"] and not fake.cancels and not res["cancelled"]
              and len(res.get("user_owned") or []) == 1, str(res))
    # G3: 0x+32hex is engine-shaped and unmatched -> cancelled exactly as before, ledger irrelevant
    for ledger in ("absent", "unreadable", "normal"):
        res, fake, gw = one({"oid": 1003, "coin": "BTC", "side": "A", "sz": "2", "limitPx": "50",
                             "cloid": ENGINE_CLOID}, ledger)
        check("G3_ENGINE_CLOID_CANCELLED__LEDGER_%s" % ledger.upper(),
              res["ok"] and [tuple(map(str, t)) for t in fake.cancels] == [("BTC", "1003")]
              and len(res["cancelled"]) == 1 and not (res.get("user_owned") or []), str(res))
    # G4: engine-shaped cloid in UPPERCASE is still engine-shaped -> cancelled
    res, fake, gw = one({"oid": 1004, "coin": "BTC", "side": "A", "sz": "1", "limitPx": "50",
                         "cloid": "0X" + "A" * 32})
    check("G4_UPPERCASE_ENGINE_CLOID_CANCELLED",
          res["ok"] and [tuple(map(str, t)) for t in fake.cancels] == [("BTC", "1004")], str(res))
    # G5: the sleeve machinery is GONE from the core - no _sleeved_coins, no sleeve constant
    check("G5_SLEEVE_MACHINERY_DELETED",
          not hasattr(c.SenderGateway, "_sleeved_coins") and not hasattr(c, "USER_SLEEVE_WALLET"), "still present")
    # G8: the label row is deduped by oid across restarts
    for _ in range(3):
        res, fake, gw = one({"oid": 1009, "coin": "BTC", "side": "B", "sz": "1", "limitPx": "10"})
        check("G8_LABEL_STILL_LEFT_ALONE", res["ok"] and not fake.cancels, str(res))
    check("G8_USER_OWNED_LABEL_DEDUPED_BY_OID", len(user_owned_rows(1009)) == 1, str(user_owned_rows(1009))[:400])
    # O5: both names classify NON_TERMINAL (else the observability unclassified list is non-empty)
    check("O5_NAMES_ARE_NON_TERMINAL",
          c.classify_terminal_row("ORPHAN_ORDER_USER_OWNED") == "NON_TERMINAL"
          and c.classify_terminal_row("USER_OWNED_ORDER_LEFT_UNTOUCHED") == "NON_TERMINAL", "unclassified")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
