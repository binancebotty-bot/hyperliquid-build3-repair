#!/usr/bin/env python3
"""Reduce-only close refused because the account is flat (24 of 318 rejects in 24 h, RESOLV): the ledger sleeve is closed
as exchange-flat from a fresh account read, with an audited row and no order. Any other state changes nothing.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_reduce_only_repair.py"""
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="roreg_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok)))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + d) if d and not ok else ""))

W = "0x" + "a" * 40
W2 = "0x" + "b" * 40
c.USER_WALLET = "0x" + "c" * 40
rows = []
class Audit:
    def append_reconciliation(self, *a, **k): rows.append((a, k))
    def append_live_fill_repair_close(self, r, n): rows.append((("repair", r), {"notes": n}))
class Ledger:
    def __init__(self, sleeves):
        self.data = {"by_wallet": {w: {"RESOLV": {"signed_size": s}} for w, s in sleeves.items()}}
        self.closed = []
        self._lock = threading.RLock()
    def coin_net(self, coin): return sum(m["RESOLV"]["signed_size"] for m in self.data["by_wallet"].values())
    def close_sleeve_as_exchange_flat(self, w, coin):
        self.closed.append((w, coin)); self.data["by_wallet"][w]["RESOLV"]["signed_size"] = 0.0
        return {"wallet": w, "coin": coin}

def run(sleeves, ex_net, ok=True):
    rows.clear()
    me = SimpleNamespace(ledger=Ledger(sleeves), audit=Audit(), _send_lock=threading.Lock())
    c._XNET.master_exposure = lambda *a, **k: ({"ok": True, "by_coin": {"RESOLV": {"net": ex_net}}} if ok else {"ok": False})
    c.follower_dex_scope = lambda: [""]
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet=W, coin="RESOLV", leader_fill_id="f1"))
    note = c.SenderGateway._repair_ledger_if_exchange_flat(me, intent, "Reduce only order would increase position.")
    return note, me.ledger, list(rows)

note, led, out = run({W: -663.0}, 0.0)
check("FLAT_ACCOUNT_CLOSES_SLEEVE", note and led.closed == [(W, "RESOLV")] and any(k.get("terminal_state") == "LEDGER_REPAIR_PROVEN_EXCHANGE_FLAT" for _a, k in out), str((note, led.closed)))
note, led, _ = run({W: -663.0}, -100.0)
check("POSITION_ON_ACCOUNT_CHANGES_NOTHING", not note and not led.closed)
note, led, _ = run({W: -663.0, W2: 50.0}, 0.0)
check("OTHER_SLEEVE_IN_COIN_CHANGES_NOTHING", not note and not led.closed)
note, led, _ = run({W: -663.0}, 0.0, ok=False)
check("UNREADABLE_ACCOUNT_CHANGES_NOTHING", not note and not led.closed)
note, led, _ = run({W: 0.0}, 0.0)
check("NO_SLEEVE_CHANGES_NOTHING", not note and not led.closed)
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
