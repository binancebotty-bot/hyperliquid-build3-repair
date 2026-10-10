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
    check("B4_PENDING_ROW_PROMOTED_TO_ORDER_RESTING", promoted and promoted[0]["status"] == "ORDER_RESTING"
          and promoted[0]["exchange_order_id"] == "555", str(promoted)[:300])

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

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
