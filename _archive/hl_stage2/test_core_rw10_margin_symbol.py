#!/usr/bin/env python3
"""rw10: the background margin-mode lane resolves a coin through the SAME resolver as the send path (kFLOKI, builder-DEX
xyz:SPCX), and a coin that truly cannot be resolved raises no per-cycle ValueError row: one rate-limited, named error row
per coin, margin mode left unset, nothing sent. Run (from _archive/hl_stage2): env -u HL_LIVE_AUDIT_DIR python test_core_rw10_margin_symbol.py"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def _try(g, coin):
    try:
        g._exchange_client_for_coin(coin)
    except Exception as exc:
        return str(exc)
    return ""


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rw10_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_DISABLE_NETWORK_REFRESH": "1"})
    import HL_Live_Copy_Service_Core as c

    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l.json"))
    g._asset_snapshot_loaded = True
    g._meta_fetched = g._core_meta_fetched = True
    g._builder_meta_fetched["xyz"] = True
    g._meta_cache = {
        "KFLOKI": {"canonical_coin": "kFLOKI", "szDecimals": 0, "symbol_source": "core_meta", "perp_dex": ""},
        "XYZ:SPCX": {"canonical_coin": "XYZ:SPCX", "sdk_coin": "xyz:SPCX", "szDecimals": 2, "symbol_source": "builder_meta",
                     "perp_dex": "xyz", "perp_dexs": ["", "xyz"]},
    }
    calls = []

    class Fake:
        def update_leverage(self, lev, name, is_cross=True):
            calls.append(name)
            return {"status": "ok"}

    g._get_exchange_client = lambda *a, **k: Fake()
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    for coin in ("KFLOKI", "kFLOKI", "XYZ:SPCX", "xyz:SPCX"):
        g.schedule_margin_mode_setup(coin)
        g.wait_margin_mode_setup(5.0)
    check("R1_RESOLVABLE_COINS_GET_MARGIN_MODE_SET", sorted(calls) == sorted(["kFLOKI", "xyz:SPCX"]), str(calls))

    del calls[:]
    for _ in range(6):  # a new fill per cycle re-queues a coin whose setup never succeeded
        g.schedule_margin_mode_setup("XYZ:BOT")
        g.wait_margin_mode_setup(5.0)
    rows = []
    if Path(c.ERRORS_CSV).exists():
        with open(c.ERRORS_CSV, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("context", "").startswith("margin_mode")]
    check("R2_UNRESOLVED_COIN_NO_EXCHANGE_CALL", calls == [], str(calls))
    check("R3_UNRESOLVED_COIN_ONE_ERROR_ROW_NOT_ONE_PER_CYCLE", len(rows) == 1, "rows=%d" % len(rows))
    check("R4_NO_VALUEERROR_AND_NAMED_REASON", bool(rows) and rows[0].get("error_type") != "ValueError"
          and "XYZ:BOT" in rows[0].get("message", ""), str(rows[:1]))
    # A symbol-resolution failure is not a margin failure: it names its own cause, and MARGIN_MODE_UNSET is left
    # for the case where the code actually reached update_leverage on a resolved coin.
    check("R4B_UNRESOLVED_IS_NOT_LABELLED_MARGIN_MODE_UNSET",
          bool(rows) and "MARGIN_MODE_UNSET" not in rows[0].get("message", "")
          and "SYMBOL_CACHE_MISS" in rows[0].get("message", ""), str(rows[:1]))
    check("R5_UNRESOLVED_COIN_STAYS_UNSET", "XYZ:BOT" not in g.__dict__.get("_mm_seen", set()))
    # The two causes must be distinguishable: a plain perp the cache cannot resolve names SYMBOL_NOT_LISTED, and a
    # genuine margin failure (code DID reach update_leverage) keeps MARGIN_MODE_UNSET as its block status.
    g.schedule_margin_mode_setup("NOPE")
    g.wait_margin_mode_setup(5.0)
    r7 = []
    if Path(c.ERRORS_CSV).exists():
        with open(c.ERRORS_CSV, newline="", encoding="utf-8") as fh:
            r7 = [r for r in csv.DictReader(fh) if r.get("context", "").startswith("margin_mode")]
    check("R7_UNRESOLVED_PLAIN_PERP_NAMED_SYMBOL_NOT_LISTED",
          len(r7) == 2 and "NOPE" in r7[-1].get("message", "")
          and "SYMBOL_NOT_LISTED" in r7[-1].get("message", "")
          and "MARGIN_MODE_UNSET" not in r7[-1].get("message", ""), str(r7[-1:]))

    class Refuse:
        def update_leverage(self, lev, name, is_cross=True):
            return {"status": "err", "response": "margin mode refused"}
    import argparse as _ap
    _intent = _ap.Namespace(fill=_ap.Namespace(coin="kFLOKI"), intent_id="I-R8")
    g.__dict__.setdefault("_margin_mode_done", set()).discard("kFLOKI")  # R1 already set it; force the real call path
    blk = g._ensure_margin_mode(Refuse(), "kFLOKI", _intent, "ENTRY", {})
    check("R8_GENUINE_MARGIN_FAILURE_UNCHANGED",
          blk is not None and blk[0] is False and blk[1] == "MARGIN_MODE_UNSET"
          and blk[2].get("terminal_state") == "MARGIN_MODE_UNSET", str(blk and blk[:2]))
    check("R9_UNRESOLVED_NEVER_EMITS_THE_MARGIN_BLOCK",
          all("MARGIN_MODE_UNSET" not in r.get("message", "") for r in r7), str(r7))

    # R10-R13 (the false-diagnosis defect): the label follows the resolver ACTUAL cause. Metadata never fetched is
    # META_UNAVAILABLE, a snapshot-only/stale-cache row is the cache label, and only a coin the fetched metadata says
    # is absent may be called SYMBOL_NOT_LISTED.
    def margin_rows():
        if not Path(c.ERRORS_CSV).exists():
            return []
        with open(c.ERRORS_CSV, newline="", encoding="utf-8") as fh:
            return [r for r in csv.DictReader(fh) if r.get("context", "").startswith("margin_mode")]

    g2 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l2.json"))
    g2._asset_snapshot_loaded = True
    g2._meta_fetched = g2._core_meta_fetched = False
    g2._builder_meta_fetched["xyz"] = True
    g2._meta_cache = {}
    g2._get_exchange_client = lambda *a, **k: Fake()
    before = len(margin_rows())
    g2.schedule_margin_mode_setup("GHOST")
    g2.wait_margin_mode_setup(5.0)
    r10 = margin_rows()[before:]
    check("R10_NO_METADATA_IS_NAMED_META_UNAVAILABLE_NOT_NOT_LISTED",
          len(r10) == 1 and "META_UNAVAILABLE" in r10[0].get("message", "")
          and "SYMBOL_NOT_LISTED" not in r10[0].get("message", ""), str(r10[:1]))

    # a row that came only from the disk snapshot: an OK-looking cache hit with no authoritative meta behind it
    g2._meta_cache = {"SNAPX": {"canonical_coin": "SNAPX", "szDecimals": 2, "symbol_source": "core_meta",
                              "_snapshot_only": True}}
    before = len(margin_rows())
    g2.schedule_margin_mode_setup("SNAPX")
    g2.wait_margin_mode_setup(5.0)
    r11 = margin_rows()[before:]
    check("R11_SNAPSHOT_ONLY_ABSENT_NAMED_ITS_OWN_CAUSE_NOT_NOT_LISTED",
          len(r11) == 1 and r11[0].get("message", "").startswith("SYMBOL_SNAPSHOT_ONLY_NO_AUTHORITATIVE_META:")
          and "SYMBOL_NOT_LISTED" not in r11[0].get("message", ""), str(r11[:1]))
    g2._meta_cache = {}

    # keep-case: a stale cache still says SYMBOL_CACHE_MISS (this one was already true before the fix)
    before = len(margin_rows())
    g2.schedule_margin_mode_setup("XYZ:QQQ")
    g2.wait_margin_mode_setup(5.0)
    r14 = margin_rows()[before:]
    check("R14_STALE_CACHE_STILL_NAMED_SYMBOL_CACHE_MISS",
          len(r14) == 1 and "SYMBOL_CACHE_MISS" in r14[0].get("message", "")
          and "SYMBOL_NOT_LISTED" not in r14[0].get("message", ""), str(r14[:1]))

    g2._meta_fetched = g2._core_meta_fetched = True
    before = len(margin_rows())
    g2.schedule_margin_mode_setup("ZZZQ")
    g2.wait_margin_mode_setup(5.0)
    r12 = margin_rows()[before:]
    check("R12_GENUINELY_ABSENT_COIN_STILL_NAMED_SYMBOL_NOT_LISTED",
          len(r12) == 1 and "SYMBOL_NOT_LISTED" in r12[0].get("message", ""), str(r12[:1]))

    g3 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l3.json"))
    _fill = _ap.Namespace(leader_fill_id="LF-R13", leader_wallet="0x" + "d" * 40, coin="GHOST", price=100.0,
                          timestamp_ms=c.utc_now_ms())
    _intent13 = _ap.Namespace(intent_id="I-R13", fill=_fill)

    def skip_for(resolved):
        g3._resolve_coin = lambda coin, allow_snapshot=False: dict(resolved)
        return g3._missed_entry_rest_or_diff(_intent13, "MARGIN_MODE_UNSET", {}).get("outcome")

    s13a = skip_for({"ok": False, "status": "META_UNAVAILABLE"})
    s13b = skip_for({"ok": False, "status": "SYMBOL_CACHE_MISS_NEEDS_REFRESH", "snapshot_only": True})
    s13c = skip_for({"ok": False, "status": "SYMBOL_CACHE_MISS_NEEDS_REFRESH"})
    s13d = skip_for({"ok": False, "status": "SYMBOL_UNRESOLVED"})
    check("R13_REFUSAL_NO_METADATA_IS_NOT_NOT_LISTED", s13a == "MISSED_ENTRY_SKIP_META_UNAVAILABLE", s13a)
    check("R13_REFUSAL_SNAPSHOT_ONLY_IS_NOT_NOT_LISTED", s13b == "MISSED_ENTRY_SKIP_SYMBOL_SNAPSHOT_ONLY", s13b)
    check("R13_REFUSAL_STALE_CACHE_IS_NOT_NOT_LISTED", s13c == "MISSED_ENTRY_SKIP_SYMBOL_CACHE_MISS", s13c)
    check("R13_REFUSAL_GENUINELY_ABSENT_COIN_STILL_NAMED_NOT_LISTED",
          s13d == "MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED", s13d)

    msg = _try(g, "XYZ:BOT")
    check("R6_NEUTRAL_HELPER_MESSAGE", bool(msg) and "for cancel" not in msg, msg)

    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(1 for _n, ok in RESULTS if not ok)))
    sys.exit(1 if any(not ok for _n, ok in RESULTS) else 0)


main()
