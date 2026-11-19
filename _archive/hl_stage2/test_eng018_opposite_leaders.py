#!/usr/bin/env python3
"""ENG-018: opposing leader sleeves remain distinct while desired net aggregates.

Pure/offline: calls the same event-authorised aggregation used by the G2 suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Live_Copy_Service as svcmod

_passes = 0
_fails = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passes, _fails
    if condition:
        _passes += 1
    else:
        _fails += 1
    print(f"{'PASS' if condition else 'FAIL'}: {name}" + (f" :: {detail}" if detail else ""))


def main() -> None:
    configs = {
        wallet: svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                        norm_base=100.0, leader_equity_base=1000.0, enabled=True)
        for wallet in ("0xw1", "0xw2")
    }

    def run_case(label: str, leader_sizes: dict[str, float], expected_net: float) -> None:
        agg = svcmod.event_authorised_desired_net("BTC", leader_sizes, configs)
        sleeves = agg.get("sleeves", {})
        check(f"{label}: both leader entries retained", agg.get("ok") and len(sleeves) == 2,
              f"entries={len(sleeves)} sleeves={sleeves}")
        check(f"{label}: desired_net equals arithmetic sum {expected_net:+.1f}",
              agg.get("ok") and abs(float(agg.get("desired_net", float('nan'))) - expected_net) < 1e-12,
              f"desired_net={agg.get('desired_net')}")
        check(f"{label}: each attributed sleeve keeps its signed size",
              all(wallet in sleeves and abs(float(sleeves[wallet]) - size * 0.1) < 1e-12
                  for wallet, size in leader_sizes.items()),
              f"sleeves={sleeves}")

    print("=== Opposing leaders +2 / -2 ===")
    run_case("opposing +2/-2", {"0xw1": 20.0, "0xw2": -20.0}, 0.0)
    print("=== Opposing leaders +3 / -1 ===")
    run_case("opposing +3/-1", {"0xw1": 30.0, "0xw2": -10.0}, 2.0)
    print("=== Same-side control +1 / +1 ===")
    run_case("same-side +1/+1", {"0xw1": 10.0, "0xw2": 10.0}, 2.0)

    print(f"TOTAL={_passes + _fails} FAILED={_fails}")
    raise SystemExit(1 if _fails else 0)


if __name__ == "__main__":
    main()
