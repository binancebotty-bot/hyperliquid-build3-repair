"""Regression for a held DEX disappearing from perpDexs after an engine restart."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import MethodType, SimpleNamespace

CORE_DIR = Path(__file__).resolve().parents[1] / "_archive" / "hl_stage2"
sys.path.insert(0, str(CORE_DIR))
import HL_Live_Copy_Service_Core as core  # noqa: E402


def main() -> None:
    results = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append(bool(condition))
        print(f"RESULT::{name}_{'PASS' if condition else 'FAIL'}" + (f" | {detail}" if not condition else ""))

    with tempfile.TemporaryDirectory(prefix="i08_dex_scope_") as tmp:
        tmp_path = Path(tmp)
        account = "0x" + "a" * 40
        now_ms = core.utc_now_ms()
        cache_path = tmp_path / "scope_dex_cache.json"
        cache_path.write_text(json.dumps({
            "account": account,
            "dex": {"xyz": [now_ms - 1_000_000, ["XYZ:GOLD"]]},
        }), encoding="utf-8")

        old_env = {key: os.environ.get(key) for key in (
            "HL_FOLLOWER_DEXES", "HL_LIVE_SCOPE_SWEEP_THREAD", "HL_LIVE_MOCK_SEND",
        )}
        os.environ.pop("HL_FOLLOWER_DEXES", None)
        os.environ["HL_LIVE_SCOPE_SWEEP_THREAD"] = "0"
        os.environ.pop("HL_LIVE_MOCK_SEND", None)
        old_core_state = core.CORE_RUNTIME_STATE_FILE
        old_exposure_fetcher = core.EXPOSURE_FETCHER
        old_user_wallet = core.USER_WALLET
        try:
            core.CORE_RUNTIME_STATE_FILE = tmp_path / "clean_core_runtime_state.json"
            core.USER_WALLET = account
            core._LEARNED_DEXES.clear()  # process restart: only the persisted sweep cache knows xyz held a position
            core.EXPOSURE_FETCHER = lambda payload: [] if payload["type"] == "perpDexs" else {
                "assetPositions": [], "marginSummary": {"accountValue": "0"},
            }

            engine = SimpleNamespace(
                _hot_stop_event=threading.Event(), _scope_cache_loaded=False, _scope_dex_cache={},
                _scope_enum_count=0, _scope_sweep_ok={"ok": True, "ms": now_ms},
                _scope_sweep_last={"ok": True, "ms": now_ms}, _scope_fail_streak=0,
                _scope_sweeper=None, cfg=SimpleNamespace(auto_send_enabled=True),
            )
            engine.run_scope_sweep = MethodType(core.LiveCopyCore.run_scope_sweep, engine)
            engine._scope_sweep_note = MethodType(core.LiveCopyCore._scope_sweep_note, engine)
            engine._scope_sweep_block = MethodType(core.LiveCopyCore._scope_sweep_block, engine)

            result = engine.run_scope_sweep()
            check("I08_VANISHED_HELD_DEX_FAILS_CLOSED",
                  not result.get("ok") and engine._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING"),
                  str(result))
            check("I08_VANISHED_HELD_DEX_REMAINS_IN_CACHE",
                  "xyz" in engine._scope_dex_cache and engine._scope_dex_cache["xyz"][1] == ("XYZ:GOLD",),
                  str(engine._scope_dex_cache))
        finally:
            core.CORE_RUNTIME_STATE_FILE = old_core_state
            core.EXPOSURE_FETCHER = old_exposure_fetcher
            core.USER_WALLET = old_user_wallet
            core._LEARNED_DEXES.clear()
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    failed = sum(not result for result in results)
    print(f"TOTAL={len(results)} PASSED={len(results) - failed} FAILED={failed}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
