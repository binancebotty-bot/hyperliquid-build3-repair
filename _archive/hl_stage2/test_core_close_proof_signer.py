#!/usr/bin/env python3
"""CS-I3 SIGNER (R1): the close prover must name the account the SDK will actually sign for.

The SDK is built with `account_address = env or None`. With HL_LIVE_HL_ACCOUNT_ADDRESS UNSET the
`None` makes the SDK sign AS THE KEY, so the signer IS the order account. Before this fix
`_follower_order_account_for_proof` returned '' in that case while `_close_proof_account_ok`
already resolved the signer from the key, so a legitimate self-signed follower held every close
with CLOSE_PROOF_HOLD_ORDER_ACCOUNT_MISMATCH - the two halves of the same proof disagreed.

F1 agent-signed (env MASTER, agent key) and F2 self-signed (env UNSET, master key) both prove the
order account and SEND; the negative twin (env OTHER_ACCOUNT) still holds with no wire call.

Offline, testnet, temp state. Standalone: python test_core_close_proof_signer.py
"""
import os
import sys
import tempfile
import threading
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="c7_signer_"))
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
import HL_Live_Copy_Service_Core as c  # noqa: E402

c.acquire_global_instance_lock(TMP / "state")

MASTER = "0x" + "e" * 40
AGENT = "0x" + "f" * 40
OTHER_ACCOUNT = "0x" + "d" * 40
A = "0x" + "a" * 40
COIN, PX, MIN_USD = "BTC", 100.0, 10.0
RESOLVED = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
            "sdk_order_compatible": True, "min_order_value_usd": MIN_USD, "min_size": 0.0, "status": "OK"}


class FakeAccount:
    """The real SDK resolves a key to an address; the suite must not need a live HLAccount."""
    by_key = {"0xmaster": MASTER, "0xagent": AGENT}

    @classmethod
    def from_key(cls, k):
        return types.SimpleNamespace(address=cls.by_key[k])


c.HLAccount, c.HLExchange = FakeAccount, object
c.MIDS_FETCHER = lambda p: [] if isinstance(p, dict) and p.get("type") == "perpDexs" else {"BTC": str(PX)}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

RESULTS = []


def check(name, ok, detail=""):
    ok = bool(ok)
    RESULTS.append((name, ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", ("" if ok or not detail else " | " + str(detail)[:600])), flush=True)


def case(name, fn):
    try:
        ok, detail = fn()
    except Exception as exc:                                       # noqa: BLE001
        ok, detail = False, "EXCEPTION %s: %s" % (type(exc).__name__, str(exc)[:300])
    check(name, ok, detail)


class FakeExchange:
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()
        self.physical_net = None

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        with self._lock:
            self.calls.append({"coin": coin, "is_buy": is_buy, "size": float(size), "px": px,
                               "reduce_only": reduce_only, "cloid": None if cloid is None else str(cloid)})
            if self.physical_net is not None:
                self.physical_net[0] += float(size) * (1 if is_buy else -1)
            return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"totalSz": str(size), "avgPx": str(px), "oid": len(self.calls)}}]}}}

    def cancel(self, coin, oid):
        return {"status": "ok"}


_n = [0]


def new_ledger():
    _n[0] += 1
    return c.ManualLedger(path=TMP / ("ledger_%d.json" % _n[0]))


def set_sleeve(ledger, wallet, signed):
    ledger.sleeve(wallet, COIN)["signed_size"] = signed
    ledger._recompute_net(ledger.data)


def make_gateway(ex, ledger, net):
    """A real SenderGateway. The REAL _close_wire_plan, _close_proof_account_ok and
    _follower_order_account_for_proof run; only the exchange and the sleeve/state data are faked."""
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    ex.physical_net = net
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: ex
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (ex, "BTC")
    gw._fresh_exchange_net = lambda coin: net[0]
    gw._persisted_exchange_positions = lambda: (({"BTC": net[0]}, "") if net[0] is not None else ({}, "unavailable"))
    gw.leader_reduced_since = lambda f: 0
    gw._margin_mode_done = {"BTC"}
    gw.cfg.master_switch_now = lambda: True
    gw.cfg.send_mode_now = lambda: "ON"
    gw.cfg.wallet_enabled = lambda w: True
    gw.cfg.wallet_mode = lambda w: "ON"
    return gw


def exit_intent(ledger, wallet, side, size, fid, sleeve, source="POLL", start=None):
    set_sleeve(ledger, wallet, sleeve)
    fill = c.LeaderFill(fid, wallet, COIN, side, PX, size, c.utc_now_ms(), source)
    if start is not None:
        fill.raw["startPosition"] = str(start)
    it = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
    it.intent_id = fid
    it.decision = "EXIT_ALLOWED"
    return it


def sleeve_of(ledger, wallet):
    row = ((ledger.data.get("by_wallet") or {}).get(wallet) or {}).get(COIN)
    return None if row is None else float(row.get("signed_size"))


def _set_env(account_env, key):
    if account_env is None:
        os.environ.pop("HL_LIVE_HL_ACCOUNT_ADDRESS", None)
    else:
        os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = account_env
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = key
    c.USER_WALLET = MASTER


