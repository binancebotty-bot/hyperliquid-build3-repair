#!/usr/bin/env python3
"""GTCROW-1820: refused-entry GTC pending-order ownership and terminal-proof lifecycle.

Independent, fail-capable offline test. No network, signing or live engine.
Actual Core path: _missed_entry_rest_or_diff -> _place_order -> _register_resting_entry.
The exchange can refuse a CANCEL or its open-orders snapshot can be incomplete:
neither is affirmative proof of a fill/cancel. Retain one owed order until
exchange confirms a terminal event; do not send a second GTC on retry.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LEADER = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" %
          (name, "PASS" if ok else "FAIL",
           (" | " + str(detail)[:1800]) if detail and not ok else ""), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="gtcrow_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_GLOBAL_LOCK_FILE": str(tmp / "sender.lock"),
        "HL_LIVE_ENV_FILE": str(tmp / "nonexistent.env"),
        "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_AUTO_SEND_ENABLED": "0", "HL_LIVE_HL_PRIVATE_KEY": "",
    })
    import HL_Live_Copy_Service_Core as c
    c.acquire_global_instance_lock(tmp / "state")
    check("HARNESS_REAL_ISOLATED_SENDER_LEASE", c._sender_lease_owned())
    c.USER_WALLET = FOLLOWER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True, "master_real_orders_enabled": True,
        "global_controls": {"marketable_bps": 20, "liq_parity": False},
        "wallets": {LEADER: {"enabled": True, "mode": "ON",
                             "copy_mode": "fixed", "fixed_notional": 1000}},
    })
    # A genuinely adverse follower price: BUY 100 versus current 120 must
    # rest at the leader's passive price, never marketable IOC.
    c.follower_mid = lambda coin, force=False: 120.0
    c.leader_mid = lambda coin, use_cached=False: 120.0
    c.LEADER_NETWORK = "testnet"
    c.FOLLOWER_NETWORK = "testnet"

    class FakeExchange:
        def __init__(self, first_oid=9001):
            self.calls, self.cancel_calls, self.cancel_replies = [], [], []
            self.next_oid = first_oid

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            oid = self.next_oid
            self.next_oid += 1
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

    resolved = {
        "ok": True, "sdk_coin": "BTC", "sz_decimals": 3,
        "price_max_decimals": 2, "perp_dexs": [""],
        "sdk_order_compatible": True, "min_order_value_usd": 1.0,
        "min_size": 0.0, "status": "OK",
    }
    seq = [0]

    def new_scenario(first_oid):
        # Each scenario is independent: registry, manual ledger and fake venue.
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
        return g._missed_entry_rest_or_diff(
            intent, "SKIPPED_IOC_NO_IMMEDIATE_MATCH", g._base_timing(intent))

    def matching(g, fid):
        return [r for r in g.resting_entries() if r.get("leader_fill_id") == fid]

    def persisted(fid):
        raw = c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        return [r for r in raw.values() if r.get("leader_fill_id") == fid] if isinstance(raw, dict) else []

    def opp(fill):
        return c.LeaderFill("opposite-" + fill.leader_fill_id, LEADER, "BTC",
                            "SELL", 100.0, 1.0, c.utc_now_ms() + 2000, "TEST", 0, {})

    # Scenario 1: actual refusal -> one GTC -> no duplication on same-fill retry.
    fake, g = new_scenario(9001)
    it = entry()
    first = rest(g, it)
    owned = matching(g, it.fill.leader_fill_id)
    disk = persisted(it.fill.leader_fill_id)
    check("GTC_REFUSED_ENTRY_RESTED_WITH_REAL_PHYSICAL_ORDER",
          first.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED"
          and first.get("order_type") == "REAL_GTC" and len(fake.calls) == 1
          and fake.calls[0]["tif"] == "Gtc" and not fake.calls[0]["reduce_only"],
          "first=%r calls=%r" % (first, fake.calls))
    check("GTC_EXACT_ONE_PENDING_LEDGER_ROW_KEYED_LEADER_FILL",
          len(owned) == len(disk) == 1
          and owned[0].get("oid") == fake.calls[0]["oid"]
          and disk[0].get("leader_fill_id") == it.fill.leader_fill_id
          and disk[0].get("intent_id") == it.intent_id,
          "owned=%r persisted=%r" % (owned, disk))
    matching_attempts = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
                         if r.get("leader_fill_id") == it.fill.leader_fill_id]
    check("GTC_DURABLE_PENDING_SEND_REVISED_TO_RESTING_OID",
          len(matching_attempts) == 2
          and matching_attempts[0].get("status") == "pending_send"
          and matching_attempts[-1].get("status") == "ORDER_RESTING"
          and matching_attempts[-1].get("exchange_order_id") == fake.calls[0]["oid"]
          and matching_attempts[0].get("attempt_id") == matching_attempts[-1].get("attempt_id")
          and matching_attempts[0].get("cloid") == matching_attempts[-1].get("cloid"),
          "attempts=%r" % matching_attempts)
    again = rest(g, it)
    check("GTC_RETRY_NEVER_DUPLICATES_PHYSICAL_OR_LEDGER",
          again.get("outcome") == "MISSED_ENTRY_ALREADY_RESTING"
          and len(fake.calls) == 1 and len(matching(g, it.fill.leader_fill_id)) == 1
          and len(persisted(it.fill.leader_fill_id)) == 1,
          "again=%r calls=%r rows=%r" %
          (again, fake.calls, matching(g, it.fill.leader_fill_id)))

    # Scenario 2: exchange refuses / cannot prove cancel. Hold a pending
    # owned order even when the next leader-fill retry arrives.
    fake, g = new_scenario(9101)
    it = entry()
    rest(g, it)
    withdrawn = g.cancel_resting_entries_against(opp(it.fill))
    check("GTC_UNCONFIRMED_CANCEL_RETAINS_ONE_OWED_LEDGER_ROW",
          len(fake.cancel_calls) == 1 and not withdrawn
          and len(matching(g, it.fill.leader_fill_id)) == 1
          and bool(matching(g, it.fill.leader_fill_id)[0].get("withdraw_pending")),
          "cancel_calls=%r pending=%r" % (fake.cancel_calls, matching(g, it.fill.leader_fill_id)))
    pre_calls = len(fake.calls)
    after_unknown_cancel = rest(g, it)
    check("GTC_UNCONFIRMED_CANCEL_MUST_NOT_RETRY_SECOND_GTC",
          len(fake.calls) == pre_calls
          and len(matching(g, it.fill.leader_fill_id)) == 1
          and len(persisted(it.fill.leader_fill_id)) == 1,
          "result=%r physical_calls=%r rows=%r" %
          (after_unknown_cancel, fake.calls, matching(g, it.fill.leader_fill_id)))

    # Scenario 3: confirmed cancellation must retire ONLY its owned OID.
    fake, g = new_scenario(9201)
    it = entry()
    rest(g, it)
    fake.cancel_replies = [{"status": "ok", "response": {"data": {
        "statuses": ["success"]}}}]
    removed = g.cancel_resting_entries_against(opp(it.fill))
    check("GTC_CONFIRMED_CANCEL_CLEARS_PENDING_LEDGER",
          len(removed) == 1 and removed[0].get("withdraw_outcome") ==
          "RESTING_ENTRY_CANCELLED_LEADER_REDUCED"
          and not matching(g, it.fill.leader_fill_id)
          and not persisted(it.fill.leader_fill_id),
          "removed=%r live=%r" % (removed, g.resting_entries()))

    # Scenario 4: exchange explicitly confirms already filled on cancel.
    fake, g = new_scenario(9301)
    it = entry()
    rest(g, it)
    fake.cancel_replies = [{"status": "err", "response": {"data": {
        "statuses": [{"error": "order already filled"}]}}}]
    removed = g.cancel_resting_entries_against(opp(it.fill))
    check("GTC_EXCHANGE_CONFIRMED_FILLED_CLEARS_PENDING_LEDGER",
          len(removed) == 1 and removed[0].get("withdraw_outcome") ==
          "RESTING_ENTRY_ALREADY_GONE" and not matching(g, it.fill.leader_fill_id)
          and not persisted(it.fill.leader_fill_id), "removed=%r" % removed)

    # Scenario 5: an open-orders snapshot that omits an OID is NOT a filled/
    # cancelled confirmation. Missing snapshot data must not make the GTC
    # eligible for another physical send. Source may currently violate this.
    fake, g = new_scenario(9401)
    it = entry()
    rest(g, it)
    with g._resting_lock:
        for row in g._resting_entries.values():
            row["placed_ms"] = c.utc_now_ms() - 15000
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, dict(g._resting_entries))
    original_periodic = c.periodic_open_orders
    c.periodic_open_orders = lambda dexes: [{"ok": True, "data": []} for _ in dexes]
    try:
        g.refresh_resting_open_sizes()
    finally:
        c.periodic_open_orders = original_periodic
    check("GTC_UNPROVEN_OID_DISAPPEARANCE_MUST_RETAIN_PENDING",
          len(matching(g, it.fill.leader_fill_id)) == 1
          and len(persisted(it.fill.leader_fill_id)) == 1
          and g.resting_entry_for(LEADER, "BTC", "BUY") is not None,
          "snapshot omitted OID; active=%r persisted=%r" %
          (g.resting_entry_for(LEADER, "BTC", "BUY"), persisted(it.fill.leader_fill_id)))
    before = len(fake.calls)
    rest(g, it)
    check("GTC_UNPROVEN_DISAPPEARANCE_MUST_NOT_DUPLICATE_WIRE",
          len(fake.calls) == before
          and len(matching(g, it.fill.leader_fill_id)) == 1,
          "before=%d after=%d rows=%r" % (before, len(fake.calls), matching(g, it.fill.leader_fill_id)))

    failed = [name for name, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)), flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
