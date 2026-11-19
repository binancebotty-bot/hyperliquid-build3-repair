#!/usr/bin/env python3
"""RED contract: Boss's 18 November ruling on the ENG-019 fallback-close path.

RULING (encoded verbatim, Core:17933 is NOT the site - see SITE below):
  * a close sends the OWNED size, not reduce-only and not clamped;
  * a readable FLAT exchange sends NOTHING;
  * a close with NO ownership record sends NOTHING, and alerts.

SITE - established by enumeration at c63d2299, not assumed:
  * The cycle loop in `main` has exactly ONE loop-level `finally`: Core:17933-17934, `core.stop()`.
    It sends no order. `LiveCopyCore.stop()` (Core:13250) cancels resting entry limits and joins
    threads only. `main`'s `run_cycle` handler (Core:17913-17917) logs and sets `summary = None`.
    => There is NO loop-level ENG-019 fallback close in the Core. ENG-019 is the loop-throughput
       invariant (certification/certification_matrix.json:24432, "Main loop keeps up with 10 very
       busy leaders"), not a close path.
  * The only fallback CLOSE reachable when a close's ownership proof does not arrive inside its
    bounded window is the ledger-lag HOLD window:
        _close_wire_plan_ledger_lag (Core:8532)
          -> _close_lag_hold_for_owned (Core:8646, polls until CLOSE_LAG_HOLD_SEC expires)
          -> _close_lag_window_expired (Core:8658)
    whose wire size is the clamping clause at Core:8666
        amount = self._floor_wire_size(round(min(requested, abs(net)), 10), sz_dec)
    and whose send is forced reduce-only at Core:8673
        return decide("SEND", amount, True)
    These five checks are anchored there. That is the DOOR_3-site family.

WHAT THIS FILE DOES NOT DO: it changes no production byte. It is RED: checks 3 and 4 are expected
to FAIL at c63d2299 because the site sends a net-clamped, reduce-only close where the ruling
requires nothing at all.

Existing sibling witness test_r4_lag_hold.py:200-202
(`LAG_HOLD_B_NEVER_CATCHES_UP_SENDS_REDUCE_ONLY`) asserts the behaviour this ruling forbids. It is
left untouched; a GREEN fix must move it with the ruling.

Standalone process: python test_ruling_eng019_fallback_contract.py
Prints RESULT::<NAME>_PASS|_FAIL per check and TOTAL=n FAILED=m; exits non-zero when anything failed.
Offline, testnet, own temp audit dir; no exchange, no network, no lease.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="eng019_ruling_"))
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

DUMMY_KEY = "0x" + "1" * 64            # synthetic, not a secret: satisfies the credentials-present pre-check
A = "0x" + "a" * 40                    # leader wallet
ACCOUNT = "0x" + "c" * 40              # the follower trading account (public address, not a secret)
COIN, PX, SZ_DEC = "BTC", 100.0, 3
RESOLVED = {"ok": True, "sdk_coin": "BTC", "sz_decimals": SZ_DEC, "price_max_decimals": 2, "perp_dexs": [""],
            "sdk_order_compatible": True, "min_order_value_usd": 10.0, "min_size": 0.0, "status": "OK"}

os.environ["HL_LIVE_HL_PRIVATE_KEY"] = DUMMY_KEY
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
c.USER_WALLET = ACCOUNT
c.HLAccount, c.HLExchange = object, object
c.MIDS_FETCHER = lambda p: [] if isinstance(p, dict) and p.get("type") == "perpDexs" else {"BTC": str(PX)}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

# the name the ruling's third clause must land on: the module's own vocabulary for "nothing is owned"
NO_OWNED = "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE"

RESULTS = []


def check(name, ok, detail=""):
    ok = bool(ok)
    RESULTS.append((name, ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
                               "" if ok or not detail else " | " + str(detail)[:600]), flush=True)


def case(name, fn):
    """One witness; an exception is a failed check carrying the exception text, never a crash."""
    try:
        ok, detail = fn()
    except Exception as exc:                                       # noqa: BLE001
        ok, detail = False, "EXCEPTION %s: %s" % (type(exc).__name__, str(exc)[:300])
    check(name, ok, detail)


# ---- the close path's bounded proof window, driven on a fake clock: sleeping only advances time
_T = [0.0]
_SAVED_CLOCK = (c._CLOSE_LAG_CLOCK, c._CLOSE_LAG_SLEEP)
c._CLOSE_LAG_CLOCK = lambda: _T[0]
c._CLOSE_LAG_SLEEP = lambda s: _T.__setitem__(0, _T[0] + s)

_n = [0]


def new_ledger():
    _n[0] += 1
    return c.ManualLedger(path=TMP / ("ledger_%d.json" % _n[0]))


def make_gateway(ledger, net_reader):
    """A real SenderGateway. The REAL _close_wire_plan / _close_wire_plan_ledger_lag /
    _close_lag_window_expired / _floor_wire_size run. Only DATA sources are replaced."""
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: object()
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (object(), "BTC")
    gw._follower_order_account_for_proof = lambda *a, **k: ACCOUNT
    gw._fresh_exchange_net = lambda coin: net_reader()
    gw.leader_reduced_since = lambda f: 0
    gw._margin_mode_done = {"BTC"}
    gw.cfg.master_switch_now = lambda: True
    gw.cfg.send_mode_now = lambda: "ON"            # _global_close_only False: the ordinary mode
    gw.cfg.wallet_enabled = lambda w: True
    gw.cfg.wallet_mode = lambda w: "ON"
    gw._reduce_only_for_intent = lambda i: True    # an EXIT close: the sanctioned close lifecycle
    return gw


def drive(record, proven, net_mag, requested, ledger_may_lag=True, tag="x"):
    """A leader close of `requested` on wallet A / BTC.

    record  = abs size on the sleeve ROW in the ledger (the ownership record; 0 = no record at all)
    proven  = abs size the FILL PROOF returns (0 on this app: proof has not arrived / cannot be made)
    net_mag = abs exchange net offered to the close, or None (the net read times out: unreadable)
    Returns (gateway, intent, plan, elapsed) where plan == (reduce_only, wire_size, why).
    """
    _T[0] = 0.0
    led = new_ledger()
    gw = make_gateway(led, lambda: None)
    it = c.IntentBuilder(c.ConfigManager(), led).build(
        c.LeaderFill("eng019-%s" % tag, A, COIN, "SELL", PX, requested, c.utc_now_ms(), "POLL"))
    it.intent_id = "eng019-%s" % tag
    it.decision = "EXIT_ALLOWED"
    side = c.ManualLedger.signed_delta(it.copy_side, 1.0)      # +1 BUY, -1 SELL
    if record:
        led.sleeve(A, COIN)["signed_size"] = -side * abs(record)
        led._recompute_net(led.data)
    gw._proven_owned_for_sleeve = lambda w, cn: (-side * abs(proven), "test")
    gw._fresh_exchange_net = lambda coin: (None if net_mag is None else (-side * abs(net_mag)))
    plan = c.SenderGateway._close_wire_plan(gw, it, requested, SZ_DEC, lambda s: True, None, ledger_may_lag)
    return gw, it, plan, _T[0]


def escalation_row(wallet, coin):
    p = c.CLOSE_ESCALATIONS_FILE
    if not p.exists():
        return None
    rows = json.loads(p.read_text(encoding="utf-8-sig"))
    return (rows or {}).get(c.normalise_wallet(wallet) + "::" + c.canonical_coin_key(coin))


def reset_escalations():
    try:
        c.CLOSE_ESCALATIONS_FILE.unlink()
    except OSError:
        pass


# =====================================================================================================
# 1. The fallback path, an OWNED position: the close sends the OWNED size and does not force reduce-only.
#    Site: Core:8532 -> 8624-8638 (net read times out after its bounded re-read).
# =====================================================================================================
def chk_owned_close_on_fallback():
    reset_escalations()
    gw, it, plan, _elapsed = drive(record=5.0, proven=5.0, net_mag=None, requested=5.0, tag="owned")
    ok = plan == (False, 5.0, "")
    return ok, "plan=%r (want (False, 5.0, ''): owned size 5.0, reduce_only NOT forced)" % (plan,)


# =====================================================================================================
# 2. The same fallback path with a READABLE FLAT exchange: nothing is sent.
#    Site: Core:8583-8590 (net readable and not opposed -> HOLD, no wire).
# =====================================================================================================
def chk_flat_exchange_sends_nothing():
    reset_escalations()
    gw, it, plan, _elapsed = drive(record=5.0, proven=5.0, net_mag=0.0, requested=5.0, tag="flat")
    ok = plan[0] is False and plan[1] == 0.0 and bool(plan[2])
    return ok, "plan=%r (want no send: reduce_only False, size 0.0, a named HOLD reason)" % (plan,)


# =====================================================================================================
# 3. The same fallback path with NO ownership record: nothing is sent AND a named alert row is written.
#    Site: Core:8574-8578 -> 8658-8673, which today SENDS (reduce_only, net-clamped).
# =====================================================================================================
def chk_no_ownership_record_sends_nothing_and_alerts():
    reset_escalations()
    gw, it, plan, elapsed = drive(record=0.0, proven=0.0, net_mag=4.0, requested=10.0, tag="noproof")
    if plan[0] is not False or plan[1] != 0.0:
        return False, "SENT WITHOUT AN OWNERSHIP RECORD: plan=%r after hold %.2fs" % (plan, elapsed)
    if plan[2] != NO_OWNED:
        return False, "refusal not named %s: why=%r" % (NO_OWNED, plan[2])
    # the alert row the ruling requires, written by the same helper the send site's caller uses
    # (Core:9704-9712 -> _journal_authorised_close_refusal -> _open_close_escalation)
    gw._journal_authorised_close_refusal(it, plan[2])
    row = escalation_row(A, COIN)
    ok = isinstance(row, dict) and row.get("reason") == NO_OWNED and row.get("state") == "OPEN"
    return ok, "escalation row=%r (want state OPEN, reason %s)" % (row, NO_OWNED)


# =====================================================================================================
# 4. The clamp at Core:8666 is the clause the ruling forbids: the wire size must never be the
#    min(requested, abs(net)) result. Driven with an ownership record of 10 on the sleeve, asked 10,
#    and an exchange net SMALLER than the request - exactly where the clamp bites.
# =====================================================================================================
def chk_wire_size_never_the_net_clamp():
    bad = []
    for net_mag in (3.0, 7.0):
        reset_escalations()
        _gw, _it, plan, _elapsed = drive(record=10.0, proven=0.0, net_mag=net_mag, requested=10.0,
                                         tag="clamp-%s" % net_mag)
        clamped = min(10.0, abs(net_mag))
        if plan[1] == clamped:
            bad.append("net=%s -> wire=%r == min(requested, abs(net))=%r" % (net_mag, plan[1], clamped))
    return (not bad), ("min(requested, abs(net)) IS the transmitted size: " + "; ".join(bad)) if bad else ""


# =====================================================================================================
# 5. CONTROL: the ordinary (non-fallback) owned close still sends the OWNED size, so a fix cannot
#    regress the normal path. Site: Core:8405-8530, ledger present, no lag window entered.
# =====================================================================================================
def chk_ordinary_owned_close_unchanged():
    reset_escalations()
    gw, it, plan, elapsed = drive(record=5.0, proven=5.0, net_mag=5.0, requested=5.0,
                                  ledger_may_lag=False, tag="ordinary")
    ok = plan[1] == 5.0 and plan[0] is True and plan[2] == ""
    return ok, "plan=%r elapsed=%.2f (want SEND of owned 5.0 on the ordinary path)" % (plan, elapsed)


case("ENG019_FALLBACK_OWNED_CLOSE_SENDS_OWNED_SIZE_NOT_REDUCE_ONLY", chk_owned_close_on_fallback)
case("ENG019_FALLBACK_FLAT_EXCHANGE_SENDS_NOTHING", chk_flat_exchange_sends_nothing)
case("ENG019_FALLBACK_NO_OWNERSHIP_RECORD_SENDS_NOTHING_AND_ALERTS", chk_no_ownership_record_sends_nothing_and_alerts)
case("ENG019_FALLBACK_WIRE_SIZE_NEVER_THE_NET_CLAMP_8666", chk_wire_size_never_the_net_clamp)
case("ENG019_ORDINARY_OWNED_CLOSE_STILL_SENDS_OWNED_SIZE", chk_ordinary_owned_close_unchanged)

c._CLOSE_LAG_CLOCK, c._CLOSE_LAG_SLEEP = _SAVED_CLOCK
FAILED = sum(1 for _, ok in RESULTS if not ok)
print("TOTAL=%d FAILED=%d" % (len(RESULTS), FAILED), flush=True)
sys.exit(1 if FAILED else 0)
