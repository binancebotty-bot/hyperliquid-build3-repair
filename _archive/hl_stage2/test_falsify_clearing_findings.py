#!/usr/bin/env python3
# RED CASE (witness) for the REAL clearing-safety defect:
# CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED rows are destroyed with NO position check
# whenever the global-close-only switch is OFF (send_mode != "CLOSE").
# F1 (UNREADABLE_NET_FALLBACK) and F3 (LEDGER_LAG_NET_UNREADABLE_RESTING) are
# FALSE POSITIVES and are deliberately NOT asserted here: clearing those reasons
# requires a fresh same-account exchange read of 0.0 (see clear path L8943-8977),
# so a flat sleeve + flat exchange is a correct clear, not a defect.
import os, sys, tempfile
HERE = __import__("pathlib").Path(__file__).resolve().parent
TMP = __import__("pathlib").Path(tempfile.mkdtemp(prefix="falsify_clear_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
    "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_GLOBAL_LOCK_FILE": str(TMP / "engine-global.lock"),
    "PYTHONHASHSEED": "0",
})
for _k in ("HL_LIVE_HL_PRIVATE_KEY", "HL_LIVE_HL_ACCOUNT_ADDRESS"):
    os.environ.pop(_k, None)
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c
c.acquire_global_instance_lock(TMP / "state")
import test_core_c7_close_must_send as t

A = t.A; COIN = t.COIN
DUMMY_KEY = "0x" + "1" * 64
ACCOUNT = t.ACCOUNT
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = DUMMY_KEY
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
c.USER_WALLET = ACCOUNT
c.HLAccount, c.HLExchange = object, object

results = []
def check(name, ok, detail):
    results.append((name, bool(ok)))
    print("RESULT::%s_%s | %s" % (name, "PASS" if ok else "FAIL", detail))

# RED CASE: clamped row with sleeve 5.0 on BOTH ledger and exchange, switch OFF.
# Correct behaviour: row MUST survive (debt still owed). Current code: cleared.
def test_f2_global_close_clamped_cleared_while_nonflat():
    led, ex, net = t.new_ledger(), t.FakeExchange(), [5.0]
    gw = t.make_gateway(ex, led, net)
    gw.cfg.send_mode_now = lambda: "OFF"   # switch off -> not close-only
    t.set_sleeve(led, A, 5.0)
    key = A + "::" + COIN
    row = {"wallet": A, "coin": COIN, "state": "OPEN",
           "reason": "CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED"}
    c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {key: row})
    cleared = gw.clear_close_escalations()
    remaining = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
    # RED: defect present iff the row was cleared despite non-flat sleeve/exchange.
    ok = (cleared == 0 and key in remaining)
    check("F2_GLOBAL_CLOSE_CLAMPED_CLEARED_WHILE_NONFLAT", ok,
          f"cleared={cleared} remaining={remaining}")

if __name__ == "__main__":
    test_f2_global_close_clamped_cleared_while_nonflat()
    failed = sum(1 for _, ok in results if not ok)
    print(f"TOTAL={len(results)} FAILED={failed}")
    sys.exit(1 if failed else 0)
