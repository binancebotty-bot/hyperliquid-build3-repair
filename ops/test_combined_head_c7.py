"""Tests for the C7-DIR-22/30 combined head: bucket-level coverage C + additive provenance.

Run: python -m pytest ops/test_combined_head_c7.py -q
"""
import ast
import csv
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("apply_hotfix_under_test", HERE / "apply_hotfix.py")
AH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AH)

CORE = ROOT / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"


def core_text():
    # the Core file carries a UTF-8 BOM; ast.parse rejects U+FEFF
    return CORE.read_text(encoding="utf-8-sig", errors="replace")
T0 = 1_700_000_000_000          # aligned to a minute boundary
MIN = 60_000


def write_csv(path: Path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def source_row(wallet, coin, side, px, sz, at):
    return {"user": wallet, "coin": coin, "side": side, "px": px, "sz": sz, "time": at}


def intent_row(wallet, coin, side, notional, fill_at=None, created=T0 + 5_000):
    return {"created_at_ms": created, "leader_wallet": wallet, "coin": coin,
            "leader_side": side, "leader_notional": notional,
            "leader_fill_timestamp_ms": "" if fill_at is None else fill_at}


def build(tmp_path, source_rows, intent_rows):
    state = tmp_path / "state"
    src = tmp_path / "source.csv"
    write_csv(src, ["user", "coin", "side", "px", "sz", "time"], source_rows)
    write_csv(state / "append_only" / "order_intents.csv",
              ["created_at_ms", "leader_wallet", "coin", "leader_side", "leader_notional",
               "leader_fill_timestamp_ms"], intent_rows)
    return state, src


def test_bucket_pass_uses_leader_fill_time(tmp_path):
    state, src = build(
        tmp_path,
        [source_row("0xAbC", "btc", "BUY", "100", "0.1", T0),
         source_row("0xAbC", "btc", "BUY", "100", "0.2", T0 + 1_000)],
        [intent_row("0xabc", "BTC", "BUY", 10.0, T0),
         intent_row("0xabc", "BTC", "BUY", 20.0, T0 + 1_000)])
    proof = AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    assert proof["failed_buckets"] == 0
    assert proof["buckets"] == 1
    assert proof["width_ms"] == AH.BUCKET_WIDTH_MS
    assert proof["provenance"] == "leader_fill_time"
    assert proof["label"] == "bucket-level coverage"


def test_bucket_count_fail_names_the_bucket(tmp_path):
    state, src = build(
        tmp_path,
        [source_row("0xabc", "BTC", "BUY", "100", "0.1", T0),
         source_row("0xabc", "BTC", "BUY", "100", "0.2", T0 + 1_000)],
        [intent_row("0xabc", "BTC", "BUY", 10.0, T0)])
    with pytest.raises(AH.HotfixError) as exc:
        AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    msg = str(exc.value)
    assert "bucket coverage FAIL" in msg
    assert "0xabc" in msg and '"cause": "count"' in msg


def test_bucket_notional_tolerance_is_1e_6(tmp_path):
    state, src = build(
        tmp_path,
        [source_row("0xabc", "ETH", "SELL", "10", "3", T0)],
        [intent_row("0xabc", "ETH", "SELL", 30.0001, T0)])
    with pytest.raises(AH.HotfixError) as exc:
        AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    assert "notional" in str(exc.value)

    state2, src2 = build(
        tmp_path / "ok",
        [source_row("0xabc", "ETH", "SELL", "10", "3", T0)],
        [intent_row("0xabc", "ETH", "SELL", 29.99999997, T0)])
    assert AH.bucket_reconciliation(state2, src2, T0 - 1, T0 + MIN - 1)["failed_buckets"] == 0


def test_missing_provenance_widens_to_five_minutes_and_says_so(tmp_path):
    state, src = build(
        tmp_path,
        [source_row("0xabc", "SOL", "BUY", "10", "1", T0),
         source_row("0xabc", "SOL", "BUY", "10", "1", T0 + 2 * MIN)],
        [intent_row("0xabc", "SOL", "BUY", 10.0, None, created=T0 + 1_000),
         intent_row("0xabc", "SOL", "BUY", 10.0, None, created=T0 + 2 * MIN + 1_000)])
    proof = AH.bucket_reconciliation(state, src, T0 - 1, T0 + 5 * MIN - 1)
    assert proof["width_ms"] == AH.BUCKET_WIDTH_WIDE_MS
    assert proof["provenance"] == "ingest_time_widened"
    assert proof["failed_buckets"] == 0


def test_replay_proof_reports_bucket_metadata():
    src_text = (HERE / "apply_hotfix.py").read_text(encoding="utf-8")
    assert '"proof_label": buckets["label"]' in src_text
    assert "failed_buckets" in src_text
    # the strict fill-id equality check must be gone: bucket coverage replaces it
    assert "gap replay is missing order_intents rows" not in src_text


def test_core_columns_are_additive_only():
    tree = ast.parse(core_text())
    fields = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ORDER_INTENT_FIELDS" for t in node.targets):
            fields = [e.value for e in node.value.elts]
    assert fields is not None
    assert fields[-2:] == ["leader_tid", "leader_fill_timestamp_ms"]
    # every pre-existing column keeps its position: additive means appended, not reordered
    assert fields[0] == "created_at" and fields[6] == "coin" and fields[17] == "reason"


def test_core_write_site_populates_both_columns():
    tree = ast.parse(core_text())
    body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "append_order_intent":
            body = node
            break
    assert body is not None
    keys = {k.value for n in ast.walk(body) if isinstance(n, ast.Dict)
            for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert "leader_tid" in keys
    assert "leader_fill_timestamp_ms" in keys
    # provenance only: the decision/reason columns must not be touched by this change
    assert "decision" in keys and "reason" in keys


def test_catchup_merge_is_accepted_when_notional_is_conserved(tmp_path):
    # Core catch-up nets several leader fills into ONE intent row (raw["merged_fill_ids"]).
    # Bucket count must not false-FAIL that: notional conservation is the acceptance.
    state, src = build(
        tmp_path,
        [source_row("0xabc", "BTC", "BUY", "100", "0.1", T0),
         source_row("0xabc", "BTC", "BUY", "110", "0.1", T0 + 1_000)],
        [intent_row("0xabc", "BTC", "BUY", 21.0, T0 + 1_000)])
    proof = AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    assert proof["failed_buckets"] == 0
    assert proof["merged_buckets"] == 1
    assert proof["source_fills"] == 2 and proof["intent_rows"] == 1


def test_dropped_fill_is_not_excused_by_merge_tolerance(tmp_path):
    # same shape as the merge case, but a fill really went missing: notional is short, so FAIL
    state, src = build(
        tmp_path,
        [source_row("0xabc", "BTC", "BUY", "100", "0.1", T0),
         source_row("0xabc", "BTC", "BUY", "110", "0.1", T0 + 1_000)],
        [intent_row("0xabc", "BTC", "BUY", 10.0, T0)])
    with pytest.raises(AH.HotfixError) as exc:
        AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    assert '"cause": "count"' in str(exc.value)


def test_zero_intent_bucket_is_never_excused_as_a_merge(tmp_path):
    # The reviewer's specific check: merged_buckets must never excuse a bucket holding ZERO
    # intent rows against real source fills. The zero-notional variant is the trap - it would
    # otherwise satisfy "notional conserved" trivially and slip through as a merge.
    state, src = build(
        tmp_path,
        [source_row("0xabc", "BTC", "BUY", "100", "0.1", T0),
         source_row("0xabc", "BTC", "BUY", "100", "0.1", T0 + 1_000)],
        [intent_row("0xabc", "BTC", "BUY", 0.0, T0)])
    with pytest.raises(AH.HotfixError) as exc:
        AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    # one zero-notional row cannot absorb two real fills: notional is not conserved
    assert '"cause": "count"' in str(exc.value)
    assert '"intent_count": 1' in str(exc.value)

    # degenerate zero-notional source rows must not create a free pass either
    state2, src2 = build(
        tmp_path / "zero",
        [source_row("0xabc", "BTC", "BUY", "0", "0", T0),
         source_row("0xabc", "BTC", "BUY", "0", "0", T0 + 1_000)],
        [])
    with pytest.raises(AH.HotfixError) as exc2:
        AH.bucket_reconciliation(state2, src2, T0 - 1, T0 + MIN - 1)
    assert '"intent_count": 0' in str(exc2.value)


def test_canonical_side_maps_direction_strings_like_core_parse_fill():
    # Core parse_fill treats "Open Long" as BUY and "Close Short" as BUY, "Open Short" as
    # SELL and "Close Long" as SELL. Source rows carrying those strings must land in the same
    # bucket as Core's canonical BUY/SELL intents.
    assert AH._canonical_side("B") == "BUY"
    assert AH._canonical_side("A") == "SELL"
    assert AH._canonical_side("BUY") == "BUY"
    assert AH._canonical_side("SELL") == "SELL"
    assert AH._canonical_side("Open Long") == "BUY"
    assert AH._canonical_side("Close Short") == "BUY"
    assert AH._canonical_side("Open Short") == "SELL"
    assert AH._canonical_side("Close Long") == "SELL"
    # case and whitespace tolerant, as the ledger can carry padded values
    assert AH._canonical_side("  open long ") == "BUY"
    assert AH._canonical_side("CLOSE SHORT") == "BUY"


def test_canonical_side_rejects_unknown_and_empty_tokens():
    # Two unknowns matching each other would pass coverage without proving anything.
    for bad in ("FLIP", "Long", "wat", "Open"):
        with pytest.raises(AH.HotfixError) as exc:
            AH._canonical_side(bad)
        assert "unknown side token" in str(exc.value)
    with pytest.raises(AH.HotfixError) as exc:
        AH._canonical_side("")
    assert "empty side token" in str(exc.value)


def test_direction_strings_reconcile_against_canonical_intents(tmp_path):
    # Production shape: raw source carries direction strings, Core intents carry BUY/SELL.
    state, src = build(
        tmp_path,
        [source_row("0xabc", "BTC", "Open Long", "100", "0.1", T0),
         source_row("0xabc", "BTC", "Close Short", "100", "0.2", T0 + 1_000),
         source_row("0xabc", "ETH", "Open Short", "50", "1.0", T0)],
        [intent_row("0xabc", "BTC", "BUY", 10.0, T0),
         intent_row("0xabc", "BTC", "BUY", 20.0, T0 + 1_000),
         intent_row("0xabc", "ETH", "SELL", 50.0, T0)])
    proof = AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    assert proof["failed_buckets"] == 0
    assert proof["source_fills"] == 3
    assert proof["intent_rows"] == 3


def test_unknown_side_token_in_source_fails_loudly(tmp_path):
    state, src = build(
        tmp_path,
        [source_row("0xabc", "BTC", "FLIP", "100", "0.1", T0)],
        [intent_row("0xabc", "BTC", "BUY", 10.0, T0)])
    with pytest.raises(AH.HotfixError) as exc:
        AH.bucket_reconciliation(state, src, T0 - 1, T0 + MIN - 1)
    assert "unknown side token" in str(exc.value)


def test_replay_timeout_message_names_last_failed_bucket():
    # Terminal failure after the retry deadline must carry the named bucket, not a bare timeout.
    bare = AH._replay_timeout_message(None)
    assert "timed out" in bare and "last failed bucket" not in bare
    named = AH._replay_timeout_message(
        'bucket coverage FAIL: [{"bucket": ["0xabc", "BTC", "BUY", 28333333], "cause": "count"}]')
    assert "timed out" in named
    assert "last failed bucket" in named
    assert "BTC" in named
    assert "the pair remains up for operator review" in named



def test_goa_header_only_source_never_proves_zero_gap(tmp_path):
    state, source = build(tmp_path, [], [])
    with pytest.raises(AH.HotfixError, match="zero-fill gap requires completed leader API proof"):
        AH.replay_proof(state, {}, set(), source, T0, T0 + MIN, ["0x" + "a" * 40])
    # A genuine all-wallet API response (even an empty one) DOES create authenticated metadata.
    from unittest.mock import patch
    with patch.object(AH, "api_leader_fills", return_value={}), \
         patch.object(AH, "LAST_SWAP", tmp_path / "last.json"):
        exported, meta = AH.export_api_source(
            ["0x" + "a" * 40], T0, T0 + MIN, "f" * 40, "https://api.hyperliquid.xyz/info")
        assert exported.read_text(encoding="utf-8").count("\n") == 1
        assert meta["api_verified"] is True
        assert meta["total_fills"] == 0


def test_goa_incomplete_api_replies_fail_closed():
    wallet = "0x" + "a" * 40
    for invalid in (None, {"error": "rate limited"},
                    [{"tid": None, "time": 100, "coin": "BTC"}],
                    [{"tid": i, "time": 100, "coin": "BTC"} for i in range(2001)]):
        with pytest.raises(AH.HotfixError):
            AH.api_leader_fills(100, 200, [wallet], fetcher=lambda _q, batch=invalid: batch)


def test_goa_full_page_without_timestamp_advance_fails_closed():
    wallet = "0x" + "a" * 40
    batch = [{"tid": i, "time": 100, "coin": "BTC",
              "side": "B", "px": "100", "sz": "0.01"} for i in range(2000)]
    with pytest.raises(AH.HotfixError, match="millisecond pagination"):
        AH.api_leader_fills(100, 200, [wallet], fetcher=lambda _q: batch)


def test_goa_dedup_uses_wallet_tid_and_conflict_rejected(tmp_path):
    wallet = "0x" + "a" * 40
    rows = [{"tid": 17, "time": 150, "coin": "BTC", "side": "B",
             "px": "100", "sz": "0.01", "hash": "shared"}]
    seen = AH.api_leader_fills(100, 200, [wallet], fetcher=lambda _q: rows)
    assert (wallet, "17") in seen and len(seen) == 1
    different = [dict(rows[0], px="101"), dict(rows[0])]
    with pytest.raises(AH.HotfixError, match="conflicting contents"):
        AH.api_leader_fills(100, 200, [wallet], fetcher=lambda _q: different)
