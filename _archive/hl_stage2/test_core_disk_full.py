#!/usr/bin/env python3
"""J1 - disk-full robustness (ENOSPC / PermissionError / short write). Proves whether the engine loses orders
silently or crashes when an audit write fails.

Every case drives the REAL code path (the real SenderGateway.send_if_allowed / LiveCopyCore._process_leader_fill /
append_csv / atomic_write_json / build_live_integrity_status) with a fake exchange that COUNTS calls, and injects a
write failure at pathlib.Path.open (a real failing write, exactly what a full disk does) and Core.os.replace for the
JSON writes. Offline: no engine, no network, no orders.

A FAIL is a FINDING about the engine (reported, never weakened). Run from _archive/hl_stage2:
  HL_LIVE_ENV_FILE=/nonexistent python -u test_core_disk_full.py
"""
from __future__ import annotations

import errno
import os
import pathlib
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
LEADER = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
FAKE_KEY = "0x" + "1" * 64


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


class Inject:
    """A failing write for one file NAME: Path.open raises ENOSPC (or the given errno) and, for JSON targets,
    Core.os.replace raises too - exactly what a full disk / a transient PermissionError looks like to append_csv
    and atomic_write_json. Only the named file is affected.

    NOTE (instrument, cost me a run): the patch MUST be installed as a plain function. A bound method assigned to a
    class attribute is not bound by the descriptor protocol, so Path.open got the MODE string as its first argument
    and every write died with AttributeError('str' object has no attribute 'name') - a pure instrument defect that
    would have been reported as five engine findings."""

    def __init__(self, c, name, exc=None, skip_first=0, also_replace=False):
        self.c, self.name = c, name
        self.exc = exc or OSError(errno.ENOSPC, "No space left on device")
        self.skip_first, self.also_replace = skip_first, also_replace
        self.hits = 0
        self._orig_open = pathlib.Path.open
        self._orig_replace = os.replace

    def _open(self, self_path, *a, **k):
        mode = a[0] if a else k.get("mode", "r")
        if self_path.name == self.name and any(ch in str(mode) for ch in "awx+"):
            if self.hits >= self.skip_first:
                self.hits += 1
                raise self.exc
            self.hits += 1
        return self._orig_open(self_path, *a, **k)

    def _replace(self, src, dst, *a, **k):
        if Path(str(dst)).name == self.name and self.hits >= self.skip_first:
            self.hits += 1
            raise self.exc
        return self._orig_replace(src, dst, *a, **k)

    def __enter__(self):
        inject = self

        def _open_path(self_path, *a, **k):      # a real function -> Path.open binds it to the Path instance
            return inject._open(self_path, *a, **k)

        def _os_replace(src, dst, *a, **k):
            return inject._replace(src, dst, *a, **k)

        pathlib.Path.open = _open_path
        if self.also_replace:
            self.c.os.replace = _os_replace
        return self

    def __exit__(self, *exc):
        pathlib.Path.open = self._orig_open
        self.c.os.replace = self._orig_replace
        return False


