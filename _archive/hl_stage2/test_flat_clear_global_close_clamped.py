#!/usr/bin/env python3
"""Flat-clearing witness for CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED owed rows.

A clamped remainder is OWED only while the global close-only switch is on, but it
must ALSO clear on POSITION FLAT (engine sleeve + fresh same-account exchange
read both flat), independent of the switch. Stale / unreadable exchange reads
must NOT clear it.
"""
import os, sys, tempfile, json
HERE = __import__("pathlib").Path(__file__).resolve().parent
TMP = __import__("pathlib").Path(tempfile.mkdtemp(prefix="flat_clear_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
    "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_GLOBAL_LOCK_FILE": str(TMP / "engine-global.lock"),
    "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000", "PYTHONHASHSEED": "0",
})
for _k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
    os.environ.pop(_k, None)
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c
c.acquire_global_instance_lock(TMP / "state")
import test_core_c7_close_must_send as t
A = t.A; COIN = t.COIN
DUMMY_KEY = t.DUMMY_KEY if hasattr(t, "DUMMY_KEY") else "0x" + "1" * 64
ACCOUNT = t.ACCOUNT
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = DUMMY_KEY
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
c.USER_WALLET = ACCOUNT
c.HLAccount, c.HLExchange = object, object

def _seed_row():
    key = A + "::" + COIN
    row = {"wallet": A, "coin": COIN, "state": "OPEN",
           "reason": "CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED",
           "terminal_rule": "ENGINE_SLEEVE_AND_FRESH_EXCHANGE_NET_BOTH_FLAT"}
    c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {key: row})
    return key

def case_flat_clears():
    led, ex, net = t.new_ledger(), t.FakeExchange(), [0.0]
    gw = t.make_gateway(ex, led, net)
    gw.cfg.send_mode_now = lambda: "CLOSE"   # switch ON: switch-off branch must NOT fire
    t.set_sleeve(led, A, 0.0)
    net[0] = 0.0
    key = _seed_row()
    cleared = gw.clear_close_escalations()
    after = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    return (cleared == 1 and key not in (after or {})), \
        "cleared=%r after=%r" % (cleared, after)

def case_stale_does_not_clear():
    led, ex, net = t.new_ledger(), t.FakeExchange(), [5.0]
    gw = t.make_gateway(ex, led, net)
    gw.cfg.send_mode_now = lambda: "CLOSE"
    t.set_sleeve(led, A, 5.0)
    net[0] = 5.0
    key = _seed_row()
    cleared = gw.clear_close_escalations()
    after = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    return (cleared == 0 and key in (after or {})), \
        "cleared=%r after=%r" % (cleared, after)

def case_unreadable_does_not_clear():
    led, ex, net = t.new_ledger(), t.FakeExchange(), [None]
    gw = t.make_gateway(ex, led, net)
    gw.cfg.send_mode_now = lambda: "CLOSE"
    t.set_sleeve(led, A, 0.0)
    # net stays None (unreadable) -> _fresh_exchange_net returns None
    gw._fresh_exchange_net = lambda coin: None
    key = _seed_row()
    cleared = gw.clear_close_escalations()
    after = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    return (cleared == 0 and key in (after or {})), \
        "cleared=%r after=%r" % (cleared, after)

def main():
    for name, fn in [("FLAT_CLEARS", case_flat_clears),
                     ("STALE_NO_CLEAR", case_stale_does_not_clear),
                     ("UNREADABLE_NO_CLEAR", case_unreadable_does_not_clear)]:
        ok, detail = fn()
        print("RESULT::%s_%s  %s" % (name, "PASS" if ok else "FAIL", detail))
    failed = 0
    # recompute
    results = []
    for name, fn in [("FLAT_CLEARS", case_flat_clears),
                     ("STALE_NO_CLEAR", case_stale_does_not_clear),
                     ("UNREADABLE_NO_CLEAR", case_unreadable_does_not_clear)]:
        ok, detail = fn()
        results.append((name, ok))
    failed = sum(1 for _, ok in results if not ok)
    print("TOTAL=%d FAILED=%d" % (len(results), failed))

if __name__ == "__main__":
    main()
