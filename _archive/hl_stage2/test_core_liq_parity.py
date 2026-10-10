#!/usr/bin/env python3
"""C3 - liquidation-price parity + margin mode, mock-send evidence (spec: issue #3 comments 6095810972 / 6095960697).

Boss 08:42Z / 08:44Z: "the follower's liquidation must never be worse than any leader's", copy leverage
default 3x on CROSS margin. The spec (a port of Build 4's proof_core/safety/liquidation_projection.py +
the P0-4 parity gate) requires:

  * Margin mode (step 1): before the FIRST order in an asset, call exchange.update_leverage(lev, coin,
    is_cross=True) once per asset per run. `lev` = min(asset maxLeverage, global_controls.follower_leverage
    (default 3)). Cache it; write a MARGIN_MODE_SET audit row; fail closed for entries (MARGIN_MODE_UNSET)
    if the call fails; closes are never blocked.
  * Parity gate (step 2) for ENTRY/ADD: leader distance = |mark - leader liquidationPx| / mark from the
    leader network (cached ~10 s). Follower distance = the projected post-trade liquidationPx (a port of
    Hyperliquid's LiquidationPx.tsx) on the follower's clearinghouseState. Allow the entry only if the
    follower distance >= the safest contributing leader's; otherwise refuse with LIQ_PARITY_BLOCKED.
    Unknown/unprovable projection fails closed; a fully-collateralised leader (no liquidationPx) takes
    the stricter rule. REDUCE/CLOSE are always allowed.

These tests drive the engine's REAL paths: step 1 through SenderGateway._send_real (a FakeExchange records
update_leverage / order), the gate through SenderGateway.send_if_allowed with the engine's own mock-send
path (HL_LIVE_MOCK_SEND=1). No exchange is touched and no order is placed. A check that FAILs is a FINDING
about the engine, not a reason to weaken the test (task C3: "If the engine fails a test, report it as a
finding with the failing output").

Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python -u test_core_liq_parity.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
SENT = "MOCK_ORDER_SENT"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="c3liq_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MOCK_SEND": "1", "HL_LIVE_LIQ_PARITY": "1", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

    def write_cfg(gc=None, auto=True):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": auto, "global_controls": gc or {},
            "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    write_cfg()

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    class FakeExchange:
        """Records every call. `raise_on_leverage` reproduces a margin-mode call the exchange refuses."""
        def __init__(self, raise_on_leverage=False):
            self.calls = []
            self.raise_on_leverage = raise_on_leverage

        def update_leverage(self, leverage, name, is_cross=True):  # the real SDK order of arguments
            self.calls.append(("update_leverage", name, leverage, is_cross))
            if self.raise_on_leverage:
                raise RuntimeError("exchange refused update_leverage")
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append(("order", coin, is_buy, size, px, tif["limit"]["tif"], reduce_only))
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    def gateway(fake, ledger=None):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        g._resolve_coin = lambda coin: dict(resolved)
        g._get_exchange_client = lambda *a, **k: fake
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (fake, "BTC")
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        return g

    def send_real(g, intent):
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            return g._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

    def mk_intent(decision, lifecycle, side="BUY", size=1.0, before=0.0):
        fill = c.LeaderFill("f1", A, "BTC", side, 100.0, size, c.utc_now_ms(), "TEST")
        return c.Intent("i1", fill, side, size, size * 100.0, "ON", "fixed", decision, lifecycle,
                        "sleeve:%s:BTC" % A, "", "FLAT", before, before, False, False, c.utc_now_ms(),
                        "lifecycle=%s;" % lifecycle)

    # ---- L1/L3: margin mode is set once, before the first order, and fails closed ----------------
    fake = FakeExchange()
    g = gateway(fake, c.ManualLedger(path=tmp / "l1.json"))
    ok, status, _ = send_real(g, mk_intent("ENTRY_ALLOWED", "ENTRY"))
    lev_calls = [x for x in fake.calls if x[0] == "update_leverage"]
    order_idx = next((i for i, x in enumerate(fake.calls) if x[0] == "order"), None)
    lev_idx = next((i for i, x in enumerate(fake.calls) if x[0] == "update_leverage"), None)
    check("L1_UPDATE_LEVERAGE_CROSS_ONCE_BEFORE_FIRST_ORDER",
          len(lev_calls) == 1 and lev_calls[0][3] is True and lev_idx is not None and order_idx is not None
          and lev_idx < order_idx and lev_calls[0][2] == 3,
          "no exchange.update_leverage(.., is_cross=True) call before the first order; calls=%s" % (fake.calls,))
    # a second order in the same asset must not repeat it (cached once per asset per run)
    order_n = len([x for x in fake.calls if x[0] == "order"])
    send_real(g, mk_intent("ENTRY_ALLOWED", "ENTRY"))
    check("L1B_UPDATE_LEVERAGE_NOT_REPEATED_PER_ORDER",
          len([x for x in fake.calls if x[0] == "update_leverage"]) == 1
          and len([x for x in fake.calls if x[0] == "order"]) == order_n + 1,
          "calls=%s" % (fake.calls,))

    # margin mode refused by the exchange: an ENTRY must be refused (MARGIN_MODE_UNSET); a CLOSE still goes
    fake_bad = FakeExchange(raise_on_leverage=True)
    gb = gateway(fake_bad, c.ManualLedger(path=tmp / "l3.json"))
    ent_ok, ent_status, _ = send_real(gb, mk_intent("ENTRY_ALLOWED", "ENTRY"))
    cl_ok, cl_status, _ = send_real(gb, mk_intent("EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0))
    check("L3_MARGIN_MODE_FAILURE_BLOCKS_ENTRY_NOT_CLOSE",
          ent_ok is False and "MARGIN_MODE_UNSET" in str(ent_status) and cl_ok is True,
          "entry=(%s,%s) want (False, *MARGIN_MODE_UNSET*); close=(%s,%s)" % (ent_ok, ent_status, cl_ok, cl_status))

    # ---- L2: the follower_leverage control (default 3, configurable) -----------------------------
    cfg_missing = c.ConfigManager()
    default_val = _probe_leverage(cfg_missing)
    write_cfg(gc={"follower_leverage": 5})
    explicit_val = _probe_leverage(c.ConfigManager())
    check("L2_FOLLOWER_LEVERAGE_CONTROL_DEFAULT_3_CONFIGURABLE",
          default_val == 3 and explicit_val == 5,
          "follower_leverage reader: missing=%r (want 3), explicit 5=%r (want 5); engine has no "
          "global_controls.follower_leverage reader" % (default_val, explicit_val))
    write_cfg()

    # ---- L4: the margin-mode call is audited (MARGIN_MODE_SET) -----------------------------------
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    check("L4_MARGIN_MODE_SET_AUDITED", "MARGIN_MODE_SET" in src,
          "no MARGIN_MODE_SET audit row anywhere in the engine")

    # ---- L5: a cross liquidation projection exists (port of LiquidationPx.tsx) -------------------
    proj = _find_projection(c)
    check("L5_LIQUIDATION_PROJECTION_PRESENT", proj is not None,
          "engine exposes no cross liquidation projection (no project_liquidation_px / liquidation_projection / "
          "projected_liquidation_px)")

    # ---- L6-L9: the parity gate on a mock send ---------------------------------------------------
    # leader holds BTC at 1x-ish with liquidationPx 50 (distance |100-50|/100 = 0.50); the follower is
    # near liquidation at 99 (distance 0.01, worse) in the unsafe case, at 10 (0.90, better) in the safe one.
    leader_reads = []

    def leader_fetcher(url, json=None, timeout=None):
        if json and json.get("type") == "clearinghouseState":
            leader_reads.append(json.get("user"))
            class R:
                def json(self_inner):
                    return {"assetPositions": [{"position": {"coin": "BTC", "szi": "1.0", "entryPx": "100",
                                                             "liquidationPx": "50"}}],
                            "crossMarginSummary": {"accountValue": "1000", "crossMaintenanceMarginUsed": "5"},
                            "marginSummary": {"accountValue": "1000"}}
            return R()
        raise RuntimeError("offline test: no other leader read")
    c.LEADER_FETCHER = leader_fetcher
    requests.post = leader_fetcher
    c.requests.post = leader_fetcher

    def follower_liq(px):
        c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": 1.0}},
                                                              "liquidation_px_by_coin": {"BTC": px}})

    def parity_entry():
        g = gateway(FakeExchange(), c.ManualLedger(path=tmp / "l6.json"))
        return g.send_if_allowed(mk_intent("ENTRY_ALLOWED", "ENTRY"))

    follower_liq(99.0)                       # follower worse than the safest leader (0.01 < 0.50): must block
    unsafe = parity_entry()
    check("L6_PARITY_BLOCKS_WORSE_THAN_SAFEST_LEADER",
          unsafe == (False, "LIQ_PARITY_BLOCKED"),
          "follower distance 0.01 < leader 0.50 but entry=%s (want (False, LIQ_PARITY_BLOCKED)); "
          "leader liquidationPx never read (leader_reads=%s)" % (unsafe, leader_reads))

    follower_liq(10.0)                       # follower safer (0.90 >= 0.50): only a PASS if a gate exists
    safe = parity_entry()
    check("L7_PARITY_ALLOWS_SAME_OR_BETTER", proj is not None and safe[1] == SENT,
          "entry=%s; gate present=%s (an allowed entry is only meaningful once the gate exists)" % (safe, proj is not None))

    class Resp:
        def __init__(self, body):
            self._b = body
        def json(self):
            return self._b

    def unreadable(url, json=None, timeout=None):
        raise RuntimeError("leader read failed")
    c.LEADER_FETCHER = unreadable
    c.requests.post = unreadable
    requests.post = unreadable
    unknown = parity_entry()
    check("L8_UNKNOWN_PROJECTION_FAILS_CLOSED", unknown == (False, "LIQ_PARITY_BLOCKED"),
          "entry=%s with unreadable leader state (want a fail-closed block)" % (unknown,))

    c.LEADER_FETCHER = leader_fetcher
    c.requests.post = leader_fetcher
    requests.post = leader_fetcher
    follower_liq(99.0)
    g9 = gateway(FakeExchange(), c.ManualLedger(path=tmp / "l9.json"))
    close = g9.send_if_allowed(mk_intent("EXIT_ALLOWED", "EXIT", "SELL", 1.0, 1.0))
    check("L9_CLOSES_NEVER_BLOCKED_BY_PARITY", close[1] == SENT,
          "close=%s (a reduce-only close must never be blocked by the parity gate)" % (close,))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


def _probe_leverage(cfg) -> object:
    """Read the spec's follower_leverage control through the engine's own reader (the contract)."""
    for getter in ("follower_leverage", "max_follower_leverage", "global_follower_leverage"):
        fn = getattr(cfg, getter, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                continue
    return None


def _find_projection(core):
    for name in ("project_liquidation_px", "liquidation_projection", "projected_liquidation_px",
                 "compute_liquidation_px", "liquidation_px_for"):
        fn = getattr(core, name, None)
        if callable(fn):
            return name
    try:
        import importlib
        mod = importlib.import_module("liquidation_projection")
        for name in ("project_liquidation_px", "project", "liquidation_px"):
            if callable(getattr(mod, name, None)):
                return "liquidation_projection.%s" % name
    except Exception:
        pass
    return None


if __name__ == "__main__":
    main()
