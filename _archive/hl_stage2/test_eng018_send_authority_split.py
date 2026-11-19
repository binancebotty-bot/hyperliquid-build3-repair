#!/usr/bin/env python3
"""ENG-018: RED-encode the SEND-AUTHORITY SPLIT introduced by c2854519.

Two routes reach ``manual_send_one_intent``. They do NOT share a size authority:

  AUTONOMOUS  (auto_live=True -- the auto-send path out of process_fill)
      size = the planner's size already recorded on the would-send row (row copy_size).
      An entry with no planner size is a NAMED refusal (ENTRY_PLANNER_SIZE_MISSING)
      and reaches ZERO exchange calls. The wallet's fixed_notional is NEVER a size
      source on this route.

  MANUAL      (auto_live=False -- the operator CLI route)
      size = wallet config fixed_notional / limit_price, ceiled to the symbol's
      szDecimals, with FIXED_NOTIONAL_BELOW_MIN and FIXED_NOTIONAL_ABOVE_CAP enforced.

Pre-fix every fixed open -- autonomous included -- re-derived the size from the wallet
config, so a planner-authorised 8 lots @ $1.40 reached the exchange as 15.0 lots /
$21.00 on a real send. The mirror-image gap mattered too: pre-fix the MANUAL route had
no wallet derivation at all (`is_auto_fixed_open` required auto_live), so an operator
send of a fixed wallet went to the wire at the row's leader-derived size. Measured on
the fix's parent, this file fails 4 of 6 cases (1, 2, 4, 5); cases 3 and 6 hold there.
Cases 1-3 pin the autonomous side, 4-5 the manual side, 6 the
single exchange.order call site.

Offline: ``send_hyperliquid_order`` is replaced by a recording stub that counts every
order that WOULD have been sent. No exchange client, no keys, no live engine, no orders.
"""
from __future__ import annotations

