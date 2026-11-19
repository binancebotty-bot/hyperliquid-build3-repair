import os, sys, tempfile, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="acd_"))
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

src = open(HERE / "test_core_close_to_target.py").read()
ns = {"__file__": str(HERE / "test_core_close_to_target.py")}
try:
    exec(compile(src, "tct", "exec"), ns)
except SystemExit:
    pass
tct = type("tct", (), ns)() if False else ns
# expose as module-like
import types
tct = types.SimpleNamespace(**ns)

def plan(**kw):
    tct.ESC.clear(); tct.WIRES.clear()
    r = tct.plan(**kw)
    return r, list(tct.ESC), list(tct.WIRES)

# A1
r, esc, wires = plan(side="SELL", size=2.0, led=2.0, ex=2.0, readable=False, owned=2.0, gmode="CLOSE")
print("A1", r, esc, wires)
assert r[1] == 0.0, r
assert "GLOBAL_CLOSE_ONLY_UNKNOWN_NET" in (r[2] or ""), r
assert wires == [], wires
assert any("CLAMPED" in e for e in esc), esc
print("RESULT::A1_PASS")

# A2
r, esc, wires = plan(side="SELL", size=2.0, led=2.0, ex=2.0, readable=False, owned=2.0)
print("A2", r, esc, wires)
assert r == (False, 2.0, ""), r
assert esc == ["CLOSE_PROOF_UNREADABLE_NET_FALLBACK"], esc
print("RESULT::A2_PASS")

# C1
def seed_row():
    key = A + "::" + COIN
    row = {"wallet": A, "coin": COIN, "state": "OPEN",
           "reason": "CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED",
           "terminal_rule": "ENGINE_SLEEVE_AND_FRESH_EXCHANGE_NET_BOTH_FLAT"}
    c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {key: row})
    return key

led, ex, net = t.new_ledger(), t.FakeExchange(), [5.0]
gw = t.make_gateway(ex, led, net)
gw.cfg.send_mode_now = lambda: "ON"
t.set_sleeve(led, A, 2.0)
net[0] = 5.0
key = seed_row()
cleared = gw.clear_close_escalations()
after = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
print("C1", cleared, after)
assert cleared == 0 and key in (after or {}), (cleared, after)
print("RESULT::C1_PASS")

# C2
led, ex, net = t.new_ledger(), t.FakeExchange(), [0.0]
gw = t.make_gateway(ex, led, net)
gw.cfg.send_mode_now = lambda: "ON"
t.set_sleeve(led, A, 0.0)
net[0] = 0.0
key = seed_row()
cleared = gw.clear_close_escalations()
after = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
print("C2", cleared, after)
assert cleared == 1 and key not in (after or {}), (cleared, after)
print("RESULT::C2_PASS")

print("TOTAL_PASS")
