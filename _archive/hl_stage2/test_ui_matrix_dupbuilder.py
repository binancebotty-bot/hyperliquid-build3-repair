#!/usr/bin/env python3
"""UI-MATRIX: cover the duplicate open-position builder `_build_real_copy_positions`.

`_build_real_copy_positions` (HL_Copy_App_SSOT.py, only caller `_live_audit_summary_full`) emits the
same open-position row shape as the inline block inside `_build_live_leader_performance`, but nothing
exercised it, so mutating it reddened zero rows.

This file calls the real builder with fixtures and asserts its row fields are DERIVED from the inputs,
not echoed: mark_px is the raw positionValue/|szi| carried through the real snapshot parser,
position_value is |sleeve size| x mark, unrealized_pnl is (mark - entry) x signed size, side/residual
come from the sign and the ownership classification. Each mutation of one derivation must redden ONLY
the rows that assertion bites (see the MUTATION:: table), and the two producers must keep the same
open-position keys.

Seams stubbed (I/O only, never business logic): the exchange HTTP round-trip (urllib urlopen), the
realized-PnL fetch, the account address, the snapshot file, the audit CSVs, service-fill evidence.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_ui_matrix_dupbuilder.py   (RESULT:: markers, exit 0/1)
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
RESULTS = []

WALLET_A = "0x" + "a" * 40
WALLET_B = "0x" + "b" * 40
ADDRESS = "0x" + "c" * 40

# Raw clearinghouse bytes: positionValue is signed (as the exchange sends it) and deliberately NOT
# equal to size*mark-as-a-field, so a naive echo of positionValue cannot satisfy the mark assertions.
RAW_CLEARINGHOUSE = {
    "marginSummary": {"accountValue": "10000", "totalMarginUsed": "1000", "totalNtlPos": "136366", "totalRawUsd": "10000"},
    "crossMarginSummary": {"accountValue": "10000", "totalMarginUsed": "0", "totalNtlPos": "136366", "totalRawUsd": "10000"},
    "withdrawable": "9000",
    "assetPositions": [
        {"position": {"coin": "BTC", "szi": "2.0", "positionValue": "130000.0", "entryPx": "61000.0",
                      "unrealizedPnl": "8000.0", "marginUsed": "500.0"}},
        {"position": {"coin": "ETH", "szi": "-3.0", "positionValue": "-6300.0", "entryPx": "2000.0",
                      "unrealizedPnl": "-300.0", "marginUsed": "250.0"}},
        {"position": {"coin": "SOL", "szi": "0.4", "positionValue": "66.0", "entryPx": "150.0",
                      "unrealizedPnl": "6.0", "marginUsed": "20.0"}},
    ],
}
RAW_SPOT = {"balances": [{"coin": "USDC", "total": "10000", "hold": "0"}]}

MANUAL = {
    "schema": "manual_live_positions.v2",
    "by_wallet": {
        WALLET_A: {"BTC": {"signed_size": 1.5, "avg_entry_px": 50000.0, "last_copy_fill_id": "f1",
                           "last_oid": "11", "last_intent_id": "i1", "last_updated_ms": 1700000000000,
                           "last_updated_at": "2026-01-01T00:00:00Z"}},
        WALLET_B: {"ETH": {"signed_size": -2.5, "avg_entry_px": 3100.0, "last_copy_fill_id": "f2",
                           "last_oid": "22", "last_intent_id": "i2", "last_updated_ms": 1700000000001,
                           "last_updated_at": "2026-01-01T00:00:01Z"}},
    },
}

# Raw exchange inputs the assertions re-derive from (never the builder's own output).
RAW_SZI = {item["position"]["coin"]: float(item["position"]["szi"]) for item in RAW_CLEARINGHOUSE["assetPositions"]}
RAW_PV = {item["position"]["coin"]: float(item["position"]["positionValue"]) for item in RAW_CLEARINGHOUSE["assetPositions"]}
RAW_ENTRY = {item["position"]["coin"]: float(item["position"]["entryPx"]) for item in RAW_CLEARINGHOUSE["assetPositions"]}

CORE_KEYS = {"coin", "signed_size", "side", "entry_px", "mark_px", "unrealized_pnl",
             "residual_size", "unsupported_size"}
BUILDER_ONLY_KEYS = {"row_type", "leader_wallet", "avg_entry_px", "last_copy_fill_id", "last_updated_ms",
                     "last_intent_id", "last_oid", "last_updated_at", "exchange_signed_size",
                     "position_value", "ledger_vs_exchange", "reconciliation_note"}
INLINE_ONLY_KEYS = {"shared", "exposure", "exchange_match", "ownership_status"}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _fake_urlopen(req, timeout=None):
    kind = json.loads(req.data.decode("utf-8")).get("type")
    body = RAW_CLEARINGHOUSE if kind == "clearinghouseState" else RAW_SPOT
    return _Resp(json.dumps(body).encode("utf-8"))


class Seams:
    """Stub the exchange/price I/O of a module, then restore it."""

    def __init__(self, mod, tmp: Path) -> None:
        self.mod, self.tmp, self.saved = mod, tmp, {}

    def __enter__(self) -> "Seams":
        mod = self.mod
        self.saved = {
            "urlopen": urllib.request.urlopen,
            "_fetch_user_realized_pnl_snapshot": mod._fetch_user_realized_pnl_snapshot,
            "_public_account_address": mod._public_account_address,
            "_service_position_evidence_by_coin": mod._service_position_evidence_by_coin,
            "EXCHANGE_ACCOUNT_SNAPSHOT_FILE": mod.EXCHANGE_ACCOUNT_SNAPSHOT_FILE,
            "LIVE_FILLS_CSV": mod.LIVE_FILLS_CSV,
            "WOULD_SEND_ORDERS_CSV": mod.WOULD_SEND_ORDERS_CSV,
        }
        urllib.request.urlopen = _fake_urlopen
        mod._fetch_user_realized_pnl_snapshot = lambda account=None, **kw: {}
        mod._public_account_address = lambda: ADDRESS
        mod._service_position_evidence_by_coin = lambda *a, **kw: {}
        mod.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = self.tmp / "exchange_account_snapshot_app.json"
        mod.LIVE_FILLS_CSV = self.tmp / "no_live_fills.csv"
        mod.WOULD_SEND_ORDERS_CSV = self.tmp / "no_would_send.csv"
        return self

    def __exit__(self, *exc) -> bool:
        for name, value in self.saved.items():
            if name == "urlopen":
                urllib.request.urlopen = value
            else:
                setattr(self.mod, name, value)
        return False


def _build_ctx(mod, tmp: Path) -> dict:
    """Run the REAL snapshot parser, then both row producers, on the same fixture."""
    with Seams(mod, tmp):
        snap = mod._fetch_exchange_account_snapshot(0.0)
        owned = mod._build_real_copy_positions(MANUAL, snap)
        live = mod._build_live_leader_performance([], MANUAL, snap, {"wallets": {WALLET_A: {}, WALLET_B: {}}}, [])
    owned_by_coin = {row["coin"]: row for row in owned if row.get("row_type") == "OWNED_COPY"}
    orphan_by_coin = {row["coin"]: row for row in owned if row.get("row_type") == "ACCOUNT_LEVEL_ONLY"}
    inline_by_key = {}
    for wallet, perf in live.items():
        for row in perf.get("current_open_positions") or []:
            inline_by_key[(wallet, row["coin"])] = row
    return {"snap": snap, "owned": owned, "owned_by_coin": owned_by_coin,
            "orphan_by_coin": orphan_by_coin, "inline": inline_by_key}


# --- assertions: one named check per derivation -------------------------------------------------

def c_mark_derived(ctx) -> tuple[bool, str]:
    """mark_px is positionValue/|szi| through the real parser, not an echo of any input field."""
    want = RAW_PV["BTC"] / abs(RAW_SZI["BTC"])          # 130000/2.0 = 65000
    got = ctx["owned_by_coin"]["BTC"]["mark_px"]
    echo = {RAW_PV["BTC"], RAW_ENTRY["BTC"], RAW_SZI["BTC"]}
    ok = got == want and want not in echo
    return ok, "mark_px=%r want=%r echoes=%r" % (got, want, sorted(echo))


def c_position_value_derived(ctx) -> tuple[bool, str]:
    """position_value is the sleeve's own notional: |sleeve size| x mark, not the account notional."""
    want = abs(1.5) * (RAW_PV["BTC"] / abs(RAW_SZI["BTC"]))   # 97500
    got = ctx["owned_by_coin"]["BTC"]["position_value"]
    ok = got == want and got != RAW_PV["BTC"]
    return ok, "position_value=%r want=%r account_notional=%r" % (got, want, RAW_PV["BTC"])


