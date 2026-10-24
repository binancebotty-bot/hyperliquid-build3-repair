"""Real-path self-check for the Live Copy ownership work (Codex review of 7c2db00).

Every check calls _live_audit_summary_full() / _live_audit_summary() itself; only the file and
exchange seams are faked, so a missing parameter or a mis-forwarded count shows up here. No network,
no process, no port, no orders.

Run: python test_ui_ownership_summary.py
"""
import json
import sys
import tempfile
import time
from pathlib import Path

import HL_Copy_App_SSOT as app
import ownership_classify as oc

TMP = Path(tempfile.mkdtemp(prefix="ui_own_"))
MISMATCH_TEXT = "records and the exchange disagree"
LEFT_OVERS = (("XYZ:ORCL", 0.058), ("XYZ:PLTR", 0.186), ("XYZ:MSTR", -0.378), ("XYZ:LLY", -0.024))


def _now():
    return int(time.time() * 1000)


def _run_full(overrides_path, position_rows, mm_rows):
    """Call the real summary with every file/exchange seam faked; returns its payload."""
    integrity = {"status": "GREEN", "available": True, "reasons": [], "counts": {},
                 "position_assignment": {"exchange_manual_mismatches": [dict(r) for r in mm_rows]}}
    state = {"service_state": {"last_state_write_ms": _now()}, "core_state": {}, "active_state": {},
             "available": True, "checkpoint_available": False}
    patches = {
        "_live_order_intents_path": lambda: TMP / "order_intents.csv",
        "_load_manual_live_positions": lambda: {},
        "_load_recent_send_attempts": lambda limit=20: [],
        "_load_send_attempt_counts": lambda: {},
        "_fetch_exchange_account_snapshot": lambda max_age_sec=15.0: {"ok": False, "available": False, "positions_by_coin": {}},
        "_manual_live_summary": lambda *a, **k: {},
        "_follower_account_value_safe": lambda: {"ok": False},
        "_append_exchange_history": lambda *a, **k: None,
        "_load_live_ws_health": lambda: {},
        "_load_clean_core_status": lambda: state,
        "_load_live_integrity_status": lambda: integrity,
        "_load_recent_reconciliation_rows": lambda limit=500: ([], 0),
        "_load_live_copy_config": lambda: {},
        "_master_switch_on": lambda cfg: False,
        "_load_recent_live_fills": lambda limit=500: [],
        "_build_live_wallet_rows": lambda *a, **k: [],
        "_build_real_copy_positions": lambda *a, **k: [dict(r) for r in position_rows],
        "_load_resting_withdraw_pending": lambda: [],
        "_public_account_address": lambda: "0x" + "a" * 40,
    }
    saved = {n: getattr(app, n) for n in patches}
    saved_own = oc.OWNERSHIP_OVERRIDES_FILE
    saved_fetch = oc.fetch_builder_dex_positions
    try:
        for n, fn in patches.items():
            setattr(app, n, fn)
        oc.OWNERSHIP_OVERRIDES_FILE = Path(overrides_path)
        oc.fetch_builder_dex_positions = lambda acct, post, max_dexes=64: {
            "ok": True, "status": "OK", "detail": "", "positions": [], "scopes": []}
        app._BUILDER_DEX_CACHE.clear()
        return app._live_audit_summary_full()
    finally:
        for n, fn in saved.items():
            setattr(app, n, fn)
        oc.OWNERSHIP_OVERRIDES_FILE = saved_own
        oc.fetch_builder_dex_positions = saved_fetch


def _write(name, rows):
    p = TMP / name
    p.write_text(json.dumps({"positions": rows}), encoding="utf-8")
    return p


TWO = _write("two.json", [{"class": "USER_OWNED", "coin": "ETH", "reason": "placed by hand"},
                          {"class": "KNOWN_UNMANAGED", "coin": "XYZ:ORCL", "reason": "empty book, no bids"}])
POS_TWO = [{"row_type": "OWNED_COPY", "coin": "ETH", "signed_size": 1.0},
           {"row_type": "ACCOUNT_LEVEL_ONLY", "coin": "XYZ:ORCL", "signed_size": None, "dex": "xyz"}]
SEEDED = Path(oc.__file__).resolve().parent / "ownership_overrides.json"


