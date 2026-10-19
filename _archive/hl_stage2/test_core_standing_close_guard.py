"""Standing recovery closes are not reduce-only; the guard cancels one whose target, sleeve or account changed, or that is old.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_standing_close_guard.py"""
import os, sys, tempfile, threading, time
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="sg_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_STANDING_GUARD_SEC": "0"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

class Ledger:
    def __init__(self, sleeve, net): self.s, self.net = sleeve, net
    def sleeve(self, w, coin): return {"signed_size": self.s}
    def coin_net(self, k): return self.net
rows = []
class Audit:
    def append_reconciliation(self, *a, **k): rows.append((a, k))

def guard(row, sleeve=10.0, led_net=10.0, ex_net=10.0, age_ms=1000, cancel_ok=True, gmode="ON"):
    rows.clear(); cancels = []
    row = dict(row, placed_ms=c.utc_now_ms() - age_ms)
    me = SimpleNamespace(_resting_lock=threading.RLock(), _standing_closes={"s1": row}, ledger=Ledger(sleeve, led_net), audit=Audit(),
                         _standing_guard_ms=0, cfg=SimpleNamespace(send_mode_now=lambda: gmode))
    me._fresh_exchange_net = lambda coin: ex_net
    me._exchange_client_for_coin = lambda coin: (object(), "BTC")
    me._cancel_order = lambda ex, sdk, oid: (cancels.append(oid), {"response": {"data": {"statuses": ["success" if cancel_ok else {"error": "boom"}]}}})[1]
    n = c.SenderGateway.guard_standing_closes(me)
    return n, cancels, dict(me._standing_closes)

base = {"oid": "7", "coin": "BTC", "sdk_coin": "BTC", "size": 10.0, "side": "SELL", "intent_id": "i1", "reduce_only": False,
        "sleeve_signed": 10.0, "wallet": "0xw", "led_net": 10.0, "sleeve_tol": 0.0}
n, can, left = guard(base)
check("UNCHANGED_ORDER_STAYS", n == 0 and not can and "s1" in left)
n, can, left = guard(base, age_ms=10 ** 9)
check("OLD_ORDER_IS_CANCELLED", n == 1 and can == ["7"] and "s1" not in left and rows[0][1]["terminal_state"] == "STANDING_CLOSE_CANCELLED_BY_GUARD")
n, can, _ = guard(base, sleeve=4.0)
check("LEADER_SLEEVE_CHANGE_CANCELS", n == 1 and can == ["7"])
n, can, _ = guard(base, ex_net=0.0)
check("TARGET_REACHED_CANCELS", n == 1)
n, can, _ = guard(base, ex_net=4.0)
check("EXCHANGE_HOLDS_LESS_THAN_ORDER_CANCELS", n == 1)
n, can, _ = guard(base, ex_net=None)
check("UNREADABLE_ACCOUNT_CANCELS", n == 1)
n, can, _ = guard(base, ex_net=25.0)
check("TARGET_NEEDS_MORE_THAN_ORDER_STAYS", n == 0)
n, can, left = guard(base, age_ms=10 ** 9, cancel_ok=False)
check("FAILED_CANCEL_KEEPS_ROW_FOR_NEXT_ROUND", n == 0 and can == ["7"] and "s1" in left)
n, can, _ = guard(base, gmode="CLOSE")
check("HEADER_CLOSE_ONLY_DOES_NOT_CANCEL_A_STANDING_CLOSE", n == 0 and not can)
n, can, left = guard(dict(base, reduce_only=True), age_ms=10 ** 9)
check("REDUCE_ONLY_ROWS_ARE_LEFT_ALONE", n == 0 and not can)
n, can, left = guard(dict(base, sleeve_signed=10.0, sleeve_tol=3.0), sleeve=7.0)
check("SLEEVE_MAY_SHRINK_BY_THE_UNSEEN_PART_FILL", n == 0, str((n, can)))
n, can, left = guard(dict(base, sleeve_signed=10.0, sleeve_tol=3.0), sleeve=5.0)
check("SLEEVE_SHRINKING_MORE_CANCELS", n == 1)
n, can, left = guard(base, sleeve=-10.0)
check("SLEEVE_FLIPPING_CANCELS", n == 1)

