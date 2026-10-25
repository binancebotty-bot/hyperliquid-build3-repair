#!/usr/bin/env python3
"""PART 2: closing the entry loss at refusal time, with no replay.

bf40a9d added gates that refuse an entry and then consume the fill: the follower-price freshness gate, the
margin-mode precondition, the snapshot-only metadata block and MARKET_HALTED. The fix runs the EXISTING
missed-entry rule once, at the point of refusal: a tradable symbol rests a GTC at the leader's price through
the existing REAL_GTC_MISSED_ENTRY_LIMIT path; otherwise a NAMED DIFF row (or a NAMED SKIP for an unlisted
symbol for MARGIN_MODE_UNSET) is written. No gate is weakened; nothing is retained or replayed.

R1 a halted reply through the REAL send_if_allowed, then the choke point rests a GTC at the leader's price.
R2 the freshness gate refusing through the REAL send_if_allowed (no follower price), then a GTC rests.
R3 snapshot-only metadata block: not tradable -> NAMED DIFF row.
R4 MARGIN_MODE_UNSET: unlisted symbol -> NAMED SKIP; transient setup failure on a tradable symbol -> GTC.
R5 direct tests for both added symbols.

Run: python test_core_deferred_entry_refusal.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
EXP_PAYLOAD = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="refusal_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    mids = {"follower": 100.0, "leader": 100.0}
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mids["follower"])} if mids["follower"] else {})
    c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mids["leader"])} if mids["leader"] else {})

    def set_mids(follower=None, leader=None):
        if follower is not None:
            mids["follower"] = follower
        if leader is not None:
            mids["leader"] = leader
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)

    # a clean, empty follower account (no unowned inventory) so intents build as ENTRY_ALLOWED offline
    c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD)
    c.LEADER_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD)
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed",
                                                                  "fixed_notional": 1000}}})
    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"r{seq[0]}", LEADER, "BTC", side, price, size, c.utc_now_ms() + seq[0], "TEST", 0, {})

    class FakeExchange:
        def __init__(self):
            self.calls, self.cancels = [], []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9000 + len(self.calls)}}]}}}

        def cancel(self, coin, oid):
            self.cancels.append((coin, oid))
            return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(fake):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin, allow_snapshot=False: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        gw._pre_send_ownership_gate = lambda intent: (True, {})
        return gw

    def clear_resting():
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})

    def build_intent(f=None):
        f = f or fill()
        return c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / f"led{seq[0]}.json")).build(f)

    def rows_for(state):
        return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == state]

    # ---- R1: a halted reply through the REAL send_if_allowed --------------------------------------
    clear_resting()
    set_mids(100.1, 100.0)
    fake = FakeExchange()
    gw = gateway(fake)
    intent = build_intent()
    gw._market_halted_until_ms["btc"] = c.utc_now_ms() + 600000
    halted_ok, halted_status = gw.send_if_allowed(intent)
    check("R1_HALTED_REPLY_THROUGH_REAL_SEND_IF_ALLOWED", not halted_ok and halted_status == "SKIPPED_MARKET_HALTED"
          and not fake.calls, f"{halted_ok} {halted_status} {fake.calls}")
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.sender._resolve_coin = lambda coin, allow_snapshot=False: dict(resolved)
    core.sender._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    core.sender._exchange_client_for_coin = lambda coin: (fake, "BTC")
    core.sender._market_halted_until_ms["btc"] = c.utc_now_ms() + 600000
    out = core._apply_missed_entry_rule_on_refusal(intent.fill, intent, halted_status)
    check("R1_HALTED_REFUSAL_RESTS_GTC_AT_LEADER_PRICE", out is not None
          and out.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED" and fake.calls
          and fake.calls[-1]["tif"] == "Gtc" and abs(fake.calls[-1]["px"] - 100.0) < 1e-9, f"{out} {fake.calls}")
    check("R1_HALTED_REFUSAL_WRITES_ITS_OWN_ROW", bool(rows_for("MISSED_ENTRY_LIMIT_RESTED")), str(rows_for("MISSED_ENTRY_LIMIT_RESTED"))[:300])

    # ---- R2: the freshness gate through the REAL send_if_allowed ----------------------------------
    clear_resting()
    set_mids(0, 100.0)
    fake2 = FakeExchange()
    gw2 = gateway(fake2)
    fresh_intent = build_intent()
    check("R2_FRESHNESS_GATE_REFUSES_THE_INTENT", fresh_intent.decision == "SEND_BLOCKED_RISK"
          and "no fresh follower-network" in fresh_intent.reason and not fresh_intent.send_allowed, fresh_intent.reason)
    fresh_ok, fresh_status = gw2.send_if_allowed(fresh_intent)
    check("R2_STALE_PRICE_REFUSAL_THROUGH_REAL_LANE", not fresh_ok and fresh_status == "INTENT_NOT_SEND_ALLOWED"
          and not fake2.calls, f"{fresh_ok} {fresh_status} {fake2.calls}")
    core2 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core2.sender._resolve_coin = lambda coin, allow_snapshot=False: dict(resolved)
    core2.sender._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    core2.sender._exchange_client_for_coin = lambda coin: (fake2, "BTC")
    out2 = core2._apply_missed_entry_rule_on_refusal(fresh_intent.fill, fresh_intent, fresh_status)
    check("R2_STALE_PRICE_REFUSAL_RESTS_GTC_AT_LEADER_PRICE", out2 is not None
          and out2.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED" and fake2.calls
          and fake2.calls[-1]["tif"] == "Gtc" and abs(fake2.calls[-1]["px"] - 100.0) < 1e-9, f"{out2} {fake2.calls}")
    check("R2_FRESHNESS_GATE_ITSELF_UNCHANGED", fresh_intent.decision == "SEND_BLOCKED_RISK")

    # ---- R3: snapshot-only metadata block -> NAMED DIFF -------------------------------------------
    clear_resting()
    fake3 = FakeExchange()
    gw3 = gateway(fake3)
    snapshot_res = {"ok": False, "raw_coin": "BTC", "status": "SYMBOL_CACHE_MISS_NEEDS_REFRESH", "snapshot_only": True,
                    "error": "BTC is only known from the disk asset snapshot; no valid authoritative meta fetch has landed",
                    "exchange_called": False}
    gw3._resolve_coin = lambda coin, allow_snapshot=False: dict(snapshot_res)
    snap_intent = build_intent()
    snap_ok, snap_status, snap_res = gw3._send_real(snap_intent)
    check("R3_SNAPSHOT_ONLY_BLOCK_REFUSES_THE_SEND", not snap_ok and snap_status == "SEND_NOT_ATTEMPTED_UNSUPPORTED_SYMBOL"
          and not fake3.calls, f"{snap_ok} {snap_status} {fake3.calls}")
    core3 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core3.sender._resolve_coin = lambda coin, allow_snapshot=False: dict(snapshot_res)
    snap_intent.reason = "BTC is only known from the disk asset snapshot"
    out3 = core3._apply_missed_entry_rule_on_refusal(snap_intent.fill, snap_intent, snap_status)
    check("R3_SNAPSHOT_ONLY_IS_A_NAMED_DIFF", out3 is not None and out3.get("outcome") == "MISSED_ENTRY_DIFF_NO_LIMIT_POSSIBLE"
          and out3.get("intent_id") == snap_intent.intent_id and out3.get("leader_fill_id") == snap_intent.fill.leader_fill_id
          and out3.get("wallet_alias") == c.normalise_wallet(LEADER) and not fake3.calls, f"{out3} {fake3.calls}")
    check("R3_NAMED_DIFF_ROW_WRITTEN", bool(rows_for("MISSED_ENTRY_DIFF_NO_LIMIT_POSSIBLE")), str(rows_for("MISSED_ENTRY_DIFF_NO_LIMIT_POSSIBLE"))[:300])

    # ---- R4: MARGIN_MODE_UNSET -------------------------------------------------------------------
    clear_resting()
    fake4 = FakeExchange()
    core4 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core4.sender._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    core4.sender._exchange_client_for_coin = lambda coin: (fake4, "BTC")
    core4.sender._resolve_coin = lambda coin, allow_snapshot=False: {
        "ok": False, "raw_coin": "WEIRD", "status": "SYMBOL_CACHE_MISS_NEEDS_REFRESH", "error": "not listed"}
    unlisted = c.Intent("i-unlisted", c.LeaderFill("rU", LEADER, "WEIRD", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {}),
                        "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY", "s1", "", "LONG", 0.0, 0.0, False, False,
                        c.utc_now_ms(), "")
    out4 = core4._apply_missed_entry_rule_on_refusal(unlisted.fill, unlisted, "MARGIN_MODE_UNSET")
    check("R4_MARGIN_MODE_UNSET_UNLISTED_IS_A_NAMED_SKIP", out4 is not None
          and out4.get("outcome") == "MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED" and not fake4.calls, f"{out4} {fake4.calls}")
    check("R4_NAMED_SKIP_ROW_WRITTEN", bool(rows_for("MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED")))
    clear_resting()
    core4.sender._resolve_coin = lambda coin, allow_snapshot=False: dict(resolved)
    transient = build_intent()
    out4b = core4._apply_missed_entry_rule_on_refusal(transient.fill, transient, "MARGIN_MODE_UNSET")
    check("R4_MARGIN_MODE_UNSET_TRANSIENT_RESTS_GTC", out4b is not None
          and out4b.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED" and fake4.calls
          and fake4.calls[-1]["tif"] == "Gtc" and abs(fake4.calls[-1]["px"] - 100.0) < 1e-9, f"{out4b} {fake4.calls}")

    # ---- R5: direct tests for the two added symbols ----------------------------------------------
    clear_resting()
    fake5 = FakeExchange()
    gw5 = gateway(fake5)
    direct = build_intent()
    out5 = gw5._missed_entry_rest_or_diff(direct, "MARGIN_MODE_UNSET")
    check("R5_SENDER_HELPER_RESTS_AND_REPORTS", out5.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED"
          and out5.get("order_type") == "REAL_GTC_MISSED_ENTRY_LIMIT" and fake5.calls[-1]["tif"] == "Gtc"
          and abs(fake5.calls[-1]["px"] - 100.0) < 1e-9, f"{out5} {fake5.calls}")
    check("R5_SENDER_HELPER_ONE_RESTING_LIMIT_PER_SIDE", gw5._missed_entry_rest_or_diff(direct, "MARGIN_MODE_UNSET")
          .get("outcome") == "MISSED_ENTRY_ALREADY_RESTING" and len(fake5.calls) == 1, str(fake5.calls))
    check("R5_CORE_HOOK_IGNORES_NON_ENTRY", core4._apply_missed_entry_rule_on_refusal(unlisted.fill, unlisted, "MASTER_REAL_ORDERS_OFF") is None)
    check("R5_CORE_HOOK_IGNORES_OTHER_STATUSES", core4._apply_missed_entry_rule_on_refusal(transient.fill, transient, "LIQ_PARITY_BLOCKED") is None)

    passed = sum(1 for _n, ok in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} passed")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
