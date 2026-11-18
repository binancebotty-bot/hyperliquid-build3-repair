"""Owed-close queue proofs (Boss 18 Nov: closes are sacred; a close held for missing ownership is not dropped).

A close held for missing ownership is persisted (OWED_CLOSES_FILE) and re-run by sweep_owed_closes through the
normal send gates. Proven here: the row lands after the hold; the sweep sends exactly once; a second sweep does
not send again; restart persistence; both-flat retirement without a send; the master switch; a 429 refusal.

Run: python3 test_owed_close_queue.py   (exit 0 only if every check passes)
"""
import importlib.util
import json
import os
import threading as _th
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cc1", HERE / "test_core_cc1_close_scenarios.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
c = t.c
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + "  ::  " + str(detail)[:220])


def reset():
    c.atomic_write_json(c.OWED_CLOSES_FILE, {})
    c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {})


def owed_rows():
    return c.load_json(c.OWED_CLOSES_FILE, {}) or {}


def open_ownership_door(gw):
    """Test seam only: the pre-send ownership door would refuse these fixtures earlier (exchange net vs ledger
    mismatch), before the close-wire hold this file proves. The door itself is covered by its own suites;
    the real _close_wire_plan, ownership hooks, sweep, store and send gates all run."""
    gw._pre_send_ownership_gate = lambda *a, **k: (True, {})
    return gw


def drop_sleeve_row(led):
    """No ownership row for this wallet+coin: the ledger has no sleeve, so the close is held (not consumed-flat)."""
    by_wallet = led.data.get("by_wallet") or {}
    (by_wallet.get(c.normalise_wallet(t.A)) or {}).pop(c.canonical_coin_key(t.COIN), None)
    led._recompute_net(led.data)


def hold_then_land_setup(exchange_net, fid):
    """Hold a SELL close while the sleeve shows no ownership, through the real send path."""
    reset()
    led, ex, net = t.new_ledger(), t.FakeExchange(), [exchange_net]
    gw = open_ownership_door(t.make_gateway(ex, led, net))
    intent = t.exit_intent(led, t.A, "SELL", 1.0, fid, 1.0)
    drop_sleeve_row(led)
    ok, status = gw.send_if_allowed(intent)
    return led, ex, net, gw, intent, ok, status


# ---- row lands after the hold: the sweep sends exactly once -----------------
led, ex, net, gw, intent, ok, status = hold_then_land_setup(3.0, "owed-land-f")
check("held close is persisted as an owed row", (not ok) and len(owed_rows()) == 1 and
      list(owed_rows().values())[0].get("state") == "OPEN" and len(ex.calls) == 0,
      "ok=%r status=%r rows=%d calls=%d" % (ok, status, len(owed_rows()), len(ex.calls)))
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0           # the ownership row lands on a later cycle
sent = gw.sweep_owed_closes()
check("row lands after the hold: sweep sends the owed close", sent == 1 and len(ex.calls) == 1,
      "sent=%r calls=%r" % (sent, ex.calls))
check("sent owed close leaves the store", owed_rows() == {}, str(owed_rows())[:120])

# ---- idempotent: a second sweep never double-sends ---------------------------
sent2 = gw.sweep_owed_closes()
check("second sweep does NOT double-send", sent2 == 0 and len(ex.calls) == 1, "sent2=%r calls=%r" % (sent2, len(ex.calls)))

# ---- restart persistence -----------------------------------------------------
led, ex, net, gw, intent, ok, status = hold_then_land_setup(3.0, "owed-restart-f")
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
ex_restarted = t.FakeExchange()
gw_restarted = open_ownership_door(t.make_gateway(ex_restarted, led, net))   # a new process over the same files
sent_r = gw_restarted.sweep_owed_closes()
check("owed close survives a restart and is sent once by the new process",
      sent_r == 1 and len(ex_restarted.calls) == 1 and owed_rows() == {},
      "sent=%r calls=%d rows_after=%d" % (sent_r, len(ex_restarted.calls), len(owed_rows())))

# ---- both sides flat retires without a send ----------------------------------
led, ex, net, gw, intent, ok, status = hold_then_land_setup(0.0, "owed-flat-f")
led.sleeve(t.A, t.COIN)["signed_size"] = 0.0
sent_f = gw.sweep_owed_closes()
check("both sides flat: owed close retired, nothing sent", sent_f == 0 and owed_rows() == {} and len(ex.calls) == 0,
      "sent=%r rows=%d calls=%d" % (sent_f, len(owed_rows()), len(ex.calls)))

