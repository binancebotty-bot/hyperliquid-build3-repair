from copy import deepcopy

import pytest

import HL_Copy_App_SSOT as ui
import HL_Live_Copy_Service_Core as engine


def _cases():
    cases = []
    autos = (None, True, False, "true")
    shapes = (
        ("missing global_controls", {}),
        ("global_controls without send_mode", {"global_controls": {}}),
        ("blank send_mode", {"global_controls": {"send_mode": ""}}),
        ("null send_mode", {"global_controls": {"send_mode": None}}),
        ("whitespace send_mode", {"global_controls": {"send_mode": "   "}}),
        ("invalid send_mode", {"global_controls": {"send_mode": "BANANA"}}),
    )
    for shape, base in shapes:
        for auto in autos:
            config = deepcopy(base)
            if auto is not None:
                config["auto_send_enabled"] = auto
            cases.append((f"{shape}; auto_send_enabled={auto!r}", config, "OFF"))
    for raw, expected in (
        ("OFF", "OFF"),
        ("ON", "ON"),
        ("CLOSE", "CLOSE"),
        ("CLOSE ONLY", "CLOSE"),
        ("close-only", "CLOSE"),
        ("close_only", "CLOSE"),
        ("clo", "CLOSE"),
    ):
        cases.append((f"valid send_mode {raw!r}", {"global_controls": {"send_mode": raw}}, expected))
    return cases


CASES = _cases()


@pytest.mark.parametrize("name,config,expected", CASES, ids=[case[0] for case in CASES])
def test_engine_and_ui_send_mode_resolvers_agree(name, config, expected):
    engine_mode = engine.ConfigManager._send_mode_of(config)
    ui_mode = ui._send_mode(config)

    assert engine_mode == expected, f"{name}: engine resolved {engine_mode!r}"
    assert ui_mode == expected, f"{name}: UI resolved {ui_mode!r}"
    assert engine_mode == ui_mode, f"{name}: engine/UI mismatch"


def main():
    failures = []
    results = []
    for name, config, expected in CASES:
        engine_mode = engine.ConfigManager._send_mode_of(config)
        ui_mode = ui._send_mode(config)
        ok = engine_mode == expected and ui_mode == expected and engine_mode == ui_mode
        results.append((name, ok))
        if not ok:
            failures.append(
                f"{name}: expected {expected!r}, engine={engine_mode!r}, UI={ui_mode!r}"
            )
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"TOTAL={len(CASES)} FAILED={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
