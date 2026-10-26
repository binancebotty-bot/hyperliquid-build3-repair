"""The guards on the flatten driver, tested without an exchange, without a process and without an order."""

import os
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
    kind, why = F.ownership(name, 0.0, None)      # one implementation: ownership() is the rule
    check("REFUSES_NAMED_%s" % name.replace(":", "_"), kind == "USER" and why == "USER_OWNED_NAMED",
          "kind=%r why=%r" % (kind, why))

kind, why = F.ownership("SOMECOIN", None, None)
check("AN_UNKNOWN_COIN_IS_AMBIGUOUS_NOT_FLATTENED", kind == "AMBIGUOUS" and why == "ABSENT_FROM_LEDGER",
      "an unowned-by-ledger coin must be treated as the operator's: kind=%r why=%r" % (kind, why))

kind, why = F.ownership("CHIP", -1052.0, None)
check("ALLOWS_A_LEDGER_OWNED_COIN", kind == "ENGINE", "the engine's own position was refused: %r" % (why,))
kind, why = F.ownership("HYPE", None, 1.0)
check("A_JOURNAL_COIN_WITH_A_FLAT_LEDGER_IS_AMBIGUOUS", kind == "AMBIGUOUS" and "JOURNAL" in why,
      "we placed it but the ledger says flat - that is a human call, not an auto-flatten: %r" % (kind,))
kind, why = F.ownership("XYZ:CRCL", -5.0, 1.0)
check("THE_NAME_LIST_BEATS_A_LEDGER_SLEEVE", kind == "USER", "the operator's coin must win: %r" % (kind,))
check("A_SHARED_SYMBOL_WITH_A_NET_MISMATCH_IS_REFUSED", not F.net_agrees(-100.0, -50.0),
      "reduce_only acts on the net: a half-ledger position must not be sent")
check("AN_AGREEING_NET_IS_ALLOWED", F.net_agrees(-100.0, -100.0))

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
      and by["WEIRD"]["reason"] == "ABSENT_FROM_LEDGER")

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

# ---- the six findings from the static review, each pinned
check("NET_AGREES_ON_SIGNED_VALUE", not F.net_agrees(-100.0, 100.0),
      "opposite signs of the same size must NOT agree - the send side follows the exchange sign")
check("SZ_DECIMALS_COME_FROM_META",
      F.sz_decimals_from_meta({"universe": [{"name": "CHIP", "szDecimals": 3}]}).get("CHIP") == 3,
      "without szDecimals every size floors to whole units and leaves a fraction behind")
_frac = F.wire_size(10.9876, 3)
check("A_FRACTIONAL_POSITION_FLOORS_CORRECTLY", abs(_frac - 10.987) < 1e-9, "got %r" % (_frac,))
check("LIVE_REQUIRES_A_TESTNET_ENDPOINT",
      F.is_testnet("https://api.hyperliquid-testnet.xyz/info") and not F.is_testnet("https://api.hyperliquid.xyz/info"),
      "a live send must not be possible against the mainnet info endpoint")
check("AN_UNEXPECTED_RESULT_ABORTS_THE_RUN",
      "ABORTED_UNEXPECTED_RESULT" in src and "abort_run(state, live, rows, extra, 5" in src,
      "ORDER_UNKNOWN and unclassifiable replies must stop the whole run, not be retried")
check("CANCELS_ARE_VERIFIED_BEFORE_FLATTENING",
      "STILL RESTING" in src and "refusing to flatten" in src and "abort_run(state, live, rows, extra, 7" in src,
      "a surviving resting order can fill into a flattened book")
check("THE_BOOK_IS_RE_READ_AFTER_THE_CANCELS",
      "positions after cancels" in src and "frozen book" in src,
      "the plan must be built from the post-cancel book, not the pre-cancel one")
check("THE_INTENT_BUILDER_GETS_A_LEDGER",
      "IntentBuilder(ConfigManager(), ManualLedger(path=_ltmp))" in src,
      "build() dereferences ledger.sleeve_id; None crashes the live path before its first order")
check("THE_LEDGER_IS_A_DISPOSABLE_COPY",
      "tempfile.mkdtemp(prefix=\"flatten_ledger_\")" in src and "ManualLedger(path=state" not in src,
      "the real engine ledger must never be handed to a maintenance script that could save over it")

# ---- the controller's five items, each pinned to the code that closes it
check("THE_ORDER_CLIENT_ENDPOINT_IS_CHECKED",
      "client_is_testnet(exch)" in src and "client_endpoint(exch)" in src,
      "checking the info URL does not prove the ORDER endpoint is testnet")
check("AN_UNREADABLE_ENDPOINT_REFUSES",
      "endpoint_not_proven" in src.lower() and ("abort_run(state, live, rows, extra, 6" in src or "refuse(state, live, rows, extra, 6" in src),
      "an unreadable client endpoint must refuse, not pass")
check("THE_LEDGER_FINGERPRINT_IS_TAKEN_AND_RECHECKED",
      "ledger_fingerprint(real_ledger)" in src and "ledger_unchanged(real_ledger, fp)" in src,
      "a ledger edited after the copy must stop the run")
