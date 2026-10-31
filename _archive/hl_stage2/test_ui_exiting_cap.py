#!/usr/bin/env python3
"""CC-1 M4-UI: executable tests for delegated remove, Core-derived caps, and no second ledger.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_ui_exiting_cap.py
"""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
import HL_Copy_App_SSOT as U

RESULTS = []
def check(name, test):
    try:
        ok = bool(test())
        reason = ""
    except Exception as exc:
        ok, reason = False, repr(exc)
    RESULTS.append(ok)
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + reason[:180]) if reason else ""))

W1, W2 = "0x" + "a"*40, "0x" + "b"*40

def ledger(nonflat=True, valid=True):
    return ({"schema": "manual_live_positions.v2",
             "by_wallet": {W1: {"BTC": {"signed_size": 0.25 if nonflat else 0.0}}}}
            if valid else {})

def config():
    return {"wallets": {W1: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed"},
                        W2: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed"}},
            "archived_wallets": {}, "global_controls": {"max_total_live_exposure_usd": 900}}

with tempfile.TemporaryDirectory(prefix="ui_exiting_") as tmp:
    state = Path(tmp)/"live_service_state.json"
    with patch.object(U, "LIVE_COPY_SERVICE_STATE_FILE", state):
        state.write_text(json.dumps({"wallet_modes_active": {"LIVE": 12, "CLO": 2, "OFF": 1},
                                     "active_wallets": 10,
                                     "effective_global_controls": {"max_total_live_exposure_usd": 900}}))
        check("CORE_CONFIGURED_VS_APPLIED_LIVE_12_10", lambda:
              U._core_control_state()["configured_live"] == 12 and
              U._core_control_state()["applied_live"] == 10)
        check("CORE_WS_CAP_IS_TEN", lambda: U._core_control_state()["ws_cap"] == 10)
        check("CORE_PUBLISHED_GLOBAL_EXPOSURE_CAP", lambda:
              U._core_control_state()["global_exposure_cap_usd"] == 900)
        state.unlink()
        check("MISSING_CORE_STATE_NEVER_FAKES_COUNTS", lambda:
              U._core_control_state()["applied_live"] is None and
              U._core_control_state()["global_exposure_cap_usd"] is None)

    check("CORE_LEDGER_NONFLAT_EXPLICIT", lambda: U._core_wallet_nonflat(ledger(), W1) is True)
    check("CORE_LEDGER_FLAT_EXPLICIT", lambda: U._core_wallet_nonflat(ledger(False), W1) is False)
    check("UNKNOWN_LEDGER_FAILS_CLOSED", lambda: U._core_wallet_nonflat({}, W1) is None)
    check("MISSING_WALLET_KEY_IS_UNKNOWN_NOT_FLAT", lambda:
          U._core_wallet_nonflat({"schema": "manual_live_positions.v2", "by_wallet": {}}, W1) is None)
    check("INVALID_LEDGER_SIZE_FAILS_CLOSED", lambda:
          U._core_wallet_nonflat({"schema": "manual_live_positions.v2",
              "by_wallet": {W1: {"BTC": {"signed_size": "NaN"}}}}, W1) is None)

    active = config()
    check("REMOVAL_NONFLAT_STAYS_FOLLOWED_CLO_EXITING", lambda:
          (U._apply_remove_wallet_command(active, W1, ledger()) is True) and
          active["wallets"][W1]["mode"] == "CLO" and
          active["wallets"][W1]["enabled"] is True and
          active["wallets"][W1]["exit_requested"] is True and
          W1 not in active["archived_wallets"])
    check("EXITING_OPEN_MUST_NOT_BE_DROPPED", lambda:
          U._finalise_exiting_wallets(active, ledger()) is False and W1 in active["wallets"])
    check("EXITING_FLAT_DROPS_OUT_OF_FOLLOWED_SET", lambda:
          U._finalise_exiting_wallets(active, ledger(False)) is True and
          W1 not in active["wallets"] and W1 in active["archived_wallets"])
    check("FLAT_REMOVAL_ARCHIVES_IMMEDIATELY", lambda:
          (lambda c: (U._apply_remove_wallet_command(c, W1, ledger(False)) is True and
                      W1 not in c["wallets"] and W1 in c["archived_wallets"]))(config()))
    check("UNKNOWN_LEDGER_DOES_NOT_ARCHIVE_ACTIVE_WALLET", lambda:
          (lambda c: (U._apply_remove_wallet_command(c, W1, {}) is True and
                      c["wallets"][W1]["mode"] == "CLO" and
                      W1 not in c["archived_wallets"]))(config()))
    check("EXITING_RENDERS_AND_CORE_STATE_WIRED", lambda:
          all(token in U.render_live_copy_control_panel() for token in (
              "EXITING", "configured LIVE", "applied LIVE", "Global cap", "lcCoreControl")))
    check("ENGINE_LEDGER_NEVER_WRITTEN_BY_DISPLAY", lambda:
          (lambda c: (U._core_wallet_nonflat(ledger(), W1) is True and c == config()))(config()))


    def get_does_not_write():
        pending = config()
        U._apply_remove_wallet_command(pending, W1, ledger())
        saved = []
        with patch.object(U, "_load_live_copy_config", return_value=pending), \
             patch.object(U, "_load_manual_live_positions", return_value=ledger(False)), \
             patch.object(U, "_save_live_copy_config", side_effect=lambda c: saved.append(c)):
            U.get_live_config()
        return not saved and W1 in pending["wallets"]
    check("GET_LIVE_CONFIG_IS_READ_ONLY", get_does_not_write)

    def post_authorized_finalise():
        pending = config()
        U._apply_remove_wallet_command(pending, W1, ledger())
        saved = []
        with patch.object(U, "_load_live_copy_config", return_value=pending), \
             patch.object(U, "_load_manual_live_positions", return_value=ledger(False)), \
             patch.object(U, "_save_live_copy_config", side_effect=lambda c: saved.append(c)):
            result = U.finalise_exiting_wallets()
        return (result.status_code == 200 and len(saved) == 1
                and W1 not in pending["wallets"] and W1 in pending["archived_wallets"])
    check("AUTHORIZED_POST_FINALISES_ONLY_PENDING_FLAT", post_authorized_finalise)

    def no_pending_no_write():
        ordinary = config()
        saved = []
        with patch.object(U, "_load_live_copy_config", return_value=ordinary), \
             patch.object(U, "_load_manual_live_positions", return_value=ledger(False)), \
             patch.object(U, "_save_live_copy_config", side_effect=lambda c: saved.append(c)):
            result = U.finalise_exiting_wallets()
        return result.status_code == 200 and not saved
    check("FINALISE_POST_NO_PENDING_DOES_NOT_WRITE", no_pending_no_write)

    def bad_mode_blocks_save():
        path = Path(tmp) / "fault_live_config.json"
        original = json.dumps({"wallets": {W1: {"mode": "BOGUS", "enabled": True}},
                               "archived_wallets": {}, "global_controls": {}})
        path.write_text(original)
        with patch.object(U, "LIVE_COPY_CONFIG_FILE", path):
            response = U.get_live_config()
            read_fault = response.status_code == 409 and b"CONFIG_FAULT_UNKNOWN_WALLET_MODE" in response.body
            save_fault = False
            try:
                U._save_live_copy_config(json.loads(original))
            except ValueError:
                save_fault = True
            return read_fault and save_fault and path.read_text() == original
    check("UNKNOWN_MODE_RED_FAULT_ZERO_FILE_OVERWRITE", bad_mode_blocks_save)

    def bad_json_blocks_save():
        path = Path(tmp) / "broken_live_config.json"
        path.write_text("{not json")
        with patch.object(U, "LIVE_COPY_CONFIG_FILE", path):
            response = U.get_live_config()
            return (response.status_code == 409 and
                    b"CONFIG_FAULT_READ_" in response.body and path.read_text() == "{not json")
    check("MALFORMED_CONFIG_FAULT_NOT_EMPTY_ROSTER", bad_json_blocks_save)

    def no_unrelated_mode_repair():
        raw = {"wallets": {W1: {"mode": "LIVE", "enabled": True}, W2: {"mode": "OFF", "enabled": False}}}
        before = json.dumps(raw, sort_keys=True)
        U.repair_live_config_consistency(raw)
        return json.dumps(raw, sort_keys=True) == before
    check("VALIDATE_WITHOUT_REWRITING_OTHER_WALLETS", no_unrelated_mode_repair)

print("TOTAL=%d FAILED=%d" % (len(RESULTS), RESULTS.count(False)))
sys.exit(1 if False in RESULTS else 0)