# plan: ledger may lag -> sized from the exchange alone, never past flat
def plan(side, size, ex, lag, mode="ON", min_ok=lambda s: True):
    me = SimpleNamespace(ledger=Ledger(0, 0), cfg=SimpleNamespace(wallet_mode=lambda w: mode, send_mode_now=lambda: "ON"))
    me._reduce_only_for_intent = lambda i: True
    me._fresh_exchange_net = lambda coin: ex
    me._floor_wire_size = lambda s, d: round(s, d)
    # unreadable-net hold helpers (real gateway methods): readable nets here never reach them
    me._net_read_ms = {}
    me._exit_hold = None
    me._exit_hold_lock = threading.RLock()
    me._net_unreadable_reason = lambda coin, key, net: c.SenderGateway._net_unreadable_reason(me, coin, key, net)
    me._net_read_age_ms = lambda coin: c.SenderGateway._net_read_age_ms(me, coin)
    me._hold_exit_unreadable_net = lambda i, reason, sz, timing=None: None
    me._take_exit_hold_replay = lambda i, key, net: False
    me._exit_hold_key = lambda i: "test-sleeve"
    intent = SimpleNamespace(intent_id="test-intent", sleeve_id="test-sleeve", fill=SimpleNamespace(leader_wallet="0xw", coin="BTC", leader_fill_id="f-test"), copy_side=side, copy_size=size)
    return c.SenderGateway._close_wire_plan(me, intent, size, 3, min_ok, None, lag)
check("LAG_SIZES_FROM_EXCHANGE_ONLY", plan("SELL", 6.0, 4.0, True) == (False, 4.0, ""))
check("LAG_NOTHING_TO_CLOSE_SKIPS", plan("SELL", 6.0, 0.0, True)[1] == 0.0 and plan("SELL", 6.0, -3.0, True)[1] == 0.0)
check("LAG_FULL_POSITION_KEEPS_ORDER_SIZE", plan("SELL", 6.0, 9.0, True) == (False, 6.0, ""))
check("LAG_WALLET_CLOSE_ONLY_IS_NOT_REDUCE_ONLY", plan("SELL", 6.0, 9.0, True, mode="CLO") == (False, 6.0, ""))
n, can, _ = guard(dict(base, sleeve_signed=10.0, sleeve_tol=4.0), sleeve=6.0, led_net=10.0, ex_net=4.0)
check("PART_FILL_ORDER_IS_GIVEN_TIME_FOR_THE_LEDGER_TO_CATCH_UP", n == 0, str((n, can)))
n, can, _ = guard(dict(base, sleeve_signed=10.0, sleeve_tol=4.0), sleeve=6.0, led_net=10.0, ex_net=4.0, age_ms=60000)
check("PART_FILL_ORDER_IS_CHECKED_AFTER_THE_GRACE", n == 1)
# the blocked-close statuses leave a final row
for st, term in (("SEND_NOT_ATTEMPTED_CLOSE_AT_TARGET", "SEND_NOT_ATTEMPTED_CLOSE_AT_TARGET"),):
    rows.clear()
    me2 = SimpleNamespace(audit=Audit())
    f = SimpleNamespace(leader_wallet="0xw", leader_fill_id="F1", coin="BTC", side="SELL")
    it = SimpleNamespace(intent_id="i1", send_allowed=True, decision="SEND_ALLOWED", reason="")
    c.LiveCopyCore._append_send_terminal(me2, f, it, st)
    check("FINAL_ROW_FOR_" + st, len(rows) == 1 and rows[0][1]["terminal_state"] == term and rows[0][1]["leader_fill_id"] == "F1")
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
