#!/usr/bin/env python3
"""ENG-018 opposing-leader intake and attribution oracle.

Run with Python 3.11: python -u _archive/hl_stage2/test_eng018_opposite_leaders.py
Offline dry-run only; automatic sends and polling are disabled.
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


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(passed)))
    print("RESULT::%s_%s%s" % (name, "PASS" if passed else "FAIL", (" | " + detail) if detail and not passed else ""))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="eng018_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {
        "0xleadera": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                      "norm_base": 1000.0, "leader_equity_base": 1000.0},
        "0xleaderb": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                      "norm_base": 1000.0, "leader_equity_base": 1000.0},
    }}), encoding="utf-8")

    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True

    configs = {
        wallet: svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                        norm_base=1000.0, leader_equity_base=1000.0, enabled=True)
        for wallet in ("0xleadera", "0xleaderb")
    }

    def fill(fid: str, wallet: str, signed_delta: float, price: float, ts: int):
        side = "BUY" if signed_delta > 0 else "SELL"
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet, coin="BTC", side=side, price=price,
            size=abs(signed_delta), signed_size_delta=signed_delta, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
        )

    def engine():
        svc = svcmod.DryRunLiveCopyService()
        svc.state["leader_event_positions"] = {}
        svc.processed_ids = set()
        svc.account_net_provider = lambda coin: {
            "ok": True,
            "net": sum(float(svc.get_position(w, coin).get("signed_size") or 0.0) for w in configs),
            "source": "TEST_AUTHORITATIVE_ACCOUNT_NET",
        }
        return svc

    def rows(path):
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return list(csv.DictReader(stream))

    # Physical event intake: both opposite leaders must survive independently even when their
    # combined account target is flat. Planner/order-intent evidence is read separately below.
    svc = engine()
    a = fill("eng018-a-plus-2", "0xleadera", 2.0, 100.0, 1000)
    b = fill("eng018-b-minus-2", "0xleaderb", -2.0, 100.0, 1001)
    svc.process_fill(a, configs[a.wallet])
    svc.process_fill(b, configs[b.wallet])
    lineage = svc.state["leader_event_positions"]
    check("OPPOSITE_EVENTS_BOTH_ACCOUNTED",
          a.fill_id in svc.processed_ids and b.fill_id in svc.processed_ids
          and lineage.get("0xleadera::BTC") == 2.0 and lineage.get("0xleaderb::BTC") == -2.0,
          f"processed={sorted(svc.processed_ids)} lineage={lineage}")

    targets = svcmod.event_authorised_desired_net(
        "BTC", svc.leader_signed_by_wallet("BTC", configs), configs)
    check("PLUS2_MINUS2_TARGET_IS_ZERO",
          targets.get("ok") and abs(float(targets.get("desired_net", 1.0))) < 1e-12
          and targets.get("sleeves") == {"0xleadera": 2.0, "0xleaderb": -2.0},
          f"target={targets}")

    intents = rows(svcmod.ORDER_INTENTS_CSV)
    linked = {row.get("leader_fill_id"): row for row in intents}
    check("EACH_EVENT_HAS_ITS_OWN_PLANNER_INTENT",
          a.fill_id in linked and b.fill_id in linked
          and linked[a.fill_id].get("leader_wallet") == a.wallet
          and linked[b.fill_id].get("leader_wallet") == b.wallet,
          f"fills={list(linked)}")
    live_fills = rows(svcmod.LIVE_FILLS_CSV)
    live_by_id = {row.get("leader_fill_id"): row for row in live_fills}
    recon_by_id = {row.get("leader_fill_id"): row for row in rows(svcmod.RECONCILIATION_CSV)}
    check("OPPOSITE_EVENTS_NOT_SKIPPED_AND_ATTRIBUTED",
          a.fill_id in live_by_id and b.fill_id in live_by_id
          and live_by_id[a.fill_id].get("leader_wallet") == a.wallet
          and live_by_id[b.fill_id].get("leader_wallet") == b.wallet
          and live_by_id[a.fill_id].get("fill_status") == "DRY_RUN_FILLED"
          and live_by_id[b.fill_id].get("fill_status") == "DRY_RUN_FILLED"
          and recon_by_id.get(a.fill_id, {}).get("event") == "DRY_RUN_FILL"
          and recon_by_id.get(b.fill_id, {}).get("event") == "DRY_RUN_FILL",
          f"live={{{a.fill_id!r}: {live_by_id.get(a.fill_id)}, {b.fill_id!r}: {live_by_id.get(b.fill_id)}}} "
          f"recon={{{a.fill_id!r}: {recon_by_id.get(a.fill_id)}, {b.fill_id!r}: {recon_by_id.get(b.fill_id)}}}")

    # Close each independent sleeve at a different price to prove realized PnL follows its
    # originating leader event rather than being pooled or assigned to the latest event.
    a_close = fill("eng018-a-close-plus-2", "0xleadera", -2.0, 110.0, 1002)
    b_close = fill("eng018-b-close-minus-2", "0xleaderb", 2.0, 90.0, 1003)
    svc.process_fill(a_close, configs[a_close.wallet])
    svc.process_fill(b_close, configs[b_close.wallet])
    live_by_id = {row.get("leader_fill_id"): row for row in rows(svcmod.LIVE_FILLS_CSV)}
    check("REALIZED_PNL_STAYS_WITH_EACH_LEADER_SLEEVE",
          abs(float(live_by_id.get(a_close.fill_id, {}).get("realized_pnl") or 0.0) - 20.0) < 1e-8
          and abs(float(live_by_id.get(b_close.fill_id, {}).get("realized_pnl") or 0.0) - 20.0) < 1e-8
          and live_by_id.get(a_close.fill_id, {}).get("leader_wallet") == a_close.wallet
          and live_by_id.get(b_close.fill_id, {}).get("leader_wallet") == b_close.wallet,
          f"a={live_by_id.get(a_close.fill_id)} b={live_by_id.get(b_close.fill_id)}")

    check("NO_PHYSICAL_SEND_PATH_ACTIVITY",
          len(rows(svcmod.SEND_ATTEMPTS_CSV)) == 0 and len(rows(svcmod.WOULD_SEND_ORDERS_CSV)) > 0,
          "auto-send disabled; dry-run intent records only")

    # Unequal opposing positions prove signed aggregation is not an arithmetic-only fixture.
    svc2 = engine()
    c = fill("eng018-a-plus-3", "0xleadera", 3.0, 100.0, 2000)
    d = fill("eng018-b-minus-1", "0xleaderb", -1.0, 100.0, 2001)
    svc2.process_fill(c, configs[c.wallet])
    svc2.process_fill(d, configs[d.wallet])
    unequal = svcmod.event_authorised_desired_net(
        "BTC", svc2.leader_signed_by_wallet("BTC", configs), configs)
    intents2 = rows(svcmod.ORDER_INTENTS_CSV)
    linked2 = {row.get("leader_fill_id"): row for row in intents2}
    check("PLUS3_MINUS1_BOTH_EVENTS_ACCOUNTED",
          c.fill_id in svc2.processed_ids and d.fill_id in svc2.processed_ids
          and svc2.state["leader_event_positions"].get("0xleadera::BTC") == 3.0
          and svc2.state["leader_event_positions"].get("0xleaderb::BTC") == -1.0,
          f"processed={sorted(svc2.processed_ids)} lineage={svc2.state['leader_event_positions']}")
    check("PLUS3_MINUS1_TARGET_IS_PLUS2",
          unequal.get("ok") and abs(float(unequal.get("desired_net", 0.0)) - 2.0) < 1e-12
          and unequal.get("sleeves") == {"0xleadera": 3.0, "0xleaderb": -1.0},
          f"target={unequal}")
    check("PLUS3_MINUS1_EVENT_INTENTS_KEEP_OWNERSHIP",
          c.fill_id in linked2 and d.fill_id in linked2
          and linked2[c.fill_id].get("leader_wallet") == c.wallet
          and linked2[d.fill_id].get("leader_wallet") == d.wallet,
          f"fills={list(linked2)}")

    # Deliberately mismatch event ownership and config ownership. This must be rejected before
    # lineage, position, PnL, or planner intent can be attributed to the wrong leader.
    svc3 = engine()
    wrong = fill("eng018-wrong-owner", "0xleaderb", 1.0, 100.0, 3000)
    before_intents = len(rows(svcmod.ORDER_INTENTS_CSV))
    svc3.process_fill(wrong, configs["0xleadera"])
    mismatch_rejected = (
        wrong.fill_id not in svc3.processed_ids
        and not svc3.state["leader_event_positions"]
        and abs(float(svc3.get_position("0xleadera", "BTC").get("signed_size") or 0.0)) < 1e-12
        and len(rows(svcmod.ORDER_INTENTS_CSV)) == before_intents
    )
    check("MISMATCHED_LEADER_OWNERSHIP_REJECTED", mismatch_rejected,
          f"processed={wrong.fill_id in svc3.processed_ids} lineage={svc3.state['leader_event_positions']}")

    failed = [name for name, passed in RESULTS if not passed]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