# =============================================================== F1: agent-signed (env MASTER, agent key)
def f1_agent_signed_proves_the_env_account_and_sends():
    """Env names MASTER, the key is the AGENT: the SDK signs for MASTER, so the prover must say MASTER
    and the real close plan must SEND a single SELL 2.0 reduce-only; net 5.0 -> 3.0."""
    saved = {k: os.environ.get(k) for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_LIVE_HL_PRIVATE_KEY")}
    old_wallet = c.USER_WALLET
    try:
        _set_env(MASTER, "0xagent")
        led, ex, net = new_ledger(), FakeExchange(), [5.0]
        gw = make_gateway(ex, led, net)
        proved = gw._follower_order_account_for_proof()
        if proved != MASTER:
            return False, "proved=%r expected MASTER" % (proved,)
        if gw._close_proof_account_ok() is not True:
            return False, "_close_proof_account_ok() is not True"
        it = exit_intent(led, A, "SELL", 5.0, "f1-f", 2.0, start=5.0)
        timing = {}
        ro, amount, why = gw._close_wire_plan(it, 2.0, 3, timing=timing)
        if not (ro is True and abs(amount - 2.0) < 1e-9 and why == ""):
            return False, "plan ro=%r amount=%r why=%r" % (ro, amount, why)
        ok, status = gw.send_if_allowed(it)
        return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 2.0) < 1e-9
                and ex.calls[0]["is_buy"] is False and ex.calls[0]["reduce_only"] is True
                and abs(net[0] - 3.0) < 1e-9), \
            "ok=%r status=%r calls=%r net=%r" % (ok, status, ex.calls, net)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        c.USER_WALLET = old_wallet


# ============================================================= F2: self-signed (env UNSET, master key)
def f2_self_signed_proves_the_signer_and_sends():
    """Env UNSET: account_address=None means the SDK signs AS THE KEY. The prover must resolve the
    signer (MASTER) and the close must SEND one SELL 2.0 reduce-only; net 5.0 -> 3.0.
    FAILS BEFORE THE FIX with why=CLOSE_PROOF_HOLD_ORDER_ACCOUNT_MISMATCH."""
    saved = {k: os.environ.get(k) for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_LIVE_HL_PRIVATE_KEY")}
    old_wallet = c.USER_WALLET
    try:
        _set_env(None, "0xmaster")
        led, ex, net = new_ledger(), FakeExchange(), [5.0]
        gw = make_gateway(ex, led, net)
        proved = gw._follower_order_account_for_proof()
        if proved != MASTER:
            return False, "proved=%r expected MASTER" % (proved,)
        it = exit_intent(led, A, "SELL", 5.0, "f2-f", 2.0, start=5.0)
        timing = {}
        ro, amount, why = gw._close_wire_plan(it, 2.0, 3, timing=timing)
        if not (ro is True and abs(amount - 2.0) < 1e-9 and why == ""):
            return False, "plan ro=%r amount=%r why=%r" % (ro, amount, why)
        ok, status = gw.send_if_allowed(it)
        return (ok and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 2.0) < 1e-9
                and ex.calls[0]["is_buy"] is False and ex.calls[0]["reduce_only"] is True
                and abs(net[0] - 3.0) < 1e-9), \
            "ok=%r status=%r calls=%r net=%r" % (ok, status, ex.calls, net)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        c.USER_WALLET = old_wallet


# ================================================== negative twin: env names a DIFFERENT trading account
def f3_negative_env_other_account_still_holds():
    """Env OTHER_ACCOUNT with the agent key: the prover names OTHER_ACCOUNT, the reader is MASTER, so the
    close HOLDS with CLOSE_PROOF_HOLD_ORDER_ACCOUNT_MISMATCH and no wire call is made."""
    saved = {k: os.environ.get(k) for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_LIVE_HL_PRIVATE_KEY")}
    old_wallet = c.USER_WALLET
    try:
        _set_env(OTHER_ACCOUNT, "0xagent")
        led, ex, net = new_ledger(), FakeExchange(), [5.0]
        gw = make_gateway(ex, led, net)
        it = exit_intent(led, A, "SELL", 5.0, "f3-f", 2.0, start=5.0)
        ok, status = gw.send_if_allowed(it)
        return (not ok and status == "SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD" and ex.calls == []
                and abs(net[0] - 5.0) < 1e-9 and abs(sleeve_of(led, A) - 2.0) < 1e-9), \
            "ok=%r status=%r calls=%r net=%r sleeve=%r" % (ok, status, ex.calls, net, sleeve_of(led, A))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        c.USER_WALLET = old_wallet


for _name, _fn in (
        ("CS_I3_F1_AGENT_SIGNED_PROVES_ENV_ACCOUNT_AND_SENDS", f1_agent_signed_proves_the_env_account_and_sends),
        ("CS_I3_F2_SELF_SIGNED_PROVES_THE_SIGNER_AND_SENDS", f2_self_signed_proves_the_signer_and_sends),
        ("CS_I3_F3_NEGATIVE_ENV_OTHER_ACCOUNT_STILL_HOLDS", f3_negative_env_other_account_still_holds),
):
    case(_name, _fn)

FAILED = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(FAILED)), flush=True)
if FAILED:
    print("FAILED: " + ", ".join(FAILED), flush=True)
sys.exit(1 if FAILED else 0)