# ---- master send switch OFF: nothing is sent, the row stays owed -------------
led, ex, net, gw, intent, ok, status = hold_then_land_setup(3.0, "owed-switch-f")
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
gw.cfg.master_switch_now = lambda: False
gw.cfg.send_mode_now = lambda: "OFF"
sent_off = gw.sweep_owed_closes()
check("switch OFF: sweep sends nothing and the close stays owed", sent_off == 0 and len(ex.calls) == 0 and len(owed_rows()) == 1,
      "sent=%r calls=%d rows=%d" % (sent_off, len(ex.calls), len(owed_rows())))
gw.cfg.master_switch_now = lambda: True
gw.cfg.send_mode_now = lambda: "ON"
sent_on = gw.sweep_owed_closes()
check("switch back ON: the owed close is sent once", sent_on == 1 and len(ex.calls) == 1, "sent=%r calls=%d" % (sent_on, len(ex.calls)))

# ---- 429 refusal: the close is not dropped -----------------------------------
class RateLimited(Exception):
    status_code = 429


class Exchange429(t.FakeExchange):
    def __init__(self):
        super().__init__()
        self.refuse_next = True

    def order(self, *a, **k):
        if self.refuse_next:
            self.refuse_next = False
            self.calls.append({"refused": True})
            raise RateLimited("429 Too Many Requests")
        return super().order(*a, **k)


reset()
led, net = t.new_ledger(), [3.0]
ex429 = Exchange429()
gw = open_ownership_door(t.make_gateway(ex429, led, net))
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-429-f", 1.0)
drop_sleeve_row(led)
gw.send_if_allowed(intent)
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
sent_429 = gw.sweep_owed_closes()
check("429 refusal: the owed close is NOT dropped", sent_429 == 0 and len(owed_rows()) == 1,
      "sent=%r rows=%d" % (sent_429, len(owed_rows())))
# The refused send left the in-memory pending-exit mark (30 s TTL, production behaviour). Let that TTL lapse
# through the real TTL check (env override to 1 ms), not by reaching into the guard.
_old_ttl = os.environ.get("HL_LIVE_PENDING_EXIT_GUARD_TTL_MS")
os.environ["HL_LIVE_PENDING_EXIT_GUARD_TTL_MS"] = "1"
time.sleep(0.01)
gw._exchange_rate_limit_cooldown_until_ms = 0
try:
    sent_after = gw.sweep_owed_closes()
finally:
    if _old_ttl is None:
        os.environ.pop("HL_LIVE_PENDING_EXIT_GUARD_TTL_MS", None)
    else:
        os.environ["HL_LIVE_PENDING_EXIT_GUARD_TTL_MS"] = _old_ttl
filled_calls = [x for x in ex429.calls if not x.get("refused")]
check("after the 429 clears: sent exactly once", sent_after == 1 and len(filled_calls) == 1 and owed_rows() == {},
      "sent=%r filled_calls=%d rows=%d" % (sent_after, len(filled_calls), len(owed_rows())))

# ---- crash between the send and the retire: the restarted sweep must NOT send again ----------
class Crash(BaseException):
    """Stands in for a process death right after the exchange accepted the order."""


led, ex, net, gw, intent, ok, status = hold_then_land_setup(3.0, "owed-crash-f")
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
gw._retire_owed_close = lambda key, row: (_ for _ in ()).throw(Crash())
try:
    gw.sweep_owed_closes()
    crashed = False
except Crash:
    crashed = True
check("crash injected after the exchange accepted the close", crashed and len(ex.calls) == 1 and len(owed_rows()) == 1,
      "crashed=%r calls=%d rows=%d" % (crashed, len(ex.calls), len(owed_rows())))
ex_after = t.FakeExchange()
gw_after = open_ownership_door(t.make_gateway(ex_after, led, net))
sent_after_crash = gw_after.sweep_owed_closes()
check("restart after crash: the send log shows the order, so NO second send and the row retires",
      sent_after_crash == 0 and len(ex_after.calls) == 0 and owed_rows() == {},
      "sent=%r calls=%d rows=%d" % (sent_after_crash, len(ex_after.calls), len(owed_rows())))

