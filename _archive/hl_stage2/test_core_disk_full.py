#!/usr/bin/env python3
"""J1 - disk-full robustness (ENOSPC / PermissionError / short write).

Goal: prove the engine neither loses an order record silently nor crashes when an audit write fails.

Every case drives a REAL engine boundary - `LiveCopyCore._run_plan` (the worker that calls
_process_leader_fill), `SenderGateway.send_if_allowed`, `append_csv`, `atomic_write_json`,
`build_live_integrity_status`, `run_cycle` - with a fake exchange that COUNTS calls. The write failure is
injected at `pathlib.Path.open` (a real failing write, exactly what a full disk does) and at `Core.os.replace`
for the JSON writes. Offline: no engine, no network, no orders, no key.

An A/B/C/D/E FAIL is a FINDING about the engine (reported, never weakened, with a proposed patch diff in the
same directory: J1_PATCH_*.diff). Run from _archive/hl_stage2:

    HL_LIVE_ENV_FILE=/nonexistent python -u test_core_disk_full.py

Notes on two deliberate harness choices (these were once a false finding):

  * The failure of the intent append is judged at `_run_plan` (the production worker boundary), NOT at
    `_process_leader_fill` itself: in production every call to _process_leader_fill is wrapped by
    `_run_plan._one` (log_error "ws_hot_send") or by run_cycle's outer try. Testing the bare method reports a
    containment gap that the caller already closes.
  * A real full disk fails EVERY write, including the error log. Each single-file case is paired with a
    whole-disk case, because a containment path that logs through the same broken disk is not a containment
    path.
"""
from __future__ import annotations

import errno
import json
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


