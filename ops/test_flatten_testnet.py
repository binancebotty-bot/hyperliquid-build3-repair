"""The guards on the flatten driver, tested without an exchange, without a process and without an order."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flatten_testnet as F   # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if (detail and not ok) else ""))


# ---- 1. USER-OWNED: named, and absent-from-ledger, are both refused
for name in ("XYZ:CRCL", "XYZ:ORCL", "XYZ:LLY"):
    refuse, why = F.is_user_owned(name, 0.0)
    check("REFUSES_NAMED_%s" % name.replace(":", "_"), refuse and why == "USER_OWNED_NAMED",
          "refuse=%r why=%r" % (refuse, why))

refuse, why = F.is_user_owned("SOMECOIN", None)
check("REFUSES_A_COIN_ABSENT_FROM_THE_LEDGER", refuse and why == "USER_OWNED_ABSENT_FROM_LEDGER",
      "an unowned-by-ledger coin must be treated as the operator's: refuse=%r why=%r" % (refuse, why))

refuse, why = F.is_user_owned("CHIP", -1052.0)
check("ALLOWS_A_LEDGER_OWNED_COIN", not refuse, "the engine's own position was refused: %r" % (why,))

# ---- 2. reduce_only geometry: the order always opposes the net
check("A_LONG_IS_CLOSED_BY_SELLING", F.order_side(10.0) is False)
check("A_SHORT_IS_CLOSED_BY_BUYING", F.order_side(-10.0) is True)
check("A_FLAT_BOOK_HAS_NO_SIDE", F.order_side(0.0) is None)

# ---- 3. wire size never exceeds abs(net), including when rounding would go up
for net, dec in ((10.0, 2), (-10.0, 2), (1234.5678, 3), (0.00019, 4), (-91.0, 0)):
    sz = F.wire_size(net, dec)
    check("SIZE_NEVER_EXCEEDS_NET_%s_%s" % (str(abs(net)).replace(".", "_"), dec),
          sz <= abs(net) + 1e-12, "net=%r dec=%r size=%r" % (net, dec, sz))

# ---- 4. price: through the mid on the correct side, never zero
buy = F.limit_price(100.0, True, 1)
sell = F.limit_price(100.0, False, 1)
check("A_BUY_PRICE_IS_ABOVE_THE_MID", buy > 100.0, "buy=%r" % (buy,))
check("A_SELL_PRICE_IS_BELOW_THE_MID", sell < 100.0, "sell=%r" % (sell,))
check("THE_RETRY_IS_WIDER_BUT_BOUNDED", F.limit_price(100.0, True, 2) > buy
      and F.limit_price(100.0, True, 2) <= 100.0 * 1.005, "retry=%r" % (F.limit_price(100.0, True, 2),))
check("A_ZERO_MID_IS_INVALID", not F.valid_price(0.0) and F.valid_price(1.0))

# ---- 5. a stale mid is NOT a mid
fresh = {"mids": {"CHIP": "0.05"}, "ts": 1000.0}
check("A_STALE_MID_IS_REFUSED", F.fresh_mid(fresh, "CHIP", 1010.0) is None,
      "a 10 s old mid was accepted")
check("A_FRESH_MID_IS_ACCEPTED", F.fresh_mid(fresh, "CHIP", 1002.0) == 0.05)
check("A_MISSING_MID_IS_NONE", F.fresh_mid({"mids": {}, "ts": 1000.0}, "NOPE", 1000.0) is None)

# ---- 6. the plan: skips user-owned and unlisted, keeps the engine's own
positions = [{"coin": "CHIP", "net": -1052.0, "value": 50.0},
             {"coin": "XYZ:CRCL", "net": 5.0, "value": 1.0},
             {"coin": "WEIRD", "net": 1.0, "value": 1.0}]
plan = F.build_plan(positions, {"CHIP": -1052.0}, {"CHIP": 0}, listed={"CHIP"})
by = {p["coin"]: p for p in plan}
check("PLAN_FLATTENS_THE_ENGINE_POSITION", by["CHIP"]["action"] == "FLATTEN")
check("PLAN_SKIPS_THE_OPERATORS_COIN", by["XYZ:CRCL"]["action"] == "SKIP"
      and by["XYZ:CRCL"]["reason"] == "USER_OWNED_NAMED")
check("PLAN_SKIPS_WHAT_THE_LEDGER_DOES_NOT_OWN", by["WEIRD"]["action"] == "SKIP"
      and by["WEIRD"]["reason"] == "USER_OWNED_ABSENT_FROM_LEDGER")

# the real case that caught this: the ledger spells it KBONK, the exchange kBONK
_case = F.build_plan([{"coin": "kBONK", "net": -12026.0, "value": 36.0}], {"KBONK": -12026.0}, {"kBONK": 0})
check("A_COIN_IS_MATCHED_CASE_BLIND", _case[0]["action"] == "FLATTEN",
      "a case difference made an engine position look hand-placed: %r" % (_case[0]["reason"],))

# ---- 7. the driver cannot run live without an explicit flag, and refuses while an engine exists
src = (HERE / "flatten_testnet.py").read_text(encoding="utf-8")
check("DRY_RUN_IS_THE_DEFAULT", '"--live", action="store_true"' in src and "live = bool(args.live)" in src,
      "a missing --live must mean nothing is sent")
check("IT_REFUSES_WHILE_AN_ENGINE_RUNS",
      "engine_pids(state)" in src and "Stop the pair first" in src,
      "the pid guard is missing or no longer uses the proven stop_pair.pids() - the wmic version returned [] and never fired")
check("UNKNOWN_PID_STATE_BLOCKS",
      "return [-1]" in src and "unknown is NOT permission" in src,
      "if the process list cannot be read the driver must refuse, not proceed")
check("THE_RETRY_COUNT_IS_CAPPED", "MAX_ATTEMPTS" in src)
check("IT_READS_THE_RESULT_FROM_THE_EXCHANGE", "open_positions(wallet)" in src.split("after = ")[-1][:200])

failed = [n for n, ok in results if not ok]
print("TOTAL=%d FAILED=%d" % (len(results), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
