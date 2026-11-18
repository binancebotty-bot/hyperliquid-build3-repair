#!/usr/bin/env python3
"""Gap 7 (plan check 18 Nov, Boss OD-10): entry tolerance default is 20 bps (0.2 %), and the UI shows the value the
engine uses. Gap 6 (E1): max_diff_pct is ignored by the engine and is not shown on any UI control.

G7_1 engine default with no saved Global Controls = 20 bps.
G7_2 UI (Global Controls view) with no saved value shows 0.2 %, the same as the engine.
G7_3 a saved 0.5 % shows 0.5 % in the UI and reads back as 50 bps in the engine.
G6_1 max_diff_pct is in ENGINE_IGNORED_WALLET_KEYS and has no UI field (nothing to remove or relabel).

Run: python test_core_gap7_entry_tolerance_default.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

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
    tmp = Path(tempfile.mkdtemp(prefix="gap7_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Live_Copy_Service_Core as c
    import HL_Copy_App_SSOT as ui

    class Cfg(c.ConfigManager):
        def __init__(self, gc):
            self._gc = gc
        @property
        def global_controls(self):
            return self._gc

    check("G7_1_ENGINE_DEFAULT_20_BPS", Cfg({}).marketable_bps() == 20.0, str(Cfg({}).marketable_bps()))
    shown = ui._global_controls_for_ui({}).get("marketable_slippage_pct")
    check("G7_2_UI_SHOWS_ENGINE_DEFAULT", shown is not None and abs(float(shown) - 0.2) < 1e-9, str(shown))
    ui_val = ui._global_controls_for_ui({"marketable_slippage_pct": 0.5}).get("marketable_slippage_pct")
    eng = Cfg({"marketable_slippage_pct": 0.5}).marketable_bps()
    check("G7_3_SAVED_VALUE_SAME_IN_UI_AND_ENGINE", abs(float(ui_val) - 0.5) < 1e-9 and abs(eng - 50.0) < 1e-9,
          f"ui={ui_val} engine_bps={eng}")
    check("G6_1_MAX_DIFF_PCT_NOT_APPLIED_AND_NOT_IN_UI",
          "max_diff_pct" in ui.ENGINE_IGNORED_WALLET_KEYS
          and Path(ui.__file__).read_text(encoding="utf-8").count("max_diff_pct") == 1,
          "expected exactly one mention in SSOT: the ignored-key list")

    failed = [n for n, ok in RESULTS if not ok]
    print("RESULT::SUMMARY_%d_PASS_%d_FAIL" % (len(RESULTS) - len(failed), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