class _Half:
    """A file whose write() stores only the first half of the text (a short write that does not raise)."""

    def __init__(self, fh):
        self._fh = fh

    def write(self, s):
        half = s[: max(0, len(s) // 2)]
        self._fh.write(half)
        return len(half)

    def __enter__(self):
        self._fh.__enter__()
        return self

    def __exit__(self, *a):
        return self._fh.__exit__(*a)

    def __getattr__(self, k):
        return getattr(self._fh, k)


class Inject:
    """Fail the WRITE of the named file(s) - Path.open in a write mode raises (or short-writes), and, for JSON
    targets, Core.os.replace raises too. names=None fails EVERY write (a whole full disk). Installed as plain
    functions because a bound method assigned to a class attribute is not re-bound by the descriptor protocol
    (Path.open would then receive the mode string as its first argument - an instrument defect, not a finding)."""

    def __init__(self, c, names=None, mode="enospc", skip=0, also_replace=False):
        self.c, self.names, self.mode, self.skip = c, names, mode, skip
        self.also_replace = also_replace or names is None
        self.hits = 0
        self._orig_open = pathlib.Path.open
        self._orig_write_text = pathlib.Path.write_text
        self._orig_replace = os.replace

    def _exc(self):
        return PermissionError("denied") if self.mode == "perm" else OSError(errno.ENOSPC, "No space left on device")

    def _matches(self, name):
        return (self.names is None or name in self.names
                or any(name.startswith(n + ".") for n in self.names))   # atomic_write_json's *.tmp temp file

    def _open(self, self_path, *a, **k):
        mode = a[0] if a else k.get("mode", "r")
        if self._matches(self_path.name) and any(ch in str(mode) for ch in "awx+"):
            if self.hits >= self.skip:
                self.hits += 1
                if self.mode == "short":
                    return _Half(self._orig_open(self_path, *a, **k))
                raise self._exc()
            self.hits += 1
        return self._orig_open(self_path, *a, **k)

    def _replace(self, src, dst, *a, **k):
        if self._matches(Path(str(dst)).name) and self.hits >= self.skip:
            self.hits += 1
            raise self._exc()
        return self._orig_replace(src, dst, *a, **k)

    def __enter__(self):
        inject = self
        pathlib.Path.open = lambda self_path, *a, **k: inject._open(self_path, *a, **k)
        pathlib.Path.write_text = lambda self_path, data, *a, **k: inject._write_text(self_path, data, *a, **k)
        if self.also_replace:
            self.c.os.replace = lambda src, dst, *a, **k: inject._replace(src, dst, *a, **k)
        return self

    def _write_text(self, self_path, data, *a, **k):
        # Path.write_text is how atomic_write_json writes its temp file; it must be injected too or the JSON
        # cases would compare against an uninjected write.
        if self._matches(self_path.name) and self.hits >= self.skip:
            self.hits += 1
            if self.mode == "short":
                half = str(data)[: max(0, len(str(data)) // 2)]
                with self._orig_open(self_path, "w", encoding="utf-8") as fh:
                    fh.write(half)
                return len(half)          # a real short write reports the count it actually stored
            raise self._exc()
        return self._orig_write_text(self_path, data, *a, **k)

    def __exit__(self, *exc):
        pathlib.Path.open = self._orig_open
        pathlib.Path.write_text = self._orig_write_text
        self.c.os.replace = self._orig_replace
        return False


class FakeExchange:
    """Counts the physical order calls; never signs, never sends."""

    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({"coin": coin, "is_buy": is_buy, "size": size, "px": px, "reduce_only": reduce_only})
        if self.response is not None:
            return self.response
        return {"response": {"data": {"statuses": [{"filled": {"totalSz": str(size), "avgPx": str(px),
                                                               "oid": 900000 + len(self.calls)}}]}}}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="j1disk_"))
    os.environ.update({"HL_LIVE_DEFER_MAX_SEC": "-1", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_HL_PRIVATE_KEY": FAKE_KEY,
                       "HL_LIVE_HL_ACCOUNT_ADDRESS": FOLLOWER, "HL_LIVE_HOT_INNER": "1", "HL_LIVE_HOT_SEND_WORKERS": "1"})
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
    fake = FakeExchange()
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

    def errors():
        return c.read_csv_rows(c.ERRORS_CSV) if c.ERRORS_CSV.exists() else []

    def error_contexts():
        return [str(r.get("context") or "") for r in errors()]

    def intent_rows():
        return c.read_csv_rows(c.ORDER_INTENTS_CSV) if c.ORDER_INTENTS_CSV.exists() else []

    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig", errors="replace")

    # ================= (a) order_intents append fails BEFORE any send =================
    # Judged at _run_plan, the production worker boundary that wraps _process_leader_fill.
    it_a = intent(fid="a")
    core.intents_by_id[it_a.intent_id] = it_a
    fake_a = FakeExchange()
    s._get_exchange_client = lambda *_a, **_k: fake_a
    raised_a = None
    with Inject(c, {"order_intents.csv"}):
        try:
            core._run_plan(0, [it_a.fill])
        except BaseException as exc:  # noqa: BLE001 - the point of the check
            raised_a = exc
    check("A1_NO_ORDER_SENT_WHEN_INTENT_ROW_CANNOT_BE_WRITTEN", fake_a.calls == [], "exchange calls=%d" % len(fake_a.calls))
    check("A2_FAILURE_CONTAINED_AT_THE_WORKER_BOUNDARY", raised_a is None,
          "the intent-append failure escaped _run_plan: %r" % (raised_a,))
    check("A3_LOUD_RECORD_OF_THE_FAILURE", "ws_hot_send" in error_contexts(),
          "errors.csv contexts=%s" % error_contexts()[-3:])
    it_a2 = intent(fid="a2")
    core.intents_by_id[it_a2.intent_id] = it_a2
    before_rows = len(intent_rows())
    raised_a4 = None
    try:
        core._run_plan(0, [it_a2.fill])
    except BaseException as exc:  # noqa: BLE001
        raised_a4 = exc
    check("A4_CYCLE_KEEPS_WORKING_AFTER_THE_FAILURE",
          raised_a4 is None and len(intent_rows()) > before_rows,
          "next fill raised %r; intent rows %d -> %d" % (raised_a4, before_rows, len(intent_rows())))
    # A real full disk also breaks the error log: the containment path must still contain.
    it_a5 = intent(fid="a5")
    core.intents_by_id[it_a5.intent_id] = it_a5
    raised_a5 = None
    with Inject(c, None):          # every write fails, including errors.csv
        try:
            core._run_plan(0, [it_a5.fill])
        except BaseException as exc:  # noqa: BLE001
            raised_a5 = exc
    check("A5_WHOLE_DISK_FULL_CANNOT_KILL_THE_WORKER", raised_a5 is None,
          "with every audit write failing, _run_plan raised %r (the error path logs through the same disk)" % (raised_a5,))

    # ================= (b) send_attempts writes fail =================
    fake_b = FakeExchange()
    s._get_exchange_client = lambda *_a, **_k: fake_b
    raised_b, status_b = None, None
    with Inject(c, {"send_attempts.csv"}):
        try:
            _sent, status_b = s.send_if_allowed(intent(fid="b"))
        except BaseException as exc:  # noqa: BLE001
            raised_b = exc
    check("B1_NO_EXCHANGE_CALL_WHEN_PENDING_ROW_CANNOT_BE_WRITTEN", fake_b.calls == [], "calls=%d" % len(fake_b.calls))
    check("B2_FAIL_CLOSED_STATUS_RETURNED", raised_b is None and status_b in
          {"SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED", "AUDIT_WRITE_FAILED"},
          "raised=%r status=%r" % (raised_b, status_b))
    # Extend to the FINAL status row: the pending row lands, the final row cannot be written.
    c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
    fake_b3 = FakeExchange()
    s._get_exchange_client = lambda *_a, **_k: fake_b3
    it_b3 = intent(fid="b3")
    raised_b3, status_b3 = None, None
    with Inject(c, {"send_attempts.csv"}, skip=1):   # 1st append ok (pending), 2nd fails (final row)
        try:
            _sent_b3, status_b3 = s.send_if_allowed(it_b3)
        except BaseException as exc:  # noqa: BLE001
            raised_b3 = exc
    rows_b3 = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == it_b3.intent_id]
    expect_cloid = c.generate_cloid(it_b3.intent_id)
    pending_ok = len(rows_b3) == 1 and rows_b3[0].get("status") == "pending_send" and rows_b3[0].get("cloid") == expect_cloid
    print("OBSERVE::B3 exchange_calls=%d raised=%r status=%r rows_for_intent=%d" % (len(fake_b3.calls), raised_b3, status_b3, len(rows_b3)))
    check("B3_FINAL_ROW_WRITE_FAILURE_STILL_SENDS_THE_ORDER_ONCE_AND_KEEPS_IT_NAMED",
          len(fake_b3.calls) == 1 and pending_ok,
          "sent=%d pending_row_with_cloid=%s" % (len(fake_b3.calls), pending_ok))
    check("B3B_THE_PRODUCTION_SEND_CALLER_CONTAINS_THE_FINAL_ROW_FAILURE",
          bool(re.search(r"try:\s*\n\s*sent, send_status = self\.sender\.send_if_allowed\(", src)),
          "no handler around the per-fill send_if_allowed call")
    # whole disk
    it_b4 = intent(fid="b4")
    core.intents_by_id[it_b4.intent_id] = it_b4
    fake_b4 = FakeExchange()
    s._get_exchange_client = lambda *_a, **_k: fake_b4
    raised_b4 = None
    with Inject(c, None):
        try:
            core._run_plan(0, [it_b4.fill])
        except BaseException as exc:  # noqa: BLE001
            raised_b4 = exc
    print("OBSERVE::B4 exchange_calls=%d raised=%r" % (len(fake_b4.calls), raised_b4))
    check("B4_WHOLE_DISK_FULL_DOES_NOT_ESCAPE_THE_WORKER", raised_b4 is None,
          "with every audit write failing, _run_plan raised %r" % (raised_b4,))

    # ================= (c) reconciliation append fails AFTER an order was sent =================
    reject = {"response": {"data": {"statuses": [{"error": "IOC would immediately match"}]}}}
    fake_c = FakeExchange(response=reject)
    s._get_exchange_client = lambda *_a, **_k: fake_c
    it_c = intent(fid="c")
    raised_c = None
    with Inject(c, {"reconciliation.csv"}):
        try:
            s.send_if_allowed(it_c)
        except BaseException as exc:  # noqa: BLE001
            raised_c = exc
    print("OBSERVE::C2 send_if_allowed raised after the lost reconciliation row: %r" % (raised_c,))
    check("C1_THE_ORDER_WAS_REALLY_ATTEMPTED_BEFORE_THE_FAILURE", len(fake_c.calls) == 1, "calls=%d" % len(fake_c.calls))
    check("C2A_THE_PRODUCTION_SEND_CALLER_CONTAINS_THE_LOST_RECONCILIATION_ROW",
          bool(re.search(r"try:\s*\n\s*sent, send_status = self\.sender\.send_if_allowed\(", src)),
          "no handler around the per-fill send_if_allowed call")
    # A retry must reuse the same deterministic cloid (the exchange then rejects the duplicate) and the order
    # must already be engine-owned, so no second physical order is placed for the same intent.
    cloids_c, oids_c = s._engine_owned_cloids_and_oids()
    expect_cloid_c = c.generate_cloid(it_c.intent_id)
    check("C3_THE_SENT_ORDER_IS_ENGINE_OWNED_AND_ITS_CLOID_IS_DETERMINISTIC",
          expect_cloid_c in cloids_c and c.generate_cloid(it_c.intent_id) == expect_cloid_c,
          "cloid=%s owned=%s" % (expect_cloid_c, expect_cloid_c in cloids_c))
    st = c.build_live_integrity_status()
    counts = st.get("counts") or {}
    lost = {k: v for k, v in counts.items() if "audit_write" in k and v}
    print("OBSERVE::C4 integrity status=%s audit_write counts=%s" % (st.get("status"), lost))
    check("C4_THE_LOST_RECONCILIATION_ROW_IS_COUNTED_IN_THE_INTEGRITY_STATUS", bool(lost),
          "no audit-write-failure count in the integrity status: counts=%s" % sorted(counts))

    # ================= (d) state / runtime json write fails =================
    raised_d = None
    with Inject(c, {"live_integrity_status.json"}, also_replace=True):
        try:
            c.write_live_integrity_status()
        except BaseException as exc:  # noqa: BLE001
            raised_d = exc
    check("D1_JSON_WRITE_FAILURE_IS_RECORDED", len(errors()) > 0, "errors.csv rows=%d" % len(errors()))
    later = None
    try:
        later = c.write_live_integrity_status()
    except BaseException as exc:  # noqa: BLE001
        later = exc
    check("D3_NEXT_CALL_STILL_RUNS_AFTER_A_JSON_WRITE_FAILURE",
          isinstance(later, dict) and str(later.get("status")), "next call -> %r" % (type(later).__name__,))
    check("D2_THE_PER_CYCLE_CALLER_CONTAINS_THE_INTEGRITY_WRITE_FAILURE",
          bool(re.search(r"try:\s*\n\s*write_live_integrity_status\(", src)),
          "no guard around write_live_integrity_status in its per-cycle caller")
    saved_write = core.state_writer.write
    core.state_writer.write = lambda *a, **k: (_ for _ in ()).throw(OSError(errno.ENOSPC, "No space left on device"))
    raised_d4 = None
    try:
        core.run_cycle(use_source_csv=False)
    except BaseException as exc:  # noqa: BLE001
        raised_d4 = exc
    finally:
        core.state_writer.write = saved_write
    check("D4_STATE_WRITE_CANNOT_KILL_THE_CYCLE", raised_d4 is None,
          "run_cycle raised %r when the state write failed (the main loop does not catch it either)" % (raised_d4,))
    # D5: the run_cycle call inside the engine loop must sit under a handler that catches a failing cycle
    # (a bare try/.../finally with no except lets one bad cycle end the process).
    _i = src.rindex("summary = core.run_cycle(")
    loop_guarded = bool(re.search(r"except\b", src[_i:_i + 500]))   # a handler after the call protects the loop
    check("D5_THE_ENGINE_LOOP_CANNOT_EXIT_ON_A_RUN_CYCLE_FAILURE", loop_guarded,
          "main()'s 'summary = core.run_cycle(...)' is not under an except: one failing cycle ends the process")

    # ================= (e) short write (a write that stores fewer bytes without raising) =================
    p_csv = tmp / "short.csv"
    c.append_csv(p_csv, c.ORDER_INTENT_FIELDS, {"intent_id": "seed", "coin": "BTC"})
    with Inject(c, {"short.csv"}, mode="short"):
        short_raised = None
        try:
            c.append_csv(p_csv, c.ORDER_INTENT_FIELDS, {"intent_id": "tail", "coin": "SOL", "notes": "MARKER-NOTES-" + "x" * 40})
        except BaseException as exc:  # noqa: BLE001
            short_raised = exc
    rows = list(c.csv.DictReader(p_csv.open(newline="", encoding="utf-8-sig")))
    tail = [r for r in rows if r.get("intent_id") == "tail"]
    check("E1_SHORT_CSV_WRITE_IS_NOT_SILENTLY_PUBLISHED",
          short_raised is not None or (tail and tail[0].get("notes") == "MARKER-NOTES-" + "x" * 40),
          "raised=%r tail_row=%s" % (short_raised, (tail[0] if tail else None)))
    p_js = tmp / "short.json"
    payload = {"k": "v" * 64, "n": 1}
    short_json_raised = None
    with Inject(c, {"short.json"}, mode="short"):
        try:
            c.atomic_write_json(p_js, payload)
        except BaseException as exc:  # noqa: BLE001
            short_json_raised = exc
    parsed = None
    try:
        parsed = json.loads(p_js.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        parsed = None
    check("E2_SHORT_JSON_WRITE_IS_NOT_SILENTLY_PUBLISHED", short_json_raised is not None or parsed == payload,
          "raised=%r published json parses to %r (want a raise, or the full payload)" % (short_json_raised, parsed))
    p_js2 = tmp / "orphan.json"
    with Inject(c, {"orphan.json"}, also_replace=True, skip=1):   # tmp write ok, the replace fails
        try:
            c.atomic_write_json(p_js2, {"k": 1})
        except BaseException:  # noqa: BLE001
            pass
    orphans = sorted(q.name for q in tmp.glob("orphan.json.*.tmp"))
    check("E3_FAILED_JSON_WRITE_LEAVES_NO_ORPHAN_TMP", orphans == [],
          "orphan temp files left behind: %s" % (orphans,))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    for n in failed:
        print("FINDING::%s" % n)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
