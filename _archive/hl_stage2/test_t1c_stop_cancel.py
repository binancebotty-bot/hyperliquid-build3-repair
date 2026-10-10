#!/usr/bin/env python3
"""T1c: stop cancels resting entry limits (orphan-order invariant, part c).

On stop/disarm the engine cancels its resting entry limits FIRST via the existing withdraw path. Cancelled
limits are recorded; a cancel that fails stays in the registry with its cloid (withdraw_pending) so the next
startup's orphan check adopts it. No exception is swallowed without an audit row.

Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_t1c_stop_cancel.py   # RESULT:: markers, exit 0/1.
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
    tmp = Path(tempfile.mkdtemp(prefix="t1c_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.follower_dex_scope = lambda: [""]
    c._LEARNED_DEXES = set()
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.ensure_csv_header(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)

    class FakeExchange:
        def __init__(self):
            self.cancels = []

        def cancel(self, coin, oid):
            self.cancels.append((coin, oid))
            if str(oid) == "222":
                return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [
                    {"error": "some other cancel problem"}]}}}
            return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}

    def intent(iid):
        f = c.LeaderFill("f" + iid, LEADER, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {})
        return c.Intent(intent_id=iid, fill=f, copy_side="BUY", copy_size=1.0, copy_notional=100.0,
                        wallet_mode="LIVE", copy_mode="fixed", decision="ENTRY_ALLOWED", reason="", sleeve_id="s" + iid,
                        position_id="", position_direction_before="", wallet_position_before=0.0, coin_net_before=0.0,
                        reduce_only_intended=False, reduce_only_sent_planned=False, created_at_ms=c.utc_now_ms())

    fake = FakeExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
    gw._register_resting_entry(intent("ia"), "BTC", "111", 100.0, 1.0, "missed entry limit A")
    gw._register_resting_entry(intent("ib"), "BTC", "222", 100.0, 1.0, "missed entry limit B")
    check("C1_TWO_LIMITS_RESTING", set(gw._resting_entries) == {"111", "222"}, str(list(gw._resting_entries)))
    check("C1B_LIMITS_CARRY_A_CLOID", all(r.get("cloid") for r in gw._resting_entries.values()),
          str(gw._resting_entries))

    # ---- stop cancels both; the failing one stays resting with its cloid -------------------------------
    withdrawn = gw.stop_cancel_resting_entries()
    check("C2_STOP_CANCELLED_BOTH_ON_THE_EXCHANGE", fake.cancels == [("BTC", 111), ("BTC", 222)], str(fake.cancels))
    check("C3_CANCELLED_ROW_REMOVED", "111" not in gw._resting_entries and [w["oid"] for w in withdrawn] == ["111"],
          str(withdrawn))
    check("C4_FAILED_CANCEL_STILL_RESTING_WITH_CLOID",
          "222" in gw._resting_entries and gw._resting_entries["222"].get("withdraw_pending")
          and gw._resting_entries["222"].get("cloid") == c.generate_cloid("ib"), str(gw._resting_entries.get("222")))
    recon = c.read_csv_rows(c.RECONCILIATION_CSV)
    check("C5_CANCEL_RECORDED_AS_CANCELLED_ON_STOP",
          any(r.get("status") == "RESTING_ENTRY_CANCELLED_ON_STOP" and r.get("exchange_order_id") == "111" for r in recon),
          str(recon)[:400])
    check("C6_FAILED_CANCEL_AUDITED_NOT_SWALLOWED",
          any(r.get("status") == "RESTING_ENTRY_CANCEL_FAILED" and r.get("exchange_order_id") == "222" for r in recon),
          str(recon)[:400])

    # ---- next startup adopts the still-resting limit ---------------------------------------------------
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 222, "coin": "BTC", "side": "B", "sz": "1.0", "limitPx": "100",
                                        "cloid": c.generate_cloid("ib")}]
    res = gw.startup_orphan_order_check()
    check("C7_STARTUP_ADOPTS_THE_FAILED_LIMIT", res["ok"] and [a["oid"] for a in res["adopted"]] == ["222"]
          and not res["cancelled"], str(res))
    check("C8_ADOPTION_AUDITED",
          any(r.get("status") == "ORPHAN_ORDER_ADOPTED" and r.get("exchange_order_id") == "222"
              for r in c.read_csv_rows(c.RECONCILIATION_CSV)), "no ORPHAN_ORDER_ADOPTED row")

    # ---- stop never raises even if the withdraw machinery explodes -------------------------------------
    gw2 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw2._resting_entries = {"333": {"oid": "333", "coin": "BTC", "side": "BUY", "size": 1.0, "limit_px": 100.0,
                                    "cloid": "0x" + "3" * 32}}

    def boom(_rows):
        raise RuntimeError("withdraw machinery exploded")
    gw2._claim_rows = boom
    ok = True
    try:
        out = gw2.stop_cancel_resting_entries()
    except Exception:
        ok = False
        out = None
    check("C9_STOP_NEVER_RAISES", ok and out == [], str(out))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
