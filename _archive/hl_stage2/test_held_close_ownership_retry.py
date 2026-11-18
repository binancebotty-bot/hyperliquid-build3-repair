"""Held-close proofs (Boss rule: closes are sacred; no proven ownership means nothing is sent).

(a) a close held for missing ownership must be re-evaluated and sent once the ownership row lands
(b) a held close must never be cleared while the follower still holds sleeve-owned or exchange exposure;
    flat on both sides is the only clearing evidence

Run: python3 test_held_close_ownership_retry.py   (exit 0 only if every check passes)
"""
import importlib.util
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


def reset_escalations():
    c.atomic_write_json(c.CLOSE_ESCALATIONS_FILE, {})


def hold_escalation(gw, intent):
    gw._open_close_escalation(intent, "CLOSE_HELD_LAG_EXPIRED_NO_OWNERSHIP")


def key_for(intent):
    return c.normalise_wallet(t.A) + "::" + c.canonical_coin_key(t.COIN)


def open_row_present(intent):
    rows = c.load_json(c.CLOSE_ESCALATIONS_FILE, {}) or {}
    return (rows.get(key_for(intent)) or {}).get("state") == "OPEN"


# ---- (b) clearing rule -------------------------------------------------------
for label, sleeve_owned, exch_net, expect_clear in [
    ("HELD_NOT_CLEARED_WHILE_SLEEVE_OWNED", 2.0, 0.0, False),
    ("HELD_NOT_CLEARED_WHILE_EXCHANGE_EXPOSED", 0.0, 3.0, False),
    ("HELD_CLEARED_ONLY_WHEN_BOTH_FLAT", 0.0, 0.0, True),
]:
    reset_escalations()
    led, ex, net = t.new_ledger(), t.FakeExchange(), [exch_net]
    gw = t.make_gateway(ex, led, net)
    intent = t.exit_intent(led, t.A, "SELL", 1.0, "held-b-" + label, 1.0)
    led.sleeve(t.A, t.COIN)["signed_size"] = sleeve_owned
    hold_escalation(gw, intent)
    cleared = gw.clear_close_escalations()
    still_open = open_row_present(intent)
    if expect_clear:
        check("(b) " + label, cleared == 1 and not still_open, "cleared=%r open=%r" % (cleared, still_open))
    else:
        check("(b) " + label, cleared == 0 and still_open, "cleared=%r open=%r" % (cleared, still_open))

# ---- (a) re-evaluation once the ownership row lands -------------------------
reset_escalations()
led, ex, net = t.new_ledger(), t.FakeExchange(), [3.0]
gw = t.make_gateway(ex, led, net)
intent = t.exit_intent(led, t.A, "SELL", 1.0, "held-a-f", 1.0)
state = {"owned": 0.0}
gw._lag_owned_now = lambda i: state["owned"]          # the ledger row as the lag path sees it
gw._close_lag_hold_for_owned = lambda i, tol: state["owned"]  # the bounded window: owned proof at expiry
gw._proven_owned_for_sleeve = lambda w, coin: (state["owned"], "test_ledger_row")
min_ok = lambda sz: True
timing = {}
first = gw._close_wire_plan(intent, 1.0, 2, min_ok, timing, ledger_may_lag=True)
check("(a) held while ownership row is absent", first[1] == 0.0 and first[0] is False,
      "first=%r" % (first,))
state["owned"] = 1.0                                   # the row lands on a later cycle
second = gw._close_wire_plan(intent, 1.0, 2, min_ok, {}, ledger_may_lag=True)
check("(a) re-evaluated decision sends once the row exists", second[1] > 0.0, "second=%r" % (second,))

# The decision above is stateless, so it only matters if something calls it again. Look for the re-drive.
has_redrive = any(hasattr(gw, n) for n in ("redrive_held_closes", "retry_held_closes", "sweep_owed_closes"))
check("(a) a re-drive path exists that re-invokes held closes", has_redrive,
      "no re-drive method on SenderGateway; a held close is only re-run by the fill that created it")

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
raise SystemExit(1 if failed else 0)
