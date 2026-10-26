#!/usr/bin/env python3
"""Cap refusals must be countable from the journal alone: the row carries cap_name / cap_value /
measured_exposure_usd / cap_coin, refusals reach exposure_cap_trace.jsonl, and the reject category is
CAP_REFUSED for a cap but RISK_OR_BUDGET_BLOCK for a non-cap block (UNOWNED_INVENTORY, unreadable limits).
Reporting only: every decision and block-reason string must stay byte-for-byte what it was.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_cap_journal_fields.py"""
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="cap_journal_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
os.environ.pop("HL_LIVE_CAP_SIZE_DOWN", None)
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

CAP_COLS = ("cap_name", "cap_value", "measured_exposure_usd", "cap_coin")

def builder(total=1000.0, net_btc=1.0, cap_total=0.0, cap_asset=0.0, min_n=10.0, ok=True,
            max_wallet=0.0, wallet_usd=0.0, max_order=0.0, unowned=""):
    b = c.IntentBuilder.__new__(c.IntentBuilder)
    b.cfg = SimpleNamespace(max_total_exposure=lambda: cap_total, max_asset_directional_exposure=lambda: cap_asset,
                            min_notional=lambda: min_n, max_wallet_exposure=lambda w: max_wallet,
                            max_order_notional=lambda: max_order, wallet_enabled=lambda w: True,
                            wallet_mode=lambda w: "FULL", is_symbol_allowed=lambda s: (True, ""),
                            auto_send_enabled=True)
    b.ledger = SimpleNamespace(wallet_abs_exposure_usd=lambda w, px: wallet_usd)
    b.follower_exposure = lambda: ({"ok": True, "total_usd": total, "by_coin": {"BTC": {"net": net_btc}}} if ok
                                   else {"ok": False, "status": "UNAVAILABLE"})
    b._resting = lambda: {"total_usd": 0.0, "buy_units": {}, "sell_units": {}}
    b._exposure_pending = []
    b._exposure = {"ok": True, "total_usd": total}
    b._sizing_block = {}
    b._is_leader_close_fill = lambda f: False
    b._unowned_inventory_block = lambda f: unowned
    b._order_value_px = lambda f: f.price  # order_notional == copy_notional; the cap check is what is under test
    return b

def fill(side="BUY"):
    return SimpleNamespace(price=100.0, side=side, coin="BTC", leader_wallet="0xW", leader_fill_id="lf1",
                           notional=20.0, raw={}, timestamp_ms=0)

def decision(b, notional=20.0, side="BUY"):
    c._CAP_TLS.scale = 1.0
    c._CAP_TLS.cap_detail = None
    return c.IntentBuilder._decision(b, "0xW", fill(side), "ENTRY", notional, 0.0), getattr(c._CAP_TLS, "cap_detail", None)

def cap_block(b, notional):
    c._CAP_TLS.scale = 1.0
    c._CAP_TLS.cap_detail = None
    r = c.IntentBuilder._exposure_cap_block(b, fill(), notional)
    return r, getattr(c._CAP_TLS, "cap_detail", None)

# 1. the CSV column list carries the four fields (append_reconciliation writes only these)
check("FIELDS_HAVE_CAP_COLUMNS", all(k in c.RECONCILIATION_FIELDS for k in CAP_COLS),
      [k for k in CAP_COLS if k not in c.RECONCILIATION_FIELDS])
check("FIELDS_NO_DUPLICATE_COIN", c.RECONCILIATION_FIELDS.count("coin") == 1, c.RECONCILIATION_FIELDS.count("coin"))

# 2/3. wallet cap: same decision and same reason string as before, plus the numbers it used
r, d = decision(builder(max_wallet=200.0, wallet_usd=190.0))
check("WALLET_CAP_REASON_UNCHANGED", r == ("SEND_BLOCKED_RISK", "max wallet exposure exceeded"), r)
check("WALLET_CAP_DETAIL_RECORDED", bool(d) and d.get("cap_name") == "max_wallet_exposure"
      and abs(float(d.get("cap_value")) - 200.0) < 1e-9
      and abs(float(d.get("measured_exposure_usd")) - 210.0) < 1e-6 and d.get("coin") == "BTC", d)

