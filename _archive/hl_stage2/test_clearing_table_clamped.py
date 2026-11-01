#!/usr/bin/env python3
"""Clearing table + overwrite check for CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED owed rows.

A clamped RED (reason CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED) held with a
NON-FLAT sleeve must SURVIVE when global close-only is switched OFF and the
exchange read is, in turn: STALE, UNREADABLE, OPPOSITE, NON-ZERO, PARTIAL vs
fresh. Only CURRENT sleeve-flat AND FRESH exchange-flat may clear it.
"""
import os, sys, tempfile, json
HERE = __import__("pathlib").Path(__file__).resolve().parent
TMP = __import__("pathlib").Path(tempfile.mkdtemp(prefix="clearing_table_"))
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
DUMMY_KEY = t.DUMMY_KEY
ACCOUNT = t.ACCOUNT
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = DUMMY_KEY
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
c.USER_WALLET = ACCOUNT
c.HLAccount, c.HLExchange = object, object

REASON = "CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED"
RED = REASON

def _seed_row(key=None):
    if key is None:
        key = A + "::" + COIN
    row = {"wallet": A, "coin": COIN, "state": "OPEN",
           "reason": REASON,
           "terminal_rule": "ENGINE_SLEEVE_AND_FRESH_EXCHANGE_NET_BOTH_FLAT"}
    c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {key: row})
    return key

def _red_present(key):
    d = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) or {}
    return key in d and isinstance(d.get(key), dict) and d[key].get("state") == "OPEN"

def _make(sleeve, exval, fresh=True, unreadable=False):
    led, ex, net = t.new_ledger(), t.FakeExchange(), [exval if exval is not None else 0.0]
    gw = t.make_gateway(ex, led, net)
    gw.cfg.send_mode_now = lambda: "CLOSE"   # global close-only switched OFF branch not taken for clear
    # global close-only OFF:
    gw.cfg.master_switch_now = lambda: True
    t.set_sleeve(led, A, sleeve)
    if unreadable:
        gw._fresh_exchange_net = lambda coin: None
    else:
        gw._fresh_exchange_net = lambda coin: exval
    return led, gw

# Table cases: (case, sleeve, exchange value, expected_survive)
cases = [
    ("STALE", 5.0, 5.0),
    ("UNREADABLE", 5.0, None),
    ("OPPOSITE", 5.0, -5.0),
    ("NON-ZERO", 5.0, 3.25),
    ("PARTIAL", 5.0, 2.5),
    ("FRESH_FLAT", 0.0, 0.0),
]

print("CASE,SLEEVE,EXCHANGE,RED_PRESENT,REASON")
results = []
for name, slv, exv in cases:
    led, gw = _make(slv, exv, unreadable=(exv is None))
    key = _seed_row()
    cleared = gw.clear_close_escalations()
    present = _red_present(key)
    # expected: survive for non-flat; clear for flat
    if name == "FRESH_FLAT":
        ok = (not present) and cleared == 1
    else:
        ok = present and cleared == 0
    reason = "survives (sleeve/exchange not both flat)" if present else "cleared (sleeve+exchange both flat)"
    print("RESULT::%s_%s  case=%s sleeve=%s exchange=%s red_present=%s cleared=%d reason=%s" % (
        name, "PASS" if ok else "FAIL", name, slv, exv, "yes" if present else "no", cleared, reason))
    results.append((name, ok))

# RESTART section
print("---RESTART---")
led, ex, net = t.new_ledger(), t.FakeExchange(), [0.0]
gw1 = t.make_gateway(ex, led, net)
gw1.cfg.send_mode_now = lambda: "CLOSE"
t.set_sleeve(led, A, 0.0)
net[0] = 0.0
key = _seed_row()
before_file = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
print("RESTART_BEFORE_CLEAR_FILE=%s" % json.dumps(before_file))
# re-instantiate sender on same state dir
gw2 = t.make_gateway(ex, led, net)
gw2.cfg.send_mode_now = lambda: "CLOSE"
gw2._fresh_exchange_net = lambda coin: 0.0
t.set_sleeve(led, A, 0.0)
cleared2 = gw2.clear_close_escalations()
after_file = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
print("RESTART_AFTER_CLEAR_FILE=%s cleared=%d" % (json.dumps(after_file), cleared2))
restart_ok = (key in (before_file or {}) and key not in (after_file or {}))
print("RESULT::RESTART_%s  before_has=%s after_has=%s cleared=%d" % (
    "PASS" if restart_ok else "FAIL", key in (before_file or {}), key in (after_file or {}), cleared2))
results.append(("RESTART", restart_ok))

# OVERWRITE section
print("---OVERWRITE---")
specific_key = A + "::" + COIN + "::SPECIFIC"
# use normal key but mark specific owed row
_owed_key = A + "::" + COIN
row_specific = {"wallet": A, "coin": COIN, "state": "OPEN",
                "reason": REASON, "tag": "SPECIFIC_OWED_ROW"}
c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {_owed_key: row_specific})
led2, ex2, net2 = t.new_ledger(), t.FakeExchange(), [1.0]
gw3 = t.make_gateway(ex2, led2, net2)
gw3.cfg.send_mode_now = lambda: "CLOSE"
# wallet-mode change: wallet disabled for this wallet
gw3.cfg.wallet_enabled = lambda w: False
gw3.cfg.wallet_mode = lambda w: "OFF"
t.set_sleeve(led2, A, 0.5)   # partial fill sleeve non-flat
net2[0] = 0.5
gw3._fresh_exchange_net = lambda coin: 0.5
before_ov = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
print("OVERWRITE_BEFORE=%s" % json.dumps(before_ov))
cleared_ov = gw3.clear_close_escalations()
after_ov = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
print("OVERWRITE_AFTER=%s cleared=%d" % (json.dumps(after_ov), cleared_ov))
ov_ok = (_owed_key in (after_ov or {}))
print("RESULT::OVERWRITE_%s  specific_row_survives=%s" % ("PASS" if ov_ok else "FAIL", ov_ok))
results.append(("OVERWRITE", ov_ok))

failed = [n for n, ok in results if not ok]
print("TOTAL=%d FAILED=%d" % (len(results), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
raise SystemExit(1 if failed else 0)
