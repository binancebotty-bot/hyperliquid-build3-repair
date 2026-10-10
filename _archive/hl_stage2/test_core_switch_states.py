#!/usr/bin/env python3
"""C3 - three-state sending switch, mock-send evidence (spec: issue #3 comment 6095815151).

Boss 08:44Z: "OFF means off, CLOSE only reduces positions, ON is full."
The spec asks for a global `global_controls.send_mode` with values OFF / CLOSE / ON:

  * OFF   - nothing of the engine's is sent, convergence closes included.
  * CLOSE - only reductions/reduces go out; ENTRY and ADD (missed-entry resting limits and top-ups
            included) are refused with ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY. Resting ENTRY limits are
            withdrawn exactly as on a switch to OFF; resting CLOSE limits stay.
  * ON    - full copying.
  * send_mode absent must keep today's meaning: auto_send_enabled false -> OFF, true -> ON.
  * ConfigManager.master_switch_now() returns True for CLOSE and ON, False for OFF.

These tests run against the engine's real send gate (`SenderGateway.send_if_allowed`) with the engine's
own mock-send path (HL_LIVE_MOCK_SEND=1): no exchange is touched and no order is placed. The
ownership gate, leader-reduced check and any real exchange client are stubbed out so the ONLY thing
under test is the sending switch. A check that FAILs is a FINDING about the engine, not a reason to
weaken the test (task C3: "If the engine fails a test, report it as a finding with the failing output").

Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python -u test_core_switch_states.py
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
SENT = "MOCK_ORDER_SENT"
CLOSE_BLOCKED = "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="c3switch_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MOCK_SEND": "1", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    os.environ.pop("HL_LIVE_AUTO_SEND_ENABLED", None)
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

    def write_cfg(body: dict) -> None:
        body.setdefault("global_controls", {})
        body.setdefault("wallets", {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}})
        c.atomic_write_json(c.LIVE_CONFIG_FILE, body)

    def config(auto=None, send_mode=None, mode="ON") -> None:
        gc = {}
        if send_mode is not None:
            gc["send_mode"] = send_mode
        body = {"global_controls": gc}
        if auto is not None:
            body["auto_send_enabled"] = auto
        write_cfg(body)

    def gateway():
        """A send gate with ownership/leader-reduced stubbed out: the switch is the only variable."""
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "led.json"))
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        return g

    def intent(decision: str, lifecycle: str, side: str = "BUY", size: float = 1.0, before: float = 0.0,
               notes_extra: str = "") -> "c.Intent":
        fill = c.LeaderFill("f1", A, "BTC", side, 100.0, size, c.utc_now_ms(), "TEST")
        return c.Intent("i1", fill, side, size, size * 100.0, "ON", "fixed", decision, lifecycle,
                        "sleeve:%s:BTC" % A, "", "FLAT", before, before, False, False, c.utc_now_ms(),
                        "lifecycle=%s;%s" % (lifecycle, notes_extra))

    def send(g, decision, lifecycle, side="BUY", size=1.0, before=0.0, notes_extra=""):
        return g.send_if_allowed(intent(decision, lifecycle, side, size, before, notes_extra))

    # ---- S0: the three-state config surface ----------------------------------------------------------
    # spec: master_switch_now() is True for CLOSE and ON, False for OFF; send_mode absent keeps the
    # legacy auto_send_enabled mapping.
    write_cfg({"global_controls": {"send_mode": "CLOSE"}})          # auto_send_enabled deliberately absent
    close_armed = c.ConfigManager().master_switch_now()
    config(auto=True, send_mode="OFF")
    off_armed = c.ConfigManager().master_switch_now()
    config(auto=True, send_mode="ON")
    on_armed = c.ConfigManager().master_switch_now()
    check("S0_THREE_STATE_SWITCH_RECOGNISED", close_armed is True and off_armed is False and on_armed is True,
          "send_mode CLOSE=%s (want True), OFF=%s (want False), ON=%s (want True)" % (close_armed, off_armed, on_armed))

    # ---- S1: send_mode absent keeps today's meaning --------------------------------------------------
    config(auto=False)
    legacy_off = c.ConfigManager().master_switch_now()
    config(auto=True)
    legacy_on = c.ConfigManager().master_switch_now()
    check("S1_ABSENT_SEND_MODE_KEEPS_LEGACY_MAPPING", legacy_off is False and legacy_on is True,
          "auto=False -> %s, auto=True -> %s" % (legacy_off, legacy_on))

    # ---- S2: OFF sends nothing (entry, exit, add) ----------------------------------------------------
    config(auto=True, send_mode="OFF")
    ent = send(gateway(), "ENTRY_ALLOWED", "ENTRY", "BUY", 1.0, 0.0)
    exi = send(gateway(), "EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0)
    add = send(gateway(), "ENTRY_ALLOWED", "ADD", "BUY", 0.1, 1.0)
    check("S2_SEND_MODE_OFF_SENDS_NOTHING", ent[0] is False and exi[0] is False and add[0] is False,
          "entry=%s exit=%s add=%s" % (ent, exi, add))

    # ---- S3: OFF also stops convergence closes -------------------------------------------------------
    config(auto=True, send_mode="OFF")
    conv = send(gateway(), "EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0, notes_extra="converge_reason=LEADER_FLAT;")
    check("S3_SEND_MODE_OFF_STOPS_CONVERGENCE_CLOSE", conv[0] is False, "convergence exit=%s" % (conv,))

    # ---- S4: CLOSE blocks ENTRY with the spec's reason -----------------------------------------------
    config(auto=True, send_mode="CLOSE")
    ent = send(gateway(), "ENTRY_ALLOWED", "ENTRY", "BUY", 1.0, 0.0)
    check("S4_CLOSE_BLOCKS_ENTRY", ent == (False, CLOSE_BLOCKED), "entry=%s want (False, %s)" % (ent, CLOSE_BLOCKED))

    # ---- S5: CLOSE blocks ADD with the spec's reason -------------------------------------------------
    config(auto=True, send_mode="CLOSE")
    add = send(gateway(), "ENTRY_ALLOWED", "ADD", "BUY", 0.1, 1.0)
    check("S5_CLOSE_BLOCKS_ADD", add == (False, CLOSE_BLOCKED), "add=%s want (False, %s)" % (add, CLOSE_BLOCKED))

    # ---- S6: CLOSE still sends reductions (EXIT and REDUCE) -------------------------------------------
    config(auto=True, send_mode="CLOSE")
    exi = send(gateway(), "EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0)
    red = send(gateway(), "EXIT_ALLOWED", "REDUCE", "SELL", 0.4, 1.0)
    check("S6_CLOSE_SENDS_REDUCTIONS_ONLY", exi[1] == SENT and red[1] == SENT, "exit=%s reduce=%s" % (exi, red))

    # ---- S7: CLOSE does not block convergence closes --------------------------------------------------
    config(auto=True, send_mode="CLOSE")
    conv = send(gateway(), "EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0, notes_extra="converge_reason=LEADER_FLAT;")
    check("S7_CLOSE_SENDS_CONVERGENCE_CLOSE", conv[1] == SENT, "convergence exit=%s" % (conv,))

    # ---- S8: ON sends all ----------------------------------------------------------------------------
    config(auto=True, send_mode="ON")
    ent = send(gateway(), "ENTRY_ALLOWED", "ENTRY", "BUY", 1.0, 0.0)
    exi = send(gateway(), "EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0)
    check("S8_SEND_MODE_ON_SENDS_ALL", ent[1] == SENT and exi[1] == SENT, "entry=%s exit=%s" % (ent, exi))

    # ---- S9: resting ENTRY limits are withdrawn on a switch to CLOSE (spec item 2) --------------------
    # Structural: the cycle withdraws resting entries when sending is off; the spec requires the same on
    # a switch to CLOSE (resting close limits stay). The condition must be CLOSE-aware, not `not master_enabled`.
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    # strictly: the engine must treat CLOSE like OFF for the resting-entry withdrawal
    close_aware = bool(re.search(r"withdraw_resting_entries_sending_off", src)) and bool(
        re.search(r"send_mode\s*==\s*[\"']CLOSE[\"']", src))
    check("S9_RESTING_ENTRY_LIMITS_WITHDRAWN_ON_CLOSE", close_aware,
          "engine has no send_mode==CLOSE branch withdrawing resting entry limits (only `if not master_enabled`)")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