# 4. order-notional cap
r, d = decision(builder(max_order=5.0))
check("ORDER_CAP_REASON_UNCHANGED", r == ("SEND_BLOCKED_RISK", "max order notional exceeded"), r)
check("ORDER_CAP_DETAIL_RECORDED", bool(d) and d.get("cap_name") == "max_order_notional"
      and abs(float(d.get("measured_exposure_usd")) - 20.0) < 1e-9, d)

# 5/6. total and per-asset caps, same block strings as before
r, d = cap_block(builder(total=1100.0, cap_total=1050.0), 12.0)
check("TOTAL_CAP_REASON_UNCHANGED", r == "max total exposure exceeded", r)
check("TOTAL_CAP_DETAIL_RECORDED", bool(d) and d.get("cap_name") == "max_total_exposure"
      and abs(float(d.get("cap_value")) - 1050.0) < 1e-9 and float(d.get("measured_exposure_usd")) > 0, d)
r, d = cap_block(builder(total=0.0, net_btc=1.0, cap_asset=90.0), 20.0)
check("ASSET_CAP_REASON_UNCHANGED", r == "max asset directional exposure exceeded", r)
check("ASSET_CAP_DETAIL_RECORDED", bool(d) and d.get("cap_name") == "max_asset_exposure"
      and abs(float(d.get("cap_value")) - 90.0) < 1e-9 and float(d.get("measured_exposure_usd")) > 0, d)

# 7. a non-cap block records no cap, so its row must keep RISK_OR_BUDGET_BLOCK
r, d = decision(builder(unowned="UNOWNED_INVENTORY: BTC exchange net 1 != engine-owned net 0; entries blocked"))
check("UNOWNED_BLOCK_UNCHANGED", r[0] == "SEND_BLOCKED_RISK" and str(r[1]).startswith("UNOWNED_INVENTORY"), r)
check("UNOWNED_IS_NOT_A_CAP", not (d or {}).get("cap_name"), d)

# 8. the reconciliation row really carries the four fields (round-trip through the real writer)
audit = c.AuditLogWriter()
audit.append_reconciliation("ENTRY_SAFETY_BLOCK", "ENTRY_BLOCKED_RISK", leader_wallet="0xW",
                            leader_fill_id="lf-row", intent_id="i1", coin="BTC",
                            action="NO_SEND_RISK_OR_BUDGET_BLOCK", reject_category="CAP_REFUSED",
                            terminal_state="ENTRY_BLOCKED_RISK", cap_name="max_wallet_exposure",
                            cap_value=200.0, measured_exposure_usd=210.0, cap_coin="BTC", notes="x")
rows = list(csv.DictReader(open(c.RECONCILIATION_CSV, newline="", encoding="utf-8")))
row = [x for x in rows if x.get("intent_id") == "i1"][-1] if rows else {}
check("RECON_ROW_WRITES_CAP_FIELDS", row.get("cap_name") == "max_wallet_exposure"
      and str(row.get("cap_value")) == "200.0" and str(row.get("measured_exposure_usd")) == "210.0"
      and row.get("cap_coin") == "BTC" and row.get("reject_category") == "CAP_REFUSED", row)

# 9. a refusal also lands in the trace, with its measurements
b = builder(total=1100.0, cap_total=1050.0)
c._CAP_TLS.cap_detail = {"cap_name": "max_total_exposure", "cap_value": 1050.0,
                         "measured_exposure_usd": 1112.0, "coin": "BTC"}
c.IntentBuilder._trace_exposure_cap(b, fill(), 12.0, "max total exposure exceeded")
c._CAP_TLS.cap_detail = None
trace = [json.loads(l) for l in open(c.AUDIT_DIR / "exposure_cap_trace.jsonl", encoding="utf-8") if l.strip()]
rec = [t for t in trace if t.get("decision") == "BLOCKED"][-1] if trace else {}
check("TRACE_WRITES_BLOCKED_WITH_MEASUREMENTS", rec.get("reason") == "max total exposure exceeded"
      and rec.get("cap_name") == "max_total_exposure" and str(rec.get("cap_value")) == "1050.0"
      and str(rec.get("measured_exposure_usd")) == "1112.0", rec)

# 10. the ENTRY_BLOCKED_RISK writer passes the four fields and switches the category only for a cap
src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8", errors="replace")
head = src.index('action="NO_SEND_RISK_OR_BUDGET_BLOCK"')
block = src[head:head + 900]
check("WRITER_PASSES_CAP_FIELDS", all(k + "=" in block for k in CAP_COLS) and "CAP_REFUSED" in block, block[:300])

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
