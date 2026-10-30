#!/usr/bin/env python3
"""CC-1 R36 item (d): real coverage for GUT regressions R16 and R21.

R16 - a mutable global_state/config hash creates NO operational veto.
  WHAT READS THE HASH (established before the assertion):
    * Core has no config digest at all. ConfigManager loads live_config.json at construction and hot
      re-reads it by st_mtime_ns (send_mode_now, min_24h_notional_usd); both compare CONTENT
      (send_mode / min_24h_notional_usd), never a hash.
    * the only config-hash producers in the repo are ops/seed_pair_state.py, which RECORDS
      config_sha_before/after in a change log for the operator, and ops/start_pair.py --expect-sha,
      an explicit operator-pinned COMMIT sha. Neither gates a send.
  So the invariant pinned here: a byte edit that changes the config's sha256 (and mtime) but no
  operational key must leave the send decision unchanged; and every refusal that does occur must
  name a real cause (mode, ownership, key, data), never a hash.

R21 - a delayed entry must never execute at worse than the leader reference.
  Rule under test: missed_entry_decision. Inside the tolerance -> IOC now; beyond it -> no chase, a
  GTC rests at the leader reference. TOLERANCE = marketable_bps = DEFAULT_SLIPPAGE_BPS = 20 bps
  (Boss's default 0.2 %). Justification: 20 bps is the engine's own shipped allowance, so the test
  pins shipped behaviour instead of a number the test invents; the bound is leader_ref +/- 20 bps and
  beyond tolerance no order may be priced at the market at all (0 % would forbid the configured
  slippage the engine deliberately applies).

Run: C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe test_core_c7_gaps_r16_r21.py
Offline: no network, no orders.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
TOL_BPS = 20.0
EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
RESOLVED = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
            "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
# every reason _master_gate_reason can return; a hash/config veto is not in this set
REAL_CAUSES = {"", "MISSING_INTENT_CONTEXT", "MASTER_REAL_ORDERS_OFF", "SEND_BLOCKED_SENDER_KEY_NOT_VALID",
               "WALLET_DISABLED_AT_SEND", "WALLET_OFF", "CLO_BLOCKS_ENTRY", "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY"}


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s %s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)[:220]) if not cond else ""))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


BASE_CFG = {
    "auto_send_enabled": True,
    "global_controls": {"marketable_bps": TOL_BPS, "send_mode": "ON"},
    "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}},
}


def main():
    tmp = Path(tempfile.mkdtemp(prefix="c7gaps_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
                       "HL_LIVE_MM_WAIT_SEC": "2"})
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
    c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
    c.LEADER_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
    cfg_path = Path(c.LIVE_CONFIG_FILE)
    c.atomic_write_json(cfg_path, dict(BASE_CFG, notes="alpha"))

    seq = [0]

    def set_mids(follower=None, leader=None):
        if follower is not None:
            mids["follower"] = follower
        if leader is not None:
            mids["leader"] = leader
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0, dexes=[])

    def fill(price=100.0, side="BUY", age_ms=0):
        seq[0] += 1
        return c.LeaderFill("r%d" % seq[0], LEADER, "BTC", side, price, 1.0,
                            c.utc_now_ms() - int(age_ms) + seq[0], "TEST", 0, {})

    class FakeExchange:
        def __init__(self):
            self.calls, self.cancels = [], []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9000 + len(self.calls)}}]}}}

        def cancel(self, coin, oid):
            self.cancels.append((coin, oid))
            return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}

    def gateway(fake, cfg=None):
        gw = c.SenderGateway(cfg or c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin, allow_snapshot=False: dict(RESOLVED)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        gw._pre_send_ownership_gate = lambda intent: (True, {})
        return gw

    def intent(f=None):
        return c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / ("led%d.json" % seq[0]))).build(f or fill())

    def clear():
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})

    # ================= R16: a config hash creates NO operational veto =================

    # (a) two configs whose bytes differ (different sha256) but whose operational keys are identical:
    #     the gate must not be able to tell them apart.
    p_a, p_b = tmp / "cfg_a.json", tmp / "cfg_b.json"
    c.atomic_write_json(p_a, dict(BASE_CFG, notes="alpha", extra_blob="x" * 40))
    c.atomic_write_json(p_b, dict(BASE_CFG, notes="beta", extra_blob="y" * 40))
    sha_a, sha_b = sha(p_a), sha(p_b)
    cm_a, cm_b = c.ConfigManager(p_a), c.ConfigManager(p_b)
    reason_a = gateway(FakeExchange(), cm_a)._master_gate_reason(intent(fill()), "r16")
    reason_b = gateway(FakeExchange(), cm_b)._master_gate_reason(intent(fill()), "r16")
    check("R16_DIFFERENT_CONFIG_BYTES_HAVE_DIFFERENT_SHA", sha_a != sha_b and len(sha_a) == 64, "%s %s" % (sha_a[:12], sha_b[:12]))
    check("R16_HARMLESS_CONFIG_EDIT_DOES_NOT_REFUSE", reason_a == "" and reason_b == "", "a=%r b=%r" % (reason_a, reason_b))
    check("R16_HARMLESS_EDIT_LEAVES_OPERATIONAL_KEYS_EQUAL",
          (cm_a.send_mode, cm_a.marketable_bps(), cm_a.wallet_mode(LEADER), cm_a.wallet_enabled(LEADER))
          == (cm_b.send_mode, cm_b.marketable_bps(), cm_b.wallet_mode(LEADER), cm_b.wallet_enabled(LEADER))
          == ("ON", TOL_BPS, "ON", True),
          "%r %r" % ((cm_a.send_mode, cm_a.marketable_bps()), (cm_b.send_mode, cm_b.marketable_bps())))

    # (b) the live shape of "mutable global_state": the file changes UNDER a running ConfigManager.
    #     Only bytes/notes/mtime change, so send_mode_now() must still allow.
    p_live = tmp / "cfg_live.json"
    c.atomic_write_json(p_live, dict(BASE_CFG, notes="before"))
    cm_live = c.ConfigManager(p_live)
    before_sha = sha(p_live)
    c.atomic_write_json(p_live, dict(BASE_CFG, notes="after", touched=str(c.utc_now_ms())))
    os.utime(p_live, None)
    after_sha = sha(p_live)
    live_reason = gateway(FakeExchange(), cm_live)._master_gate_reason(intent(fill()), "r16:hot")
    check("R16_HOT_CONFIG_BYTE_CHANGE_IS_A_NEW_HASH", before_sha != after_sha, "%s %s" % (before_sha[:12], after_sha[:12]))
    check("R16_HOT_CONFIG_BYTE_CHANGE_DOES_NOT_REFUSE", live_reason == "" and cm_live.send_mode_now() == "ON",
          "reason=%r mode=%r" % (live_reason, cm_live.send_mode_now()))

    # (c) a refusal that IS produced must name a real cause, never the hash.
    named = {}
    c.atomic_write_json(p_live, dict(BASE_CFG, global_controls={"marketable_bps": TOL_BPS, "send_mode": "OFF"}))
    os.utime(p_live, None)
    named["send_mode_off"] = gateway(FakeExchange(), c.ConfigManager(p_live))._master_gate_reason(intent(fill()), "r16:off")
    c.atomic_write_json(p_live, dict(BASE_CFG, wallets={LEADER: {"enabled": True, "mode": "OFF"}}))
    os.utime(p_live, None)
    named["wallet_off"] = gateway(FakeExchange(), c.ConfigManager(p_live))._master_gate_reason(intent(fill()), "r16:woff")
    c.atomic_write_json(p_live, dict(BASE_CFG, wallets={LEADER: {"enabled": True, "mode": "CLO"}}))
    os.utime(p_live, None)
    named["wallet_clo"] = gateway(FakeExchange(), c.ConfigManager(p_live))._master_gate_reason(intent(fill()), "r16:clo")
    named["no_intent"] = gateway(FakeExchange(), cm_a)._master_gate_reason(None, "r16:none")
    gw_key = gateway(FakeExchange(), cm_a)
    gw_key.sender_key_invalid = "signer unknown"
    named["sender_key"] = gw_key._master_gate_reason(intent(fill()), "r16:key")
    bad = {k: v for k, v in named.items() if v not in REAL_CAUSES}
    check("R16_EVERY_REFUSAL_NAMES_A_REAL_CAUSE", not bad, "unexpected=%r all=%r" % (bad, named))
    check("R16_NO_REFUSAL_MENTIONS_THE_HASH",
          all(("hash" not in str(v).lower()) and ("sha" not in str(v).lower()) for v in named.values()), repr(named))
    check("R16_MODE_OFF_REFUSAL_NAMES_THE_MODE", named["send_mode_off"] == "MASTER_REAL_ORDERS_OFF", repr(named["send_mode_off"]))

    # (d) the physical send path must not consult a hash either: changed hash + mode ON -> the order goes.
    c.atomic_write_json(p_live, dict(BASE_CFG, notes="still_on", marker=str(c.utc_now_ms())))
    os.utime(p_live, None)
    clear()
    set_mids(100.0, 100.0)
    fake_ok = FakeExchange()
    o_ok = gateway(fake_ok, c.ConfigManager(p_live))._missed_entry_rest_or_diff(intent(fill()), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R16_CHANGED_HASH_DOES_NOT_BLOCK_THE_PHYSICAL_SEND",
          len(fake_ok.calls) == 1 and o_ok.get("outcome") in {"FILLED_AWAITING_COPY_POLL", "MISSED_ENTRY_LIMIT_RESTED"},
          "%s %s" % (o_ok.get("outcome"), fake_ok.calls))

    # (e) static: nothing in Core derives a send veto from a config/global_state digest.
    offenders = []
    for n, line in enumerate(Path(c.__file__).read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        low = line.lower()
        if "config" not in low and "global_state" not in low:
            continue
        if any(k in low for k in ("hexdigest", "sha256", "md5", "config_sha", "state_hash")):
            offenders.append((n, line.strip()[:120]))
    check("R16_CORE_HAS_NO_CONFIG_HASH_VETO", not offenders, repr(offenders[:3]))

    # ================= R21: a delayed entry is never worse than the leader reference =================
    def buy_bound(ref):
        return ref * (1.0 + TOL_BPS / 10000.0)

    def sell_bound(ref):
        return ref * (1.0 - TOL_BPS / 10000.0)

    # (a) BUY, market moved 500 bps against the follower between leader time and execution.
    clear()
    set_mids(105.0, 105.0)
    f_bad = FakeExchange()
    o_bad = gateway(f_bad)._missed_entry_rest_or_diff(intent(fill(price=100.0, side="BUY")), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R21_BUY_BEYOND_TOLERANCE_DOES_NOT_TAKE",
          not o_bad.get("take") and abs(float(o_bad.get("adverse_bps") or 0) - 500.0) < 1.0,
          "take=%r adverse=%r" % (o_bad.get("take"), o_bad.get("adverse_bps")))
    check("R21_BUY_BEYOND_TOLERANCE_NEVER_FILLS_WORSE_THAN_LEADER_REF",
          bool(f_bad.calls) and all(call["tif"] == "Gtc" and call["px"] <= 100.0 + 1e-9 for call in f_bad.calls),
          str(f_bad.calls))

    # (b) SELL, market moved 500 bps against the follower.
    clear()
    set_mids(95.0, 95.0)
    f_sell = FakeExchange()
    o_sell = gateway(f_sell)._missed_entry_rest_or_diff(intent(fill(price=100.0, side="SELL")), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R21_SELL_BEYOND_TOLERANCE_NEVER_FILLS_WORSE_THAN_LEADER_REF",
          not o_sell.get("take") and bool(f_sell.calls)
          and all(call["tif"] == "Gtc" and call["px"] >= 100.0 - 1e-9 for call in f_sell.calls),
          "%r %s" % (o_sell.get("take"), f_sell.calls))

    # (c) BUY inside the tolerance: it may take, but never above leader_ref + tolerance.
    clear()
    set_mids(100.15, 100.15)
    f_in = FakeExchange()
    o_in = gateway(f_in)._missed_entry_rest_or_diff(intent(fill(price=100.0, side="BUY")), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R21_BUY_WITHIN_TOLERANCE_TAKES", bool(o_in.get("take")) and bool(f_in.calls) and f_in.calls[0]["tif"] == "Ioc",
          "take=%r %s" % (o_in.get("take"), f_in.calls))
    check("R21_BUY_WITHIN_TOLERANCE_WIRE_PRICE_BOUNDED",
          bool(f_in.calls) and f_in.calls[0]["px"] <= buy_bound(100.0) + 1e-9,
          "px=%r bound=%r" % (f_in.calls[0]["px"] if f_in.calls else None, buy_bound(100.0)))

    # (d) SELL inside the tolerance: never below leader_ref - tolerance.
    clear()
    set_mids(99.85, 99.85)
    f_sin = FakeExchange()
    o_sin = gateway(f_sin)._missed_entry_rest_or_diff(intent(fill(price=100.0, side="SELL")), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R21_SELL_WITHIN_TOLERANCE_WIRE_PRICE_BOUNDED",
          bool(o_sin.get("take")) and bool(f_sin.calls) and f_sin.calls[0]["tif"] == "Ioc"
          and f_sin.calls[0]["px"] >= sell_bound(100.0) - 1e-9,
          "take=%r %s bound=%r" % (o_sin.get("take"), f_sin.calls, sell_bound(100.0)))

    # (e) decision function over a sweep of adverse moves: take iff within tolerance, cap always bounded.
    worst_cap, cap_bad, take_bad = 0.0, [], []
    for adv in (0, 5, 10, 19, 20, 21, 50, 200, 1000, 5000):
        px_mkt = 100.0 * (1.0 + adv / 10000.0)
        d = c.missed_entry_decision("BUY", 100.0, px_mkt, px_mkt, TOL_BPS)
        if bool(d.get("take")) != (adv <= TOL_BPS):
            take_bad.append((adv, d.get("take")))
        if float(d.get("cap_px") or 0) > buy_bound(100.0) + 1e-6:
            cap_bad.append((adv, d.get("cap_px")))
        worst_cap = max(worst_cap, float(d.get("cap_px") or 0))
    check("R21_DECISION_TAKES_ONLY_WITHIN_TOLERANCE", not take_bad, repr(take_bad))
    check("R21_DECISION_CAP_NEVER_ABOVE_LEADER_REF_PLUS_TOL",
          not cap_bad and worst_cap <= buy_bound(100.0) + 1e-6, "cap_bad=%r worst=%r" % (cap_bad[:3], worst_cap))

    # (f) cross-network: the reference is the CONVERTED leader price. A follower book 10 % above the
    #     leader's, with the leader's own market unmoved, is the same relative price: 0 bps adverse.
    clear()
    set_mids(110.0, 100.0)
    f_x = FakeExchange()
    o_x = gateway(f_x)._missed_entry_rest_or_diff(intent(fill(price=100.0, side="BUY")), "FOLLOWER_PRICE_FRESHNESS_GATE")
    ref_x = 110.0 * 100.0 / 100.0
    check("R21_CROSS_NETWORK_MEASURES_AGAINST_CONVERTED_REFERENCE",
          abs(float(o_x.get("adverse_bps") or 0)) < 1e-6 and bool(o_x.get("take")),
          "adverse=%r take=%r" % (o_x.get("adverse_bps"), o_x.get("take")))
    check("R21_CROSS_NETWORK_WIRE_PRICE_BOUNDED_BY_CONVERTED_REFERENCE",
          bool(f_x.calls) and f_x.calls[0]["px"] <= buy_bound(ref_x) + 1e-9,
          "px=%r bound=%r" % (f_x.calls[0]["px"] if f_x.calls else None, buy_bound(ref_x)))

    passed = sum(1 for _n, ok in RESULTS if ok)
    failed = len(RESULTS) - passed
    print("\nTOTAL=%d FAILED=%d" % (len(RESULTS), failed))
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
