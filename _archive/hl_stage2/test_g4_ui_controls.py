#!/usr/bin/env python3
"""G4 UI lifecycle/control tests (review item B) -- IN-PROCESS, no LIVE orders.

Proves the restored Build3 UI's controls either AFFECT the repaired engine's truth or FAIL CLOSED:
  - wallet mode OFF / CLOSE_ONLY written by the UI change the engine's effective authority
    (the engine reads the UI's wallet_gate.json via a read-only bridge that can only REDUCE it)
  - unknown modes are rejected 400 BAD_MODE (fail closed)
  - the account/USER wallet can never be switched ON (fail closed)
  - reset-safe and snapshot endpoints touch no engine truth and grant no authority

Run: python test_g4_ui_controls.py     # RESULT:: markers, exit 0/1
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="g4ui_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {
        "0xfixed": {"mode": "LIVE", "enabled": True, "copy_mode": "fixed",
                    "norm_base": 100.0, "leader_equity_base": 1000.0, "fixed_notional": 1000.0},
    }}), encoding="utf-8")

    gate_path = HERE / "wallet_gate.json"           # exactly where the restored UI writes it
    saved_gate = gate_path.read_text(encoding="utf-8") if gate_path.exists() else None
    os.environ["HL_LIVE_WALLET_GATE_FILE"] = str(gate_path)

    import HL_Live_Copy_Service as svcmod
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    svcmod.TEST_INJECTION_ENABLED = True
    client = TestClient(ui.app)

    FIX = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                  fixed_notional=1000.0, norm_base=100.0,
                                  leader_equity_base=1000.0, enabled=True)
    PX = 100.0

    def fill(fid, wallet, coin, side, price, size, ts, delta=None):
        d = delta if delta is not None else (size if side.upper() == "BUY" else -size)
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=coin.upper(), side=side.upper(),
            price=price, size=abs(size), signed_size_delta=d, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
        )

    def engine():
        svc = svcmod.DryRunLiveCopyService()
        svc.state["leader_event_positions"] = {}
        svc.processed_ids = set()
        svc.account_net_provider = lambda coin: {"ok": True, "net": 0.0, "source": "TEST"}
        return svc

    try:
        # ---------- B1: UI control EXECUTES and persists its truth ----------
        r = client.post("/api/set-wallet-mode", json={"wallet": "0xfixed", "mode": "OFF"})
        gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {}
        check("B_SET_WALLET_MODE_EXECUTES_AND_PERSISTS",
              r.status_code == 200 and r.json().get("ok") and str(gate.get("0xfixed", {}).get("mode")).upper() == "OFF",
              f"status={r.status_code} body={r.text[:120]}")

        # ---------- B2: that UI truth AFFECTS the repaired engine ----------
        e = engine()
        seen = e.wallet_gate_mode("0xfixed")
        e.process_fill(fill("u1", "0xfixed", "BTC", "BUY", PX, 10.0, 1000), FIX)
        pos = float(e.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
        check("B_UI_OFF_AFFECTS_ENGINE_TRUTH",
              seen == "OFF" and abs(pos) < 1e-12 and int(e.state["counters"].get("fills_skipped_off", 0)) >= 1,
              f"gate={seen} pos={pos} counters={e.state['counters']}")

        # ---------- B3: CLOSE_ONLY maps to the engine's reduce/exit-only semantics ----------
        client.post("/api/set-wallet-mode", json={"wallet": "0xfixed", "mode": "CLOSE_ONLY"})
        e2 = engine()
        seen2 = e2.wallet_gate_mode("0xfixed")
        e2.process_fill(fill("u2", "0xfixed", "BTC", "BUY", PX, 10.0, 2000), FIX)   # would be a new entry
        pos2 = float(e2.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
        blocked = int(e2.state["counters"].get("fills_skipped_clo_entry", 0))
        check("B_UI_CLOSE_ONLY_BLOCKS_NEW_ENTRIES",
              seen2 == "CLOSE_ONLY" and abs(pos2) < 1e-12 and blocked >= 1,
              f"gate={seen2} pos={pos2} clo_blocked={blocked}")

        # ---------- B4: unknown/unsupported control FAILS CLOSED ----------
        before_gate = gate_path.read_text(encoding="utf-8")
        r4 = client.post("/api/set-wallet-mode", json={"wallet": "0xfixed", "mode": "EMERGENCY_STOP"})
        after_gate = gate_path.read_text(encoding="utf-8")
        r4b = client.post("/api/set-all-modes", json={"mode": "PAUSED"})
        check("B_UNKNOWN_MODE_FAILS_CLOSED",
              r4.status_code == 400 and r4.json().get("error") == "BAD_MODE"
              and r4b.status_code == 400 and before_gate == after_gate,
              f"set={r4.status_code} all={r4b.status_code}")

        # ---------- B5: the account/USER wallet can never be switched ON ----------
        r5 = client.post("/api/set-wallet-mode", json={"wallet": ui.USER_WALLET, "mode": "ON"})
        gate5 = json.loads(gate_path.read_text(encoding="utf-8"))
        check("B_USER_WALLET_NEVER_ENABLES",
              r5.status_code == 200 and str(gate5.get(ui.USER_WALLET, {}).get("mode")).upper() == "OFF",
              f"status={r5.status_code} gate={gate5.get(ui.USER_WALLET)}")

        # ---------- B6: RESET_SAFE removes derived files, touches NO engine truth ----------
        e3 = engine()
        e3.process_fill(fill("u3", "0xfixed", "BTC", "BUY", PX, 10.0, 3000), FIX)
        e3.persist()
        state_before = (tmp / "live_service_state.json").read_text(encoding="utf-8")
        r6 = client.post("/api/reset-app-history")
        state_after = (tmp / "live_service_state.json").read_text(encoding="utf-8")
        check("B_RESET_SAFE_DOES_NOT_TOUCH_ENGINE_TRUTH",
              r6.status_code == 200 and r6.json().get("ok") and state_before == state_after,
              f"status={r6.status_code}")

        # ---------- B7: snapshot grants no authority ----------
        ledger_before = json.dumps(e3.state.get("fixed_sleeves"), sort_keys=True)
        r7 = client.post("/api/snapshot")
        ledger_after = json.dumps(e3.state.get("fixed_sleeves"), sort_keys=True)
        check("B_SNAPSHOT_GRANTS_NO_AUTHORITY",
              r7.status_code == 200 and ledger_before == ledger_after, f"status={r7.status_code}")
    finally:
        if saved_gate is None:
            try:
                gate_path.unlink()
            except Exception:
                pass
        else:
            gate_path.write_text(saved_gate, encoding="utf-8")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
