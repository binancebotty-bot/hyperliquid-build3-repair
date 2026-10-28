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