def c_unrealized_derived(ctx) -> tuple[bool, str]:
    """unrealized_pnl is (mark - ledger entry) x signed size, not the exchange's own PnL."""
    mark = RAW_PV["BTC"] / abs(RAW_SZI["BTC"])
    want = round((mark - 50000.0) * 1.5, 8)                   # 22500
    got = ctx["owned_by_coin"]["BTC"]["unrealized_pnl"]
    ok = got == want and got != 8000.0
    return ok, "unrealized_pnl=%r want=%r exchange_pnl=8000.0" % (got, want)


def c_side_and_residual_derived(ctx) -> tuple[bool, str]:
    """side follows the sign of the sleeve; residual is exchange net minus owned net."""
    btc, eth = ctx["owned_by_coin"]["BTC"], ctx["owned_by_coin"]["ETH"]
    ok = (btc["side"] == "LONG" and eth["side"] == "SHORT"
          and btc["residual_size"] == 0.5 and eth["residual_size"] == -0.5
          and btc["ledger_vs_exchange"] == "RESIDUAL_ACCOUNT_LEVEL")
    return ok, "btc=(%r,%r,%r) eth=(%r,%r,%r)" % (btc["side"], btc["residual_size"], btc["ledger_vs_exchange"],
                                                  eth["side"], eth["residual_size"], eth["ledger_vs_exchange"])


