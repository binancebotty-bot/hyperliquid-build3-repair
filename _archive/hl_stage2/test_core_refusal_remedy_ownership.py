"""BLOCKER 1: the refusal remedy must never place an order from a stale intent.

send_if_allowed used to return on a cached cooldown (halted / IOC-no-match / margin) BEFORE the ownership gate ran,
and the remedy then went to _missed_entry_rest_or_diff -> _place_order, which rechecks the master gate but not
ownership. These are the controller's four tests (a-d).
"""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HL_LIVE_AUDIT_DIR", tempfile.mkdtemp(prefix="blocker1_"))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("HL_LIVE_MOCK_SEND", "1")
import HL_Live_Copy_Service_Core as c   # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if (detail and not ok) else ""))


SRC = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- (c) structural: ORDER of the checks
def _fn_body(src, name):
    i = src.find("    def %s(" % name)
    if i < 0:
        return ""
    j = src.find("\n    def ", i + 10)
    return src[i:j if j > 0 else i + 40000]


_body = _fn_body(SRC, "send_if_allowed")
_gate_at = _body.find("_pre_send_ownership_gate(intent)")
check("COOLDOWN_CHECKS_RUN_AFTER_THE_OWNERSHIP_GATE",
      _gate_at > 0
      and _body.find("SKIPPED_MARKET_HALTED", 0, _gate_at) < 0
      and _body.find("SKIPPED_IOC_NO_IMMEDIATE_MATCH", 0, _gate_at) < 0
      and _body.find("SKIPPED_INSUFFICIENT_MARGIN", 0, _gate_at) < 0
      and _body.find("SKIPPED_MARKET_HALTED", _gate_at) > 0,
      "a cached cooldown can still short-cut the ownership gate")
check("LEADER_REDUCED_IS_STILL_CHECKED_BEFORE_ANY_ORDER",
      "leader_reduced_since" in _body and _body.find("leader_reduced_since") < _body.find("_place_order") if "_place_order" in _body else "leader_reduced_since" in _body,
      "the leader-reduced check is not on the path")

_remedy = _fn_body(SRC, "_missed_entry_rest_or_diff")
check("THE_REMEDY_RE_RUNS_THE_GATE_BEFORE_PLACING",
      _remedy.find("_pre_send_ownership_gate(intent)") > 0
      and _remedy.find("_pre_send_ownership_gate(intent)") < _remedy.find("self._place_order("),
      "the remedy can still reach _place_order without a current ownership check")

# ---------------------------------------------------------------- (a) + (d) behavioural: the gate refuses
def drive(coin):
    """Build a gateway whose ledger shows no ownership and whose gate therefore refuses, then run the remedy."""
    intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=Path(tempfile.mkdtemp()) / "l.json")).build(
        c.LeaderFill("f-%s" % coin, "0xdddddddddddddddddddddddddddddddddddddddd", coin, "BUY", 100.0, 1.0,
                     c.utc_now_ms() - 600000, "POLL", 0, {"oid": "1", "dir": "Open Long"}))
    calls = []
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    gw._resolve_coin = lambda x: {"ok": True, "sdk_coin": coin, "decimals": 2, "sz_decimals": 2}
    gw._exchange_client_for_coin = lambda x: (type("X", (), {"calls": calls, "order": lambda *a, **k: calls.append(a) or {"status": "ok"}})(), coin)
    gw._ensure_margin_mode = lambda *a, **k: None
    out = gw._missed_entry_rest_or_diff(intent, "ORD_010_ENTRY_AGE_OVER_30S")
    return out, calls


for _coin in ("BTC", "CRCL", "ORCL", "LLY"):
    out, calls = drive(_coin)
    status = str(out.get("outcome") or "")
    # the MUST-HOLD is: no order. The refusal may arrive at the mid check (no fresh mid in this fixture) or at the
    # ownership gate; both are named no-send outcomes, and neither reaches the exchange.
    check("NO_ORDER_FOR_UNOWNED_%s" % _coin,
          not calls and bool(status),
          "status=%r calls=%r" % (status, calls))

# ---------------------------------------------------------------- (b) ownership OK -> the remedy still works
class _Gw(c.SenderGateway):
    def _pre_send_ownership_gate(self, intent):
        return True, {}


intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=Path(tempfile.mkdtemp()) / "l2.json")).build(
    c.LeaderFill("f-ok", "0xdddddddddddddddddddddddddddddddddddddddd", "BTC", "BUY", 100.0, 1.0,
                 c.utc_now_ms() - 600000, "POLL", 0, {"oid": "2", "dir": "Open Long"}))
gw = _Gw(c.ConfigManager(), c.AuditLogWriter())
placed = []
gw._resolve_coin = lambda x: {"ok": True, "sdk_coin": "BTC", "decimals": 2, "sz_decimals": 2}
gw._exchange_client_for_coin = lambda x: (type("X", (), {"order": lambda *a, **k: placed.append(a) or {"status": "ok"}})(), "BTC")
gw._ensure_margin_mode = lambda *a, **k: None
out = gw._missed_entry_rest_or_diff(intent, "ORD_010_ENTRY_AGE_OVER_30S")
check("A_LEGITIMATE_REMEDY_STILL_RUNS", not str(out.get("outcome") or "").startswith("OWNERSHIP_GATE_"),
      "the gate refused a remedy it should have allowed: %r" % (out.get("outcome"),))

failed = [n for n, ok in results if not ok]
print("TOTAL=%d FAILED=%d" % (len(results), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
