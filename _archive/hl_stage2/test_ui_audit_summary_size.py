#!/usr/bin/env python3
"""UI1: /api/live-audit-summary must stay small (run 5: 81 MB / 12 s, dashboard blank).

Synthetic state with 250k ids per list and 5,000 execution rows goes through the real _slim_ui_payload and
the real row cap. Asserts size, counts and that every small field the page reads survives.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_ui_audit_summary_size.py   (RESULT:: markers, exit 0/1)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


import HL_Copy_App_SSOT as ui  # noqa: E402

have_new = hasattr(ui, "_slim_ui_payload")
check("UI1_SLIM_FUNCTION_EXISTS", have_new)
if have_new:
    ids = [f"leader-fill-{i:08d}-abcdef0123456789" for i in range(250_000)]
    state = {"processed_leader_fill_ids": ids, "processed_copy_fill_ids": ids[:20_000], "ws_status": "OK",
             "resting_entry_limits": 3, "wallet_modes_active": {"0xabc": "ON"}, "send_block_reason": "",
             "small_list": ["a", "b"]}
    rows = [{"time": f"t{i}", "coin": "BTC", "side": "BUY", "status": "ORDER_FILLED", "fill_bps": 1.5}
            for i in range(5000)]
    full = {"clean_core_status": {"service_state": state, "core_state": dict(state)},
            "core_service_state": state, "execution_quality_rows": rows,
            "execution_quality_summary": {"filled_count": 5000}}
    before = len(json.dumps(full))
    orig_full = getattr(ui, "_live_audit_summary_full", None)
    check("UI1_FULL_BUILDER_EXISTS", orig_full is not None)
    ui._live_audit_summary_full = lambda: json.loads(json.dumps(full))
    out = ui._live_audit_summary()
    after = len(json.dumps(out))
    check("UI1_UNDER_1MB", after < 1_000_000, "after=%d before=%d" % (after, before))
    ss = out["core_service_state"]
    check("UI1_ID_LISTS_BECOME_COUNTS", ss.get("processed_leader_fill_ids_count") == 250_000
          and ss.get("processed_copy_fill_ids_count") == 20_000 and "processed_leader_fill_ids" not in ss)
    check("UI1_NESTED_COPY_ALSO_SLIMMED", out["clean_core_status"]["service_state"].get("processed_leader_fill_ids_count") == 250_000)
    check("UI1_SMALL_FIELDS_KEPT", ss.get("ws_status") == "OK" and ss.get("resting_entry_limits") == 3
          and ss.get("wallet_modes_active") == {"0xabc": "ON"} and ss.get("small_list") == ["a", "b"])
    check("UI1_EXEC_ROWS_CAPPED_WITH_TOTAL", len(out["execution_quality_rows"]) == ui._UI_EXEC_ROWS_CAP
          and out.get("execution_quality_rows_total") == 5000)
    check("UI1_EXEC_SUMMARY_UNTOUCHED", out["execution_quality_summary"] == {"filled_count": 5000})
    check("UI1_NEWEST_ROWS_KEPT", out["execution_quality_rows"][0]["time"] == "t0")

total = len(RESULTS)
failed = sum(1 for _n, ok in RESULTS if not ok)
print("TOTAL=%d FAILED=%d" % (total, failed))
sys.exit(1 if failed else 0)
