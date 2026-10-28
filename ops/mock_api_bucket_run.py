"""Mocked-API bucket run: prove bucket coverage end-to-end from an API-shaped payload.

No network, no credentials, no live engine. The /info userFills payload is mocked, the rows
it would produce are written exactly as the ingest writes them (source ledger) and as the
Core writes them (order_intents), then bucket_reconciliation is asked to judge coverage.

Cases:
  1 CLEAN     two fills, two intents, same bucket                    -> PASS
  2 MERGED    two fills netted into one catch-up intent              -> PASS, merged_buckets=1
  3 DROPPED   one fill never became an intent (short notional)       -> FAIL, cause=count
  4 DRIFTED   intent notional disagrees with the source fills        -> FAIL, cause=notional
  5 WIDENED   intents carry ingest time only                         -> PASS at 5 minutes

Run: python ops/mock_api_bucket_run.py     (exit 0 = all expectations held)
"""
import csv
import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("apply_hotfix_mock", HERE / "apply_hotfix.py")
HOTFIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOTFIX)

WALLET = "0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205"
T0 = 1_759_000_020_000          # inside one minute boundary
STOP_MS = T0 - 60_000
FIRST_MS = T0 + 300_000


def api_payload():
    """Shaped like Hyperliquid /info userFills: hash, tid, coin, side, px, sz, time, closedPnl."""
    return [
        {"hash": "0xa1", "tid": 8001, "coin": "BTC", "side": "B", "px": "61000.0",
         "sz": "0.010", "time": T0 + 1_000, "closedPnl": "0.0", "user": WALLET},
        {"hash": "0xa2", "tid": 8002, "coin": "BTC", "side": "B", "px": "61500.0",
         "sz": "0.010", "time": T0 + 40_000, "closedPnl": "0.0", "user": WALLET},
        {"hash": "0xb1", "tid": 8003, "coin": "ETH", "side": "A", "px": "2400.0",
         "sz": "0.500", "time": T0 + 120_000, "closedPnl": "0.0", "user": WALLET},
    ]


def ingest_rows(payload):
    """What the ingest writes to the local raw leader-fill ledger."""
    rows = []
    for f in payload:
        rows.append({"leader_fill_id": f["hash"], "user": f["user"], "coin": f["coin"],
                     "side": f["side"], "px": f["px"], "sz": f["sz"], "time": f["time"],
                     "tid": str(f["tid"])})
    return rows


def _core_side(api_side):
    """What Core's LeaderFill.side actually is: BUY/SELL, never raw API B/A.

    Deliberately a separate implementation from production _canonical_side so a mutation in
    production cannot move both sides at once and mask the B/A-vs-BUY/SELL mismatch.
    """
    token = str(api_side or "").strip().upper()
    return {"B": "BUY", "A": "SELL"}.get(token, token)

def intent_rows(payload, drop_tids=(), merge_tids=(), notional_scale=1.0, ingest_time=False):
    """What the Core writes to order_intents, including the catch-up merge shape."""
    rows = []
    merged_done = False
    for f in payload:
        if f["tid"] in drop_tids:
            continue
        notional = abs(float(f["px"]) * float(f["sz"])) * notional_scale
        if f["tid"] in merge_tids:
            if merged_done:
                continue
            group = [g for g in payload if g["tid"] in merge_tids]
            notional = sum(abs(float(g["px"]) * float(g["sz"])) for g in group) * notional_scale
            at = max(g["time"] for g in group)
            merged_done = True
        else:
            at = f["time"]
        rows.append({"created_at_ms": at + 2_000 if ingest_time else at + 2_000,
                     "leader_fill_id": f["hash"], "leader_wallet": f["user"],
                     "coin": f["coin"], "leader_side": _core_side(f["side"]),
                     "leader_notional": "%.10f" % notional,
                     "leader_tid": str(f["tid"]),
                     "leader_fill_timestamp_ms": "" if ingest_time else at})
    return rows


