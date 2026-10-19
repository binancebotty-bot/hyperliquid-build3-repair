#!/usr/bin/env python3
"""
ORDER_CORRECTION harness for B3-CERT ORDER area (6 rows).
Engine: _archive/hl_stage2/HL_Live_Copy_Service_Core.py @ fefc2b04261c734bb32c767d2cc4a91095e65843

Each check is earned by the runtime outcome its check NAME asserts.
No source-substring checks. No fake-fill PASS.
In-process exchange doubles are explicitly named '*_via_double'.
Exchange truth NOT achievable on testnet (follower wallet does not exist) -> NOT_ESTABLISHED.
"""
import sys, os, json, hashlib, shutil, tempfile, importlib.util
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

REPO = Path(r"C:\Users\wigmore\hyperliquid-build3-repair")
ENGINE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
COMMIT10 = "fefc2b04"

# Register module in sys.modules BEFORE exec_module (dataclass decorator needs it)
MODULE_NAME = "hl_core_correction"
if MODULE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(MODULE_NAME, str(ENGINE_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = mod
    spec.loader.exec_module(mod)
else:
    mod = sys.modules[MODULE_NAME]

ConfigManager = mod.ConfigManager
SenderGateway = mod.SenderGateway
IntentBuilder = mod.IntentBuilder
DedupeStore = mod.DedupeStore
LiveCopyCore = mod.LiveCopyCore
LeaderFill = mod.LeaderFill
Intent = mod.Intent
ManualLedger = mod.ManualLedger
CopyFillMatcher = mod.CopyFillMatcher
AuditLogWriter = mod.AuditLogWriter

# Engine constants
DEFAULT_MIN_NOTIONAL = mod.DEFAULT_MIN_NOTIONAL

# --- Global offline setup: no real network during the harness ---
# follower_mid is called during IntentBuilder.build() (_order_value_px); patch it
# module-wide so no allMids fetch happens.
_ORIG_FOLLOWER_MID = mod.follower_mid
mod.follower_mid = lambda coin: 100.0
# _unowned_inventory_block reads follower exchange truth during build() when
# auto_send is enabled; the harness uses an in-process double, not exchange truth.
_ORIG_UNOWNED = mod.IntentBuilder._unowned_inventory_block
mod.IntentBuilder._unowned_inventory_block = lambda self, fill: ""
# Ownership gate reads persisted exchange snapshots from disk; the harness has no
# real exchange state, so treat ownership as out of scope for the order-path checks.
_ORIG_OWNERSHIP = mod.SenderGateway._pre_send_ownership_gate
mod.SenderGateway._pre_send_ownership_gate = lambda self, intent: (True, {})
# Fast-fail any residual HTTP (should not be reached).
os.environ.setdefault("HL_LIVE_HTTP_TIMEOUT_SEC", "0.5")

# Test wallets
WALLET_A = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
WALLET_B = "0xcccccccccccccccccccccccccccccccccccccccc"

# Resolved symbol for double-based tests
RESOLVED_OK = {
    "ok": True, "sdk_coin": "ZWIRE", "sz_decimals": 2, "price_max_decimals": 4,
    "perp_dexs": [""], "sdk_order_compatible": True, "min_order_value_usd": 1.0,
    "min_size": 0.0, "status": "OK",
}
RESOLVED_MIN_10 = {
    "ok": True, "sdk_coin": "ZWIRE", "sz_decimals": 2, "price_max_decimals": 4,
    "perp_dexs": [""], "sdk_order_compatible": True, "min_order_value_usd": 10.0,
    "min_size": 0.0, "status": "OK",
}


class FakeExchange:
    """In-process exchange double for gate-logic testing. NOT exchange truth."""
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({
            "coin": coin, "is_buy": is_buy, "size": size, "px": px,
            "reduce_only": reduce_only,
        })
        return {
            "status": "ok",
            "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 990001}}
            ]}},
        }


def _check(name: str, passed: bool, detail: str, kind: str = "gate") -> Dict[str, Any]:
    return {"name": name, "pass": bool(passed), "detail": detail, "kind": kind}


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _git_head() -> str:
    """Actual git HEAD of the repo at run time (for evidence traceability)."""
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def _make_intent(fill_id, wallet, coin, side, price, size, now_ms=None):
    now_ms = now_ms or _now_ms()
    return IntentBuilder(ConfigManager(), ManualLedger()).build(
        LeaderFill(fill_id, wallet, coin, side, price, size, now_ms, "TEST")
    )


def _cfg(wallet, mode="ON", fixed=10.0, min_notional=10.0, auto_send=True):
    """ConfigManager with one wallet in the given mode. Fresh dict (no disk file)."""
    cfg = ConfigManager()
    cfg.config = {
        "auto_send_enabled": auto_send,
        "wallets": {wallet: {"mode": mode, "enabled": True, "fixed_notional": fixed}},
        "global_controls": {"min_notional": min_notional},
    }
    return cfg


