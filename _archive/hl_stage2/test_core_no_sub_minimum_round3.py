#!/usr/bin/env python3
"""Round 3 of the no-sub-minimum rule: controller ruling 6301015850 (option C), two follow-ups.

(i) ONE MINIMUM: convergence judges a sleeve by the same number the wire gate applies
    (SenderGateway._effective_symbol_min_notional, symbol minimum included).
(ii) NO PHANTOM CLOSES: when the wire gate refuses a convergence close, the CONVERGE_CLOSE row says REFUSED.

Offline only. Run: python test_core_no_sub_minimum_round3.py
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="nosubmin_r3_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet"})
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

MIN = c.DEFAULT_MIN_NOTIONAL
SYMBOL_MIN = MIN * 2
A = "0x" + "a" * 40

stub = SimpleNamespace(
    cfg=SimpleNamespace(min_notional=lambda: MIN),
    sender=SimpleNamespace(
        _resolve_coin=lambda coin: {"ok": True, "sdk_coin": str(coin), "raw_coin": str(coin),
                                    "min_order_value_usd": SYMBOL_MIN},
        _effective_symbol_min_notional=lambda resolved: max(MIN, float(resolved.get("min_order_value_usd") or 0.0)),
    ),
)
_cand_fn = getattr(c.LiveCopyCore, "_converge_candidate", None)
_eff_fn = getattr(c.LiveCopyCore, "_converge_effective_min", None)
if _eff_fn is not None:  # the real helper on a stub: the round-2 head has none and falls back to the configured min
    stub._converge_effective_min = lambda coin: _eff_fn(stub, coin)

def cand(size, px, lead, epx, coin="BTC"):
    if _cand_fn is None:
        return False, "MISSING"
    try:
        return _cand_fn(stub, size, px, lead, epx, coin)
    except TypeError:
        return _cand_fn(stub, size, px, lead, epx)

ok_, reason = cand(0.15, 100.0, +5.0, 60.0)
check("R3_UNIFIED_MIN_GAP_SLEEVE_IS_A_REMAINDER", ok_ is True and reason == "SUB_MINIMUM_PARTIAL_FILL_REMAINDER", (ok_, reason))
ok_, reason = cand(0.15, 100.0, +5.0, 100.0)
check("R3_UNIFIED_MIN_GAP_PRICE_ONLY_LEFT_ALONE", ok_ is False and reason == "", (ok_, reason))
ok_, reason = cand(0.25, 100.0, +5.0, 100.0)
check("R3_UNIFIED_MIN_NORMAL_SLEEVE_UNCHANGED", ok_ is False and reason == "", (ok_, reason))
ok_, reason = cand(0.15, 100.0, 0.0, 100.0)
check("R3_UNIFIED_MIN_GAP_LEADER_FLAT_CLOSES", ok_ is True and reason == "LEADER_FLAT", (ok_, reason))
ok_, reason = cand(0.15, 100.0, -5.0, 60.0)
check("R3_UNIFIED_MIN_GAP_LEADER_OPPOSITE_CLOSES", ok_ is True and reason == "LEADER_OPPOSITE_SIDE", (ok_, reason))

os.environ.update({"HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
import requests
c.requests.post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline test: no network"))
c.USER_WALLET = "0x" + "c" * 40
c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"ETH": "100"}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
c.LEADER_FETCHER = lambda payload: {"marginSummary": {"accountValue": "1000"}, "assetPositions": []}

c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
    A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
core = c.LiveCopyCore(source_csv=tmp / "none.csv")
core.cfg.master_switch_now = lambda: True
core.ledger.sleeve(A, "ETH")["signed_size"] = 1.0
core.ledger.sleeve(A, "ETH")["position_id"] = "p-refused"
core.ledger._recompute_net(core.ledger.data)
core.sender.send_if_allowed = lambda intent, block="": (False, "SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL")
os.environ["HL_LIVE_CONVERGE_CONFIRM_SEC"] = "0"
core.converge_once()
core.converge_once()
core.stop()
rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("event") == "CONVERGE_CLOSE"]
refused = [r for r in rows if r.get("action") == "NO_SEND_GATE_REFUSED"]
check("R3_REFUSED_CONVERGE_WRITES_A_REFUSED_ROW", bool(refused)
      and all("REFUSED" in str(r.get("status")) for r in refused), [r.get("status") for r in rows])
check("R3_REFUSED_CONVERGE_NEVER_NAMES_A_CLOSE",
      all("CLOSE_ENGINE_SLEEVE" not in str(r.get("action") or "") for r in rows)
      and not any(str(r.get("status") or "") in ("CONVERGE_LEADER_FLAT", "CONVERGE_LEADER_OPPOSITE_SIDE") for r in rows),
      [(r.get("status"), r.get("action")) for r in rows])

# ---------------------------------------------------------------- ruling 6301015850 C: multi-leader control
# A sub-minimum price-only sleeve whose OWN leader still holds waits for coin-flat or its own leader
# leaving; no sibling leader's sleeve is closed to clear it.
B = "0x" + "b" * 40
c.LEADER_FETCHER = lambda payload: (
    {"marginSummary": {"accountValue": "1000"},
     "assetPositions": [{"position": {"coin": "ETH", "szi": "5", "positionValue": "500"}}]}
    if str(payload.get("user") or "").lower() == A else
    {"marginSummary": {"accountValue": "1000"}, "assetPositions": []}
)
c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
    A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12},
    B: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
_n0 = len([r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("event") == "CONVERGE_CLOSE"])  # earlier cases wrote rows for A too
core2 = c.LiveCopyCore(source_csv=tmp / "none2.csv")
core2.cfg.master_switch_now = lambda: True
core2.ledger.sleeve(A, "ETH")["signed_size"] = 0.05    # $5 at the mid: genuinely under the $10 minimum,
core2.ledger.sleeve(A, "ETH")["position_id"] = "p-a"   # entered at $400 so it fell there from price alone
core2.ledger.sleeve(A, "ETH")["avg_entry_px"] = 400.0
core2.ledger.sleeve(B, "ETH")["signed_size"] = 1.0
core2.ledger.sleeve(B, "ETH")["position_id"] = "p-b"
core2.ledger._recompute_net(core2.ledger.data)
core2.sender.send_if_allowed = lambda intent, block="": (False, "OFFLINE_TEST_GATE")
out2 = core2.converge_once()
core2.converge_once()
core2.stop()
rows2 = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("event") == "CONVERGE_CLOSE"][_n0:]  # only the rows this case wrote
check("R3_MULTI_LEADER_SUB_MINIMUM_SLEEVE_IS_NOT_CLOSED",
      abs(core2.ledger.sleeve(A, "ETH")["signed_size"] - 0.05) < 1e-9
      and 0.05 * 100.0 < c.DEFAULT_MIN_NOTIONAL)  # the premise: it really is under the minimum
check("R3_MULTI_LEADER_NO_SIBLING_SLEEVE_CLOSED",
      not any(str(r.get("leader_wallet") or "").lower() == A for r in rows2), rows2)
check("R3_MULTI_LEADER_COIN_FLAT_SLEEVE_STILL_CLOSES",
      out2.get("queued", 0) >= 1 and any(str(r.get("leader_wallet") or "").lower() == B for r in rows2),
      (out2.get("queued"), rows2))

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
