"""ENG-INV-13: restart/recovery creates ZERO new trade authority.

Runner: plain `python test_engine_inv_13.py` (pytest is unavailable here).
Offline only: no keys, no exchange calls, no engine start/stop.
"""
from __future__ import annotations

import ast
import dataclasses
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILS, TOTAL = [], [0]


def check(name, cond, detail=""):
    TOTAL[0] += 1
    if cond:
        print("PASS:", name, (":: " + str(detail)) if detail else "")
    else:
        FAILS.append(name)
        print("FAIL:", name, (":: " + str(detail)) if detail else "")


def body_of(src, header):
    m = re.search(header, src)
    if not m:
        return ""
    body = src[m.start():]
    nxt = re.search(r"\n    def |\ndef ", body[1:])
    return body[: nxt.start() + 1] if nxt else body


def main():
    tmp = Path(tempfile.mkdtemp(prefix="inv13_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "mainnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_DISABLE_NETWORK_REFRESH": "1",
    })
    LEADER, FOLLOWER = "0x" + "a" * 40, "0x" + "e" * 40
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import HL_Live_Copy_Service_Core as c
    c.USER_WALLET = FOLLOWER  # fetch_snapshot is stubbed below, so no network is touched

    # Offline seams: any code path that reaches for the network raises at once instead of
    # blocking. Without this a mutation that builds a catch-up intent merely HANGS, and a
    # hang is not a clean RED.
    def _offline(*a, **k):
        raise RuntimeError("offline test: no network")
    c.EXPOSURE_FETCHER = _offline
    c.LEADER_FETCHER = _offline
    c.MIDS_FETCHER = _offline
    c.requests = type("OfflineRequests", (), {"post": staticmethod(_offline)})()

    def config(auto=False):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": auto, "global_controls": {},
            "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed",
                                 "fixed_notional": 1000}},
        })

    # ---- CENSUS ---------------------------------------------------------------------
    core_src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    svc_src = (HERE / "HL_Live_Copy_Service.py").read_text(encoding="utf-8-sig")
    handover = next(p for p in [HERE, *HERE.parents]
                    if (p / "TESTNET_RUN_HANDOVER.md").exists()) / "TESTNET_RUN_HANDOVER.md"
    handover = handover.read_text(encoding="utf-8-sig")
    check("C1_CORE_IS_THE_SHIPPING_ENGINE",
          "Engine base moved to the real Core engine" in handover
          and "HL_Live_Copy_Service_Core.py" in handover)
    # Real call sites only: the other text hits are docstring/comment mentions.
    tree = ast.parse(core_src)
    order_sites = [n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "order" and getattr(n.func.value, "id", "") == "exchange"]
    check("C2_EXACTLY_ONE_WIRE_ORDER_SITE_IN_CORE", order_sites == [2715], str(order_sites))
    SENDS = ("_place_order(", "_send_real(", "send_if_allowed(", "exchange.order(", ".order(")
    observers = ["compare_snapshot", "audit_orphan_attribution", "repair_flat_ledger_only_positions",
                 "repair_recovery_copy_fills", "refresh_asset_universe", "warm_symbol_cache",
                 "warm_exchange_client", "fetch_snapshot", "write_live_integrity_status"]
    reach = []
    for fn in observers:
        b = body_of(core_src, r"\n    def " + fn + r"\(")
        hits = [s for s in SENDS if s in b]
        if hits:
            reach.append(fn + "->" + str(hits))
    check("C3_NO_RECOVERY_OR_OBSERVER_FUNCTION_REACHES_A_SEND", not reach, "; ".join(reach))
    # C3b: nothing on the recovery path may BUILD its own SenderGateway — that is what makes
    # the per-instance tripwires below sufficient rather than merely convenient.
    builders = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in observers:
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id in {"SenderGateway", "LiveCopyCore"}):
                builders.append(node.name + "->" + sub.func.id)
    check("C3B_RECOVERY_BUILDS_NO_OWN_SENDER", not builders, "; ".join(builders))
    wb = body_of(core_src, r"\n    def write\(self, summary: CycleSummary")
    check("C4_STATE_WRITER_CANNOT_SEND", bool(wb) and not [s for s in SENDS if s in wb])
    check("C5_SUPERSEDED_SERVICE_IS_SEPARATE", "exchange.order(" in svc_src,
          "old dry-run service keeps its own order site; Core does not import it")

    # ---- BEHAVIOUR: restart/recovery over deliberately stale local state --------------
    config()
    stale = {"schema": "manual_live_positions.v1.wallet_sleeves",
             "by_wallet": {LEADER: {"BTC": {"sleeve_id": LEADER + "::BTC", "leader_wallet": LEADER,
                                            "coin": "BTC", "direction": "LONG", "signed_size": 2.0,
                                            "avg_entry_px": 100.0, "last_copy_fill_id": "cf-1"}}},
             "by_coin_net": {}}
    c.atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, stale)
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, {"live_start_ms": 1})
    c.atomic_write_json(c.SERVICE_STATE_FILE, {})
    fresh = {"created_at": c.utc_now_iso(), "created_at_ms": c.utc_now_ms(), "raw": {},
             "positions_by_coin": {"ETH": 1.0}}  # disagrees: BTC flat, unowned ETH long
    touched = []

    def arm(core):
        core.reconciler.fetch_snapshot = lambda: (fresh, "SNAPSHOT_OK")
        # Tripwire on the instance; C3b proves recovery constructs no gateway of its own.
        core.sender._place_order = lambda *a, **k: touched.append("_place_order") or {}
        core.sender._send_real = lambda *a, **k: touched.append("_send_real") or (False, "POISON", {})
        core.sender.send_if_allowed = lambda *a, **k: touched.append("send_if_allowed") or (False, "POISON")

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    arm(core)
    check("B0_STALE_LEDGER_LOADED", abs(core.ledger.wallet_coin_position(LEADER, "BTC") - 2.0) < 1e-9,
          str(core.ledger.wallet_coin_position(LEADER, "BTC")))
    rb, sb, ib = (len(c.read_csv_rows(p)) for p in
                  (c.RECONCILIATION_CSV, c.SEND_ATTEMPTS_CSV, c.ORDER_INTENTS_CSV))
    summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=True)
    rows = c.read_csv_rows(c.RECONCILIATION_CSV)[rb:]
    mism = [r for r in rows if r.get("status") == "LEDGER_EXCHANGE_NET_MISMATCH"]
    check("B1_RECOVERY_PRODUCED_RECONCILIATION_ROWS", bool(mism), str([r.get("status") for r in rows]))
    check("B2_BOTH_DISAGREEING_COINS_REPORTED", {r.get("coin") for r in mism} >= {"BTC", "ETH"},
          str(sorted({r.get("coin") for r in mism})))
    check("B3_ZERO_ORDER_CALLS", touched == [], str(touched))
    check("B4_NO_SEND_AUTHORITY_CREATED",
          len(c.read_csv_rows(c.SEND_ATTEMPTS_CSV)) == sb
          and len(c.read_csv_rows(c.ORDER_INTENTS_CSV)) == ib and not core.intents_by_id)
    check("B5_LEDGER_NOT_REWRITTEN_BY_RECONCILIATION",
          abs(core.ledger.wallet_coin_position(LEADER, "BTC") - 2.0) < 1e-9)
    check("B6_NO_SWALLOWED_FAILURE", summary.ok and summary.fatal_errors == 0,
          "ok=" + str(summary.ok) + " fatal=" + str(summary.fatal_errors))

    touched.clear()
    core2 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    arm(core2)
    s2 = core2.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=True)
    check("B7_RESTART_PROCESS_SENDS_NOTHING", touched == [] and s2.fatal_errors == 0,
          str(touched) + " fatal=" + str(s2.fatal_errors))

    # SILENCE CONTROL: nothing to reconcile -> silent, still zero sends
    core3 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core3.reconciler.fetch_snapshot = lambda: ({"positions_by_coin": {"BTC": 2.0}}, "SNAPSHOT_OK")
    core3.sender._place_order = lambda *a, **k: touched.append("_place_order") or {}
    core3.sender._send_real = lambda *a, **k: touched.append("_send_real") or (False, "POISON", {})
    core3.sender.send_if_allowed = lambda *a, **k: touched.append("send_if_allowed") or (False, "POISON")
    touched.clear()
    rb3 = len(c.read_csv_rows(c.RECONCILIATION_CSV))
    core3.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=True)
    statuses3 = [r.get("status") for r in c.read_csv_rows(c.RECONCILIATION_CSV)[rb3:]]
    check("B8_MATCHING_RECOVERY_IS_SILENT", statuses3 == ["EXCHANGE_MANUAL_NET_MATCH"], str(statuses3))
    check("B9_MATCHING_RECOVERY_SENDS_NOTHING", touched == [], str(touched))

    # PENDING-INTENT CONTROL: recovery may not arm or send a blocked intent
    blocked = dataclasses.replace(
        c.IntentBuilder(c.ConfigManager(), core.ledger).build(
            c.LeaderFill("inv13-pending", LEADER, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST")),
        decision="BELOW_MIN_NOTIONAL_BLOCKED")
    check("B10_PENDING_INTENT_STARTS_UNSENDABLE", not blocked.send_allowed, blocked.decision)
    core.intents_by_id[blocked.intent_id] = blocked
    touched.clear()
    core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=True)
    check("B11_RECOVERY_DOES_NOT_ARM_A_PENDING_INTENT",
          not core.intents_by_id[blocked.intent_id].send_allowed,
          core.intents_by_id[blocked.intent_id].decision)
    check("B12_RECOVERY_DOES_NOT_SEND_A_PENDING_INTENT", touched == [], str(touched))

    # CONTROL: the normal (non-recovery) path still reaches send authority
    config(auto=True)
    coreN = c.LiveCopyCore(source_csv=tmp / "none.csv")
    reached = []
    coreN.sender.send_if_allowed = lambda intent, reason="": (
        reached.append(intent.decision) or (False, "SEND_NOT_ATTEMPTED_TEST"))
    pb = len(c.read_csv_rows(c.ORDER_INTENTS_CSV))
    coreN._process_leader_fill(c.LeaderFill("inv13-live-1", LEADER, "BTC", "BUY", 100.0, 1.0,
                                           c.utc_now_ms() + 5000, "WS_CAPTURED"), None, "")
    check("B13_NORMAL_CYCLE_STILL_REACHES_THE_SENDER", bool(reached)
          and len(c.read_csv_rows(c.ORDER_INTENTS_CSV)) > pb,
          "decision=" + str(reached) + " intents+="
          + str(len(c.read_csv_rows(c.ORDER_INTENTS_CSV)) - pb))

    print("RESULT::ENG_INV_13 TOTAL=" + str(TOTAL[0]) + " FAILED=" + str(len(FAILS)))
    if FAILS:
        print("FAILED_CHECKS::" + ",".join(FAILS))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
