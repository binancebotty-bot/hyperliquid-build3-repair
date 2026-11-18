"""Readable FLAT exchange never gets a close order (Boss rule: a close with nothing on the exchange to reduce holds).

(a) main path: readable flat exchange (net 0) with a sleeve that says 1.0 and a ledger net that drifted to 0 -> HOLD, no order
(b) ledger-lag path: readable flat exchange -> HOLD, no order
(c) unreadable net still sends the fill-proven owned size, reduce_only NOT forced (31 Oct rule)

Each case has a mutation check (run the mutated core, expect the case to fail). Run: python3 test_close_readable_flat.py
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


# (a) main path: owned 1.0 on the sleeve, ledger coin net drifted to 0 (stale), exchange readable and flat
led, ex, net = t.new_ledger(), t.FakeExchange(), [0.0]
gw = t.make_gateway(ex, led, net)
intent = t.exit_intent(led, t.A, "SELL", 1.0, "flat-main-f", 1.0)
led.data["by_coin_net"] = {}                      # the drift: sleeve says 1.0, coin net says 0
ok_a, status_a = gw.send_if_allowed(intent)
check("(a) main path, readable flat exchange: no order", (not ok_a) and len(ex.calls) == 0,
      "ok=%r status=%r calls=%r" % (ok_a, status_a, ex.calls))

# (b) ledger-lag path: same readable flat exchange, owned proven, the lag branch
led, ex, net = t.new_ledger(), t.FakeExchange(), [0.0]
gw = t.make_gateway(ex, led, net)
intent = t.exit_intent(led, t.A, "SELL", 1.0, "flat-lag-f", 1.0)
ro_b, amt_b, why_b = c.SenderGateway._close_wire_plan_ledger_lag(gw, intent, 1.0, 2, lambda sz: True, lambda kind, amount=0.0, ro=False, why="": (ro, amount, why))
check("(b) ledger-lag path, readable flat exchange: holds, no send", ro_b is False and amt_b == 0.0 and why_b != "" and "SEND" not in why_b,
      "ro=%r amount=%r why=%r" % (ro_b, amt_b, why_b))

# (c) unreadable net: re-read once then still unreadable -> sends the owned size, reduce_only NOT forced
led, ex, net = t.new_ledger(), t.FakeExchange(replies=[t.filled(1.0, 99.8)]), [None]
gw = t.make_gateway(ex, led, net)
intent = t.exit_intent(led, t.A, "SELL", 1.0, "unreadable-c-f", 1.0)
ok_c, status_c = gw.send_if_allowed(intent)
check("(c) unreadable net: sends the owned size, reduce_only False",
      ok_c and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 1.0) < 1e-9 and ex.calls[0]["reduce_only"] is False,
      "ok=%r status=%r calls=%r" % (ok_c, status_c, ex.calls))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
raise SystemExit(1 if failed else 0)
