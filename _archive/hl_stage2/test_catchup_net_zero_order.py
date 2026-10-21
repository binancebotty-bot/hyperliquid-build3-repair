"""Ordering contract for catchup_net_zero: id DURABLE (dedupe_ids.jsonl) before its row.

C crash window: raise between flush and row write -> id in JSONL, no row; restart re-poll adds ZERO rows for it.
D ordering: monotonic counter at both sites -> flush_seq < row_seq per zero-net id.
Plain python (no pytest); failures are assertions, so a revert reads RED.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "a" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="catchup_zero_order_"))
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
    t_stop = now - 3600000
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

    want_ids = {c.LeaderFillIngestor.parse_fill(LEADER, raw, "POLL").leader_fill_id for raw in WINDOW}

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.async_dispatch = True
    rewind(core)
    orig_trace = core._fill_trace
    fired = {"n": 0}

    def crash_trace(kind, fill=None, extra=None):
        if kind == "catchup_net_zero" and fill is not None:
            fired["n"] += 1
            raise RuntimeError("injected crash between flush and row write")
        return orig_trace(kind, fill, extra)

    core._fill_trace = crash_trace
    core.run_cycle(use_source_csv=False, poll_live=True)
    core._fill_trace = orig_trace
    time.sleep(0.2)
    rows_c = zero_rows()
    ids_c = jsonl_ids()
    check("C1_CRASH_INJECTED", fired["n"] >= 1, "row write must be reached (fired=%d)" % fired["n"])
    check("C2_ID_DURABLE_BEFORE_ROW", want_ids.issubset(set(ids_c)), "jsonl=%s want=%s" % (ids_c, sorted(want_ids)))
    check("C3_ROW_LOST_IS_ALLOWED", not [r for r in rows_c if r in want_ids], "rows=%s" % (rows_c,))
    core.stop()

    core2 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core2.async_dispatch = True
    rewind(core2)
    before = len(rows_c)
    core2.run_cycle(use_source_csv=False, poll_live=True)
    time.sleep(0.2)
    new_rows = [r for r in zero_rows()[before:] if r in want_ids]
    check("C4_ZERO_NEW_ROWS_AFTER_RESTART", not new_rows, "new=%s" % (new_rows,))
    core2.stop()

    core3 = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core3.dedupe.processed.clear()  # the C phase persisted these ids; D needs them seen again
    core3.async_dispatch = True
    rewind(core3)
    seq = {"n": 0}
    durable_seq, row_seq = {}, {}
    orig_flush = core3.dedupe.flush_jsonl

    def flush_probe():
        seq["n"] += 1
        s = seq["n"]
        pending = list(core3.dedupe._jsonl_new_leader)
        orig_flush()
        for fid in pending:
            durable_seq.setdefault(str(fid), s)

    def row_probe(kind, fill=None, extra=None):
        if kind == "catchup_net_zero" and fill is not None:
            seq["n"] += 1
            row_seq[str(fill.leader_fill_id)] = seq["n"]
        return orig_trace(kind, fill, extra)

    core3.dedupe.flush_jsonl = flush_probe
    core3._fill_trace = row_probe
    core3.run_cycle(use_source_csv=False, poll_live=True)
    time.sleep(0.2)
    bad = []
    for fid in sorted(want_ids):
        fs, rs = durable_seq.get(fid), row_seq.get(fid)
        if fs is None or rs is None or not (fs < rs):
            bad.append("%s flush_seq=%s row_seq=%s" % (fid[:12], fs, rs))
    check("D_FLUSH_BEFORE_ROW_PER_ID", not bad, "; ".join(bad))
    core3.stop()

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
