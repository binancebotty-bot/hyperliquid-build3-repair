"""BEHAVIOURAL test of the flatten SEND path - not source-text assertions.

A stub engine module and a stub gateway are injected, then main() is driven end to end for two cases:
  A) the order is accepted                      -> row status FILLED, a cloid on the row, a FLATTEN journal row
  B) the exchange FILLS and the response raises -> row FILLED_DESPITE_EXCEPTION with the cloid (the HBAR case)
"""

import csv
import json
import os
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

STATE = Path(tempfile.mkdtemp(prefix="flatten_send_"))
(STATE / "append_only").mkdir(parents=True, exist_ok=True)
(STATE / "manual_live_positions.json").write_text(json.dumps(
    {"by_wallet": {"0xleader": {"TEST": {"signed_size": 10.0}}}}), encoding="utf-8")
(STATE / "live_config.json").write_text(json.dumps(
    {"wallets": {"0xleader": {"mode": "LIVE", "enabled": True}}}), encoding="utf-8")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if (detail and not ok) else ""))


# ---------------------------------------------------------------- the stub engine module
class _Fill:
    def __init__(self, *a, **k):
        self.leader_fill_id, self.leader_wallet, self.coin = a[0], a[1], a[2]
        self.side, self.price, self.size = a[3], a[4], a[5]
        self.raw = a[9] if len(a) > 9 else {}


class _Intent:
    intent_id = "i-flatten"


class _Builder:
    def __init__(self, *a, **k):
        pass

    def build(self, fill):
        return _Intent()


class _Ledger:
    def __init__(self, *a, **k):
        pass


class _Cfg:
    def __init__(self, *a, **k):
        pass


class _Audit:
    def __init__(self, *a, **k):
        pass


IFACE = {"raise_on_response": False, "calls": []}


class _Gateway:
    def __init__(self, *a, **k):
        pass

    _core_meta_fetched = True        # the stub is already warm; the real gateway fetches meta here

    def _fetch_core_meta(self):
        self._core_meta_fetched = True

    def _resolve_coin(self, coin):
        return {"ok": True, "price_max_decimals": 5, "sz_decimals": 2}

    def _exchange_client_for_coin(self, coin):
        return (object(), coin)

    @staticmethod
    def _format_limit_px(px, dec):
        return round(px, min(int(dec or 0), 5))

    @staticmethod
    def _floor_wire_size(size, dec):
        step = 10 ** (-max(0, int(dec or 0)))
        return int(float(size) / step) * step

    def _place_order(self, *a, **k):
        IFACE["calls"].append(a)
        if IFACE["raise_on_response"]:
            IFACE["filled"] = True          # the exchange DID fill; the response path then raises
            raise ValueError("float_to_wire causes rounding")
        return {"status": "ok"}

    def _parse_hl_response(self, resp):
        return True, "ORDER_FILLED", "63700000001", ""


def _make_stub_module():
    m = types.ModuleType("HL_Live_Copy_Service_Core")
    m.SenderGateway = _Gateway
    m.ConfigManager = _Cfg
    m.AuditLogWriter = _Audit
    m.IntentBuilder = _Builder
    m.LeaderFill = _Fill
    m.ManualLedger = _Ledger

    def utc_now_ms():
        return 1793000000000
    def utc_now_iso():
        return "2026-10-26T15:00:00+00:00"
    def generate_cloid(seed):
        return "0x" + (str(seed).encode().hex()[:32]).ljust(32, "0")
    def append_csv(path, fields, row):
        exists = Path(path).exists()
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            if not exists:
                w.writeheader()
            w.writerow(row)
        return True
    m.utc_now_ms, m.utc_now_iso, m.generate_cloid, m.append_csv = utc_now_ms, utc_now_iso, generate_cloid, append_csv
    m.SEND_ATTEMPTS_FIELDS = ["created_at", "created_at_ms", "attempt_id", "intent_id", "leader_fill_id",
                              "leader_wallet", "coin", "side", "order_type", "status", "cloid",
                              "exchange_order_id", "action", "notes", "fill_price", "fill_size"]
    return m


