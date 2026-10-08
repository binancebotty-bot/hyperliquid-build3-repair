#!/usr/bin/env python3
"""G4-C1 tests: operator global control max_order_notional_usd enforced for FIXED entries.

Exercises the REAL in-process POST /api/global-controls, then the REAL engine process_fill/planner
via the SAME live_config.json the UI writes (no new store, no second writer).

Required behaviour under test:
  - over-cap NEW entry -> fail closed with an explicit status and ZERO executable/sent intent
  - within-cap -> passes only pre-existing gates
  - zero / unset -> behaviour unchanged
  - invalid nonzero values do not become authority
  - CLOSE / reduce-only NEVER blocked by the entry-size cap
  - unrelated inventory unchanged

Run: python test_g4_order_cap.py      # RESULT:: markers, exit 0/1. No network, no LIVE orders.
"""
from __future__ import annotations

import csv
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
    tmp = Path(tempfile.mkdtemp(prefix="g4cap_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"
    cfg_path = tmp / "live_config.json"
    cfg_path.write_text(json.dumps({
        "wallets": {
            "0xfixed": {"mode": "LIVE", "enabled": True, "copy_mode": "fixed",
                        "norm_base": 100.0, "leader_equity_base": 1000.0, "fixed_notional": 1000.0},
            "0xprop": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                       "norm_base": 100.0, "leader_equity_base": 1000.0},
        },
        "global_controls": {"max_order_notional_usd": 0.0},
    }), encoding="utf-8")

    import HL_Live_Copy_Service as svcmod
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    svcmod.TEST_INJECTION_ENABLED = True

    # make the UI write exactly the file the engine reads (production topology, temp-isolated)
    ui.LIVE_COPY_CONFIG_FILE = cfg_path
    client = TestClient(ui.app)

    FIX = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                  fixed_notional=1000.0, norm_base=100.0,
                                  leader_equity_base=1000.0, enabled=True)
    PROP = svcmod.LiveWalletConfig(wallet="0xprop", mode="LIVE", copy_mode="proportional",
                                   norm_base=100.0, leader_equity_base=1000.0, enabled=True)
    PX = 100.0

    def fill(fid, wallet, coin, side, price, size, ts, delta=None):
        d = delta if delta is not None else (size if side.upper() == "BUY" else -size)
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=coin.upper(), side=side.upper(),
            price=price, size=abs(size), signed_size_delta=d, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
        )

    def engine(wallets=("0xfixed",)):
        s = svcmod.DryRunLiveCopyService()
        s.state["leader_event_positions"] = {}
        s.processed_ids = set()

        def provider(coin):
            total = sum(float(s.get_position(w, coin).get("signed_size") or 0.0) for w in wallets)
            return {"ok": True, "net": total, "source": "TEST"}
        s.account_net_provider = provider
        return s

    def intents(wallet="0xfixed"):
        if not svcmod.ORDER_INTENTS_CSV.exists():
            return []
        with svcmod.ORDER_INTENTS_CSV.open(newline="", encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f) if str(r.get("leader_wallet", "")).lower() == wallet]
        return rows[-1:]   # audit CSV is append-only and shared across engines in this file

    def would_sends(wallet="0xfixed"):
        if not svcmod.WOULD_SEND_ORDERS_CSV.exists():
            return []
        with svcmod.WOULD_SEND_ORDERS_CSV.open(newline="", encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f) if str(r.get("leader_wallet", "")).lower() == wallet]
        return rows[-1:]

    intended_notional = 1000.0   # fixed_notional 1000 at price 100 -> 10 shares

    # ---------- 1) the REAL UI POST persists the control into the SAME config the engine reads ----------
    r = client.post("/api/global-controls", json={"max_order_notional_usd": 500.0})
    persisted = json.loads(cfg_path.read_text(encoding="utf-8")).get("global_controls", {})
    check("C1_UI_POST_PERSISTS_MAX_ORDER_NOTIONAL",
          r.status_code == 200 and r.json().get("ok")
          and abs(float(persisted.get("max_order_notional_usd") or 0.0) - 500.0) < 1e-9,
          f"status={r.status_code} persisted={persisted}")

    # ---------- 2) over-cap NEW entry fails closed: explicit status, ZERO executable intent ----------
    e1 = engine()
    check("C1_ENGINE_READS_SAME_SOURCE", abs(e1.global_order_cap() - 500.0) < 1e-9, f"cap={e1.global_order_cap()}")
    e1.process_fill(fill("c1", "0xfixed", "BTC", "BUY", PX, 10.0, 1000), FIX)
    rows = intents()
    pos = float(e1.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    check("C1_OVER_CAP_ENTRY_BLOCKED_FAIL_CLOSED",
          len(rows) == 1
          and rows[0].get("status") == "BLOCKED_GLOBAL_MAX_ORDER_NOTIONAL"
          and rows[0].get("execution_decision") == "BLOCKED_GLOBAL_MAX_ORDER_NOTIONAL"
          and rows[0].get("decision_reason") == "GLOBAL_MAX_ORDER_NOTIONAL_EXCEEDED"
          and abs(pos) < 1e-12,
          f"row_status={rows[0].get('status') if rows else None} pos={pos}")
    check("C1_OVER_CAP_WRITES_ZERO_EXECUTABLE_INTENT",
          len(would_sends()) == 0 and int(e1.state["counters"].get("entries_blocked_global_max_order_notional", 0)) >= 1,
          f"would_send={len(would_sends())}")

    # ---------- 3) within-cap passes the pre-existing gates ----------
    client.post("/api/global-controls", json={"max_order_notional_usd": 2000.0})
    e2 = engine()
    e2.process_fill(fill("c2", "0xfixed", "BTC", "BUY", PX, 10.0, 1000), FIX)
    rows2 = intents()
    pos2 = float(e2.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    check("C1_WITHIN_CAP_PASSES_EXISTING_GATES",
          len(rows2) == 1 and str(rows2[0].get("status")) == "DRY_RUN_FILLED"
          and abs(pos2 - 10.0) < 1e-9
          and "BLOCKED" not in str(rows2[0].get("execution_decision")),
          f"status={rows2[0].get('status') if rows2 else None} pos={pos2}")

    # ---------- 4) zero / unset -> unchanged ----------
    client.post("/api/global-controls", json={"max_order_notional_usd": 0.0})
    e3 = engine()
    check("C1_ZERO_CAP_IS_OFF", abs(e3.global_order_cap()) < 1e-12, f"cap={e3.global_order_cap()}")
    e3.process_fill(fill("c3", "0xfixed", "BTC", "BUY", PX, 10.0, 1000), FIX)
    rows3 = intents()
    pos3 = float(e3.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    check("C1_ZERO_CAP_ENTRY_UNCHANGED",
          len(rows3) == 1 and str(rows3[0].get("status")) == "DRY_RUN_FILLED" and abs(pos3 - 10.0) < 1e-9,
          f"status={rows3[0].get('status') if rows3 else None} pos={pos3}")

    # ---------- 5) invalid nonzero value never becomes authority ----------
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    raw.setdefault("global_controls", {})["max_order_notional_usd"] = "not-a-number"
    cfg_path.write_text(json.dumps(raw), encoding="utf-8")
    check("C1_NON_NUMERIC_CAP_NOT_AUTHORITY", abs(engine().global_order_cap()) < 1e-12)
    raw["global_controls"]["max_order_notional_usd"] = -25.0
    cfg_path.write_text(json.dumps(raw), encoding="utf-8")
    check("C1_NEGATIVE_CAP_NOT_AUTHORITY", abs(engine().global_order_cap()) < 1e-12)

    # ---------- 6) CLOSE / reduce-only NEVER blocked by the entry cap ----------
    # seed a real follower position at cap 0, then tighten the cap hard and REDUCE.
    client.post("/api/global-controls", json={"max_order_notional_usd": 0.0})
    e4 = engine()
    e4.process_fill(fill("d1", "0xfixed", "BTC", "BUY", PX, 10.0, 1000), FIX)          # open 10 shares
    seeded = float(e4.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    client.post("/api/global-controls", json={"max_order_notional_usd": 50.0})          # absurdly small cap
    e4.process_fill(fill("d2", "0xfixed", "BTC", "SELL", PX, 5.0, 2000, delta=-5.0), FIX)  # reduce 50%
    reduced = float(e4.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    e4.process_fill(fill("d3", "0xfixed", "BTC", "SELL", PX, 5.0, 3000, delta=-5.0), FIX)  # close to flat
    flat = float(e4.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    check("C1_REDUCE_AND_CLOSE_NEVER_BLOCKED_BY_ENTRY_CAP",
          abs(seeded - 10.0) < 1e-9 and abs(reduced - 5.0) < 1e-9 and abs(flat) < 1e-12,
          f"seeded={seeded} reduced={reduced} flat={flat}")

    # ---------- 7) unrelated inventory unchanged while entries are cap-blocked ----------
    client.post("/api/global-controls", json={"max_order_notional_usd": 100.0})
    e5 = engine(("0xfixed", "0xprop"))
    e5.process_fill(fill("p1", "0xprop", "BTC", "BUY", PX, 5.0, 100), PROP)
    prop_before = float(e5.get_position("0xprop", "BTC").get("signed_size") or 0.0)
    e5.process_fill(fill("c9", "0xfixed", "BTC", "BUY", PX, 10.0, 200), FIX)   # cap-blocked entry
    prop_after = float(e5.get_position("0xprop", "BTC").get("signed_size") or 0.0)
    fixed_pos = float(e5.get_position("0xfixed", "BTC").get("signed_size") or 0.0)
    check("C1_UNRELATED_INVENTORY_UNCHANGED",
          prop_before > 0 and abs(prop_after - prop_before) < 1e-9 and abs(fixed_pos) < 1e-12,
          f"prop {prop_before}->{prop_after} fixed={fixed_pos}")

    # ---------- 8) exactly one physical exchange order site preserved ----------
    src = Path(svcmod.__file__).read_text(encoding="utf-8", errors="replace")
    sites = [ln for ln in src.splitlines() if ".order(" in ln and "exchange" in ln.lower()]
    check("C1_SINGLE_EXCHANGE_ORDER_SITE", len(sites) == 1, f"sites={len(sites)}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