def c_short_mark_positive(ctx) -> tuple[bool, str]:
    """A short keeps its sign in szi/side only: the mark is |positionValue|/|szi|, so the builder carries
    a POSITIVE mark and a real PnL for the short row instead of dropping both."""
    snap_mark = ctx["snap"]["positions_by_coin"]["ETH"]["mark_px"]
    row = ctx["owned_by_coin"]["ETH"]
    want = abs(RAW_PV["ETH"]) / abs(RAW_SZI["ETH"])            # 6300/3.0 = 2100
    want_upnl = round((want - 3100.0) * -2.5, 8)               # (mark - entry) x signed sleeve size
    ok = (snap_mark == want and row["signed_size"] == -2.5 and row["side"] == "SHORT"
          and row["mark_px"] == want and row["unrealized_pnl"] == want_upnl)
    return ok, "snap_mark=%r want=%r row_mark_px=%r row_upnl=%r want_upnl=%r" % (
        snap_mark, want, row["mark_px"], row["unrealized_pnl"], want_upnl)


def c_orphan_row_from_exchange_only(ctx) -> tuple[bool, str]:
    """The exchange-only row takes its mark from the same derived snapshot mark and no ledger fields."""
    row = ctx["orphan_by_coin"]["SOL"]
    want = RAW_PV["SOL"] / abs(RAW_SZI["SOL"])                # 66/0.4 = 165
    ok = row.get("mark_px") == want and row.get("signed_size") is None and row.get("position_value") == ctx["snap"]["positions_by_coin"]["SOL"]["position_value"]
    return ok, "mark_px=%r want=%r signed_size=%r" % (row.get("mark_px"), want, row.get("signed_size"))


def c_shape_core_keys(ctx) -> tuple[bool, str]:
    """Both producers carry the same open-position core keys."""
    builder = set(ctx["owned_by_coin"]["BTC"])
    inline = set(ctx["inline"][(WALLET_A, "BTC")])
    ok = CORE_KEYS <= builder and CORE_KEYS <= inline
    return ok, "missing_builder=%r missing_inline=%r" % (sorted(CORE_KEYS - builder), sorted(CORE_KEYS - inline))


def c_shape_key_drift(ctx) -> tuple[bool, str]:
    """Full key sets: core + the declared per-producer extras. Any drift on either side reddens here."""
    builder = set(ctx["owned_by_coin"]["BTC"])
    inline = set(ctx["inline"][(WALLET_A, "BTC")])
    ok = builder == CORE_KEYS | BUILDER_ONLY_KEYS and inline == CORE_KEYS | INLINE_ONLY_KEYS
    return ok, "builder_extra=%r builder_missing=%r inline_extra=%r inline_missing=%r" % (
        sorted(builder - (CORE_KEYS | BUILDER_ONLY_KEYS)), sorted((CORE_KEYS | BUILDER_ONLY_KEYS) - builder),
        sorted(inline - (CORE_KEYS | INLINE_ONLY_KEYS)), sorted((CORE_KEYS | INLINE_ONLY_KEYS) - inline))