# ---- two sweeps at once: exactly one send ---------------------------------------------------
# Deterministic race: sweeper A is parked right after it claims the row and BEFORE its pending_send row exists,
# which is the window only the in-process in-flight set covers. Sweeper B runs its sweep inside that window.
led, ex, net, gw, intent, ok, status = hold_then_land_setup(3.0, "owed-conc-f")
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
ex_race = t.FakeExchange()
gw_a = open_ownership_door(t.make_gateway(ex_race, led, net))
gw_b = open_ownership_door(t.make_gateway(ex_race, led, net))   # a second sweeper object in the same process
parked, release = _th.Event(), _th.Event()
_orig_claim = gw_a._owed_set_claim


def _claim_then_park(key, row, claim_id):
    out = _orig_claim(key, row, claim_id)
    if claim_id is not None:
        parked.set()
        release.wait(5)
    return out


gw_a._owed_set_claim = _claim_then_park
a_result = []
th_a = _th.Thread(target=lambda: a_result.append(gw_a.sweep_owed_closes()))
th_a.start()
parked.wait(5)
b_sent = gw_b.sweep_owed_closes()                 # runs while A holds the claim, before A has written pending_send
release.set()
th_a.join(10)
check("two concurrent sweeps: exactly one send", (b_sent + sum(a_result)) == 1 and len(ex_race.calls) == 1,
      "b=%r a=%r calls=%d" % (b_sent, a_result, len(ex_race.calls)))

# ---- the REAL ownership door admits the owed close on the sweep (no stub on the second cycle) ----
# Phase 1 holds the close with the door stubbed: the real door refuses a no-row close BEFORE the close-wire hold,
# so no owed row would exist (see the report: that refusal is not persisted). Phase 2 is the real door, unstubbed.
reset()
led, net = t.new_ledger(), [1.0]
ex_door = t.FakeExchange()
gw_door = open_ownership_door(t.make_gateway(ex_door, led, net))
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-door-f", 1.0)
drop_sleeve_row(led)
gw_door.send_if_allowed(intent)
held_rows = len(owed_rows())
del gw_door.__dict__["_pre_send_ownership_gate"]        # the real door is back
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0           # the fill is on the books; the exchange shows the same position
sent_door = gw_door.sweep_owed_closes()
check("real ownership door admits the owed close on the sweep and it is sent once",
      held_rows == 1 and sent_door == 1 and len(ex_door.calls) == 1 and owed_rows() == {},
      "held_rows=%d sent=%r calls=%d rows=%d" % (held_rows, sent_door, len(ex_door.calls), len(owed_rows())))

# ---- a close the REAL door refuses for no matching sleeve: sends nothing, writes no owed row ----
# Boss rule: user coins are the user's own and are never adopted. A close with no sleeve row is refused by the
# door (_pre_send_ownership_gate, NO_MATCHING_WALLET_SLEEVE) before the close-wire hold, so it is NOT an owed close.
# The owed queue covers only a close that is held AFTER the door admits it. Known path that reaches this refusal
# with a legitimate sleeve: a leader close whose entry ledger row lands after the close fill; the lag wait in
# send_if_allowed only retries UNEXPLAINED_EXCHANGE_POSITION and SIGN_CONFLICT, not this status (see report).
reset()
led, net = t.new_ledger(), [0.0]
ex_nosleeve = t.FakeExchange()
gw_nosleeve = t.make_gateway(ex_nosleeve, led, net)     # real door, nothing stubbed
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-nosleeve-f", 1.0)
drop_sleeve_row(led)
ok_ns, status_ns = gw_nosleeve.send_if_allowed(intent)
check("door-refused no-sleeve close: sends nothing, writes no owed row",
      (not ok_ns) and len(ex_nosleeve.calls) == 0 and owed_rows() == {},
      "ok=%r status=%r calls=%d rows=%d" % (ok_ns, status_ns, len(ex_nosleeve.calls), len(owed_rows())))

# ---- no-sleeve close WITH our entry fill on record: the entry's sleeve row may be late ----------
# Entry evidence = a live_fills row for this leader wallet+coin on the opposite side (recent). Without it the close is
# refused once and nothing is owed (the 32e01c6 test). With it the door waits (lag window), then owes the close.
def _write_entry_fill(fid, side="BUY"):
    c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, {
        "created_at": "", "created_at_ms": str(c.utc_now_ms()), "copy_fill_id": fid + "-cp", "intent_id": fid,
        "leader_fill_id": fid, "leader_wallet": t.A, "sleeve_id": "", "position_id": "", "coin": t.COIN,
        "side": side, "fill_price": "100", "fill_size": "1.0", "fill_notional": "100", "fee": "0",
        "source": "POLL", "exchange_hash": "", "exchange_order_id": "", "ledger_action": "", "wallet_position_before": "",
        "wallet_position_after": "", "coin_net_after": "", "notes": ""})


