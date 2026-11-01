#!/usr/bin/env python3
"""Handover window regression tests for GTC missed-entry rest."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LEADER = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
          (" | " + str(detail)[:1800]) if detail and not ok else ""), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="gtcrowh_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_GLOBAL_LOCK_FILE": str(tmp / "sender.lock"),
        "HL_LIVE_ENV_FILE": str(tmp / "nonexistent.env"),
        "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_AUTO_SEND_ENABLED": "0", "HL_LIVE_HL_PRIVATE_KEY": "",
    })
    import HL_Live_Copy_Service_Core as c
    c.acquire_global_instance_lock(tmp / "state")
    c.USER_WALLET = FOLLOWER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True, "master_real_orders_enabled": True,
        "global_controls": {"marketable_bps": 20, "liq_parity": False},
        "wallets": {LEADER: {"enabled": True, "mode": "ON",
                             "copy_mode": "fixed", "fixed_notional": 1000}},
    })
    c.follower_mid = lambda coin, force=False: 120.0
    c.leader_mid = lambda coin, use_cached=False: 120.0
    c.LEADER_NETWORK = "testnet"
    c.FOLLOWER_NETWORK = "testnet"

    class FakeExchange:
        def __init__(self, first_oid=9001):
            self.calls, self.cancel_calls, self.cancel_replies = [], [], []
            self.next_oid = first_oid
        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            oid = self.next_oid; self.next_oid += 1
            self.calls.append({"oid": str(oid), "coin": coin, "size": size,
                               "tif": tif["limit"]["tif"], "side": "BUY" if is_buy else "SELL",
                               "cloid": str(cloid) if cloid is not None else "",
                               "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {
                "statuses": [{"resting": {"oid": oid}}]}}}
        def cancel(self, coin, oid):
            self.cancel_calls.append((coin, int(oid)))
            if not self.cancel_replies:
                return {"status": "err", "response": {"data": {
                    "statuses": [{"error": "cancel status unavailable"}]}}}
            return self.cancel_replies.pop(0)

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3,
                "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0,
                "min_size": 0.0, "status": "OK"}
    seq = [0]

    def new_scenario(first_oid, clear=True):
        if clear:
            c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        fake = FakeExchange(first_oid)
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(),
                            c.ManualLedger(path=tmp / ("ledger_%s.json" % first_oid)))
        g._resolve_coin = lambda coin: dict(resolved)
        g._exchange_client_for_coin = lambda coin: (fake, "BTC")
        g._get_exchange_client = lambda *a, **k: fake
        g._ensure_margin_mode = lambda *a, **k: None
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._pre_send_ownership_gate = lambda intent: (True, {})
        g._reserve_exchange_order_slot = lambda **k: c.utc_now_ms()
        return fake, g

    def entry():
        seq[0] += 1
        fill = c.LeaderFill("gtc-fill-%s" % seq[0], LEADER, "BTC",
                            "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {})
        return c.Intent("gtc-intent-%s" % seq[0], fill, "BUY", 1.0, 100.0,
                        "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % LEADER, "", "FLAT", 0.0, 0.0,
                        False, False, c.utc_now_ms(), "lifecycle=ENTRY;")

    def rest(g, intent):
        return g._missed_entry_rest_or_diff(intent, "SKIPPED_IOC_NO_IMMEDIATE_MATCH", g._base_timing(intent))

    def matching(g, fid):
        return [r for r in g.resting_entries() if r.get("leader_fill_id") == fid]

    # Case 1: forced handover interleaving
    fake, g = new_scenario(10101)
    it = entry()
    results = []
    started = threading.Event()
    gate = threading.Event()
    orig_register = g._register_resting_entry
    def patched(intent, sdk_coin, oid, px, size, why, cloid="", attempt_id=""):
        started.set()
        gate.wait(timeout=5)
        return orig_register(intent, sdk_coin, oid, px, size, why, cloid=cloid, attempt_id=attempt_id)
    g._register_resting_entry = patched

    def worker():
        results.append(rest(g, it))
    t1 = threading.Thread(target=worker)
    t1.start()
    started.wait(timeout=5)
    results.append(rest(g, it))
    gate.set()
    t1.join()

    rested = [r for r in results if r.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED"]
    already = [r for r in results if r.get("outcome") == "MISSED_ENTRY_ALREADY_RESTING"]
    check("GTC_CONCURRENT_RETRY_HANDOVER_WINDOW_NO_DUPLICATE_WIRE",
          len(rested) == 1 and len(already) == 1 and len(fake.calls) == 1
          and len(matching(g, it.fill.leader_fill_id)) == 1,
          "results=%r calls=%d" % (results, len(fake.calls)))

    # Case 2: _register raises -> reservation retained, no second physical entry
    fake2, g2 = new_scenario(10201)
    it2 = entry()
    g2._register_resting_entry = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    raised = False
    try:
        rest(g2, it2)
    except Exception:
        raised = True
    row = g2.resting_entry_for(LEADER, "BTC", "BUY")
    check("GTC_HANDOVER_REGISTER_RAISE_RETAINS_RESERVATION",
          raised and row is not None and bool(row.get("reserved")),
          "raised=%s row=%r" % (raised, row))
    before = len(fake2.calls)
    try:
        again = rest(g2, it2)
    except Exception as e:
        again = {"outcome": "EXCEPTION:" + str(e)}
    check("GTC_HANDOVER_REGISTER_RAISE_NO_DUPLICATE_WIRE",
          len(fake2.calls) == before and again.get("outcome") == "MISSED_ENTRY_ALREADY_RESTING",
          "again=%r calls=%d" % (again, len(fake2.calls)))

    failed = [name for name, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