def c_shape_value_parity(ctx) -> tuple[bool, str]:
    """Same fixture through both producers: every core field agrees, and the row notional
    (builder position_value / inline exposure) agrees wherever a live mark exists."""
    diffs = []
    for row in ctx["owned_by_coin"].values():
        peer = ctx["inline"].get((row["leader_wallet"], row["coin"]), {})
        for key in sorted(CORE_KEYS):
            if row.get(key) != peer.get(key):
                diffs.append("%s.%s builder=%r inline=%r" % (row["coin"], key, row.get(key), peer.get(key)))
        if row.get("mark_px") is not None and row.get("position_value") != peer.get("exposure"):
            diffs.append("%s.position_value=%r exposure=%r" % (row["coin"], row.get("position_value"), peer.get("exposure")))
    return not diffs, "; ".join(diffs)


def c_short_notional_from_mark(ctx) -> tuple[bool, str]:
    """The short's notional is |size| x derived mark in BOTH producers, never the entry-price fallback."""
    owned = ctx["owned_by_coin"]["ETH"]
    inline = ctx["inline"][(WALLET_B, "ETH")]
    want = abs(-2.5) * (abs(RAW_PV["ETH"]) / abs(RAW_SZI["ETH"]))   # 2.5 x 2100 = 5250
    entry_fallback = round(abs(-2.5) * 3100.0, 4)                  # 7750 if the mark were missing
    ok = owned["position_value"] == want and inline["exposure"] == want and want != entry_fallback
    return ok, "builder_position_value=%r inline_exposure=%r want=%r entry_fallback=%r" % (
        owned["position_value"], inline["exposure"], want, entry_fallback)


CHECKS = [
    ("DUP_MARK_DERIVED_PV_OVER_SIZE", c_mark_derived),
    ("DUP_POSITION_VALUE_DERIVED", c_position_value_derived),
    ("DUP_UNREALIZED_DERIVED", c_unrealized_derived),
    ("DUP_SIDE_AND_RESIDUAL_DERIVED", c_side_and_residual_derived),
    ("DUP_SHORT_MARK_POSITIVE", c_short_mark_positive),
    ("DUP_ORPHAN_ROW_FROM_EXCHANGE_ONLY", c_orphan_row_from_exchange_only),
    ("DUP_SHAPE_CORE_KEYS", c_shape_core_keys),
    ("DUP_SHAPE_KEY_DRIFT", c_shape_key_drift),
    ("DUP_SHAPE_VALUE_PARITY", c_shape_value_parity),
    ("DUP_SHORT_NOTIONAL_FROM_MARK", c_short_notional_from_mark),
]