def _health(out):
    """The health payload the summary exposes (top level, or inside live_top_status)."""
    return out.get("health") or (out.get("live_top_status") or {}).get("health") or {}


def check_summary_completes():
    """(a) the _build_live_top_status call site no longer raises TypeError."""
    out = _run_full(TWO, POS_TWO, [])
    assert isinstance(_health(out), dict) and _health(out), out.keys()
    assert isinstance(out.get("live_top_status"), dict), out
    assert isinstance(app._live_audit_summary(), dict)
    print("(a) _live_audit_summary_full + _live_audit_summary complete, no TypeError")


def check_counts_reach_health():
    """(b) USER_OWNED and KNOWN_UNMANAGED counts are non-zero in the health payload."""
    h = _health(_run_full(TWO, POS_TWO, []))
    assert h["user_owned_count"] == 1, h
    assert h["known_unmanaged_count"] == 1, h
    assert h["unknown_ownership_count"] == 0, h
    print("(b) health counts user_owned=%s known_unmanaged=%s unknown=%s"
          % (h["user_owned_count"], h["known_unmanaged_count"], h["unknown_ownership_count"]))


def check_per_record_suppression():
    """(c) the override coin's mismatch is quiet; any other coin's mismatch is still red."""
    quiet = _health(_run_full(TWO, POS_TWO, [{"coin": "XYZ:ORCL", "manual": 0.058}]))
    assert quiet["level"] == "green", quiet
    assert MISMATCH_TEXT not in quiet["text"], quiet
    loud = _health(_run_full(TWO, POS_TWO, [{"coin": "XYZ:ORCL", "manual": 0.058},
                                            {"coin": "DOGE", "manual": 12.0}]))
    assert loud["level"] == "red", loud
    assert MISMATCH_TEXT in loud["text"], loud
    print("(c) override coin quiet (green); unrelated DOGE mismatch still red")


def check_unknown_drives_red():
    """(d) one UNKNOWN item alone is red."""
    h = _health(_run_full(TWO, POS_TWO + [{"row_type": "OWNED_COPY", "coin": "WIF", "signed_size": 3.0}], []))
    assert h["unknown_ownership_count"] == 1, h
    assert h["level"] == "red" and "unknown ownership" in h["text"], h
    print("(d) UNKNOWN alone -> red:", h["text"][:64])


def check_seeded_leftovers():
    """(e) the four seeded leftovers load from the shipped file as KNOWN_UNMANAGED, never ENGINE."""
    loaded = oc.load_ownership_overrides(SEEDED)
    for coin, _ in LEFT_OVERS:
        assert loaded.get(coin, {}).get("class") == "KNOWN_UNMANAGED", (coin, loaded.get(coin))
    rows = [{"row_type": "ACCOUNT_LEVEL_ONLY", "coin": c, "signed_size": s, "dex": "xyz"} for c, s in LEFT_OVERS]
    h = _health(_run_full(SEEDED, rows, []))
    assert h["known_unmanaged_count"] == 4, h
    assert h["user_owned_count"] == 0 and h["unknown_ownership_count"] == 0, h
    print("(e) seeded leftovers: known_unmanaged=%s user_owned=%s unknown=%s"
          % (h["known_unmanaged_count"], h["user_owned_count"], h["unknown_ownership_count"]))


def check_absent_file_degrades():
    """(f) no ownership_overrides.json -> everything UNKNOWN, no exception."""
    missing = TMP / "nope" / "ownership_overrides.json"
    assert oc.load_ownership_overrides(missing) == {}
    h = _health(_run_full(missing, POS_TWO, []))
    assert h["unknown_ownership_count"] == 2, h
    assert h["user_owned_count"] == 0 and h["known_unmanaged_count"] == 0, h
    assert h["level"] == "red" and "unknown ownership" in h["text"], h
    print("(f) absent file -> 2 UNKNOWN, red, no exception")


if __name__ == "__main__":
    checks = (check_summary_completes, check_counts_reach_health, check_per_record_suppression,
              check_unknown_drives_red, check_seeded_leftovers, check_absent_file_degrades)
    for fn in checks:
        fn()
    print("ALL UI OWNERSHIP SUMMARY CHECKS PASSED (%d/%d)" % (len(checks), len(checks)))
    sys.exit(0)
