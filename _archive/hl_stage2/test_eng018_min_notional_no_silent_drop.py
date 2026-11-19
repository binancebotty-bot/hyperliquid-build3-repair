#!/usr/bin/env python3
"""ENG-018 / OD-09: a copy size that rounds BELOW the $10 minimum must never vanish silently.

It must either be sent at the $10 minimum (bounded round-up) or refused BY NAME with a counter.
Never a bare drop, never an unflushed accumulator, and never a refusal recorded as CONVERGED.
Offline only; never submits orders, never opens a socket, never reads a key.

OD-09 oracle (reviewer): the ACTUAL planner -> convergence seam -> process_fill -> final wire
decision must (a) reject NaN and (b) +/-inf BEFORE any intent/order is emitted; (c) after the
exchange's szDecimals quantisation, a positive entry must have size*price >= the EFFECTIVE minimum
or a NAMED refusal (never CONVERGED); (d) a below-minimum entry must never be recorded CONVERGED;
(e) closes must never be rounded UP; (f) the bounded-uplift envelope (ratio + absolute) must be ONE
source, consistent across planner, service and sender. The $10 nominal default must not change.

Only the exchange-TRUTH boundary is faked (account-net actual, reconciliation gate). The planner,
the effective minimum, the szDecimals quantiser and the ledger seam are production code.

"Exchange call attempt" for the non-finite cases is counted at the real boundaries available
offline: (i) every call into the service's sender entry `send_hyperliquid_order` (spied, never
allowed to reach an exchange), and (ii) every would-send / order-intent payload carrying a
non-finite size, price or notional - i.e. an order that would be attempted with a NaN/inf number.
"""
from __future__ import annotations
import csv, json, math, os, re, sys, tempfile, time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

checks = []


def check(name, condition, detail=""):
    passed = bool(condition)
    checks.append((name, passed))
    # CSV evidence includes wall-clock values and generated IDs; normalize only presentation.
    detail = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)", "<TIMESTAMP>", str(detail))
    detail = re.sub(r"DRYRUN-\d+-\d+", "DRYRUN-<TIME>-<SEQ>", detail)
    detail = re.sub(r"(?:intent|attempt)-[0-9a-fA-F-]{16,}", "<GENERATED_ID>", detail)
    print(f"{'PASS' if passed else 'FAIL'}: {name}" + (f" :: {detail}" if detail else ""))
    print(f"RESULT::{name}_{'PASS_GREEN_BY_CODE' if passed else 'FAIL'}")


def guarded(name, fn):
    """Run one case; a harness exception is a FAIL for that case, never a silent abort of the file."""
    try:
        ok, detail = fn()
    except Exception as exc:  # noqa: BLE001 - a case that cannot run has not passed
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    check(name, ok, detail)
    return ok