# Each mutation edits exactly one derivation; the failures must be ONLY these rows.
MUTATIONS = [
    ("M1_drop_division_in_snapshot_mark",
     'mark_px = abs(fnum(pos.get("positionValue"))) / abs(size) if abs(size) > 1e-12 else 0.0',
     'mark_px = fnum(pos.get("positionValue")) if abs(size) > 1e-12 else 0.0',
     {"DUP_MARK_DERIVED_PV_OVER_SIZE", "DUP_POSITION_VALUE_DERIVED", "DUP_UNREALIZED_DERIVED",
      "DUP_SHORT_MARK_POSITIVE", "DUP_SHORT_NOTIONAL_FROM_MARK", "DUP_ORPHAN_ROW_FROM_EXCHANGE_ONLY"}),
    ("M2_builders_mark_echoes_position_value",
     '        ex_signed = _exchange_signed_size(ex)\n'
     '        ex_mark = _exchange_field(ex, "mark_px")\n'
     '        ex_entry = _exchange_field(ex, "entry_px")',
     '        ex_signed = _exchange_signed_size(ex)\n'
     '        ex_mark = fnum(ex.get("position_value"))\n'
     '        ex_entry = _exchange_field(ex, "entry_px")',
     {"DUP_MARK_DERIVED_PV_OVER_SIZE", "DUP_POSITION_VALUE_DERIVED", "DUP_UNREALIZED_DERIVED",
      "DUP_SHAPE_VALUE_PARITY", "DUP_SHORT_MARK_POSITIVE", "DUP_SHORT_NOTIONAL_FROM_MARK"}),
    ("M3_position_value_drops_size_factor",
     "owned_position_value = abs(signed) * ex_mark if ex_mark > 0 else None",
     "owned_position_value = abs(ex_mark) if ex_mark > 0 else None",
     {"DUP_POSITION_VALUE_DERIVED", "DUP_SHAPE_VALUE_PARITY", "DUP_SHORT_NOTIONAL_FROM_MARK"}),
    ("M4_unrealized_echoes_exchange_pnl",
     "owned_unrealized = _owned_sleeve_unrealized(signed, avg_entry, ex_mark)",
     'owned_unrealized = fnum(ex.get("unrealized_pnl")) if ex_mark > 0 else None',
     {"DUP_UNREALIZED_DERIVED", "DUP_SHAPE_VALUE_PARITY", "DUP_SHORT_MARK_POSITIVE"}),
    # the exact field emission that a sweep of this builder could not redden before: one row alone bites
    ("M5_owned_row_drops_mark_px",
     '            "entry_px": avg_entry if avg_entry > 0 else None,\n'
     '            "mark_px": ex_mark if ex_mark > 0 else None,',
     '            "entry_px": avg_entry if avg_entry > 0 else None,\n'
     '            "mark_px": None,',
     {"DUP_MARK_DERIVED_PV_OVER_SIZE", "DUP_SHAPE_VALUE_PARITY", "DUP_SHORT_MARK_POSITIVE"}),
]


class _MutLoader(importlib.machinery.SourceFileLoader):
    """Import a module from in-memory (mutated) source, with __file__ still pointing at the real path."""

    def __init__(self, fullname: str, path: str, source: str) -> None:
        super().__init__(fullname, path)
        self._source = source

    def get_data(self, path: str) -> bytes:
        if os.path.abspath(path) == os.path.abspath(self.path):
            return self._source.encode("utf-8")
        return super().get_data(path)

    def get_code(self, fullname: str):
        # compile the mutated source directly: never let an existing __pycache__ .pyc win
        return compile(self._source, self.path, "exec", dont_inherit=True)

    def set_data(self, path: str, data: bytes) -> None:
        pass  # never leave mutated bytecode in the repo's __pycache__


def _load_mutated(source_path: Path, name: str, source: str):
    loader = _MutLoader(name, str(source_path), source)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


def _run_checks(mod, tmp: Path) -> dict:
    ctx = _build_ctx(mod, tmp)
    return {name: fn(ctx) for name, fn in CHECKS}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="dupbuilder_"))
    try:
        import HL_Copy_App_SSOT as ui  # noqa: E402
        source_path = Path(ui.__file__).resolve()

        baseline = _run_checks(ui, tmp)
        for name, (ok, detail) in baseline.items():
            check(name, ok, detail)

        ctx = _build_ctx(ui, tmp)
        for row in ctx["owned"]:
            print("BUILDER_ROW::" + json.dumps({k: row.get(k) for k in
                  ("row_type", "coin", "leader_wallet", "side", "entry_px", "mark_px", "position_value",
                   "unrealized_pnl", "residual_size", "ledger_vs_exchange")}, sort_keys=True))

        source = source_path.read_text(encoding="utf-8-sig")
        print("\nMUTATION::%-42s %-4s %s" % ("mutation", "rc", "rows that reddened"))
        for index, (label, old, new, expected) in enumerate(MUTATIONS, start=1):
            if source.count(old) != 1:
                check("%s_SOURCE_MATCH" % label.upper(), False, "occurrences=%d" % source.count(old))
                continue
            mod = _load_mutated(source_path, "hl_dup_mut_%d" % index, source.replace(old, new))
            mutated = _run_checks(mod, tmp)
            failed = {name for name, (ok, _d) in mutated.items() if not ok}
            check("%s_ONLY_EXPECTED_ROWS" % label.upper(), failed == expected,
                  "failed=%r expected=%r" % (sorted(failed), sorted(expected)))
            print("MUTATION::%-42s %-4s %s" % (label, "OK" if failed == expected else "BAD", sorted(failed)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [name for name, ok in RESULTS if not ok]
    print("\nTOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED::" + ",".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