def _clear_live_fills():
    try:
        c.LIVE_FILLS_CSV.unlink()
    except FileNotFoundError:
        pass


os.environ["HL_LIVE_UNEXPLAINED_WAIT_SEC"] = "2"
os.environ["HL_LIVE_NO_SLEEVE_EVIDENCE_MS"] = "60000"

# (1) the row lands INSIDE the window: the close sends once, nothing owed
reset(); _clear_live_fills()
led, net = t.new_ledger(), [0.0]
ex_in = t.FakeExchange()
gw_in = t.make_gateway(ex_in, led, net)
_write_entry_fill("owed-inwin-entry")
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-inwin-f", 1.0)
drop_sleeve_row(led)
def _land_in_window():
    led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
    net[0] = 1.0
gw_in.truth_refresh = _land_in_window
ok_in, status_in = gw_in.send_if_allowed(intent)
check("no-sleeve close, row lands inside the window: sent once, nothing owed",
      ok_in and len(ex_in.calls) == 1 and owed_rows() == {},
      "ok=%r status=%r calls=%d rows=%d" % (ok_in, status_in, len(ex_in.calls), len(owed_rows())))

# (2) the row lands AFTER the window: owed, then the sweep sends once when it lands
reset(); _clear_live_fills()
led, net = t.new_ledger(), [0.0]
ex_after = t.FakeExchange()
gw_after = t.make_gateway(ex_after, led, net)
_write_entry_fill("owed-afterwin-entry")
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-afterwin-f", 1.0)
drop_sleeve_row(led)
ok_a, status_a = gw_after.send_if_allowed(intent)
check("no-sleeve close, row not yet landed: held and owed, no send",
      (not ok_a) and status_a == "CLOSE_HELD_OWED_NO_SLEEVE_YET" and len(ex_after.calls) == 0 and len(owed_rows()) == 1,
      "ok=%r status=%r calls=%d rows=%d" % (ok_a, status_a, len(ex_after.calls), len(owed_rows())))
led.sleeve(t.A, t.COIN)["signed_size"] = 1.0
net[0] = 1.0
sent_a = gw_after.sweep_owed_closes()
check("row lands after the window: owed sweep sends once",
      sent_a == 1 and len(ex_after.calls) == 1 and owed_rows() == {},
      "sent=%r calls=%d rows=%d" % (sent_a, len(ex_after.calls), len(owed_rows())))

# (3) no entry fill on record (a genuine user coin): refused once, nothing owed, no wait
reset(); _clear_live_fills()
led, net = t.new_ledger(), [0.0]
ex_user = t.FakeExchange()
gw_user = t.make_gateway(ex_user, led, net)
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-user-f", 1.0)
drop_sleeve_row(led)
t0 = time.monotonic()
ok_u, status_u = gw_user.send_if_allowed(intent)
elapsed = time.monotonic() - t0
check("no entry fill on record: refused once, nothing owed, no wait",
      (not ok_u) and status_u == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE" and len(ex_user.calls) == 0
      and owed_rows() == {} and elapsed < 1.0,
      "status=%r calls=%d rows=%d elapsed=%.2f" % (status_u, len(ex_user.calls), len(owed_rows()), elapsed))
# (4) only a SAME-side fill on record (a close, not an entry): no evidence, refused once, nothing owed
reset(); _clear_live_fills()
led, net = t.new_ledger(), [0.0]
ex_same = t.FakeExchange()
gw_same = t.make_gateway(ex_same, led, net)
_write_entry_fill("owed-sameside-f", side="SELL")
intent = t.exit_intent(led, t.A, "SELL", 1.0, "owed-sameside-close", 1.0)
drop_sleeve_row(led)
ok_s, status_s = gw_same.send_if_allowed(intent)
check("only a same-side fill on record: refused once, nothing owed",
      (not ok_s) and status_s == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE" and len(ex_same.calls) == 0 and owed_rows() == {},
      "status=%r calls=%d rows=%d" % (status_s, len(ex_same.calls), len(owed_rows())))
_clear_live_fills()

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
raise SystemExit(1 if failed else 0)