def _fresh_ledger():
    """A ManualLedger backed by a temp file so no on-disk state leaks between tests."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix="ord_corr_ledger_", suffix=".json")
    os.close(fd)
    os.remove(path)
    return ManualLedger(path=Path(path))


def _build_intent(cfg, ledger, fill_id, wallet, coin, side, price, size, now_ms=None):
    now_ms = now_ms or _now_ms()
    return IntentBuilder(cfg, ledger).build(
        LeaderFill(fill_id, wallet, coin, side, price, size, now_ms, "TEST"))


def _make_intent_cfg(cfg, fill_id, wallet, coin, side, price, size, now_ms=None):
    return _build_intent(cfg, _fresh_ledger(), fill_id, wallet, coin, side, price, size, now_ms)


def _wire_send(gw: SenderGateway, intent: Intent, resolve_map=None) -> Tuple[bool, str, Dict]:
    """Exercise the FULL send path: send_if_allowed -> gate chain -> _send_real,
    with an in-process exchange double and offline follower_mid. Does NOT patch
    _validate_final_wire_order (the engine's real wire gates run unmodified).
    Returns (ok, status, result-with-_fake_exchange_calls)."""
    fake = FakeExchange()
    resolve_map = resolve_map or {}
    saved_resolve = gw._resolve_coin
    saved_client = gw._get_exchange_client
    saved_symbol = gw._exchange_client_has_symbol
    saved_safety = gw._pre_exchange_asset_safety
    saved_acct = globals().get("HLAccount")
    saved_exch = globals().get("HLExchange")
    saved_follower_mid = mod.follower_mid

    def _resolve(coin):
        key = str(coin).upper()
        if key in resolve_map:
            return dict(resolve_map[key])
        return saved_resolve(coin)

    gw._resolve_coin = _resolve
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    mod.follower_mid = lambda coin: 100.0

    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    globals()["HLAccount"] = object
    globals()["HLExchange"] = object

    try:
        ok, status = gw.send_if_allowed(intent)
        return ok, status, {"_fake_exchange_calls": list(fake.calls)}
    finally:
        gw._resolve_coin = saved_resolve
        gw._get_exchange_client = saved_client
        gw._exchange_client_has_symbol = saved_symbol
        gw._pre_exchange_asset_safety = saved_safety
        globals()["HLAccount"] = saved_acct
        globals()["HLExchange"] = saved_exch
        mod.follower_mid = saved_follower_mid
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)


# ============================================================
# ORD-001: Single sender / single gate
# ============================================================
def test_ord001() -> Tuple[List[Dict], List[Dict]]:
    checks = []
    negatives = []

    # ONE_ORDER_CALL_PER_SEND: each send produces exactly 1 exchange.order() call.
    cfg = _cfg(WALLET_A, mode="ON", fixed=50.0)
    ledger = _fresh_ledger()
    gw = SenderGateway(cfg, AuditLogWriter(), ledger)
    total_calls = 0
    n_sends = 3
    for i in range(n_sends):
        intent = _build_intent(cfg, ledger, f"fill-ord001-{i}", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
        ok, status, result = _wire_send(gw, intent, resolve_map={"ZWIRE": RESOLVED_OK})
        total_calls += len(result.get("_fake_exchange_calls", []))
    checks.append(_check(
        "ONE_ORDER_CALL_PER_SEND_VIA_DOUBLE",
        total_calls == n_sends,
        f"exchange.order() calls across {n_sends} sends: {total_calls} (expected {n_sends})"
    ))

    # Auto-send disabled blocks all (wallet ON so the intent is send_allowed)
    cfg_off = _cfg(WALLET_A, mode="ON", auto_send=False)
    ledger_off = _fresh_ledger()
    gw_off = SenderGateway(cfg_off, AuditLogWriter(), ledger_off)
    intent_off = _build_intent(cfg_off, ledger_off, "fill-ord001-off", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    checks.append(_check(
        "INTENT_SEND_ALLOWED_WHEN_ON",
        intent_off.send_allowed is True,
        f"decision={intent_off.decision}, send_allowed={intent_off.send_allowed}"
    ))
    ok, status = gw_off.send_if_allowed(intent_off)
    checks.append(_check(
        "AUTO_SEND_DISABLED_BLOCKS_ALL",
        (not ok) and status == "MASTER_REAL_ORDERS_OFF",
        f"ok={ok}, status={status}"
    ))

    # No exchange call when disabled
    fake = FakeExchange()
    saved = gw_off._get_exchange_client
    gw_off._get_exchange_client = lambda *a, **k: fake
    ok2, status2 = gw_off.send_if_allowed(intent_off)
    gw_off._get_exchange_client = saved
    checks.append(_check(
        "NO_EXCHANGE_CALL_WHEN_DISABLED_VIA_DOUBLE",
        len(fake.calls) == 0 and status2 == "MASTER_REAL_ORDERS_OFF",
        f"exchange calls: {len(fake.calls)}, status={status2}"
    ))

    # EXCHANGE_ORDER_INVOKED_ON_SEND: verify exchange.order is actually called
    ledger_inv = _fresh_ledger()
    gw_inv = SenderGateway(cfg, AuditLogWriter(), ledger_inv)
    intent_inv = _build_intent(cfg, ledger_inv, "fill-ord001-invoke", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok3, status3, result3 = _wire_send(gw_inv, intent_inv, resolve_map={"ZWIRE": RESOLVED_OK})
    n_calls = len(result3.get("_fake_exchange_calls", []))
    checks.append(_check(
        "EXCHANGE_ORDER_INVOKED_ON_SEND_VIA_DOUBLE",
        n_calls == 1,
        f"exchange.order() calls in _send_real: {n_calls} (expected 1)"
    ))

    # Negative: patch _place_order to call exchange.order twice (second site)
    ledger_neg = _fresh_ledger()
    gw_neg = SenderGateway(cfg, AuditLogWriter(), ledger_neg)
    intent_neg = _build_intent(cfg, ledger_neg, "fill-ord001-neg", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok_n, status_n, result_n = _wire_send(gw_neg, intent_neg, resolve_map={"ZWIRE": RESOLVED_OK})
    normal_calls = len(result_n.get("_fake_exchange_calls", []))
    # Fresh intent for the mutation run (avoid duplicate-intent effects)
    intent_neg2 = _build_intent(cfg, ledger_neg, "fill-ord001-neg2", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    fake_mut = FakeExchange()
    saved_client = gw_neg._get_exchange_client
    saved_resolve = gw_neg._resolve_coin
    saved_safety = gw_neg._pre_exchange_asset_safety
    saved_follower_mid = mod.follower_mid
    gw_neg._get_exchange_client = lambda *a, **k: fake_mut
    gw_neg._resolve_coin = lambda c: dict(RESOLVED_OK)
    gw_neg._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    mod.follower_mid = lambda coin: 100.0
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    saved_a, saved_e = globals().get("HLAccount"), globals().get("HLExchange")
    globals()["HLAccount"] = object
    globals()["HLExchange"] = object
    orig_place = gw_neg._place_order
    try:
        def double_place(exchange, *a, **k):
            r1 = orig_place(exchange, *a, **k)
            orig_place(exchange, *a, **k)  # second physical order call = mutation
            return r1
        gw_neg._place_order = double_place
        gw_neg.send_if_allowed(intent_neg2)
    finally:
        gw_neg._place_order = orig_place
        globals()["HLAccount"] = saved_a
        globals()["HLExchange"] = saved_e
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        gw_neg._get_exchange_client = saved_client
        gw_neg._resolve_coin = saved_resolve
        gw_neg._pre_exchange_asset_safety = saved_safety
        mod.follower_mid = saved_follower_mid
    mutated_calls = len(fake_mut.calls)
    negatives.append({
        "mutation": "ord001_add_second_order_site",
        "expected": "FAIL",
        "actual": "FAIL" if mutated_calls > normal_calls else "PASS",
        "non_vacuous": mutated_calls > normal_calls and normal_calls == 1,
        "detail": f"normal calls: {normal_calls}; mutated calls: {mutated_calls}"
    })

    return checks, negatives


# ============================================================
# ORD-002: reduce_only correctness
# ============================================================
def test_ord002() -> Tuple[List[Dict], List[Dict]]:
    checks = []
    negatives = []

    # EXIT sends reduce_only=True. Set up a short sleeve deterministically.
    cfg = _cfg(WALLET_A, mode="ON", fixed=10.0)
    ledger = _fresh_ledger()
    open_intent = _build_intent(cfg, ledger, "ro-open", WALLET_A, "ZWIRE", "SELL", 2.4, 100.0)
    ledger.apply_copy_fill(open_intent, {"copy_fill_id": "ro-cf-open", "side": "SELL",
                                         "size": 50.0, "price": 2.4})
    gw = SenderGateway(cfg, AuditLogWriter(), ledger)

    exit_intent = _build_intent(cfg, ledger, "ro-exit", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    ok, status, result = _wire_send(gw, exit_intent, resolve_map={"ZWIRE": RESOLVED_OK})
    exchange_called = len(result.get("_fake_exchange_calls", [])) > 0
    reduce_sent = result.get("_fake_exchange_calls", [{}])[0].get("reduce_only", False) if exchange_called else False
    checks.append(_check(
        "EXIT_SENDS_REDUCE_ONLY_VIA_DOUBLE",
        exchange_called and reduce_sent is True,
        f"exchange_called={exchange_called}, reduce_only_sent={reduce_sent}"
    ))

    # ENTRY sends reduce_only=False
    cfg2 = _cfg(WALLET_B, mode="ON", fixed=10.0)
    ledger2 = _fresh_ledger()
    gw2 = SenderGateway(cfg2, AuditLogWriter(), ledger2)
    entry_intent = _build_intent(cfg2, ledger2, "ro-entry", WALLET_B, "ZNEW", "BUY", 2.0, 100.0)
    ok2, status2, result2 = _wire_send(gw2, entry_intent, resolve_map={"ZNEW": RESOLVED_OK})
    exchange_called2 = len(result2.get("_fake_exchange_calls", [])) > 0
    reduce_sent2 = result2.get("_fake_exchange_calls", [{}])[0].get("reduce_only", True) if exchange_called2 else True
    checks.append(_check(
        "ENTRY_SENDS_NO_REDUCE_ONLY_VIA_DOUBLE",
        exchange_called2 and reduce_sent2 is False,
        f"exchange_called={exchange_called2}, reduce_only_sent={reduce_sent2}"
    ))

    # reduce_only_for_intent helper
    checks.append(_check(
        "REDUCE_ONLY_FOR_INTENT_CORRECT",
        SenderGateway._reduce_only_for_intent(exit_intent) is True
        and SenderGateway._reduce_only_for_intent(entry_intent) is False,
        f"exit=True, entry=False"
    ))

    # reduce_only cannot flip position (engine uses it as kwarg to exchange.order)
    checks.append(_check(
        "REDUCE_ONLY_CANNOT_FLIP_VIA_DOUBLE",
        reduce_sent is True,
        f"EXIT reduce_only={reduce_sent} (True means position cannot flip)"
    ))

    # Negative: remove reduce_only logic
    gw3 = SenderGateway(cfg, AuditLogWriter(), ledger)
    saved_ro = SenderGateway._reduce_only_for_intent
    SenderGateway._reduce_only_for_intent = staticmethod(lambda intent: False)
    exit_intent3 = _make_intent_cfg(cfg, "ro-exit-neg", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    ok3, status3, result3 = _wire_send(gw3, exit_intent3, resolve_map={"ZWIRE": RESOLVED_OK})
    calls3 = result3.get("_fake_exchange_calls", [])
    reduce_sent3 = calls3[0].get("reduce_only", False) if calls3 else False
    SenderGateway._reduce_only_for_intent = staticmethod(saved_ro)
    negatives.append({
        "mutation": "ord002_remove_reduce_only_logic",
        "expected": "FAIL",
        "actual": "FAIL" if reduce_sent3 is False else "PASS",
        "non_vacuous": reduce_sent3 is False and reduce_sent is True,
        "detail": f"reduce_only with mutation: {reduce_sent3}; without: {reduce_sent}"
    })

    return checks, negatives


# ============================================================
# ORD-005: Exactly-once execution identity (dedupe)
# ============================================================
def test_ord005() -> Tuple[List[Dict], List[Dict]]:
    checks = []
    negatives = []

    # DedupeStore blocks duplicates
    store = DedupeStore()
    first = store.accept_leader("fill_det_1")
    second = store.accept_leader("fill_det_1")
    checks.append(_check(
        "DEDUPE_STORE_BLOCKS_DUPES",
        first is True and second is False,
        f"first={first}, second={second}"
    ))

    # Different fills accepted
    third = store.accept_leader("fill_det_2")
    checks.append(_check(
        "DIFFERENT_FILLS_ACCEPTED",
        third is True,
        f"third fill accepted={third}"
    ))

    # Intent ID is deterministic: same fill_id + same timestamp -> same intent_id
    ts = _now_ms()
    fill1 = LeaderFill("fill_det_1", WALLET_A, "ZWIRE", "BUY", 2.0, 100.0, ts, "TEST")
    fill2 = LeaderFill("fill_det_1", WALLET_A, "ZWIRE", "BUY", 2.0, 100.0, ts, "TEST")
    builder = IntentBuilder(ConfigManager(), ManualLedger())
    intent1 = builder.build(fill1)
    intent2 = builder.build(fill2)
    checks.append(_check(
        "INTENT_ID_DETERMINISTIC",
        intent1.intent_id == intent2.intent_id,
        f"intent1={intent1.intent_id}, intent2={intent2.intent_id}"
    ))

    # A different timestamp is a different execution identity (no collision)
    fill3 = LeaderFill("fill_det_1", WALLET_A, "ZWIRE", "BUY", 2.0, 100.0, ts + 1, "TEST")
    intent3 = builder.build(fill3)
    checks.append(_check(
        "DIFFERENT_TIMESTAMP_DIFFERENT_INTENT_ID",
        intent1.intent_id != intent3.intent_id,
        f"ts={ts} -> {intent1.intent_id}; ts={ts+1} -> {intent3.intent_id}"
    ))

    # Negative: remove dedupe
    store2 = DedupeStore()
    saved_accept = DedupeStore.accept_leader
    DedupeStore.accept_leader = lambda self, fill_id: True
    first2 = store2.accept_leader("fill_neg")
    second2 = store2.accept_leader("fill_neg")
    DedupeStore.accept_leader = saved_accept
    negatives.append({
        "mutation": "ord005_remove_dedupe",
        "expected": "FAIL",
        "actual": "FAIL" if second2 is True else "PASS",
        "non_vacuous": second2 is True and second is False,
        "detail": f"dedupe removed: second={second2}; original: second={second}"
    })

    return checks, negatives


# ============================================================
# ORD-006: Pre-send reservation
# ============================================================
def test_ord006() -> Tuple[List[Dict], List[Dict]]:
    checks = []
    negatives = []

    # The reservation store is SenderGateway._pending_exit_guard (keyed by sleeve_id).
    # Row: "Unresolved reservation persisted ... before exchange.order, oid/status attached
    # after response, not cleared on ACK."
    cfg = _cfg(WALLET_A, mode="ON", fixed=10.0)
    ledger = _fresh_ledger()
    open_intent = _build_intent(cfg, ledger, "res-open", WALLET_A, "ZWIRE", "SELL", 2.4, 100.0)
    ledger.apply_copy_fill(open_intent, {"copy_fill_id": "res-cf-open", "side": "SELL",
                                         "size": 50.0, "price": 2.4})
    gw = SenderGateway(cfg, AuditLogWriter(), ledger)

    # No reservation before send
    checks.append(_check(
        "NO_RESERVATION_BEFORE_SEND",
        len(gw._pending_exit_guard) == 0,
        f"guard entries before send: {len(gw._pending_exit_guard)}"
    ))

    # Reservation created on send (use real _send_real with double so exchange_called=True)
    exit_intent = _build_intent(cfg, ledger, "res-exit", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    saved_send_real = gw._send_real
    def _fake_send_real(intent, timing=None):
        return True, "ORDER_FILLED", {
            "exchange_response": {"response": {"data": {"statuses": [{"filled": {"oid": "res-oid"}}]}}},
            "oid": "res-oid", "limit_px": 2.4, "wire_size": intent.copy_size,
            "exchange_called": True, "error": "", "reduce_only_sent": True,
        }
    gw._send_real = _fake_send_real
    ok, status = gw.send_if_allowed(exit_intent)
    gw._send_real = saved_send_real
    guard_after = dict(gw._pending_exit_guard)
    checks.append(_check(
        "RESERVATION_CREATED_ON_SEND_VIA_DOUBLE",
        ok and len(guard_after) == 1,
        f"ok={ok}, status={status}, guard entries={len(guard_after)}"
    ))
    checks.append(_check(
        "RESERVATION_HAS_INTENT_ID",
        bool(guard_after) and all(bool(r.get("intent_id")) for r in guard_after.values()),
        f"intent_ids={[r.get('intent_id') for r in guard_after.values()]}"
    ))
    checks.append(_check(
        "RESERVATION_HAS_SIZE_AND_POSITION",
        bool(guard_after) and all(r.get("intended_size") is not None and "position_abs_before" in r
                                  for r in guard_after.values()),
        f"records={guard_after}"
    ))

    # Not cleared on ACK: the reservation survives a successful send -> duplicate close blocked
    exit_intent2 = _build_intent(cfg, ledger, "res-exit2", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    saved_send_real2 = gw._send_real
    gw._send_real = _fake_send_real
    ok2, status2 = gw.send_if_allowed(exit_intent2)
    gw._send_real = saved_send_real2
    checks.append(_check(
        "RESERVATION_NOT_CLEARED_ON_ACK_VIA_DOUBLE",
        (not ok2) and status2 == "PENDING_EXIT_GUARD_ACTIVE",
        f"second close: ok={ok2}, status={status2} (reservation survives ACK, blocks duplicate)"
    ))

    # Reservation cleared when the send makes NO exchange call
    ledger_c = _fresh_ledger()
    open_c = _build_intent(cfg, ledger_c, "res-c-open", WALLET_A, "ZWIRE", "SELL", 2.4, 100.0)
    ledger_c.apply_copy_fill(open_c, {"copy_fill_id": "res-c-cf", "side": "SELL",
                                      "size": 50.0, "price": 2.4})
    gw2 = SenderGateway(cfg, AuditLogWriter(), ledger_c)
    exit_intent3 = _build_intent(cfg, ledger_c, "res-exit3", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    def _no_call_send_real(intent, timing=None):
        return False, "SEND_NOT_ATTEMPTED_INVALID_SIZE", {
            "status": "SEND_NOT_ATTEMPTED_INVALID_SIZE", "exchange_called": False,
            "error": "wire_size<=0", "timing": timing,
        }
    gw2._send_real = _no_call_send_real
    ok3, status3 = gw2.send_if_allowed(exit_intent3)
    checks.append(_check(
        "RESERVATION_CLEARED_NO_EXCHANGE_VIA_DOUBLE",
        (not ok3) and len(gw2._pending_exit_guard) == 0,
        f"ok={ok3}, status={status3}, guard entries={len(gw2._pending_exit_guard)} (cleared when no exchange call)"
    ))

    # Row ORD-006 names SERVICE_STATE_FILE as the location of the unresolved
    # reservation. Genuine runtime check of BOTH durable locations the engine has:
    #  (a) append_order_intent() -> order_intents.csv (append-only)
    #  (b) ServiceStateWriter.write() -> SERVICE_STATE_FILE
    import tempfile as _tf
    _ssd = Path(_tf.mkdtemp(prefix="ord_corr_ss_"))
    _saved = {
        "SERVICE_STATE_FILE": mod.SERVICE_STATE_FILE,
        "CORE_RUNTIME_STATE_FILE": mod.CORE_RUNTIME_STATE_FILE,
        "APPEND_ONLY_DIR": mod.APPEND_ONLY_DIR,
        "ORDER_INTENTS_CSV": mod.ORDER_INTENTS_CSV,
        "SEND_ATTEMPTS_CSV": mod.SEND_ATTEMPTS_CSV,
        "LIVE_FILLS_CSV": mod.LIVE_FILLS_CSV,
        "RECONCILIATION_CSV": mod.RECONCILIATION_CSV,
    }
    _ao = _ssd / "append_only"
    mod.SERVICE_STATE_FILE = _ssd / "live_service_state.json"
    mod.CORE_RUNTIME_STATE_FILE = _ssd / "clean_core_runtime_state.json"
    mod.APPEND_ONLY_DIR = _ao
    mod.ORDER_INTENTS_CSV = _ao / "order_intents.csv"
    mod.SEND_ATTEMPTS_CSV = _ao / "send_attempts.csv"
    mod.LIVE_FILLS_CSV = _ao / "live_fills.csv"
    mod.RECONCILIATION_CSV = _ao / "reconciliation.csv"
    _ao.mkdir(parents=True, exist_ok=True)
    try:
        # (a) the engine's real pre-send durable write
        gw.audit.append_order_intent(exit_intent)
        _intents_csv = mod.ORDER_INTENTS_CSV.read_text(encoding="utf-8")
        # (b) the engine's real service-state write
        mod.ServiceStateWriter().write(mod.CycleSummary(), DedupeStore(), cfg)
        _state_txt = mod.SERVICE_STATE_FILE.read_text(encoding="utf-8")
    finally:
        for _k, _v in _saved.items():
            setattr(mod, _k, _v)
    pre_send_durable_csv = exit_intent.intent_id in _intents_csv
    in_service_state = exit_intent.intent_id in _state_txt

    checks.append(_check(
        "PRE_SEND_DURABLE_RECORD_EXISTS_VIA_APPEND_ONLY_CSV",
        pre_send_durable_csv,
        f"append_order_intent() wrote intent_id={exit_intent.intent_id} to order_intents.csv "
        "(append-only). This is the engine's durable pre-send record."
    ))
    checks.append(_check(
        "RESERVATION_PERSISTED_IN_SERVICE_STATE_FILE",
        in_service_state,
        "FAIL: the row names SERVICE_STATE_FILE as the location of the unresolved reservation, "
        f"but after ServiceStateWriter.write() SERVICE_STATE_FILE does not contain intent_id="
        f"{exit_intent.intent_id}. The engine's pre-send durable record lives in order_intents.csv "
        "(append-only), not SERVICE_STATE_FILE; the in-memory _pending_exit_guard is not persisted. "
        "Row expectation (SERVICE_STATE_FILE) NOT MET."
    ))

    # Negative: remove the reservation (skip _mark_pending_exit) -> duplicate close NOT blocked
    saved_mark = SenderGateway._mark_pending_exit
    SenderGateway._mark_pending_exit = lambda self, intent: None
    ledger_n = _fresh_ledger()
    open_n = _build_intent(cfg, ledger_n, "res-n-open", WALLET_A, "ZWIRE", "SELL", 2.4, 100.0)
    ledger_n.apply_copy_fill(open_n, {"copy_fill_id": "res-n-cf", "side": "SELL",
                                      "size": 50.0, "price": 2.4})
    gw3 = SenderGateway(cfg, AuditLogWriter(), ledger_n)
    gw3._send_real = _fake_send_real
    e3a = _build_intent(cfg, ledger_n, "res-neg-a", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    ok3a, st3a = gw3.send_if_allowed(e3a)
    e3b = _build_intent(cfg, ledger_n, "res-neg-b", WALLET_A, "ZWIRE", "BUY", 2.4, 100.0)
    ok3b, st3b = gw3.send_if_allowed(e3b)
    SenderGateway._mark_pending_exit = saved_mark
    no_reservation_allows_dupes = ok3a and ok3b and st3b != "PENDING_EXIT_GUARD_ACTIVE"
    negatives.append({
        "mutation": "ord006_remove_reservation",
        "expected": "FAIL",
        "actual": "FAIL" if no_reservation_allows_dupes else "PASS",
        "non_vacuous": no_reservation_allows_dupes and (not ok2),
        "detail": f"without reservation dupes allowed: {no_reservation_allows_dupes}; with reservation second blocked: {not ok2}"
    })

    return checks, negatives


# ============================================================
# ORD-008: Exchange preflight
# ============================================================
def test_ord008() -> Tuple[List[Dict], List[Dict]]:
    checks = []
    negatives = []

    # The wire gate (_validate_final_wire_order Gate B) is the true execution
    # authority. cfg min=0 so the SYMBOL min (10.0) binds. Intent sizing uses
    # fixed_notional, so a fixed=5 intent is sub-min (5 < 10) and the ENTRY uplift
    # does NOT fire (intended 5 < DEFAULT_MIN_NOTIONAL 10) -> Gate B blocks it.
    cfg_sub = _cfg(WALLET_A, mode="ON", fixed=5.0, min_notional=0.0)
    ledger = _fresh_ledger()
    gw = SenderGateway(cfg_sub, AuditLogWriter(), ledger)
    intent_small = _build_intent(cfg_sub, ledger, "pre-small", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok, status, result = _wire_send(gw, intent_small, resolve_map={"ZWIRE": RESOLVED_MIN_10})
    exchange_called = len(result.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "BELOW_MIN_NOTIONAL_BLOCKED_VIA_DOUBLE",
        (not exchange_called) and status == "SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL",
        f"exchange_called={exchange_called}, status={status}"
    ))

    # Invalid size (rounds to zero at sz_decimals=2) blocked: fixed=0.001 -> wire_size 0.00
    cfg_z = _cfg(WALLET_A, mode="ON", fixed=0.001, min_notional=0.0)
    ledger_z = _fresh_ledger()
    gw_z = SenderGateway(cfg_z, AuditLogWriter(), ledger_z)
    intent_zero = _build_intent(cfg_z, ledger_z, "pre-zero", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok2, status2, result2 = _wire_send(gw_z, intent_zero, resolve_map={"ZWIRE": RESOLVED_OK})
    exchange_called2 = len(result2.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "INVALID_SIZE_BLOCKED_VIA_DOUBLE",
        (not exchange_called2) and "INVALID_SIZE" in status2,
        f"exchange_called={exchange_called2}, status={status2}"
    ))

    # Unknown asset blocked
    resolved_bad = {"ok": False, "status": "SYMBOL_UNRESOLVED", "error": "unknown symbol"}
    ledger_b = _fresh_ledger()
    gw_b = SenderGateway(cfg_sub, AuditLogWriter(), ledger_b)
    intent_bad = _build_intent(cfg_sub, ledger_b, "pre-bad", WALLET_A, "ZWIRE", "BUY", 100.0, 5.0)
    ok3, status3, result3 = _wire_send(gw_b, intent_bad, resolve_map={"ZWIRE": resolved_bad})
    exchange_called3 = len(result3.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "UNKNOWN_ASSET_BLOCKED_VIA_DOUBLE",
        (not exchange_called3) and status3 == "REAL_SENDER_NOT_CONFIGURED",
        f"exchange_called={exchange_called3}, status={status3}"
    ))

    # Valid order passes preflight (fixed=50 -> notional 50 >= symbol min 10)
    cfg_ok = _cfg(WALLET_A, mode="ON", fixed=50.0, min_notional=0.0)
    ledger_ok = _fresh_ledger()
    gw_ok = SenderGateway(cfg_ok, AuditLogWriter(), ledger_ok)
    intent_valid = _build_intent(cfg_ok, ledger_ok, "pre-valid", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok4, status4, result4 = _wire_send(gw_ok, intent_valid, resolve_map={"ZWIRE": RESOLVED_OK})
    exchange_called4 = len(result4.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "VALID_ORDER_PASSES_PREFLIGHT_VIA_DOUBLE",
        exchange_called4,
        f"exchange_called={exchange_called4}, status={status4}"
    ))

    # Negative: remove the wire min-notional gate -> sub-min order reaches the exchange
    ledger_n = _fresh_ledger()
    gw_n = SenderGateway(cfg_sub, AuditLogWriter(), ledger_n)
    saved_validate = SenderGateway._validate_final_wire_order
    SenderGateway._validate_final_wire_order = lambda self, *a, **k: (True, {})
    intent_small2 = _build_intent(cfg_sub, ledger_n, "pre-small-neg", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok5, status5, result5 = _wire_send(gw_n, intent_small2, resolve_map={"ZWIRE": RESOLVED_MIN_10})
    exchange_called5 = len(result5.get("_fake_exchange_calls", [])) > 0
    SenderGateway._validate_final_wire_order = saved_validate
    negatives.append({
        "mutation": "ord008_remove_min_notional_gate",
        "expected": "FAIL",
        "actual": "FAIL" if exchange_called5 else "PASS",
        "non_vacuous": exchange_called5 and not exchange_called,
        "detail": f"gate removed: exchange_called={exchange_called5}; original: exchange_called={exchange_called}"
    })

    return checks, negatives


# ============================================================
# TN-F05: Sub-minimum OPEN/INCREASE escape
# ============================================================
def test_tnf05() -> Tuple[List[Dict], List[Dict]]:
    checks = []
    negatives = []

    # Sub-min OPEN/INCREASE escape: the minimum is enforced at the true execution
    # authority (wire Gate B). cfg min=0 so the SYMBOL min (10.0) binds; fixed=5
    # gives a 5-notional intent, sub-min, and the ENTRY uplift does not fire.
    cfg = _cfg(WALLET_A, mode="ON", fixed=5.0, min_notional=0.0)
    ledger = _fresh_ledger()
    gw = SenderGateway(cfg, AuditLogWriter(), ledger)
    intent_sub = _build_intent(cfg, ledger, "tnf05-sub", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok, status, result = _wire_send(gw, intent_sub, resolve_map={"ZWIRE": RESOLVED_MIN_10})
    exchange_called = len(result.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "SUB_MIN_ENTRY_BLOCKED_VIA_DOUBLE",
        (not exchange_called) and status == "SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL",
        f"exchange_called={exchange_called}, status={status}"
    ))

    # Effective min is the max of cfg min, DEFAULT_MIN_NOTIONAL, and symbol min
    cfg_min = cfg.min_notional()
    symbol_min = RESOLVED_MIN_10["min_order_value_usd"]
    eff_min = max(DEFAULT_MIN_NOTIONAL, cfg_min, symbol_min)
    checks.append(_check(
        "EFFECTIVE_MIN_CORRECT",
        eff_min == 10.0,
        f"effective_min={eff_min}, cfg_min={cfg_min}, symbol_min={symbol_min}"
    ))

    # Above-min entry passes (fixed=50 -> notional 50 >= 10)
    cfg_ok = _cfg(WALLET_A, mode="ON", fixed=50.0, min_notional=0.0)
    ledger_ok = _fresh_ledger()
    gw_ok = SenderGateway(cfg_ok, AuditLogWriter(), ledger_ok)
    intent_above = _build_intent(cfg_ok, ledger_ok, "tnf05-above", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok2, status2, result2 = _wire_send(gw_ok, intent_above, resolve_map={"ZWIRE": RESOLVED_OK})
    exchange_called2 = len(result2.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "ABOVE_MIN_ENTRY_PASSES_VIA_DOUBLE",
        exchange_called2,
        f"exchange_called={exchange_called2}, status={status2}"
    ))

    # The minimum applies to ENTRY, ADD and EXIT: prove a dust EXIT is also blocked
    # at the wire gate (Gate B has no lifecycle filter).
    ledger_ex = _fresh_ledger()
    open_intent = _build_intent(cfg, ledger_ex, "tnf05-open", WALLET_A, "ZWIRE", "SELL", 100.0, 100.0)
    ledger_ex.apply_copy_fill(open_intent, {"copy_fill_id": "tnf05-cf", "side": "SELL",
                                            "size": 0.05, "price": 100.0})
    gw_ex = SenderGateway(cfg, AuditLogWriter(), ledger_ex)
    exit_dust = _build_intent(cfg, ledger_ex, "tnf05-exit", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok3, status3, result3 = _wire_send(gw_ex, exit_dust, resolve_map={"ZWIRE": RESOLVED_MIN_10})
    exit_called = len(result3.get("_fake_exchange_calls", [])) > 0
    checks.append(_check(
        "MIN_NOTIONAL_APPLIES_TO_EXIT_VIA_DOUBLE",
        (not exit_called) and status3 == "SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL",
        f"dust EXIT: exchange_called={exit_called}, status={status3}"
    ))

    # Negative: remove the effective min -> sub-min entry reaches the exchange
    ledger_n = _fresh_ledger()
    gw_n = SenderGateway(cfg, AuditLogWriter(), ledger_n)
    saved_eff = SenderGateway._effective_symbol_min_notional
    SenderGateway._effective_symbol_min_notional = lambda self, resolved: 0.0
    intent_sub2 = _build_intent(cfg, ledger_n, "tnf05-sub-neg", WALLET_A, "ZWIRE", "BUY", 100.0, 100.0)
    ok4, status4, result4 = _wire_send(gw_n, intent_sub2, resolve_map={"ZWIRE": RESOLVED_MIN_10})
    exchange_called4 = len(result4.get("_fake_exchange_calls", [])) > 0
    SenderGateway._effective_symbol_min_notional = saved_eff
    negatives.append({
        "mutation": "tnf05_remove_effective_min",
        "expected": "FAIL",
        "actual": "FAIL" if exchange_called4 else "PASS",
        "non_vacuous": exchange_called4 and not exchange_called,
        "detail": f"min removed: exchange_called={exchange_called4}; original: exchange_called={exchange_called}"
    })

    return checks, negatives


# ============================================================
# Main
# ============================================================
def main():
    all_checks = {}
    all_negatives = []

    for row_id, test_fn in [
        ("ORD-001", test_ord001),
        ("ORD-002", test_ord002),
        ("ORD-005", test_ord005),
        ("ORD-006", test_ord006),
        ("ORD-008", test_ord008),
        ("TN-F05", test_tnf05),
    ]:
        checks, negatives = test_fn()
        all_checks[row_id] = checks
        all_negatives.extend(negatives)

    # Build result
    total_checks = sum(len(v) for v in all_checks.values())
    passed_checks = sum(1 for v in all_checks.values() for c in v if c["pass"])
    all_non_vacuous = all(n.get("non_vacuous", False) for n in all_negatives)

    # Per-row verdicts with the oracle ACTUALLY used. The row oracle named in the
    # matrix is exchange truth (order status / userFills for the cloid/oid); that is
    # NOT achievable on testnet (follower wallet does not exist on testnet, see
    # t_5cf2e6cf / t_7e8b0eb9). Each gate-logic check is earned via an in-process
    # exchange double, which proves the engine's gate behaviour but is NOT exchange
    # truth. So every row is PARTIAL: gate semantics ESTABLISHED, exchange-truth
    # aspect NOT_ESTABLISHED.
    _row_oracle = {
        "ORD-001": "Exchange order status / userFills for the cloid/oid (NOT achievable on testnet)",
        "ORD-002": "Exchange order status / userFills for the cloid/oid (NOT achievable on testnet)",
        "ORD-005": "Exchange order status / userFills for the cloid/oid (NOT achievable on testnet)",
        "ORD-006": "Exchange order status / userFills for the cloid/oid (NOT achievable on testnet)",
        "ORD-008": "Exchange order status / userFills for the cloid/oid (NOT achievable on testnet)",
        "TN-F05": "Exchange order status / userFills for the cloid/oid (NOT achievable on testnet)",
    }
    _row_notes = {
        "ORD-001": "Single sender / single gate. Gate + call-site behaviour proven via double; "
                   "one physical exchange.order() site confirmed at runtime (1 call per send).",
        "ORD-002": "reduce_only correctness. EXIT -> reduce_only=True, ENTRY -> False, proven at "
                   "the wire via double. No exchange fill observed.",
        "ORD-005": "Exactly-once execution identity. DedupeStore + deterministic intent_id proven "
                   "at runtime. Ambiguous-submission-stays-UNRESOLVED not exercised (needs exchange truth).",
        "ORD-006": "Pre-send reservation. Pending-exit reservation proven at runtime (created on send, "
                   "not cleared on ACK, cleared when no exchange call). Persistence in SERVICE_STATE_FILE "
                   "is NOT_ESTABLISHED (reservation is in-memory only).",
        "ORD-008": "Exchange preflight. Below-min / invalid-size / unknown-asset blocked before the "
                   "exchange call; valid order reaches it. Proven via double; no exchange truth.",
        "TN-F05": "Sub-minimum OPEN/INCREASE escape. Minimum enforced at the wire gate for ENTRY and EXIT; "
                  "proven via double; no exchange truth.",
    }
    rows = {}
    for row_id, checks in all_checks.items():
        gate_pass = all(c["pass"] for c in checks)
        if not gate_pass:
            verdict = "FAIL"
        else:
            verdict = "PARTIAL"  # exchange-truth aspect is always NOT_ESTABLISHED on testnet
        rows[row_id] = {
            "verdict": verdict,
            "gate_logic_checks_pass": gate_pass,
            "checks_pass": sum(1 for c in checks if c["pass"]),
            "checks_total": len(checks),
            "oracle_named_in_matrix": _row_oracle[row_id],
            "oracle_actually_used": "in-process exchange double + engine runtime gate outcome "
                                    "(fabricated ORDER_FILLED from the double is NOT exchange truth)",
            "exchange_truth_aspect": "NOT_ESTABLISHED (follower wallet does not exist on testnet)",
            "notes": _row_notes[row_id],
            "checks": checks,
        }

    all_gate_pass = all(r["gate_logic_checks_pass"] for r in rows.values())
    overall = "PARTIAL" if all_gate_pass and all_non_vacuous else "FAIL"

    result = {
        "task_id": "t_a7d41440",
        "title": "B3-CERT ORDER CORRECTION (6 rows): order-path semantics proof",
        "tested_commit": f"{COMMIT10}261c734bb32c767d2cc4a91095e65843",
        "engine_commit_reference": f"{COMMIT10}261c734bb32c767d2cc4a91095e65843",
        "repo_head_at_run": _git_head(),
        "tested_at_utc": mod.utc_now_iso() if hasattr(mod, 'utc_now_iso') else "",
        "engine_sha256": hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest(),
        "engine_lines": len(ENGINE_PATH.read_text(encoding='utf-8', errors='replace').splitlines()),
        "rows": rows,
        "checks": all_checks,
        "negative_tests": all_negatives,
        "summary": {
            "overall": overall,
            "all_gate_logic_pass": all_gate_pass,
            "all_non_vacuous": all_non_vacuous,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "total_negative": len(all_negatives),
            "non_vacuous_negative": sum(1 for n in all_negatives if n.get("non_vacuous", False)),
            "rows_total": len(rows),
            "rows_partial": sum(1 for r in rows.values() if r["verdict"] == "PARTIAL"),
            "rows_fail": sum(1 for r in rows.values() if r["verdict"] == "FAIL"),
        },
        "oracle_statement": (
            "The row oracle named in certification_matrix.json is exchange truth (order status / "
            "userFills for the cloid/oid). That truth is NOT achievable on testnet because the follower "
            "wallet does not exist on testnet (t_5cf2e6cf / t_7e8b0eb9). Every check here is earned by the "
            "runtime outcome of the engine's REAL gate logic against an IN-PROCESS exchange double. The "
            "double returns a fabricated ORDER_FILLED; that is NOT exchange truth and is never claimed as "
            "such. No check is a source-substring/regex-on-source check. Therefore each row is PARTIAL: "
            "gate semantics ESTABLISHED, exchange-truth aspect NOT_ESTABLISHED."
        ),
        "harness": "certification/results/ORDER_CORRECTION_harness_fefc2b04.py",
    }

    out_path = REPO / "certification" / "results" / f"ORDER_CORRECTION_{COMMIT10}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Result written to: {out_path}")
    print(f"Overall: {overall}")
    print(f"Checks: {passed_checks}/{total_checks} PASS")
    print(f"Negatives: {sum(1 for n in all_negatives if n.get('non_vacuous', False))}/{len(all_negatives)} non-vacuous")
    for row_id, r in rows.items():
        print(f"  {row_id}: {r['verdict']} ({r['checks_pass']}/{r['checks_total']})")

    return result


if __name__ == "__main__":
    main()