def extra_intent(coin, tid, px, sz, event_ms, created_ms, side="B"):
    """One Core intent row shaped like the additive writer: event stamp and ingest time differ."""
    return {"created_at_ms": created_ms, "leader_fill_id": "0x%s" % tid, "leader_wallet": WALLET,
            "coin": coin, "leader_side": _core_side(side),
            "leader_notional": "%.10f" % (abs(float(px) * float(sz))),
            "leader_tid": str(tid), "leader_fill_timestamp_ms": event_ms}


def write_case(root, name, source_rows, intents):
    state = root / name / "state"
    (state / "append_only").mkdir(parents=True)
    src = root / name / "source.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["leader_fill_id", "user", "coin", "side", "px", "sz",
                                           "time", "tid"])
        w.writeheader()
        w.writerows(source_rows)
    with (state / "append_only" / "order_intents.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["created_at_ms", "leader_fill_id", "leader_wallet",
                                           "coin", "leader_side", "leader_notional", "leader_tid",
                                           "leader_fill_timestamp_ms"])
        w.writeheader()
        w.writerows(intents)
    return state, src


def run():
    payload = api_payload()
    src_rows = ingest_rows(payload)
    results, failed = [], 0

    def case(name, intents, expect_error=None, expect=None, source=None):
        nonlocal failed
        root = Path(tmp)
        state, src = write_case(root, name, source if source is not None else src_rows, intents)
        try:
            proof = HOTFIX.bucket_reconciliation(state, src, STOP_MS, FIRST_MS)
        except HOTFIX.HotfixError as exc:
            if expect_error and expect_error in str(exc):
                results.append("RESULT::MOCK_%s_PASS (raised as expected: %s)"
                               % (name, expect_error))
                return
            failed += 1
            results.append("FAIL MOCK_%s | unexpected raise: %s" % (name, exc))
            return
        if expect_error:
            failed += 1
            results.append("FAIL MOCK_%s | expected %r, got PASS %r" % (name, expect_error, proof))
            return
        for k, v in (expect or {}).items():
            if proof.get(k) != v:
                failed += 1
                results.append("FAIL MOCK_%s | %s=%r want %r (%r)" % (name, k, proof.get(k), v, proof))
                return
        results.append("RESULT::MOCK_%s_PASS %s" % (name, {k: proof[k] for k in
                                                          ("buckets", "source_fills", "intent_rows",
                                                           "width_ms", "provenance",
                                                           "merged_buckets", "failed_buckets")}))

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = tmp_dir
        case("CLEAN", intent_rows(payload),
             # ROUND 1 (00:01Z) and the two BTC fills at +1s/+40s share a bucket; ROUND 2 (00:02Z) is its own
             expect={"failed_buckets": 0, "source_fills": 3, "intent_rows": 3, "buckets": 2})
        case("MERGED", intent_rows(payload, merge_tids=(8001, 8002)),
             expect={"failed_buckets": 0, "merged_buckets": 1, "intent_rows": 2})
        case("DROPPED", intent_rows(payload, drop_tids=(8002,)), expect_error="bucket coverage FAIL")
        case("DRIFTED", intent_rows(payload, notional_scale=1.02), expect_error="notional")
        case("WIDENED", intent_rows(payload, ingest_time=True),
             expect={"failed_buckets": 0, "width_ms": HOTFIX.BUCKET_WIDTH_WIDE_MS,
                     "provenance": "ingest_time_widened"})

        # Production shape: the source ledger keeps raw Hyperliquid B/A while the Core writes
        # canonical BUY/SELL. Before the canonical-side fix this case failed with two count
        # errors despite a perfect replay; it must now pass.
        case("SIDE_MAPPING", intent_rows(payload),
             expect={"failed_buckets": 0, "source_fills": 3, "intent_rows": 3})

        # P1-c: an intent whose EVENT time falls after first_cycle_ms is ongoing trading, not
        # replay coverage. Including it creates a right-only bucket and a false FAIL; it must
        # be excluded while in-window fills are still counted.
        case("POST_CYCLE_EXCLUSION",
             intent_rows(payload) + [extra_intent("SOL", 9999, "100.0", "1.0",
                                                  FIRST_MS + 120_000, FIRST_MS + 120_000)],
             expect={"failed_buckets": 0, "source_fills": 3, "intent_rows": 3})

        # P1-c: a gap fill whose EVENT time is inside the window but whose INGEST time is after
        # first_cycle_ms must be retained (late-ingested gap fill), not dropped as post-cycle.
        gap_source = src_rows + [{"leader_fill_id": "0xc1", "user": WALLET, "coin": "BTC",
                                  "side": "B", "px": "62000.0", "sz": "0.010",
                                  "time": T0 + 200_000, "tid": "8004"}]
        case("LATE_INGEST_GAP_FILL",
             intent_rows(payload) + [extra_intent("BTC", 8004, "62000.0", "0.010",
                                                  T0 + 200_000, FIRST_MS + 45_000)],
             expect={"failed_buckets": 0, "source_fills": 4, "intent_rows": 4},
             source=gap_source)

        # P2-d: merged_buckets must reach the durable proof object returned to the swap record.
        case("MERGED_PROOF_KEY", intent_rows(payload, merge_tids=(8001, 8002)),
             expect={"failed_buckets": 0, "merged_buckets": 1})

        # C7-DIR-43(3): lower bound. A stamped intent whose event time is BEFORE stop_ms is a
        # late-ingested pre-stop fill and must be excluded. With no in-window source rows the
        # result is an empty-but-clean proof; including the intent would create a right-only
        # bucket and fail.
        case("LATE_PRE_STOP_FILL",
             [extra_intent("BTC", 8101, "60000.0", "0.010", STOP_MS - 5_000, STOP_MS + 1_000)],
             expect={"failed_buckets": 0, "source_fills": 0, "intent_rows": 0},
             source=[])

        # C7-DIR-43(3): upper bound for ingest-only rows. An unstamped intent created after
        # first_cycle_ms is ordinary post-cycle trading, not replay coverage; including it
        # creates a right-only bucket. It must be excluded while the three in-window fills
        # still reconcile.
        case("POST_CYCLE_UNSTAMPED",
             intent_rows(payload) + [{"created_at_ms": FIRST_MS + 120_000, "leader_fill_id": "0xd1",
                                      "leader_wallet": WALLET, "coin": "SOL", "leader_side": "BUY",
                                      "leader_notional": "100.0", "leader_tid": "9998",
                                      "leader_fill_timestamp_ms": ""}],
             expect={"failed_buckets": 0, "source_fills": 3, "intent_rows": 3})

        # Malformed financial fields must be rejected, never coerced to zero notional.
        bad_src = [dict(r) for r in src_rows]
        bad_src[0] = dict(bad_src[0]); bad_src[0]["px"] = "not-a-price"
        bad_state = Path(tmp) / "MALFORMED_SOURCE" / "state"
        (bad_state / "append_only").mkdir(parents=True)
        bad_src_path = Path(tmp) / "MALFORMED_SOURCE" / "source.csv"
        with bad_src_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["leader_fill_id", "user", "coin", "side", "px", "sz",
                                               "time", "tid"])
            w.writeheader(); w.writerows(bad_src)
        with (bad_state / "append_only" / "order_intents.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["created_at_ms", "leader_fill_id", "leader_wallet",
                                               "coin", "leader_side", "leader_notional", "leader_tid",
                                               "leader_fill_timestamp_ms"])
            w.writeheader(); w.writerows(intent_rows(payload))
        try:
            HOTFIX.bucket_reconciliation(bad_state, bad_src_path, STOP_MS, FIRST_MS)
            failed += 1
            results.append("FAIL MOCK_MALFORMED_SOURCE | expected rejection of bad px, got PASS")
        except HOTFIX.HotfixError as exc:
            if "source.px" in str(exc):
                results.append("RESULT::MOCK_MALFORMED_SOURCE_PASS (raised as expected)")
            else:
                failed += 1
                results.append("FAIL MOCK_MALFORMED_SOURCE | wrong reason: %s" % exc)

        bad_intents = intent_rows(payload)
        bad_intents[0] = dict(bad_intents[0]); bad_intents[0]["leader_notional"] = ""
        case("MALFORMED_INTENT", bad_intents, expect_error="intent.leader_notional")

    for line in results:
        print(line)
    print("TOTAL=%d FAILED=%d" % (len(results), failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