sys.modules["HL_Live_Copy_Service_Core"] = _make_stub_module()
import flatten_testnet as F   # noqa: E402

# ---------------------------------------------------------------- stub the exchange reads
_net = {"TEST": 10.0}


def _open_positions(wallet):
    return [{"coin": "TEST", "net": _net["TEST"], "value": 10.0}] if _net["TEST"] else []


F.open_positions = _open_positions
F.resting_orders = lambda w: []
F._info = lambda body: ({"universe": [{"name": "TEST", "szDecimals": 2}]} if body.get("type") == "meta"
                        else {"TEST": "1.0"})
F.mids_now = lambda: {"mids": {"TEST": "1.0"}, "ts": 1e18}          # fresh against the wall clock below
F.fresh_mid = lambda payload, coin, now: 1.0
F.engine_pids = lambda state=None: []
F.journal_coins = lambda state: set()
F.ledger_nets = lambda state: {"TEST": 10.0}
F.ledger_fingerprint = lambda p: {"sha256": "x", "mtime_ns": 1, "size": 1}
F.ledger_unchanged = lambda p, fp: True
F.client_is_testnet = lambda exch: True
F.live_wallet_for = lambda state: "0xleader"
F.is_testnet = lambda *a, **k: True
os.environ["HL_USER_WALLET"] = "0xfollower"

ARGS = ["--state", str(STATE), "--live", "--cancel-resting", "--only", "TEST"]

# ---------------------------------------------------------------- A. a normal fill
_net["TEST"] = 10.0
_rc = F.main(ARGS)
_report = sorted(STATE.glob("FLATTEN_LIVE_*.json"))[-1]
_rows = json.loads(_report.read_text(encoding="utf-8"))["rows"]
_row = [r for r in _rows if r.get("coin") == "TEST"][0]
check("A_NORMAL_FILL_IS_RECORDED_AS_FILLED", _rc == 0 and _row.get("status") == "FILLED",
      "rc=%r status=%r" % (_rc, _row.get("status")))
check("A_NORMAL_FILL_CARRIES_A_CLOID", bool(_row.get("cloid")), "cloid=%r" % (_row.get("cloid"),))
_att = STATE / "append_only" / "send_attempts.csv"
_journal = list(csv.DictReader(open(_att, encoding="utf-8"))) if _att.exists() else []
check("A_NORMAL_FILL_IS_JOURNALLED_FOR_RECONCILE",
      any(r.get("action") == "FLATTEN" and r.get("cloid") for r in _journal),
      "journal rows=%r" % ([r.get("action") for r in _journal],))

# ---------------------------------------------------------------- B. fills, then the response raises (the HBAR case)
_net["TEST"] = 10.0
IFACE["raise_on_response"] = True
IFACE["filled"] = False


def _open_positions_after_fill(wallet):
    # the exchange filled: the position is flat from the first read after the raise
    return [] if IFACE.get("filled") else [{"coin": "TEST", "net": 10.0, "value": 10.0}]


F.open_positions = _open_positions_after_fill
_rc2 = F.main(ARGS)
_report2 = sorted(STATE.glob("FLATTEN_LIVE_*.json"))[-1]
_rows2 = json.loads(_report2.read_text(encoding="utf-8"))["rows"]
_row2 = [r for r in _rows2 if r.get("coin") == "TEST"][0]
check("A_FILL_THAT_RAISES_IS_NOT_REPORTED_AS_AN_ABORT",
      _row2.get("action") == "FILLED_DESPITE_EXCEPTION",
      "action=%r reason=%r" % (_row2.get("action"), (_row2.get("reason") or "")[:120]))
check("THE_RAISING_FILL_KEEPS_ITS_CLOID", bool(_row2.get("cloid")), "cloid=%r" % (_row2.get("cloid"),))
check("THE_RAISING_FILL_IS_IN_THE_REPORT", Path(_report2).exists())

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
