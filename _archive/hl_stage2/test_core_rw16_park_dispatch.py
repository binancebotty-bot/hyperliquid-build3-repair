#!/usr/bin/env python3
"""rw16 rev 4: the park measured through the REAL dispatch path (Codex's three findings on rev 3).

D1 CLOSE SAFETY (blocker): with BTC parked, a raw leader 'Increase Long' whose side OFFSETS the position we hold is
   our EXIT (ManualLedger.classify_leader_side_for_wallet). It must still pass _dispatch_fill, be queued, and reach
   the exchange seam reduce-only: the park gates ENTRY/ADD only, never a close.
D2 RE-ARM: an expired park re-parks while qualifying rejects continue (streak 4 with park_after 3 parks again).
D3 CONSECUTIVE: a different reject category breaks the streak, so two qualifying rejects after it do not park.
D4 NON-QUALIFYING SEND: a send refused before the exchange call is not a qualifying reject either.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw16_park_dispatch.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders: every send goes to a fake exchange seam.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rw16_disp_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_WS_ENABLED": "0", "HL_LIVE_PREWARM_SYMBOL_META": "0",
                       "HL_LIVE_PREWARM_SDK_CLIENT": "0", "HL_LIVE_EARLY_PREWARM": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_HOT_SEND_WORKERS": "2",
                       "HL_LIVE_LIQ_PARITY": "0"})
    for _k in ("HL_LIVE_ILLIQUID_PARK_AFTER", "HL_LIVE_ILLIQUID_PARK_MS", "HL_LIVE_MOCK_SEND",
               "HL_LIVE_ENTRY_IOC_RETRY_BPS", "HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS"):
        os.environ.pop(_k, None)
    os.environ.update({"HL_LIVE_ENTRY_IOC_RETRY_BPS": "0", "HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS": "0"})  # one order per fill
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100", "SOL": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
    c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
    c.LEADER_FETCHER = c.EXPOSURE_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    FILLED = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": "1.0", "avgPx": "100.0", "oid": 3}}]}}}
    NOMATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"error": "Order could not immediately match against any resting orders. asset=750035"}]}}}
    RONLY = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"error": "Reduce only order would increase position."}]}}}

    class Ex:
        def __init__(self):
            self.by_coin, self.calls = {}, []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "buy": is_buy, "size": size, "reduce_only": reduce_only})
            return self.by_coin.get(str(coin).upper(), FILLED)

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core.async_dispatch = False

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    g = core.sender
    ex = Ex()
    g._resolve_coin = lambda coin: dict(resolved, sdk_coin=coin)
    g._get_exchange_client = lambda *a, **k: ex
    g._exchange_client_has_symbol = lambda *a, **k: True
    g._validate_final_wire_order = lambda *a, **k: (True, {})
    g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    g._exchange_client_for_coin = lambda coin: (ex, coin)
    g._pre_send_ownership_gate = lambda it: (True, {})
    g.leader_reduced_since = lambda f: 0
    g._margin_mode_done = {"BTC", "ETH", "SOL"}
    g.cfg.master_switch_now = lambda: True
    g.cfg.liq_parity_enabled = lambda: False
    g._fresh_exchange_net = lambda coin: None  # seam: the follower's exchange position, per scenario below
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    seq = [0]

    def fill(coin="BTC", side="BUY", direction="Open Long"):
        seq[0] += 1
        return c.LeaderFill("d%d" % seq[0], A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST", 0,
                            {"oid": str(seq[0]), "dir": direction})

    def run_through_dispatch(f):
        """The live path: _dispatch_fill gate -> lane queue -> worker -> send. (dispatch_result, status, calls)."""
        before = len(ex.calls)
        queued = core._dispatch_fill(f)
        if queued is not True:
            return queued, "", len(ex.calls) - before
        taken = []
        for q in core._hot_queues + core._prio_queues:
            while not q.empty():
                taken.append(q.get_nowait())
        assert len(taken) == 1, taken
        _ok, status, _it = core._process_leader_fill(taken[0], None, "")
        return queued, status, len(ex.calls) - before

    def park_rows(coin):
        p = c.RECONCILIATION_CSV
        if not p.exists():
            return []
        with p.open("r", newline="", encoding="utf-8-sig") as fh:
            return [r for r in csv.DictReader(fh)
                    if r.get("terminal_state") == "SKIPPED_ILLIQUID" and str(r.get("coin") or "").lower() == coin]

    def hold(coin, size):
        core.ledger.sleeve(A, coin)["signed_size"] = size
        core.ledger._recompute_net(core.ledger.data)

    # ---- D1 (BLOCKER): a parked coin never drops a leader increase that is our EXIT ----------------------------
    hold("BTC", -1.0)  # we hold SHORT BTC for this leader, so a leader BUY increase is our EXIT
    g._fresh_exchange_net = lambda coin: -1.0 if c.canonical_coin_key(coin) == "btc" else None
    lifecycle = core.ledger.classify_leader_side_for_wallet(A, "BTC", "BUY")[0]
    check("D1_LEADER_INCREASE_IS_OUR_EXIT", lifecycle == "EXIT", lifecycle)
    g._ioc_no_match_until_ms["btc"] = c.utc_now_ms() + 1800000  # BTC is parked right now
    queued, status, calls = run_through_dispatch(fill("BTC", "BUY", "Increase Long"))
    check("D1_PARKED_COIN_INCREASE_NOT_DROPPED_AT_DISPATCH", queued is True, str(queued))
    check("D1_PARKED_COIN_INCREASE_REACHES_EXCHANGE_AS_REDUCE_ONLY",
          status == "ORDER_FILLED" and calls == 1 and ex.calls[-1]["buy"] is True and ex.calls[-1]["reduce_only"] is True,
          "%s calls=%d %s" % (status, calls, ex.calls[-1:]))
    check("D1_NO_PARK_ROW_FOR_THE_CLOSE", not park_rows("btc"), str(park_rows("btc")))
    check("D1_ADD_ON_THE_PARKED_COIN_STILL_SKIPPED",
          core._dispatch_fill(fill("BTC", "SELL", "Open Short")) is None,
          "an ADD (SELL that grows our short) on the same parked coin must still be refused at dispatch")
    g._ioc_no_match_until_ms.pop("btc", None)
    hold("BTC", 0.0)
    g._fresh_exchange_net = lambda coin: None

    # ---- D2 (RE-ARM): streak 4 with park_after 3 parks again --------------------------------------------------
    os.environ["HL_LIVE_ILLIQUID_PARK_AFTER"] = "3"
    ex.by_coin["ETH"] = NOMATCH
    g._ioc_no_match_streak["eth"] = 3   # the first park has already expired
    g._ioc_no_match_until_ms["eth"] = 0
    before_rows = len(park_rows("eth"))
    queued, status, calls = run_through_dispatch(fill("ETH", "BUY", "Open Long"))
    left = g._ioc_no_match_until_ms.get("eth", 0) - c.utc_now_ms()
    check("D2_EXPIRED_PARK_REPARKS_ON_CONTINUING_REJECTS",
          status == "ORDER_REJECTED" and calls >= 1 and left > 1700000 and len(park_rows("eth")) == before_rows + 1,
          "status=%s calls=%d left=%d rows=%d" % (status, calls, left, len(park_rows("eth"))))
    check("D2_PARK_RESETS_THE_STREAK", g._ioc_no_match_streak.get("eth", 0) == 0, str(g._ioc_no_match_streak))
    g._ioc_no_match_until_ms.pop("eth", None)

    # ---- D3 (CONSECUTIVE): a different reject category breaks the streak --------------------------------------
    ex.by_coin["SOL"] = RONLY
    g._ioc_no_match_streak["sol"] = 2
    queued, status, calls = run_through_dispatch(fill("SOL", "BUY", "Open Long"))
    check("D3_OTHER_REJECT_IS_SENT_AND_BREAKS_STREAK",
          status == "ORDER_REJECTED" and calls == 1 and "sol" not in g._ioc_no_match_streak,
          "status=%s calls=%d streak=%s" % (status, calls, g._ioc_no_match_streak))
    ex.by_coin["SOL"] = NOMATCH
    sol_rows = len(park_rows("sol"))
    for _ in range(2):
        g._ioc_no_match_until_ms["sol"] = 0
        run_through_dispatch(fill("SOL", "BUY", "Open Long"))
    left_s = g._ioc_no_match_until_ms.get("sol", 0) - c.utc_now_ms()
    check("D3_TWO_QUALIFYING_REJECTS_AFTER_A_BREAK_DO_NOT_PARK",
          g._ioc_no_match_streak.get("sol") == 2 and len(park_rows("sol")) == sol_rows and 0 < left_s <= 15000,
          "streak=%s left=%d rows=%d" % (g._ioc_no_match_streak, left_s, len(park_rows("sol"))))
    g._ioc_no_match_until_ms.pop("sol", None)
    g._ioc_no_match_streak.pop("sol", None)

    # ---- D4 (NON-QUALIFYING SEND): refused before the exchange call, so it breaks the streak too --------------
    g._ioc_no_match_streak["eth"] = 2
    g.cfg.send_mode_now = lambda: "CLOSE"  # CLOSE-only refuses this ENTRY before any exchange call
    try:
        queued, status, calls = run_through_dispatch(fill("ETH", "BUY", "Open Long"))
    finally:
        g.cfg.send_mode_now = lambda: "FULL"
    check("D4_SEND_THAT_NEVER_REACHED_EXCHANGE_BREAKS_STREAK",
          queued is True and status == "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY" and calls == 0
          and "eth" not in g._ioc_no_match_streak,
          "status=%s calls=%d streak=%s" % (status, calls, g._ioc_no_match_streak))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