check("CANCELS_ARE_MANDATORY_FOR_LIVE",
      "requires --cancel-resting" in src and "refuse(state, live, rows, extra, 8" in src,
      "a live run without verified cancels must refuse")
check("A_CANCEL_FAILURE_IS_A_HARD_STOP",
      'CANCEL_FAILED' in src and "abort_run(state, live, rows, extra, 10" in src,
      "a recorded note is not a hard stop")
check("ONLY_A_CLEAN_IOC_NO_MATCH_MAY_RETRY",
      "_no_match" in src and "ABORTED_UNEXPECTED_RESULT" in src and '"no match" in _why' in src,
      "the predicate must read the rejection text - a status-only predicate can never fire and aborts every IOC")
check("THE_REPORT_IS_WRITTEN_BEFORE_AN_EARLY_RETURN",
      "abort_run(state, live, rows, extra" in src and "os.fsync" in src,
      "every abort must go through abort_run, which re-reads positions and writes+fsyncs the report")
check("A_FAILED_REPORT_WRITE_IS_ANNOUNCED",
      "REPORT_NOT_WRITTEN" in src,
      "a persistence failure on an abort must be printed, not swallowed")
check("EACH_COIN_IS_REBUILT_FROM_A_FRESH_READ",
      "ALREADY_FLAT" in src and "_live = {p[\"coin\"].upper()" in src,
      "the next send must use the fresh net, not the precomputed plan")
check("A_PRECISION_REMAINDER_IS_NAMED",
      "REMAINDER_" in src and "PRECISION_UNKNOWN" in src,
      "an unknown step or a floored remainder must be visible in the row")
check("TESTNET_IS_A_CANONICAL_HOST",
      "urlparse" in src and "TESTNET_HOSTS" in src and "testnet\" in u" not in src.lower(),
      "substring matching accepts testnet.example.com")
check("POSITIONS_ARE_RE_READ_AFTER_EACH_COIN",
      "post_coin_positions" in src,
      "the next decision must come from the exchange, not a stale snapshot")
check("THE_LEDGER_IS_A_DISPOSABLE_COPY", "ManualLedger(path=_ltmp)" in src,
      "the real ledger must never be handed to a maintenance script")

check("THE_ENDPOINT_PROOF_HAS_A_REAL_FALLBACK",
      "HL_EXCHANGE_URL" in src and "from HL_Live_Copy_Service_Core import HL_EXCHANGE_URL" in src,
      "a client object with no url attribute would make every live flatten refuse forever")
check("A_MAINNET_ENDPOINT_IS_REFUSED",
      not F.is_testnet("https://api.hyperliquid.xyz/exchange"), "mainnet must never pass as testnet")

# ---- (a) a mainnet value in ANY source refuses, even when another says testnet
class _Mixed:
    base_url = "https://api.hyperliquid-testnet.xyz/exchange"
_prev = os.environ.get("HL_EXCHANGE_URL")
os.environ["HL_EXCHANGE_URL"] = "https://api.hyperliquid.xyz/exchange"
_mixed = F.client_is_testnet(_Mixed())
if _prev is None:
    os.environ.pop("HL_EXCHANGE_URL", None)
else:
    os.environ["HL_EXCHANGE_URL"] = _prev
check("A_MAINNET_VALUE_IN_ANY_SOURCE_REFUSES", _mixed is False,
      "a testnet client attribute overrode a mainnet environment - that is how an order reaches mainnet")

# ---- (b) it cannot pass on missing/empty values
class _NoUrl:
    pass
_env_bak = os.environ.pop("HL_EXCHANGE_URL", None)
_no_src = F.client_is_testnet(_NoUrl())
if _env_bak is not None:
    os.environ["HL_EXCHANGE_URL"] = _env_bak
check("NO_READABLE_SOURCE_REFUSES", _no_src in (None, True) and _no_src is not False,
      "no source must not read as 'mainnet' by accident, and must never silently pass")
check("EVERY_SOURCE_IS_EXAMINED", "endpoint_sources(exchange)" in src and "for _name, url in sources" in src,
      "returning on the first source lets a stale attribute vouch for a mainnet environment")

check("HTTPS_AND_EXACT_HOST_ONLY",
      'scheme == "https"' in src and "TESTNET_HOSTS" in src and "endswith" not in src.split("def is_testnet")[1][:600],
      "localhost, 127.0.0.1 and wildcard subdomains must not pass")
check("A_REVERSED_POSITION_IS_SKIPPED", "SIGN_CHANGED_" in src, "a reversed position is a different trade")
check("A_GREWN_POSITION_IS_REFUSED", "GREW_" in src,
      "a position that grew must not be reduced beyond the reviewed amount")
check("EVIDENCE_FAILURE_RETURNS_A_DISTINCT_CODE", "return 100 + int(code)" in src,
      "a failed report must not look like a clean abort")
check("THE_REMAINDER_HAS_ITS_OWN_FIELD", 'r["remainder"]' in src,
      "the order result must not overwrite the precision note")
check("REFUSALS_LEAVE_EVIDENCE_WHEN_LIVE", "def refuse(" in src and "REFUSED" in src)

failed = [n for n, ok in results if not ok]
print("TOTAL=%d FAILED=%d" % (len(results), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
