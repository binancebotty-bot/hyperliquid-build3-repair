#!/usr/bin/env python3
# Sleeve convergence, trim half (missing half of ENG-INV-12 on round-3 5656832, ruling 6301015850 C).
# A leader that TRIMS (decreases, stays on the same side) must shrink the follower sleeve to the same ratio:
# one reduce-only close of exactly the remainder on the next cycle -- never an increase, never a flip, never more
# than the exchange net, never a sibling sleeve, never inventory the engine does not own. A remainder under the
# effective minimum (the same number the wire gate uses) sends NOTHING. Whole-close paths are unchanged.
# Offline only: no network, no orders, no keys. Run: python test_core_converge_trim.py
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)) if (detail and not ok) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="convergetrim_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
                       "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_CONVERGE_CONFIRM_SEC": "0", "HL_LIVE_CONVERGE_RETRY_SEC": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = "0x" + "c" * 40
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"ETH": "100", "BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    A = "0x" + "a" * 40
    B = "0x" + "b" * 40
    PX = 100.0
    pos = {A: {"ETH": 10.0}, B: {"ETH": 5.0}}

    def leader_fetcher(payload):
        if payload.get("type") != "clearinghouseState":
            raise RuntimeError("unreadable")
        user = payload.get("user")
        return {"marginSummary": {"accountValue": "1000"}, "assetPositions": [
            {"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * PX)}}
            for k, v in (pos.get(user) or {}).items() if abs(v) > 1e-12]}
    c.LEADER_FETCHER = leader_fetcher
    SYM_MIN = 10.0

    def make_core(tag, sleeves):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {'auto_send_enabled': True, 'global_controls': {}, 'wallets': {
            w: {'enabled': True, 'mode': 'ON', 'copy_mode': 'fixed', 'fixed_notional': 12} for w in (A, B)}})
        core = c.LiveCopyCore(source_csv=tmp / ('none_%s.csv' % tag))
        core.cfg.master_switch_now = lambda: True
        core.sender.sender_key_invalid = False
        core.sender._resolve_coin = lambda coin: {'ok': True, 'sdk_coin': str(coin), 'raw_coin': str(coin),
                                                  'sz_decimals': 3, 'min_order_value_usd': SYM_MIN}
        core.async_dispatch = False
        for (w, coin, size) in sleeves:
            s = core.ledger.sleeve(w, coin)
            s['signed_size'] = size
            s['position_id'] = '%s::%s::LONG::t' % (w, coin)
            s['avg_entry_px'] = PX
        core.ledger._recompute_net(core.ledger.data)
        sent = []
        core.sender.send_if_allowed = lambda intent, block='': sent.append(intent) or (False, 'TEST_NO_SEND')
        return core, sent

    def nrows():
        return len([r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get('event') == 'CONVERGE_CLOSE'])

    def rows_from(n0):
        return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get('event') == 'CONVERGE_CLOSE'][n0:]

    def trims(sent):
        return [i for i in sent if i.fill.source == 'CONVERGE']

    KEY = (c.normalise_wallet(A), 'ETH', '%s::ETH::LONG::t' % A)

    def minok(sz):
        return abs(sz * PX) >= SYM_MIN

    # leader trims 10 -> 4 with the sleeve at 10: one reduce-only close for exactly 6, next cycle
    core, sent = make_core("trim", [(A, "ETH", 10.0)])
    n0 = nrows()
    r1 = core.converge_once()
    check("TRIM_FIRST_SIGHT_ONLY_RECORDS", not sent and core._converge_lead_base.get(KEY) == (10.0, 10.0), (r1, core._converge_lead_base))
    pos[A]["ETH"] = 4.0
    r2 = core.converge_once()
    t = trims(sent)
    check("TRIM_SENDS_ONE_REDUCE_ONLY_ORDER_EXACTLY_THE_REMAINDER",
          len(t) == 1 and r2.get("queued") == 1 and t[0].copy_side == "SELL" and abs(t[0].copy_size - 6.0) < 1e-9
          and t[0].reduce_only_intended, (r2, [(i.copy_side, i.copy_size, i.reduce_only_intended) for i in t]))
    check("TRIM_IS_AN_EXIT_NEVER_AN_INCREASE_OR_FLIP", len(t) == 1 and "lifecycle=EXIT" in t[0].notes
          and t[0].copy_size <= 10.0 + 1e-12, t and t[0].notes)
    check("TRIM_IS_AUDITED_AS_A_TRIM", any(r.get("status") == "CONVERGE_TRIM_TO_TARGET_QUEUED" for r in rows_from(n0)),
          [r.get("status") for r in rows_from(n0)])
    core.sender._fresh_exchange_net = lambda coin: 5.0
    ro, size, skip = core.sender._close_wire_plan(t[0], t[0].copy_size, 3, minok)
    check("TRIM_WIRE_SIZE_NEVER_EXCEEDS_EXCHANGE_NET", not skip and ro and size <= 5.0 + 1e-12 and size < 6.0 - 1e-12, (ro, size, skip))
    core.stop()

    # a sibling leader sleeve in the same coin is untouched
    pos[A]["ETH"] = 10.0
    core, sent = make_core("sibling", [(A, "ETH", 10.0), (B, "ETH", 5.0)])
    core.converge_once()
    pos[A]["ETH"] = 4.0
    core.converge_once()
    t = trims(sent)
    check("TRIM_LEAVES_A_SIBLING_SLEEVE_UNTOUCHED",
          len(t) == 1 and t[0].fill.leader_wallet == c.normalise_wallet(A)
          and abs(core.ledger.sleeve(B, "ETH")["signed_size"] - 5.0) < 1e-12,
          [(i.fill.leader_wallet, i.copy_size) for i in t])
    core.stop()

    # inventory the engine does not own is untouched: the exchange holds 9.5, the sleeves only 6
    pos[A]["ETH"] = 10.0
    core, sent = make_core("unowned", [(A, "ETH", 6.0)])
    core.converge_once()
    pos[A]["ETH"] = 4.0
    core.converge_once()
    t = trims(sent)
    core.sender._fresh_exchange_net = lambda coin: 9.5
    ro, size, skip = core.sender._close_wire_plan(t[0], t[0].copy_size, 3, minok)
    check("TRIM_LEAVES_INVENTORY_THE_ENGINE_DOES_NOT_OWN_UNTOUCHED",
          len(t) == 1 and abs(t[0].copy_size - 3.6) < 1e-9 and not skip and size <= 3.6 + 1e-12
          and 9.5 - size >= 5.9 - 1e-9, (t and t[0].copy_size, ro, size, skip))
    core.stop()

    # remainder under the effective minimum sends nothing, using the same minimum the wire gate uses
    pos[A]["ETH"] = 10.0
    core, sent = make_core("dust", [(A, "ETH", 0.15)])
    eff = core._converge_effective_min("ETH")
    wire_min = core.sender._effective_symbol_min_notional({"ok": True, "min_order_value_usd": SYM_MIN})
    core.converge_once()
    pos[A]["ETH"] = 4.0
    core.converge_once()
    check("TRIM_USES_THE_SAME_MINIMUM_THE_WIRE_GATE_USES", abs(eff - wire_min) < 1e-12 and eff == SYM_MIN, (eff, wire_min))
    check("TRIM_BELOW_THE_EFFECTIVE_MIN_SENDS_NOTHING", not trims(sent) and 0.09 * PX < eff,
          (eff, 0.09 * PX, [i.copy_size for i in sent]))
    core.stop()
    pos[A]["ETH"] = 10.0
    core, sent = make_core("atmin", [(A, "ETH", 0.2)])
    core.converge_once()
    pos[A]["ETH"] = 4.0
    core.converge_once()
    t = trims(sent)
    check("TRIM_AT_THE_MINIMUM_STILL_SENDS", len(t) == 1 and abs(t[0].copy_size - 0.12) < 1e-12
          and 0.12 * PX >= core._converge_effective_min("ETH"), [i.copy_size for i in t])
    core.stop()

    # a leader that grew is not a trim
    pos[A]["ETH"] = 10.0
    core, sent = make_core("grow", [(A, "ETH", 10.0)])
    core.converge_once()
    pos[A]["ETH"] = 12.0
    core.converge_once()
    check("LEADER_GROWTH_IS_NOT_A_TRIM", not trims(sent) and core._converge_lead_base.get(KEY) == (12.0, 10.0), core._converge_lead_base)
    core.stop()

    # pre-existing path unchanged: a leader that left still closes the sleeve whole, and the base is dropped
    pos[A]["ETH"] = 10.0
    core, sent = make_core("flat", [(A, "ETH", 6.0)])
    core.converge_once()
    pos[A]["ETH"] = 0.0
    core.converge_once()
    cl = trims(sent)
    check("FULL_LEADER_EXIT_STILL_CLOSES_WHOLE", len(cl) == 1 and abs(cl[0].copy_size - 6.0) < 1e-12
          and cl[0].reduce_only_intended and cl[0].fill.raw.get("converge_reason") == "LEADER_FLAT",
          [(i.copy_size, i.fill.raw.get("converge_reason")) for i in cl])
    core.ledger.sleeve(A, "ETH")["signed_size"] = 0.0
    core.ledger._recompute_net(core.ledger.data)
    core.converge_once()
    check("TRIM_BASE_IS_DROPPED_WHEN_THE_SLEEVE_IS_GONE", KEY not in core._converge_lead_base and KEY not in core._converge_seen, core._converge_lead_base)
    core.stop()

    failed = R.count(False)
    print("TOTAL=%d FAILED=%d" % (len(R), failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
