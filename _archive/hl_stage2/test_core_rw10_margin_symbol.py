#!/usr/bin/env python3
"""rw10: the background margin-mode lane resolves a coin through the SAME resolver as the send path (kFLOKI, builder-DEX
xyz:SPCX), and a coin that truly cannot be resolved raises no per-cycle ValueError row: one rate-limited, named error row
per coin, margin mode left unset, nothing sent. Run (from _archive/hl_stage2): env -u HL_LIVE_AUDIT_DIR python test_core_rw10_margin_symbol.py"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def _try(g, coin):
    try:
        g._exchange_client_for_coin(coin)
    except Exception as exc:
        return str(exc)
    return ""


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rw10_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_DISABLE_NETWORK_REFRESH": "1"})
    import HL_Live_Copy_Service_Core as c

    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l.json"))
    g._asset_snapshot_loaded = True
    g._meta_fetched = g._core_meta_fetched = True
    g._builder_meta_fetched["xyz"] = True
    g._meta_cache = {
        "KFLOKI": {"canonical_coin": "kFLOKI", "szDecimals": 0, "symbol_source": "core_meta", "perp_dex": ""},
        "XYZ:SPCX": {"canonical_coin": "XYZ:SPCX", "sdk_coin": "xyz:SPCX", "szDecimals": 2, "symbol_source": "builder_meta",
                     "perp_dex": "xyz", "perp_dexs": ["", "xyz"]},
    }
    calls = []

    class Fake:
        def update_leverage(self, lev, name, is_cross=True):
            calls.append(name)
            return {"status": "ok"}

    g._get_exchange_client = lambda *a, **k: Fake()
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    for coin in ("KFLOKI", "kFLOKI", "XYZ:SPCX", "xyz:SPCX"):
        g.schedule_margin_mode_setup(coin)
        g.wait_margin_mode_setup(5.0)
    check("R1_RESOLVABLE_COINS_GET_MARGIN_MODE_SET", sorted(calls) == sorted(["kFLOKI", "xyz:SPCX"]), str(calls))

    del calls[:]
    for _ in range(6):  # a new fill per cycle re-queues a coin whose setup never succeeded
        g.schedule_margin_mode_setup("XYZ:BOT")
        g.wait_margin_mode_setup(5.0)
    rows = []
    if Path(c.ERRORS_CSV).exists():
        with open(c.ERRORS_CSV, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("context", "").startswith("margin_mode")]
    check("R2_UNRESOLVED_COIN_NO_EXCHANGE_CALL", calls == [], str(calls))
    check("R3_UNRESOLVED_COIN_ONE_ERROR_ROW_NOT_ONE_PER_CYCLE", len(rows) == 1, "rows=%d" % len(rows))
    check("R4_NO_VALUEERROR_AND_NAMED_REASON", bool(rows) and rows[0].get("error_type") != "ValueError"
          and "MARGIN_MODE_UNSET" in rows[0].get("message", "") and "XYZ:BOT" in rows[0].get("message", ""), str(rows[:1]))
    check("R5_UNRESOLVED_COIN_STAYS_UNSET", "XYZ:BOT" not in g.__dict__.get("_mm_seen", set()))
    msg = _try(g, "XYZ:BOT")
    check("R6_NEUTRAL_HELPER_MESSAGE", bool(msg) and "for cancel" not in msg, msg)

    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(1 for _n, ok in RESULTS if not ok)))
    sys.exit(1 if any(not ok for _n, ok in RESULTS) else 0)


main()