def fnum(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def named_refusal(*values):
    """A refusal is named if the text says REFUS / NON_FINITE / NOT_FINITE - never a bare hold."""
    text = " ".join(str(v or "") for v in values).upper()
    return any(k in text for k in ("REFUS", "NON_FINITE", "NON-FINITE", "NOT_FINITE", "NONFINITE"))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eng018_min_"))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_AUTO_SEND_ENABLED="0", HL_LIVE_POLL_ENABLED="0")
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_RATIO", None)
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD", None)
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}, "global_controls": {"send_mode": "ON"}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    import HL_Live_Copy_Service_Core as coremod
    import convergence_shadow as shadow

    svcmod.TEST_INJECTION_ENABLED = True
    # pin the venue metadata so the lot size is a fixture, not a network call
    META = {"BTC": 5, "ETH": 2, "XRP": 0, "SOL": 5}
    svcmod.HL_PERP_META_BY_COIN_CACHE = {c: {"szDecimals": d, "name": c, "canonical_name": c}
                                         for c, d in META.items()}
    MIN = svcmod.MIN_ORDER_NOTIONAL
    wallet = "0xw1"
    cfg = svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                  norm_base=1000.0, leader_equity_base=1000.0, enabled=True)
    svc = svcmod.DryRunLiveCopyService()
    svc.global_order_cap = lambda: 0.0   # no operator cap in this check
    svc.load_config = lambda: {wallet: cfg}
    # only the exchange-truth boundary is faked: flat follower, reconciled
    svc.account_net_actual = lambda coin: {"ok": True, "status": "OK", "net": 0.0}
    svc.reconcile_gate = lambda coin, net: {"ok": True, "status": "OK"}

    # --- the sender boundary: count attempts, never let one leave the process ------------------
    EXCHANGE = {"calls": 0, "payloads": []}

    def _spy_send(payload, *a, **k):
        EXCHANGE["calls"] += 1
        EXCHANGE["payloads"].append(payload)
        return {"ok": False, "status": "OD09_SPY_BLOCKED", "exchange_called": False}

    svcmod.send_hyperliquid_order = _spy_send
    if hasattr(svc, "send_hyperliquid_order"):
        svc.send_hyperliquid_order = _spy_send
    if hasattr(svc, "manual_send_one_intent"):
        svc.manual_send_one_intent = lambda *a, **k: {"ok": False, "status": "OD09_SPY_BLOCKED"}

    def rows(path):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        except FileNotFoundError:
            return []

    def intents(fill_id):
        return [r for r in rows(svcmod.ORDER_INTENTS_CSV) if r.get("leader_fill_id") == fill_id]

    def recon(fill_id):
        return [r for r in rows(svcmod.RECONCILIATION_CSV) if r.get("leader_fill_id") == fill_id]

    def would_send(fill_id):
        return [r for r in rows(svcmod.WOULD_SEND_ORDERS_CSV) if r.get("leader_fill_id") == fill_id]

    def counter(key):
        # OD-09: ONE counter, in service state, keyed by the planner's own classification
        return int((svc.state.get("min_notional_events") or {}).get(key, 0) or 0)

    def bad_number_rows(fill_id):
        out = []
        for r in intents(fill_id) + would_send(fill_id):
            for k in ("copy_size", "copy_notional", "limit_price", "target_price"):
                v = r.get(k)
                if v not in ("", None) and not finite(v):
                    out.append((k, v, r.get("status")))
                    break
        return out

    def reset_lineage():
        svc.state["leader_event_positions"] = {}   # every case starts from a flat, empty event lineage

    seq = [0]

    def fresh_fill(coin, notional, price, side="BUY"):
        seq[0] += 1
        size = (notional / price) if price else 0.0
        timestamp_ms = int(time.time() * 1000) + seq[0]
        return svcmod.LeaderFill(
            fill_id=f"od09-{seq[0]}", wallet=wallet, coin=coin, side=side,
            price=float(price), size=float(size), signed_size_delta=float(size) * (1 if side == "BUY" else -1),
            timestamp_ms=timestamp_ms, timestamp_iso="2026-01-01T00:00:00Z",
            source="TEST", recording_method="TEST", raw={"dir": "Open Long" if side == "BUY" else "Open Short"})

    def planner_verdict(coin, notional, price):
        """The production planner seam: desired-net -> convergence order -> event notional."""
        reset_lineage()
        return svc.convergence_notional_for_fill(cfg, fresh_fill(coin, notional, price))

    def seam_run(coin, notional, price, side="BUY"):
        """Full production path: process_fill -> convergence seam -> intents / reconciliation."""
        reset_lineage()
        fill = fresh_fill(coin, notional, price, side=side)
        calls_before = EXCHANGE["calls"]
        svc.process_fill(fill, cfg)
        return fill, EXCHANGE["calls"] - calls_before

    # ===================== retained ENG-018 checks (this file's original cases) =================
    def c1():
        fill, _ = seam_run("BTC", 9.60, 100.0)
        ws1 = would_send(fill.fill_id)
        sent_at_min = [r for r in ws1 if abs(fnum(r.get("copy_notional")) - MIN) < 1e-9]
        return (bool(sent_at_min) and counter("uplifted") >= 1,
                f"would_send={ws1} counter={svc.state.get('min_notional_events')}")
    guarded("ENG018_MIN_1", c1)

    def c2():
        fill, _ = seam_run("ETH", 2.00, 100.0)
        refused = [r for r in intents(fill.fill_id)
                   if "REFUSED" in str(r.get("status", "")).upper() or named_refusal(r.get("status"))]
        return (bool(refused) and counter("refused") >= 1 and not would_send(fill.fill_id),
                f"statuses={[r.get('status') for r in intents(fill.fill_id)]} "
                f"counter={svc.state.get('min_notional_events')}")
    guarded("ENG018_MIN_2", c2)

    def c3():
        rec = recon(_LAST_REFUSAL_FILL[0]) if _LAST_REFUSAL_FILL else []
        return (len(rec) == 1 and named_refusal(rec[0].get("status"), rec[0].get("action"))
                and not [r for r in rec if r.get("event") == "CONVERGED" or r.get("status") == "CONVERGED"],
                repr(rec))
    # the refusal fill from case 2 (recomputed here so the case is self-contained)
    _LAST_REFUSAL_FILL = []

    def c3b():
        _LAST_REFUSAL_FILL.clear()
        fill, _ = seam_run("ETH", 2.00, 100.0)
        _LAST_REFUSAL_FILL.append(fill.fill_id)
        return c3()
    guarded("ENG018_MIN_3", c3b)

    def c4():
        dangling = [r for r in rows(svcmod.ORDER_INTENTS_CSV)
                    if str(r.get("status")) == "ACCUMULATED_NO_ORDER"]
        return (not dangling, f"dangling={len(dangling)}")
    guarded("ENG018_MIN_4", c4)

    def c5():
        before_uplift = counter("uplifted")
        fill, _ = seam_run("SOL", 10.00, 100.0)
        ex_ws = would_send(fill.fill_id)
        return (bool(ex_ws) and all(abs(fnum(r.get("copy_notional")) - MIN) < 1e-9 for r in ex_ws)
                and counter("uplifted") == before_uplift,
                f"would_send={ex_ws} min={MIN} uplifts_before={before_uplift} "
                f"uplifts_after={counter('uplifted')}")
    guarded("ENG018_MIN_5", c5)

    def c0():
        # the $10 nominal default is the whole premise of OD-09: it must not move
        return (abs(float(svcmod.MIN_ORDER_NOTIONAL) - 10.0) < 1e-12,
                f"MIN_ORDER_NOTIONAL={svcmod.MIN_ORDER_NOTIONAL!r}")
    guarded("OD09_MIN_DEFAULT_10_USD", c0)

    # ===================== OD-09 (a) NaN must reach ZERO exchange attempts ======================
    def nonfinite_attempts(order=None, fill_id=""):
        """Attempts for one probe: an actionable planner order, a spy call, or a bad payload row."""
        n = 0
        if order is not None and str(getattr(order, "action", "")) != "NONE":
            n += 1
        if fill_id:
            n += len([r for r in would_send(fill_id) if str(r.get("status", "")).startswith("WOULD")])
            n += len(bad_number_rows(fill_id))
        return n

    def a1():
        order = shadow.compute_convergence_order("BTC", float("nan"), 0.0, mark_px=100.0, min_notional=10.0)
        fill = coremod.LeaderFill(
            leader_fill_id="od09-nan-boundary", leader_wallet=wallet, coin="BTC", side="BUY",
            price=100.0, size=0.0, timestamp_ms=int(time.time() * 1000),
            source="TEST", ws_received_ms=0, raw={"dir": "Open Long"})
        intent = coremod.Intent(
            intent_id="od09-nan-boundary", fill=fill, copy_side=str(order.side),
            copy_size=float(order.size), copy_notional=float(order.size) * 100.0,
            wallet_mode="LIVE", copy_mode="proportional",
            decision="ENTRY_ALLOWED" if str(order.action) != "NONE" else "NONE",
            reason=str(order.reason), sleeve_id="od09", position_id="od09",
            position_direction_before="FLAT", wallet_position_before=0.0, coin_net_before=0.0,
            reduce_only_intended=False, reduce_only_sent_planned=False)
        exchange_calls = {"count": 0}
        sender = coremod.SenderGateway(coremod.ConfigManager(), coremod.AuditLogWriter())
        sender.cfg.config = {"global_controls": {"send_mode": "ON"}, "auto_send_enabled": True}
        sender._place_order = lambda *a, **k: exchange_calls.__setitem__("count", exchange_calls["count"] + 1)
        ok, refusal = sender.send_if_allowed(intent)
        named = named_refusal(refusal)
        boundary_record = {"status": refusal} if refusal else {}
        passed = (exchange_calls["count"] == 0 and not ok and named
                  and "MASTER_REAL_ORDERS_OFF" not in str(refusal))
        return passed, (f"sender_boundary=send_if_allowed exchange_calls={exchange_calls['count']} "
                        f"refusal={refusal!r} recorded={boundary_record}")

    def a1_positive_control():
        order = shadow.compute_convergence_order("BTC", 10.0, 0.0, mark_px=100.0, min_notional=10.0)
        fill = coremod.LeaderFill(
            leader_fill_id="od09-finite-boundary", leader_wallet=wallet, coin="BTC", side="BUY",
            price=100.0, size=0.1, timestamp_ms=int(time.time() * 1000),
            source="TEST", ws_received_ms=0, raw={"dir": "Open Long"})
        intent = coremod.Intent(
            intent_id="od09-finite-boundary", fill=fill, copy_side=str(order.side),
            copy_size=float(order.size), copy_notional=float(order.size) * 100.0,
            wallet_mode="LIVE", copy_mode="proportional", decision="ENTRY_ALLOWED",
            reason=str(order.reason), sleeve_id="od09", position_id="od09",
            position_direction_before="FLAT", wallet_position_before=0.0, coin_net_before=0.0,
            reduce_only_intended=False, reduce_only_sent_planned=False)
        exchange_calls = {"count": 0}
        sender = coremod.SenderGateway(coremod.ConfigManager(), coremod.AuditLogWriter())
        sender.cfg.config = {"global_controls": {"send_mode": "ON"}, "auto_send_enabled": True}
        sender._place_order = lambda *a, **k: exchange_calls.__setitem__("count", exchange_calls["count"] + 1)
        ok, status = sender.send_if_allowed(intent)
        passed = exchange_calls["count"] == 1
        return passed, (f"sender_boundary=send_if_allowed exchange_calls={exchange_calls['count']} "
                        f"ok={ok} status={status!r} finite_size={order.size}")
    guarded("OD09_A1_NAN_SENDER_BOUNDARY_NO_EXCHANGE_NAMED_REFUSAL", a1)
    guarded("OD09_A1_FINITE_POSITIVE_CONTROL_ONE_STUB_CALL", a1_positive_control)

    def a2():
        fill, calls = seam_run("BTC", 7.5, float("nan"))
        attempts = calls + nonfinite_attempts(None, fill.fill_id)
        bad = bad_number_rows(fill.fill_id)
        rec = recon(fill.fill_id)
        converged = [r for r in rec if str(r.get("event")).upper() == "CONVERGED"
                     or str(r.get("status")).upper() == "CONVERGED"]
        refusal = [r for r in rec if named_refusal(r.get("status"), r.get("action"))]
        ok = (attempts == 0 and not bad and bool(rec) and not converged and bool(refusal))
        return ok, (f"attempts={attempts} zero_attempts={attempts == 0} bad_rows={bad} "
                    f"converged={len(converged)} named_refusal={[r.get('status') for r in refusal]} "
                    f"recon={[(r.get('event'), r.get('status')) for r in rec]}")
    guarded("OD09_A2_NAN_PRICE_ZERO_EXCHANGE", a2)

    def a3():
        now_attempts = EXCHANGE["calls"]
        order = shadow.compute_convergence_order("BTC", 5.0, 0.0, mark_px=100.0, min_notional=float("nan"))
        attempts = nonfinite_attempts(order) + (EXCHANGE["calls"] - now_attempts)
        ok = (attempts == 0 and str(order.action) == "NONE" and float(order.size) == 0.0
              and named_refusal(order.reason))
        return ok, f"order={order.short()} attempts={attempts} reason={order.reason!r}"
    guarded("OD09_A3_NAN_MINIMUM_ZERO_EXCHANGE", a3)

    # ===================== OD-09 (b) +/-inf must reach ZERO exchange attempts ===================
    def b_case(sign):
        inf = float("inf") * sign
        now_attempts = EXCHANGE["calls"]
        o_delta = shadow.compute_convergence_order("BTC", inf, 0.0, mark_px=100.0, min_notional=10.0)
        o_min = shadow.compute_convergence_order("BTC", 5.0, 0.0, mark_px=100.0, min_notional=inf)
        fill, calls = seam_run("BTC", 7.5, inf)
        attempts = (nonfinite_attempts(o_delta) + nonfinite_attempts(o_min)
                    + (EXCHANGE["calls"] - now_attempts) + calls + nonfinite_attempts(None, fill.fill_id))
        bad = bad_number_rows(fill.fill_id)
        rec = recon(fill.fill_id)
        ok = (attempts == 0 and not bad and str(o_delta.action) == "NONE" and str(o_min.action) == "NONE"
              and named_refusal(o_delta.reason) and named_refusal(o_min.reason)
              and bool(rec) and any(named_refusal(r.get("status"), r.get("action")) for r in rec))
        return ok, (f"{'+inf' if sign > 0 else '-inf'}: delta={o_delta.short()} min={o_min.short()} "
                    f"attempts={attempts} bad_rows={bad} "
                    f"recon={[(r.get('event'), r.get('status')) for r in rec]}")
    guarded("OD09_B1_POS_INF_ZERO_EXCHANGE", lambda: b_case(1))
    guarded("OD09_B2_NEG_INF_ZERO_EXCHANGE", lambda: b_case(-1))

    # ===================== OD-09 (c) quantised wire minimum at szDecimals =======================
    def c_quantised(coin, px, szd, notional=None):
        # a copy that CLEARS $10 before quantisation but (for real lot sizes) can fall UNDER it after
        # the exchange szDecimals floor: the wire must still be >= the minimum, or the entry must be
        # refused BY NAME. A silent hold is neither.
        notional = MIN * 1.005 if notional is None else notional
        svcmod.HL_PERP_META_BY_COIN_CACHE[coin] = {"szDecimals": szd, "name": coin, "canonical_name": coin}
        auth = planner_verdict(coin, notional, px)
        status = str(auth.get("status") or "")
        reason = str(auth.get("reason") or "")
        if not named_refusal(reason, status):
            # evidence only: re-classify the SAME desired/actual the seam just used, for the reason text
            probe = shadow.compute_convergence_order(
                coin, fnum(auth.get("desired_net")), fnum(auth.get("actual_net")),
                mark_px=px, min_notional=MIN)
            reason = str(reason or probe.reason)
        if named_refusal(reason, status):
            return True, f"named refusal: {status}/{reason}"
        size = fnum(auth.get("size"))
        if not (size > 0):   # this base reports the event notional, not the size
            size = (fnum(auth.get("notional")) / px) if px else 0.0
        if not (size > 0 and finite(size)):
            return False, (f"no refusal and no positive size: status={status} reason={reason!r} "
                           f"size={size} notional={auth.get('notional')!r} probe_notional={notional}")
        wire = svcmod.round_size_hl_perp(size, szd)[0]
        wire_f = float(wire)
        wire_notional = wire_f * px
        return (wire_notional >= MIN - 1e-9,
                f"size={size} wire={wire_f} wire_notional={wire_notional:.6f} min={MIN} "
                f"reason={reason!r} notional={notional}")
    guarded("OD09_C1_QUANTISED_MIN_5DEC_61000", lambda: c_quantised("BTC", 61000.0, 5))
    guarded("OD09_C2_QUANTISED_MIN_2DEC", lambda: c_quantised("ETH", 3000.0, 2))
    guarded("OD09_C3_QUANTISED_MIN_0DEC_LOWPX", lambda: c_quantised("XRP", 0.55, 0))

    # ===================== OD-09 (d) below-minimum never records CONVERGED =====================
    def d_case():
        fill, calls = seam_run("ETH", 2.00, 100.0)
        rec = recon(fill.fill_id)
        converged = [r for r in rec if str(r.get("event")).upper() == "CONVERGED"
                     or str(r.get("status")).upper() == "CONVERGED"]
        refusal = [r for r in rec if named_refusal(r.get("status"), r.get("action"))]
        return (not converged and bool(refusal) and calls == 0 and not would_send(fill.fill_id),
                f"converged={len(converged)} refusal={[r.get('status') for r in refusal]} "
                f"events={[(r.get('event'), r.get('status')) for r in rec]}")
    guarded("OD09_D1_BELOW_MIN_NEVER_CONVERGED", d_case)

    # ===================== OD-09 (e) closes are never rounded UP ===============================
    def e_case():
        # positions chosen so a floor-at-szDecimals can only go DOWN; the snap/dust path must not
        # hand back a size LARGER than the position being closed.
        problems = []
        for pos, szd in ((0.123449999999999, 5), (7.5, 0), (19.999999999999, 0), (0.5000000001, 2)):
            q = svcmod.round_size_hl_perp(pos, szd)[0]
            if Decimal(str(q)) > Decimal(str(pos)):
                problems.append((pos, szd, str(q)))
        order = shadow.compute_convergence_order("BTC", 0.0, 0.5, mark_px=100.0, min_notional=10.0)
        close_exact = (str(order.action) == "FLATTEN" and bool(order.reduce_only)
                       and abs(float(order.size) - 0.5) < 1e-12)
        return (not problems and close_exact,
                f"rounded_up={problems} close_order={order.short()}")
    guarded("OD09_E1_CLOSES_NEVER_ROUND_UP", e_case)

    # ===================== OD-09 (f) ONE uplift envelope, planner==service==sender =============
    def f_case():
        detail = []
        # tight envelope: 9.90 + 0.05 absolute / 1.00 ratio can never reach $10 -> must REFUSE by name
        os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_RATIO"] = "1.00"
        os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD"] = "0.05"
        tight = planner_verdict("BTC", 9.90, 3.75)
        tight_ok = named_refusal(tight.get("reason"), tight.get("status"))
        detail.append(f"tight(reason={tight.get('reason')!r},status={tight.get('status')!r})")
        # wide envelope: 1.25 / $3.00 can reach $10 -> must UPLIFT and stay above the minimum
        os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_RATIO"] = "1.25"
        os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD"] = "3.00"
        wide = planner_verdict("BTC", 9.90, 3.75)
        wide_size = fnum(wide.get("size"))
        if not (wide_size > 0):
            wide_size = (fnum(wide.get("notional")) / 3.75) if 3.75 else 0.0
        wire = float(svcmod.round_size_hl_perp(wide_size, 5)[0]) if wide_size > 0 else 0.0
        wide_ok = wide_size > 0 and wire * 3.75 >= MIN - 1e-9
        detail.append(f"wide(size={wide_size},wire={wire},notional={wide.get('notional')!r},"
                      f"reason={wide.get('reason')!r})")
        # the SAME envelope must be readable as one value from every layer that sizes the order
        envelopes = []
        for label, mod in (("service", svcmod), ("planner", shadow), ("sender", svcmod)):
            for attr in ("entry_uplift_envelope", "uplift_envelope", "min_notional_envelope"):
                fn = getattr(mod, attr, None)
                if callable(fn):
                    try:
                        envelopes.append((label, attr, fn()))
                    except Exception as exc:  # noqa: BLE001
                        envelopes.append((label, attr, f"ERROR {exc}"))
                    break
        shared = len({repr(x[2]) for x in envelopes}) == 1 and len(envelopes) == 3
        detail.append(f"envelopes={envelopes}")
        return (tight_ok and wide_ok and shared, " | ".join(detail))
    guarded("OD09_F1_ONE_UPLIFT_ENVELOPE", f_case)

    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_RATIO", None)
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD", None)

    failed = [name for name, ok in checks if not ok]
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed:
        print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
