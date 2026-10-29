#!/usr/bin/env python3
"""C7W20261029RB: CLO label precedence regression at a1acc28.

Run as ONE independent process:
  HL_LIVE_ENV_FILE=/nonexistent python -u _archive/hl_stage2/test_core_clo_label_order_regression.py

The first three cases are deliberately RED at a1acc28; they must turn GREEN
only after the narrow _decision() guard reorder. No Core patch or real order.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SANDBOX = tempfile.TemporaryDirectory(prefix="clo_label_order_")
ROOT = Path(SANDBOX.name)
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(ROOT / "audit"),
    "HL_LIVE_ENV_FILE": str(ROOT / "missing.env"),
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_EARLY_PREWARM": "0",
    "HL_LIVE_MOCK_SEND": "1",
    "HL_LIVE_HL_PRIVATE_KEY": "",
})
import requests  # noqa: E402


def offline(*args, **kwargs):
    raise AssertionError("network access forbidden in offline CLO regression")


requests.post = offline
import HL_Live_Copy_Service_Core as core  # noqa: E402

core.requests.post = offline

WALLET = "0x" + "a" * 40
RESULTS = []


class NoWireExchange:
    """Any real exchange.order() attempt fails the regression immediately."""

    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("exchange.order called by a no-owned-sleeve case")


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (
        name, "PASS" if ok else "FAIL",
        (" | " + str(detail)[:300]) if (detail and not ok) else ""),
        flush=True,
    )


def build_case(tag, *, side, raw, wallet_mode="CLO", enabled=True, owned=0.0):
    """Use real ConfigManager, ManualLedger and IntentBuilder.build(), not _decision stubs."""
    case_dir = ROOT / tag
    case_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = case_dir / "live_config.json"
    core.atomic_write_json(cfg_path, {
        "auto_send_enabled": False,
        "global_controls": {"send_mode": "OFF", "min_notional": 10.0},
        "wallets": {WALLET: {
            "enabled": enabled,
            "mode": wallet_mode,
            "copy_mode": "fixed",
            "fixed_notional": 100.0,
        }},
    })
    cfg = core.ConfigManager(config_path=cfg_path)
    ledger = core.ManualLedger(path=case_dir / "manual_live_positions.json")
    if owned:
        sleeve = ledger.sleeve(WALLET, "BTC")
        sleeve.update({
            "signed_size": float(owned),
            "direction": "LONG" if owned > 0 else "SHORT",
            "position_id": "owned-btc-" + tag,
            "opened_by_intent_id": "seed-" + tag,
            "avg_entry_px": 100.0,
        })
        ledger._recompute_net(ledger.data)
        ledger.save(touched_sleeves=[(WALLET, "BTC")])
    fill = core.LeaderFill(
        "clo-label-" + tag, WALLET, "BTC", side, 100.0, 1.0,
        core.utc_now_ms(), "TEST", 0, dict(raw),
    )
    intent = core.IntentBuilder(cfg, ledger).build(fill)
    return cfg, ledger, intent


def blocked_case(tag, expected, **kwargs):
    cfg, ledger, intent = build_case(tag, **kwargs)
    fake = NoWireExchange()
    gateway = core.SenderGateway.__new__(core.SenderGateway)
    gateway.cfg = cfg
    gateway.ledger = ledger
    # If a wrongly permitted intent reaches the real send gate, it would
    # reach this fake order and become an explicit FAIL. No SDK client used.
    gateway._send_real = lambda *args, **kwargs: fake.order(*args, **kwargs)
    result = gateway.send_if_allowed(intent)
    ok = (intent.decision == expected
          and not intent.send_allowed
          and result == (False, "INTENT_NOT_SEND_ALLOWED")
          and not fake.calls)
    return ok, "decision=%s expected=%s route=%r exchange_calls=%d" % (
        intent.decision, expected, result, len(fake.calls))


check("CLO_FLAT_SELL_CLOSE_LONG_NO_SLEEVE",
      lambda: blocked_case("close_long", "SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION",
                           side="SELL", raw={"dir": "Close Long"}))

check("CLO_FLAT_BUY_CLOSE_SHORT_NO_SLEEVE",
      lambda: blocked_case("close_short", "SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION",
                           side="BUY", raw={"dir": "Close Short"}))

check("CLO_FLAT_EXPLICIT_REDUCE_ONLY_NO_SLEEVE",
      lambda: blocked_case("reduce_only", "SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION",
                           side="BUY", raw={"dir": "Open Long", "reduceOnly": True}))

check("CLO_FLAT_OPEN_LONG_IS_BLOCKED",
      lambda: blocked_case("open_long", "BLOCKED_CLO_ENTRY",
                           side="BUY", raw={"dir": "Open Long"}))

check("CLO_FLAT_AMBIGUOUS_METADATA_IS_BLOCKED",
      lambda: blocked_case("ambiguous", "BLOCKED_CLO_ENTRY",
                           side="BUY", raw={}))


def owned_exit():
    _, ledger, intent = build_case(
        "owned_exit", side="SELL", raw={"dir": "Close Long"},
        owned=2.75,
    )
    owned = ledger.wallet_coin_position(WALLET, "BTC")
    ok = (intent.decision == "EXIT_ALLOWED"
          and intent.send_allowed
          and intent.reduce_only_intended
          and abs(intent.copy_size - owned) < 1e-9
          and owned == 2.75)
    # Do not initiate an exit: only the intent builder is under test here.
    return ok, "decision=%s owned=%s copy_size=%s" % (
        intent.decision, owned, intent.copy_size)


check("CLO_OWNED_LONG_CLOSE_EXIT_FULL_SLEEVE", owned_exit)


def off_and_disabled():
    mode_off, a = blocked_case(
        "mode_off", "BLOCKED_OFF", side="SELL",
        raw={"dir": "Close Long"}, wallet_mode="OFF")
    disabled, b = blocked_case(
        "disabled", "BLOCKED_OFF", side="BUY",
        raw={"dir": "Close Short"}, enabled=False)
    return mode_off and disabled, "OFF: %s; disabled: %s" % (a, b)


check("FLAT_LEADER_CLOSE_OFF_OR_DISABLED_STILL_BLOCKED", off_and_disabled)

check("ON_FLAT_LEADER_CLOSE_NO_SLEEVE",
      lambda: blocked_case("mode_on", "SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION",
                           side="SELL", raw={"dir": "Close Long"},
                           wallet_mode="ON"))

failed = [name for name, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)), flush=True)
sys.exit(1 if failed else 0)