class FakeExchange:
    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({"coin": coin, "is_buy": is_buy, "size": size, "px": px, "reduce_only": reduce_only})
        if self.response is not None:
            return self.response
        return {"response": {"data": {"statuses": [{"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 900000 + len(self.calls)}}]}}}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="j1disk_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_HL_PRIVATE_KEY": FAKE_KEY,
                       "HL_LIVE_HL_ACCOUNT_ADDRESS": FOLLOWER})
    os.environ.pop("HL_LIVE_MOCK_SEND", None)          # the real send path, with a fake exchange
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    _acct, _exch = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object

    def write_cfg():
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "master_real_orders_enabled": True,
                                                 "global_controls": {"min_notional": 1},
                                                 "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed",
                                                                      "fixed_notional": 100}}})

    write_cfg()
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    s = core.sender
    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK",
                "raw_coin": "BTC"}
    s._resolve_coin = lambda coin: dict(resolved)
    s._get_exchange_client = lambda *_a, **_k: fake
    s._exchange_client_has_symbol = lambda *_a, **_k: True
    s._pre_exchange_asset_safety = lambda *_a, **_k: (True, {})
    s._pre_send_ownership_gate = lambda intent: (True, {})
    s.leader_reduced_since = lambda fill: False
    s._leader_state = lambda wallet, dex="": ({"assetPositions": [{"position": {"coin": "", "liquidationPx": "60"}}]}, "ok")
    s._follower_projected_liq_px = lambda intent, mark: (mark * 0.1, "test fact")
    s._ensure_margin_mode = lambda *a, **k: None

    def intent(lifecycle="ENTRY", side="BUY", size=1.0, reduce_only=False, fid="j1"):
        fill = c.LeaderFill(fid, LEADER, "BTC", side, 100.0, size, c.utc_now_ms(), "TEST")
        return c.Intent("int-" + fid, fill, side, size, size * 100.0, "ON", "fixed", "EXIT_ALLOWED", lifecycle,
                        "sleeve:%s:BTC" % LEADER, "", "LONG", 0.0, 0.0, reduce_only, reduce_only,
                        c.utc_now_ms(), "lifecycle=%s;" % lifecycle)

    # ============================ (a) order_intents append fails BEFORE any send ============================
    it_a = intent(fid="a")
    core.intents_by_id[it_a.intent_id] = it_a
    fake = FakeExchange()
    raised_a = None
    with Inject(c, "order_intents.csv"):
        try:
            core._process_leader_fill(it_a.fill)
        except BaseException as exc:  # noqa: BLE001 - the point of the check
            raised_a = exc
    check("A1_NO_ORDER_SENT_WHEN_INTENT_ROW_CANNOT_BE_WRITTEN", fake.calls == [], "exchange calls=%d" % len(fake.calls))
    check("A2_FAILURE_CONTAINED_IN_THE_FILL_UNIT", raised_a is None,
          "the intent-append failure raised %r out of _process_leader_fill (nothing contained it)" % (raised_a,))
    err_rows = c.read_csv_rows(c.ERRORS_CSV) if c.ERRORS_CSV.exists() else []
    check("A3_LOUD_RECORD_OF_THE_FAILURE", len(err_rows) > 0,
          "errors.csv rows=%d: no loud record was written" % len(err_rows))
    it_a2 = intent(fid="a2")
    raised_a4 = None
    try:
        core._process_leader_fill(it_a2.fill)
    except BaseException as exc:  # noqa: BLE001
        raised_a4 = exc
    check("A4_CYCLE_KEEPS_WORKING_AFTER_THE_FAILURE", raised_a4 is None,
          "the next fill raised %r" % (raised_a4,))

    # ============================ (b) send_attempts pending_send write fails ==============================
    fake2 = FakeExchange()
    s._get_exchange_client = lambda *_a, **_k: fake2
    raised_b, status_b = None, None
    with Inject(c, "send_attempts.csv"):
        try:
            _sent, status_b = s.send_if_allowed(intent(fid="b"))
        except BaseException as exc:  # noqa: BLE001
            raised_b = exc
    check("B1_NO_EXCHANGE_CALL_WHEN_PENDING_ROW_CANNOT_BE_WRITTEN", fake2.calls == [], "calls=%d" % len(fake2.calls))
    check("B2_FAIL_CLOSED_STATUS_RETURNED", raised_b is None and status_b in
          {"SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED", "AUDIT_WRITE_FAILED"},
          "raised=%r status=%r" % (raised_b, status_b))
    # extend to the FINAL status row: the pending row lands, the final row cannot be written.
    # The file must already exist WITH rows, else the very first write is the header creation and the skip counts it.
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    fake3 = FakeExchange()
    s._get_exchange_client = lambda *_a, **_k: fake3
    raised_b2, status_b2 = None, None
    with Inject(c, "send_attempts.csv", skip_first=1):   # 1st append ok (pending), 2nd fails (final row)
        try:
            _sent, status_b2 = s.send_if_allowed(intent(fid="b2"))
        except BaseException as exc:  # noqa: BLE001
            raised_b2 = exc
    print("OBSERVE::B3 exchange_calls=%d raised=%r status=%r" % (len(fake3.calls), raised_b2, status_b2))
    check("B3_FINAL_ROW_WRITE_FAILURE_SURVIVES_AND_IS_RECORDED",
          raised_b2 is None and len(fake3.calls) == 1,
          "sent=%d raised=%r status=%r" % (len(fake3.calls), raised_b2, status_b2))

    # ============================ (c) reconciliation append fails AFTER an order was sent ==================
    reject = {"response": {"data": {"statuses": [{"error": "IOC would immediately match"}]}}}
    fake4 = FakeExchange(response=reject)
    s._get_exchange_client = lambda *_a, **_k: fake4
    it_c = intent(fid="c")
    raised_c = None
    with Inject(c, "reconciliation.csv"):
        try:
            s.send_if_allowed(it_c)
        except BaseException as exc:  # noqa: BLE001
            raised_c = exc
    check("C1_THE_ORDER_WAS_REALLY_ATTEMPTED_BEFORE_THE_FAILURE", len(fake4.calls) == 1, "calls=%d" % len(fake4.calls))
    check("C2_NO_CRASH_ON_THE_LOST_RECONCILIATION_ROW", raised_c is None, "raised=%r" % (raised_c,))
    core.intents_by_id[it_c.intent_id] = it_c
    core.dedupe.processed.add(it_c.fill.leader_fill_id)
    core._process_leader_fill(it_c.fill)                      # the same leader fill replayed
    check("C3_NO_SECOND_ORDER_FOR_THE_SAME_INTENT_ON_RETRY", len(fake4.calls) == 1,
          "replay produced %d exchange calls" % len(fake4.calls))
    st = c.build_live_integrity_status()
    nz = {k: v for k, v in (st.get("counts") or {}).items() if v}
    print("OBSERVE::C4 integrity status=%s non-zero counts=%s" % (st.get("status"), nz))
    check("C4_LOST_RECONCILIATION_ROW_IS_NOT_SILENT",
          str(st.get("status")) != "GREEN",
          "integrity status=%s counts=%s" % (st.get("status"), nz))

    # ============================ (d) state / runtime json write fails ====================================
    raised_d = None
    with Inject(c, "live_integrity_status.json", also_replace=True):
        try:
            c.write_live_integrity_status()
        except BaseException as exc:  # noqa: BLE001
            raised_d = exc
    err_rows = c.read_csv_rows(c.ERRORS_CSV) if c.ERRORS_CSV.exists() else []
    check("D1_JSON_WRITE_FAILURE_IS_RECORDED", len(err_rows) > 0, "errors.csv rows=%d" % len(err_rows))

    later = None
    try:
        later = c.write_live_integrity_status()
    except BaseException as exc:  # noqa: BLE001
        later = exc
    check("D3_NEXT_CYCLE_STILL_RUNS_AFTER_A_JSON_WRITE_FAILURE",
          isinstance(later, dict) and str(later.get("status")), "next call -> %r" % (later,))
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig", errors="replace")
    guarded = bool(re.search(r"try:\s*\n\s*self\.state_writer\.write\(summary", src))
    d2_guarded = bool(re.search(r"try:\s*\n\s*write_live_integrity_status\(", src))
    check("D2_THE_PER_CYCLE_CALLER_CONTAINS_THE_JSON_WRITE_FAILURE", d2_guarded,
          "no guard around write_live_integrity_status in its per-cycle caller")
    check("D4_STATE_WRITE_CANNOT_KILL_THE_CYCLE", guarded,
          "run_cycle's finally calls self.state_writer.write(summary, ...) without a guard")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    for n in failed:
        print("FINDING::%s failed against the engine" % n)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
