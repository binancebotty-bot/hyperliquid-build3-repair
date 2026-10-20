#!/usr/bin/env python3
"""An unresolved ambiguous send discovered at startup is alerted once, never queried or resent."""
import csv
import os
import sys
import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="ambiguous_startup_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_AUTO_SEND_ENABLED": "0"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

rows = [
    {"attempt_id": "a1", "status": "ORDER_UNKNOWN", "terminal_state": "SEND_OUTCOME_UNKNOWN_HOLD",
     "cloid": "0xambiguous1", "intent_id": "i1", "leader_fill_id": "f1", "leader_wallet": "0xleader",
     "coin": "BTC", "side": "SELL", "copy_size": "1", "limit_price": "100",
     "created_at_ms": "1000", "order_type": "REAL_IOC"},
    {"attempt_id": "a2", "status": "ORDER_UNKNOWN", "terminal_state": "", "cloid": "0xambiguous2",
     "intent_id": "i2", "leader_fill_id": "f2", "leader_wallet": "0xleader", "coin": "ETH",
     "side": "BUY", "copy_size": "2", "limit_price": "200", "created_at_ms": "2000",
     "order_type": "REAL_IOC"},
    {"attempt_id": "a3", "status": "ORDER_FILLED", "terminal_state": "FILLED_AWAITING_COPY_POLL",
     "cloid": "0xfilled", "intent_id": "i3", "leader_fill_id": "f3", "leader_wallet": "0xleader",
     "coin": "SOL", "side": "BUY", "copy_size": "1", "limit_price": "50",
     "created_at_ms": "3000", "order_type": "REAL_IOC"},
]
c.SEND_ATTEMPTS_CSV.parent.mkdir(parents=True, exist_ok=True)
with c.SEND_ATTEMPTS_CSV.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=c.SEND_ATTEMPT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)

original_update = c.update_send_attempt_row
try:
    # Simulate a crash after the alert append but before the matching send-attempt row update.
    c.update_send_attempt_row = lambda attempt_id, updates, base_row=None: False if attempt_id == "a1" else original_update(attempt_id, updates, base_row)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.stop()
    c.update_send_attempt_row = original_update
    restarted = c.LiveCopyCore(source_csv=tmp / "none.csv")
    restarted.stop()
finally:
    c.update_send_attempt_row = original_update

alerts = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
          if r.get("status") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"]
latest = {}
for row in c.iter_csv_rows(c.SEND_ATTEMPTS_CSV):
    latest[row.get("attempt_id", "")] = row
ok = (len(alerts) == 2
      and all(any(f"cloid=0xambiguous{n};" in r.get("notes", "") for r in alerts) for n in (1, 2))
      and all(r.get("action") == "MANUAL_REVIEW_CHECK_ORDER_BY_CLOID" for r in alerts)
      and latest["a1"].get("terminal_state") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"
      and latest["a2"].get("terminal_state") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"
      and latest["a3"].get("terminal_state") == "FILLED_AWAITING_COPY_POLL")
print("RESULT::STARTUP_UNKNOWN_ATTEMPTS_ALERTED_ONCE_NO_EXCHANGE_ACTION_%s" % ("PASS" if ok else "FAIL"))
if not ok:
    print("DEBUG count=%r cloids=%r actions=%r latest=%r" % (
        len(alerts), [r.get("notes", "") for r in alerts],
        [r.get("action") for r in alerts], {k: v.get("terminal_state") for k, v in latest.items()}))
print("TOTAL=1 FAILED=%d" % (0 if ok else 1))
sys.exit(0 if ok else 1)
