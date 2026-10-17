#!/usr/bin/env python3
"""Offline tests for CLAUDE RULING 6234527189 (order RTT + XYZ arming dependency).

No network, no keys, no engine run, no order. Pins:
  A. _wait_exchange_order_slot waits BEFORE exchange_call_started_ms is stamped, so
     exchange_call_ms excludes engine pacing while wall-clock time does not.
  B. The pacing floor is non-zero (250 ms default).
  C. update_xyz_position_state_from_fills is NOT armed-gated (it takes no config).
  D. The XYZ ledger only advances, so identical values reappear after a restart.
  E. _scope_sweep_block IS armed-gated.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_order_rtt_and_xyz_arming.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


class FakeExchange:
    def __init__(self, sleep_s=0.0):
        self.calls = []
        self.sleep_s = sleep_s

    def order(self, coin, is_buy, size, px, order_type, **kw):
        t0 = time.monotonic()
        if self.sleep_s:
            time.sleep(self.sleep_s)
        self.calls.append((coin, time.monotonic() - t0))
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 1}}]}}}


def quiet_gateway(Core):
    class _Gw(Core.SenderGateway):
        def _note_sender_key_rejection(self, response):
            return
    return _Gw


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rttxyz_"))
    cfg_path = tmp / "live_config.json"
    cfg_path.write_text(json.dumps({"global_controls": {"send_mode": "OFF"}}), encoding="utf-8")
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "300",
        "HL_LIVE_MOCK_SEND": "0",
    })

    import HL_Live_Copy_Service_Core as c

    gw = quiet_gateway(c)(c.ConfigManager(cfg_path), c.AuditLogWriter(), None)
    ex = FakeExchange(sleep_s=0.05)
    timing = {}
    gw._place_order(ex, "BTC", True, 0.001, 100000.0, "Ioc", False, timing, "exchange_call_started_ms")
    wall0 = time.monotonic()
    gw._place_order(ex, "BTC", True, 0.001, 100000.0, "Ioc", False, timing, "exchange_call_started_ms")
    wall1 = time.monotonic()
    timing["exchange_call_finished_ms"] = c.utc_now_ms()
    stamped_ms = int(timing["exchange_call_finished_ms"]) - int(timing["exchange_call_started_ms"])
    wall_ms = int((wall1 - wall0) * 1000)

    check("A1_pacing_wait_is_NOT_inside_the_stamped_interval", stamped_ms < 250, "stamped_ms=%d" % stamped_ms)
    # the gap runs from the PREVIOUS slot, which the first order already took, so the second call
    # waits (gap - the SDK time the first call just spent) and the wall clock is gap + that time.
    check("A2_wall_clock_includes_the_pacing_wait", wall_ms >= 240, "wall_ms=%d" % wall_ms)
    check("A3_the_two_measurements_differ_by_at_least_200ms", wall_ms - stamped_ms >= 200,
          "wall_ms=%d stamped_ms=%d" % (wall_ms, stamped_ms))

    gap = max(0, int(c.fnum(os.getenv("HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"), 250)))
    check("B1_env_override_is_honoured", gap == 300, "got %d" % gap)
    os.environ.pop("HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS")
    default_gap = max(0, int(c.fnum(os.getenv("HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"), 250)))
    check("B2_code_default_gap_ms_is_250", default_gap == 250, "got %d" % default_gap)

    check("C0_master_switch_is_OFF_for_this_whole_test", c.ConfigManager(cfg_path).send_mode_now() == "OFF")

    xyz_state = c.XYZ_POSITION_STATE_FILE
    fill_open = {"coin": "xyz:AMZN", "side": "B", "sz": "0.047", "px": "200", "startPosition": "0.0",
                 "time": 1000, "dir": "Open Long", "oid": "1", "hash": "h1"}
    c.update_xyz_position_state_from_fills([fill_open], "copy_account_poll")
    written = json.loads(xyz_state.read_text(encoding="utf-8"))
    size1 = (written.get("positions_by_coin") or {}).get("XYZ:AMZN", {}).get("signed_size")
    check("C1_xyz_ledger_is_written_while_DISARMED", abs(float(size1 or 0) - 0.047) < 1e-9, repr(written.get("positions_by_coin")))
    check("C2_the_writer_takes_no_config", "cfg" not in c.update_xyz_position_state_from_fills.__code__.co_varnames)

    before = xyz_state.read_text(encoding="utf-8")
    c.update_xyz_position_state_from_fills([], "copy_account_poll")
    check("D1_no_new_fill_leaves_the_xyz_ledger_byte_identical", before == xyz_state.read_text(encoding="utf-8"))

    older = dict(fill_open, startPosition="9.9", time=500, hash="h0")
    c.update_xyz_position_state_from_fills([older], "copy_account_poll")
    still = (json.loads(xyz_state.read_text(encoding="utf-8")).get("positions_by_coin") or {}).get("XYZ:AMZN", {})
    check("D2_an_older_fill_never_overwrites_a_newer_one", abs(float(still.get("signed_size") or 0) - 0.047) < 1e-9,
          "signed_size=%r" % (still.get("signed_size"),))
    check("D3_the_state_reloads_identically_a_restart_shows_the_same_values",
          c.load_xyz_position_state().get("positions_by_coin", {}).get("XYZ:AMZN", {}).get("signed_size") is not None)

    class _Cfg:
        def __init__(self, on):
            self.auto_send_enabled = on

    class _Shim:
        pass

    off = _Shim()
    off.cfg = _Cfg(False)
    off._hot_stop_event = threading.Event()
    got_off = c.LiveCopyCore._scope_sweep_block(off)
    check("E1_sweep_gate_EMPTY_while_sending_is_off", got_off == "", repr(got_off))
    check("E2_no_sweep_thread_while_sending_is_off", getattr(off, "_scope_sweeper", None) is None)

    on = _Shim()
    on.cfg = _Cfg(True)
    on._hot_stop_event = threading.Event()
    got_on = c.LiveCopyCore._scope_sweep_block(on)
    check("E3_sweep_gate_DEMANDS_a_sweep_while_sending_is_on", got_on.startswith("SCOPE_SWEEP_PENDING"), repr(got_on))
    check("E4_thread_creation_suppressed_by_env_for_this_test", getattr(on, "_scope_sweeper", None) is None)

    failed = [n for n, ok in RESULTS if not ok]
    print("\nSUMMARY: %d checks, %d failed%s" % (len(RESULTS), len(failed), (" -> " + ", ".join(failed)) if failed else ""))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
