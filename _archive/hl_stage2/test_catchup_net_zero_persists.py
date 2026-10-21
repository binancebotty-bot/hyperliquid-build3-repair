#!/usr/bin/env python3
"""catchup_net_zero must be a TERMINAL, PERSISTED state: one row per leader fill id, ever.

Measured defect (build 2ed99c5): 120 catchup_net_zero rows from 25 distinct leader fill ids; one id written
80 times in 72 s. dedupe_ids.jsonl had 0 lines for those ids, so nothing stopped the next poll (or the next
process) from collapsing the same stale run again.

A: the same zero-net stale run polled TWICE in one process -> each id gets exactly one catchup_net_zero row
   and exactly one dedupe_ids.jsonl line (current head: two rows per id, zero lines).
B: restart simulation -> a fresh LiveCopyCore over the same state dir already knows the ids, so the identical
   poll window writes NO new row (current head: collapses it again).

Run (from _archive/hl_stage2): python test_catchup_net_zero_persists.py
RESULT:: markers, exit 0/1. Offline: no network, no orders, no keys."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from collections import Counter as _C
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "a" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="catchup_zero_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent",
        "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_WS_ENABLED": "0",
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0",
        "HL_LIVE_CATCHUP_COLLAPSE": "1", "HL_LIVE_CATCHUP_COLLAPSE_AGE_MS": "600000",
    })
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*_a, **_k):
        raise RuntimeError("offline test: no network")

    requests.post = offline
    requests.get = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": False,
        "global_controls": {},
        "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
    })

    now = c.utc_now_ms()
    t_stop = now - 3_600_000
    WINDOW = [
        {"coin": "KIOXIA", "px": "100.0", "sz": "10", "side": "B", "time": t_stop + 1000, "startPosition": "0",
         "dir": "Open Long", "closedPnl": "0.0", "hash": "0xzero1", "oid": 7001, "crossed": True, "fee": "0.01", "tid": 90001},
        {"coin": "KIOXIA", "px": "101.0", "sz": "10", "side": "A", "time": t_stop + 2000, "startPosition": "10",
         "dir": "Close Long", "closedPnl": "0.0", "hash": "0xzero2", "oid": 7002, "crossed": True, "fee": "0.01", "tid": 90002},
    ]

    class _Resp:
        status_code = 200

        def __init__(self, data):
            self._d = data

        def json(self):
            return self._d

    def fake_post(url, json=None, timeout=None, **_k):
        if (json or {}).get("type") == "userFillsByTime":
            return _Resp([f for f in WINDOW if json["startTime"] <= f["time"] <= json["endTime"]])
        raise RuntimeError("offline test: no network")

    c.requests.post = fake_post

    state_dir = Path(c.CORE_RUNTIME_STATE_FILE).parent
    trace_path = state_dir / "fill_trace.jsonl"
    jsonl_path = state_dir / c.DEDUPE_IDS_JSONL_NAME

    def zero_rows():
        if not trace_path.exists():
            return []
        out = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("k") == "catchup_net_zero":
                    out.append(str(rec.get("id")))
        return out

    def jsonl_ids():
        if not jsonl_path.exists():
            return []
        out = []
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("type") == "leader":
                    out.append(str(rec.get("id")))
        return out

    def rewind(core):
        core._last_leader_poll_ms = 0
        st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}) or {}
        st["last_leader_poll_cursor_ms"] = {LEADER: t_stop}
        c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
        core._leader_poll_cursors = {LEADER: t_stop}
        core._held_read_cursor = {}

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.async_dispatch = True
    rewind(core)

    sm1 = core.run_cycle(use_source_csv=False, poll_live=True)
    check("A1_CYCLE1_OK", sm1.ok and sm1.fatal_errors == 0, "poll=%s errs=%s" % (sm1.poll_loop_status, sm1.fatal_errors))
    rows1, ids1 = zero_rows(), jsonl_ids()
    check("A2_FIRST_POLL_ROW_PER_ID", len(rows1) == 2 and len(set(rows1)) == 2, "rows=%s" % (rows1,))
    check("A3_FIRST_POLL_PERSISTS_ID", len(ids1) == 2 and set(ids1) == set(rows1), "jsonl=%s rows=%s" % (ids1, rows1))

    time.sleep(0.05)
    rewind(core)
    sm2 = core.run_cycle(use_source_csv=False, poll_live=True)
    check("A4_CYCLE2_OK", sm2.ok and sm2.fatal_errors == 0, "poll=%s errs=%s" % (sm2.poll_loop_status, sm2.fatal_errors))
    rows2, ids2 = zero_rows(), jsonl_ids()
    cnt = _C(rows2)
    check("A5_ONE_ROW_PER_ID_AFTER_TWO_POLLS", len(rows2) == 2 and all(v == 1 for v in cnt.values()), "rows=%s" % (rows2,))
    jcnt = _C(ids2)
    check("A6_ONE_JSONL_LINE_PER_ID", len(ids2) == 2 and all(v == 1 for v in jcnt.values()), "jsonl=%s" % (ids2,))
    core.stop()

    core2 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core2.async_dispatch = True
    parsed = [c.LeaderFillIngestor.parse_fill(LEADER, raw, "POLL") for raw in WINDOW]
    want = {f.leader_fill_id for f in parsed if f}
    known = {i for i in want if i in core2.dedupe.processed}
    check("B1_RESTART_KNOWS_IDS", len(want) == 2 and known == want,
          "want=%s known=%s processed=%d" % (sorted(want), sorted(known), len(core2.dedupe.processed)))
    # the COLLAPSE predicate must see them (terminal); _already_handled intentionally does NOT, because the
    # persisted store also holds EXIT ids that must still be re-attempted across a restart.
    # degrade to the old predicate when the fix is reverted, so the revert reads as an ASSERTION, not a traceback
    _pred = getattr(core2, "_catchup_handled", core2._already_handled)
    check("B2_RESTART_CATCHUP_HANDLED", all(_pred(f) for f in parsed if f),
          "the collapse predicate must consult dedupe.processed, not only _idem_accepted")
    check("B2b_ALREADY_HANDLED_UNCHANGED_FOR_EXITS", not any(core2._already_handled(f) for f in parsed if f),
          "_already_handled must stay _idem_accepted-only so EXIT fills replay after a restart")

    before = len(zero_rows())
    rewind(core2)
    sm3 = core2.run_cycle(use_source_csv=False, poll_live=True)
    check("B3_CYCLE3_OK", sm3.ok and sm3.fatal_errors == 0, "poll=%s errs=%s" % (sm3.poll_loop_status, sm3.fatal_errors))
    new_rows = zero_rows()[before:]
    check("B4_NO_NEW_ROW_AFTER_RESTART", not new_rows, "new=%s" % (new_rows,))
    core2.stop()

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