import ast
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# --- import-time isolation: audit dir, config file and every seam pointed at a temp tree ---
TMP = Path(tempfile.mkdtemp(prefix="eng018_authority_"))
os.environ.update(
    HL_LIVE_AUDIT_DIR=str(TMP),
    HL_LIVE_AUTO_SEND_ENABLED="1",          # this suite exercises the auto-live route itself
    HL_LIVE_AUTO_SEND_MAX_PER_RUN="50",
    HL_LIVE_AUTO_SEND_MARKETABLE_BPS="5",
    HL_LIVE_AUTO_SEND_WALLET="",
    HL_LIVE_POLL_ENABLED="0",
    HL_LIVE_HL_PRIVATE_KEY="***",
    HL_LIVE_MAX_MANUAL_ORDER_NOTIONAL_USD="25",
    HL_LIVE_GLOBAL_LOCK_FILE=str(TMP / "test_only_global.lock"),
)
(TMP / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")

import HL_Live_Copy_Service as svcmod  # noqa: E402

svcmod.TEST_INJECTION_ENABLED = True
svcmod.HL_PERP_META_BY_COIN_CACHE = {"TESTFIXED": {"szDecimals": 0, "name": "TESTFIXED"}}

WALLET = "0xw1"
COIN = "TESTFIXED"
PRICE = 1.40                 # szDecimals=0 -> integer lots, $10 min notional
PLANNER_SIZE = 8.0           # the planner's ceilinged size for an $11.20 entry
PLANNER_NOTIONAL = PLANNER_SIZE * PRICE          # 11.20
WALLET_FIXED_NOTIONAL = 20.0                     # 20/1.40 = 14.2857 -> base sent 15.0 / $21.00
WALLET_DERIVED_SIZE = 15.0                       # ceil(14.2857) at szDecimals=0
WALLET_DERIVED_NOTIONAL = WALLET_DERIVED_SIZE * PRICE   # 21.00

MARKER_NAME = "ENTRY_" + "PLANNER_SIZE_MISSING"
CORE_PATH = HERE / "HL_Live_Copy_Service_Core.py"
EXPECTED_CORE_EXCHANGE_ORDER_CALLS = 1

sent: list[dict] = []        # the ONLY exchange seam: every entry here is an order that would be sent


def fnum(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def fake_send(payload, marketable_bps=0.0, use_current_quote=False, max_notional=None):
    size = fnum(payload.get("copy_size"))
    price = fnum(payload.get("limit_price"))
    sent.append({
        "copy_size": size,
        "limit_price": price,
        "copy_notional": size * price,
        "payload_copy_notional": fnum(payload.get("copy_notional")),
        "intended_notional": payload.get("intended_notional"),
        "fixed_notional": payload.get("fixed_notional"),
        "reduce_only": bool(payload.get("reduce_only")),
        "max_notional": max_notional,
        "auto_live": payload.get("auto_live"),
    })
    return {"ok": True, "status": "ORDER_FILLED", "oid": "selftest-oid", "fill_size": size,
            "size": size, "coin": payload.get("coin"), "side": payload.get("side"),
            "reduce_only": payload.get("reduce_only")}


svcmod.send_hyperliquid_order = fake_send


def set_wallet(fixed_notional, extra=None):
    wallet_cfg = {"mode": "LIVE", "enabled": True, "copy_mode": "fixed",
                  "fixed_notional": float(fixed_notional)}
    if extra:
        wallet_cfg.update(extra)
    (TMP / "live_config.json").write_text(json.dumps({"wallets": {WALLET: wallet_cfg}}), encoding="utf-8")
    return wallet_cfg


def new_service(cfg):
    svc = svcmod.DryRunLiveCopyService()
    svc.global_order_cap = lambda: 0.0
    svc.account_net_actual = lambda c: {"ok": True, "status": "OK", "net": 0.0}
    svc.reconcile_gate = lambda c, net: {"ok": True, "status": "OK"}
    svc.load_config = lambda: {WALLET: cfg}
    return svc


def would_send_row(intent_id, size, notional, limit_price=PRICE, reduce_only=False):
    """The production would-send row shape, written through the production writer."""
    return {
        "created_at": svcmod.utc_now_iso(), "dry_run": True, "intent_id": intent_id,
        "leader_wallet": WALLET, "leader_fill_id": intent_id,
        "source_reason": "LIVE_WS_DETECTED", "execution_decision": "WOULD_PLACE_IOC_LIMIT",
        "decision_reason": "LIVE_WS_FAST_PATH", "coin": COIN, "side": "BUY",
        "copy_size": size, "copy_notional": notional, "order_type": "IOC_LIMIT",
        "limit_price": limit_price, "reduce_only": reduce_only,
        "manual_reconcile_required": False, "status": "WOULD_SEND_DRY_RUN",
        "notes": "eng018 send-authority fixture",
    }


def append_row(row):
    svcmod.append_csv(svcmod.WOULD_SEND_ORDERS_CSV, svcmod.WOULD_SEND_ORDER_FIELDS, row)


def last_attempt(intent_id):
    if not svcmod.SEND_ATTEMPTS_CSV.exists():
        return {}
    with open(svcmod.SEND_ATTEMPTS_CSV, newline="", encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh) if str(r.get("intent_id", "")).strip() == intent_id]
    return rows[-1] if rows else {}


def drive_auto_live_entry(planner_notional, planner_size, wallet_fixed_notional, limit_price=PRICE,
                          fill_id="eng018-auto-entry"):
    """The REAL chain: process_fill -> planner -> would-send -> auto-send -> exchange seam."""
    set_wallet(wallet_fixed_notional)
    cfg = svcmod.LiveWalletConfig(wallet=WALLET, mode="LIVE", copy_mode="fixed",
                                  fixed_notional=float(wallet_fixed_notional), enabled=True)
    svc = new_service(cfg)
    auth = {"ok": True, "status": "OK", "notional": planner_notional, "size": planner_size,
            "action": "OPEN", "side": "BUY", "reduce_only": False, "reason": "OPEN",
            "min_notional_event": ""}
    svc.convergence_notional_for_fill = lambda c, f: dict(auth)
    svcmod.dry_run_intent_audit_decision = lambda *a, **k: {
        "execution_decision": "WOULD_PLACE_IOC_LIMIT", "status": "DRY_RUN_FILLED",
        "reason": "LIVE_WS_DETECTED", "decision_reason": "LIVE_WS_FAST_PATH",
        "target_price": limit_price, "suggested_order_type": "IOC_LIMIT",
        "suggested_limit_price": limit_price, "manual_reconcile_required": False}
    fill = svcmod.LeaderFill(fill_id, WALLET, COIN, "BUY", PRICE, 1.0, 1.0, 1700000000000,
                             "2026-01-01T00:00:00Z", "ws", "test", {})
    before = len(sent)
    svc.process_fill(fill, cfg)
    return svc, sent[before:], before


def report(name, checks):
    ok = True
    for label, condition, detail in checks:
        passed = bool(condition)
        ok = ok and passed
        print(f"{'PASS' if passed else 'FAIL'}: {label}" + (f" :: {detail}" if detail else ""))
    print(f"RESULT::{name}_{'PASS' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------------------- 1: autonomous size authority
def case_auto_live_planner_size():
    svc, calls, _ = drive_auto_live_entry(PLANNER_NOTIONAL, PLANNER_SIZE, WALLET_FIXED_NOTIONAL)
    got = calls[-1] if calls else {}
    wire_size = fnum(got.get("copy_size"))
    wire_notional = fnum(got.get("copy_notional"))
    return report("AUTO_LIVE_PLANNER_SIZE", [
        ("auto-live fixed open reaches the exchange exactly once", len(calls) == 1, f"exchange_calls={len(calls)}"),
        (f"wire size is the planner's {PLANNER_SIZE} (not {20.0 / PRICE:.4f}, not {WALLET_DERIVED_SIZE})",
         len(calls) == 1 and abs(wire_size - PLANNER_SIZE) < 1e-12,
         f"wallet_fixed_notional={WALLET_FIXED_NOTIONAL} derived={WALLET_FIXED_NOTIONAL / PRICE:.4f} "
         f"wire_copy_size={wire_size}"),
        (f"wire notional is the planner's {PLANNER_NOTIONAL:.2f} (not {WALLET_DERIVED_NOTIONAL:.2f})",
         len(calls) == 1 and abs(wire_notional - PLANNER_NOTIONAL) < 1e-9,
         f"wire_notional={wire_notional:.6f}"),
        ("the payload carries the planner's copy_notional, not the wallet's fixed_notional",
         len(calls) == 1 and abs(fnum(got.get("payload_copy_notional")) - PLANNER_NOTIONAL) < 1e-9,
         f"payload_copy_notional={got.get('payload_copy_notional')} intended_notional={got.get('intended_notional')}"),
    ])


# --------------------------------------------------------------------------- 2: no planner size => named refusal
def case_auto_live_no_planner_size():
    set_wallet(WALLET_FIXED_NOTIONAL)          # a wallet size exists and must NOT be used
    cfg = svcmod.LiveWalletConfig(wallet=WALLET, mode="LIVE", copy_mode="fixed",
                                  fixed_notional=WALLET_FIXED_NOTIONAL, enabled=True)
    svc = new_service(cfg)
    row = would_send_row("eng018-auto-nosize", 0.0, 0.0)
    append_row(row)
    before = len(sent)
    # maybe_auto_send_would_send inspects the ORDER-INTENT row ("reason"); append_would_send_order
    # renames it to "source_reason" in the CSV -- the intent-row shape is what production passes.
    res = svc.maybe_auto_send_would_send(cfg, dict(row, reason="LIVE_WS_DETECTED"))
    attempt = last_attempt("eng018-auto-nosize")
    status = str(res.get("status") or "")
    return report("AUTO_LIVE_NO_PLANNER_SIZE", [
        ("an auto-live entry with no planner size reaches NO exchange call",
         len(sent) == before, f"exchange_calls_added={len(sent) - before} status={status}"),
        (f"that refusal is the NAMED {MARKER_NAME}, not a generic bad-row refusal",
         status == MARKER_NAME, f"status={status}"),
        ("the refusal is durable in send_attempts under the same name",
         str(attempt.get("status") or "") == MARKER_NAME,
         f"send_attempt_status={attempt.get('status')} error={attempt.get('error')}"),
    ])


# --------------------------------------------------------------------------- 3: unusable limit price
def case_auto_live_limit_price_invalid():
    set_wallet(WALLET_FIXED_NOTIONAL)
    cfg = svcmod.LiveWalletConfig(wallet=WALLET, mode="LIVE", copy_mode="fixed",
                                  fixed_notional=WALLET_FIXED_NOTIONAL, enabled=True)
    svc = new_service(cfg)
    row = would_send_row("eng018-auto-noprice", PLANNER_SIZE, PLANNER_NOTIONAL, limit_price=0.0)
    append_row(row)
    before = len(sent)
    res = svc.maybe_auto_send_would_send(cfg, dict(row, reason="LIVE_WS_DETECTED"))
    attempt = last_attempt("eng018-auto-noprice")
    status = str(res.get("status") or "")
    error = str(res.get("error") or attempt.get("error") or "")
    return report("AUTO_LIVE_LIMIT_PRICE_INVALID", [
        ("an auto-live entry with a non-positive limit price reaches NO exchange call",
         len(sent) == before, f"exchange_calls_added={len(sent) - before} status={status}"),
        ("the entry is refused, not silently dropped", bool(status) and status != "WOULD_SEND_DRY_RUN",
         f"status={status}"),
        ("the refusal names the price and is durable in send_attempts",
         "limit_price" in error and str(attempt.get("status") or "") == status,
         f"error={error} send_attempt_status={attempt.get('status')}"),
    ])


# --------------------------------------------------------------------------- 4: manual wallet authority
def case_manual_wallet_derivation():
    set_wallet(10.5)                            # $10.5 at szDecimals=0, $1.40 -> ceil 8 lots ($11.20)
    row = would_send_row("eng018-manual-ok", 7500.0, 7500.0 * PRICE)
    append_row(row)
    before = len(sent)
    res = svcmod.manual_send_one_intent("eng018-manual-ok", True)     # operator CLI route: no auto_live
    got = sent[-1] if len(sent) > before else {}
    ok_send = (len(sent) == before + 1 and str(res.get("status")) == "ORDER_FILLED"
               and abs(fnum(got.get("copy_size")) - 8.0) < 1e-12)

    set_wallet(5.0)                             # below the $10 exchange minimum
    below_row = would_send_row("eng018-manual-below", 7500.0, 7500.0 * PRICE)
    append_row(below_row)
    before2 = len(sent)
    below = svcmod.manual_send_one_intent("eng018-manual-below", True)

    set_wallet(30.0)                            # above the $25 configured manual cap
    above_row = would_send_row("eng018-manual-above", 7500.0, 7500.0 * PRICE)
    append_row(above_row)
    before3 = len(sent)
    above = svcmod.manual_send_one_intent("eng018-manual-above", True)

    return report("MANUAL_WALLET_DERIVATION", [
        ("a MANUAL fixed open still reaches the exchange, sized by wallet fixed_notional (10.5 -> 8 lots)",
         ok_send, f"status={res.get('status')} wire_copy_size={got.get('copy_size')} "
                  f"intended_notional={res.get('payload', {}).get('intended_notional')}"),
        ("the manual wire size is NOT the row's copy_size (7500)",
         len(sent) > before and abs(fnum(got.get("copy_size")) - 7500.0) > 1.0,
         f"row_copy_size=7500.0 wire_copy_size={got.get('copy_size')}"),
        ("FIXED_NOTIONAL_BELOW_MIN is enforced on the manual route with zero exchange calls",
         str(below.get("status")) == "FIXED_NOTIONAL_BELOW_MIN" and len(sent) == before2,
         f"status={below.get('status')} exchange_calls_added={len(sent) - before2}"),
        ("FIXED_NOTIONAL_ABOVE_CAP is enforced on the manual route with zero exchange calls",
         str(above.get("status")) == "FIXED_NOTIONAL_ABOVE_CAP" and len(sent) == before3,
         f"status={above.get('status')} exchange_calls_added={len(sent) - before3}"),
    ])


# --------------------------------------------------------------------------- 5: which authority the manual route uses
def case_manual_authority_regression_guard():
    """Reverting c2854519 makes case 1 fail; this case additionally pins the manual
    side so a future "fix" cannot silently hand the operator route to the planner."""
    set_wallet(10.5)
    wire = {}
    payloads = {}
    for intent_id, row_size in (("eng018-guard-small", 3.0), ("eng018-guard-large", 900.0)):
        append_row(would_send_row(intent_id, row_size, row_size * PRICE))
        before = len(sent)
        res = svcmod.manual_send_one_intent(intent_id, True)
        wire[intent_id] = fnum(sent[-1].get("copy_size")) if len(sent) > before else None
        payloads[intent_id] = res.get("payload", {}) or {}
    small, large = wire["eng018-guard-small"], wire["eng018-guard-large"]
    return report("MANUAL_AUTHORITY_REGRESSION_GUARD", [
        ("the manual route's size authority is the wallet's fixed_notional, not the row's copy_size",
         small is not None and large is not None and abs(small - 8.0) < 1e-12 and abs(large - 8.0) < 1e-12,
         f"row_copy_size=3.0 -> wire={small}; row_copy_size=900.0 -> wire={large}; wallet=10.5 -> 8 lots"),
        ("changing the row's copy_size ALONE does not change the manual wire size",
         small is not None and large is not None and abs(small - large) < 1e-12,
         f"wire small={small} wire large={large}"),
        ("the manual payload records the wallet fixed_notional as the intended notional",
         abs(fnum(payloads["eng018-guard-small"].get("intended_notional")) - 10.5) < 1e-9
         and abs(fnum(payloads["eng018-guard-small"].get("fixed_notional")) - 10.5) < 1e-9,
         f"intended_notional={payloads['eng018-guard-small'].get('intended_notional')} "
         f"fixed_notional={payloads['eng018-guard-small'].get('fixed_notional')}"),
        ("the two row sizes would have differed if the row were the authority",
         small is not None and large is not None and abs(900.0 - 3.0) > 1.0,
         "control: row copy_size differs by 897 lots"),
    ])


# --------------------------------------------------------------------------- 6: single exchange.order call site
def case_exchange_order_callsites():
    source = CORE_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(CORE_PATH))
    ast_calls = [n.lineno for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "order" and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == "exchange"]
    textual = source.count("exchange.order(")
    others = []
    for path in sorted(HERE.glob("*.py")):
        if path.name == CORE_PATH.name or path.name == Path(__file__).name:
            continue
        try:
            other = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(other):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "order" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "exchange"):
                others.append(f"{path.name}:{node.lineno}")
    return report("EXCHANGE_ORDER_CALLSITE_COUNT", [
        (f"the Core owns exactly {EXPECTED_CORE_EXCHANGE_ORDER_CALLS} exchange.order(...) call site(s)",
         len(ast_calls) == EXPECTED_CORE_EXCHANGE_ORDER_CALLS,
         f"core_ast_call_sites={len(ast_calls)} at lines {ast_calls} (textual occurrences incl. docstrings={textual})"),
        ("no other stage2 module gained an exchange.order(...) call site",
         not others, f"foreign_call_sites={others or 'none'}"),
    ])


def main():
    results = [
        case_auto_live_planner_size(),
        case_auto_live_no_planner_size(),
        case_auto_live_limit_price_invalid(),
        case_manual_wallet_derivation(),
        case_manual_authority_regression_guard(),
        case_exchange_order_callsites(),
    ]
    total = len(results)
    failed = total - sum(1 for ok in results if ok)
    print(f"TOTAL={total} FAILED={failed}")
    print(f"HEAD={_head()}")
    print(f"AUDIT_DIR={TMP}")
    return 1 if failed else 0


def _head():
    try:
        import subprocess
        return subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return "UNKNOWN"


if __name__ == "__main__":
    sys.exit(main())
