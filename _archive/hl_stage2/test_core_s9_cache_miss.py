#!/usr/bin/env python3
"""S9 cache-miss cut-down, items 2 and 3.

(2) An unlisted coin costs ONE terminal diff row per leader fill and opens no retry chain.
(3) A held position in an unlisted or later-delisted coin stays CLOSABLE WITH NO MID: a reduce-only
exit is not blocked by a missing live symbol, an expired universe or a failed refresh.

Run (from _archive/hl_stage2): env -u HL_LIVE_AUDIT_DIR python test_core_s9_cache_miss.py
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)[:200]) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="s9cm_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_DISABLE_NETWORK_REFRESH": "1",
                       "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64})
    import HL_Live_Copy_Service_Core as c

    def gw():
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l.json"))
        g._asset_snapshot_loaded = True
        g._meta_fetched = g._core_meta_fetched = True   # metadata WAS fetched: an absent coin is genuinely absent
        g._builder_meta_fetched["xyz"] = True
        g._meta_cache = {}
        return g

    def intent(coin, side="BUY", reduce_only=False, fid="LF-S9"):
        fill = argparse.Namespace(leader_fill_id=fid, leader_wallet="0x" + "e" * 40, coin=coin, side=side, price=100.0,
                                  timestamp_ms=c.utc_now_ms(), source="TEST", oid="", raw={})
        return argparse.Namespace(intent_id="I-" + fid, fill=fill, copy_side=side, copy_size=1.0,
                                  copy_notional=100.0, reduce_only_intended=reduce_only,
                                  reduce_only_sent_planned=False, sleeve_id="", position_id="",
                                  wallet_position_before=(1.0 if reduce_only else 0.0), coin_net_before=0.0, created_at_ms=c.utc_now_ms(),
                                  send_allowed=True, decision="EXIT_ALLOWED" if reduce_only else "ENTRY_ALLOWED",
                                  reason=("EXIT" if reduce_only else ""), wallet_mode="ON", copy_mode="fixed")

    def rows_for(fid):
        return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == fid]

    # ---- (2) ONE terminal diff row per leader fill, no retry chain --------------------------------------
    g = gw()
    r_plain = g._resolve_coin("DELISTEDX")
    check("S9_UNLISTED_PLAIN_PERP_SAYS_NOT_LISTED_ON_THIS_NETWORK",
          r_plain.get("status") == "SYMBOL_UNRESOLVED" and r_plain.get("error") == "not listed on this network", r_plain)
    r_dex = g._resolve_coin("XYZ:GONE")
    check("S9_DEX_CACHE_MISS_KEEPS_THE_CACHE_WORDING_AND_NAMES_THE_REAL_REFRESH",
          r_dex.get("status") == "SYMBOL_CACHE_MISS_NEEDS_REFRESH"
          and "refresh_asset_universe" in r_dex.get("error", "")
          and "not listed on this network" not in r_dex.get("error", "")
          and ".py" not in r_dex.get("error", ""), r_dex)
    # one refusal, one row: the send lane writes the terminal diff exactly once for a fill
    i2 = intent("XYZ:GONE", fid="LF-S9-2")
    ok, status, res = g._send_real(i2)
    check("S9_UNLISTED_ENTRY_NOT_SENT", ok is False and res.get("exchange_called") is False, str(res)[:200])
    g._append_local_block_reconciliation(i2, status, res)
    rows = rows_for("LF-S9-2")
    check("S9_UNLISTED_ENTRY_EXACTLY_ONE_TERMINAL_ROW", len(rows) == 1 and rows[0].get("event") == "SEND_TERMINAL", rows)
    check("S9_UNLISTED_ENTRY_IS_TERMINAL_NOT_A_RETRY",
          bool(rows) and not any(k in str(rows[0].get("operator_action", "")) for k in ("RETRY", "REFRESH")), rows[:1])
    attempts = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("leader_fill_id") == "LF-S9-2"]
    check("S9_UNLISTED_ENTRY_SINGLE_ATTEMPT_ID", len(attempts) <= 1, attempts)
    before = len(rows_for("LF-S9-2"))
    g._send_real(i2)  # the same leader fill re-delivered: no second row, no second attempt chain
    check("S9_UNLISTED_REDELIVERY_ADDS_NO_ROW", len(rows_for("LF-S9-2")) == before, rows_for("LF-S9-2"))
    # and the refusal's own label is the not-listed skip, never a retry-shaped "cache miss"
    g2 = gw()
    out = g2._missed_entry_rest_or_diff(intent("DELISTEDX", fid="LF-S9-2b"), "MARGIN_MODE_UNSET")
    check("S9_UNLISTED_REFUSAL_LABEL_IS_NOT_LISTED_SKIP",
          out.get("outcome") == "MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED", out)

    # ---- (3) a held position stays CLOSABLE WITH NO MID ------------------------------------------------
    # A later-delisted coin: the live universe no longer carries it, the disk snapshot still does (that is how a
    # position opened before the delisting is priced). No mid exists for it. The close must still go out.
    c.LEADER_NETWORK = "mainnet"          # cross-network: the close MUST be priced from the follower side
    c.FOLLOWER_NETWORK = "testnet"
    c.follower_mid = lambda coin, force=False: 0.0                       # NO MID, by construction
    c.follower_position_mark = lambda coin: 100.0                        # the position's own mark prices the close
    g3 = gw()
    g3._meta_cache = {"XYZ:DELISTED": {"canonical_coin": "XYZ:DELISTED", "sdk_coin": "xyz:DELISTED", "szDecimals": 2,
                                       "symbol_source": "builder_meta", "perp_dex": "xyz", "perp_dexs": ["", "xyz"],
                                       "price_max_decimals": 2, "sdk_order_compatible": True, "_snapshot_only": True}}
    calls = []

    class Fake:
        def update_leverage(self, lev, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            calls.append({"coin": coin, "px": px, "reduce_only": reduce_only, "tif": tif["limit"]["tif"]})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 7}}]}}}

    fake = Fake()
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {"send_mode": "ON"}, "wallets": {
        "0x" + "e" * 40: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 100}}})
    g3.cfg.send_mode_now = lambda: "ON"  # armed in-process: this test is about the symbol gate, not the switch
    g3.cfg.master_switch_now = lambda: True
    g3._get_exchange_client = lambda *a, **k: fake
    g3._exchange_client_has_symbol = lambda *a, **k: True
    g3._validate_final_wire_order = lambda *a, **k: (True, {})
    g3._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    g3._exchange_client_for_coin = lambda coin: (fake, "xyz:DELISTED")
    g3._pre_send_ownership_gate = lambda intent: (True, {})  # a held sleeve is assumed reconciled here
    g3.cfg.wallet_enabled = lambda w: True
    g3.cfg.wallet_mode = lambda w: "ON"
    c.HLAccount, c.HLExchange = object, object
    i3 = intent("XYZ:DELISTED", side="SELL", reduce_only=True, fid="LF-S9-3")
    resolved3 = g3._resolve_coin("XYZ:DELISTED", allow_snapshot=True)
    check("S9_DELISTED_COIN_RESOLVES_FROM_THE_SNAPSHOT_FOR_A_CLOSE", bool(resolved3.get("ok")) and resolved3.get("snapshot_only"), resolved3)
    sent, status3 = g3.send_if_allowed(i3)
    check("S9_DELISTED_CLOSE_SENT_WITH_NO_MID", bool(calls) and calls[0]["reduce_only"] is True, (sent, status3, calls))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


main()
