"""Fill-trace contention: RED then GREEN (soak finding 2026-11-23, addendum included)."""
from __future__ import annotations

import builtins
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("PAID_GUARD_ALLOW", "1")

import HL_Live_Copy_Service_Core as core  # noqa: E402

checks = []
_opens = {"count": 0}
_count_lock = threading.Lock()
_real_open = builtins.open


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    if not ok:
        print("FAIL %s: %s" % (name, detail))


def counting_open(file, *a, **k):
    try:
        if str(file).endswith("fill_trace.jsonl"):
            with _count_lock:
                _opens["count"] += 1
    except Exception:
        pass
    return _real_open(file, *a, **k)


def fresh(tmp):
    core.CORE_RUNTIME_STATE_FILE = Path(tmp) / "clean_core_runtime_state.json"
    return object.__new__(core.LiveCopyCore)


def close_handle(obj):
    try:
        obj._fill_trace_close()
    except Exception:
        pass
    core._FILL_TRACE_WRITE_HOOK = None


def make_fill(i):
    return SimpleNamespace(leader_fill_id="F%d" % i, leader_wallet="0xwallet0001", coin="BTC", timestamp_ms=1700000000000)


def t1_t2():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        obj = fresh(tmp)
        core.open = counting_open
        _opens["count"] = 0
        nt, nc = 30, 200

        def hammer(ti):
            for i in range(nc):
                obj._fill_trace("proc_start", make_fill(ti * nc + i), {"ti": ti, "n": i})

        ths = [threading.Thread(target=hammer, args=(ti,)) for ti in range(nt)]
        try:
            for t in ths: t.start()
            for t in ths: t.join(30)
            obj._fill_trace_flush(20)
        finally:
            core._FILL_TRACE_WRITE_HOOK = None
            if hasattr(core, "open"): del core.open
        total = nt * nc
        check("T1_OPEN_COUNT_SMALL", _opens["count"] <= 5, "opens=%d for %d lines" % (_opens["count"], total))
        path = tmp / "fill_trace.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        check("T2_ALL_LINES_PRESENT", len(lines) == total, "lines=%d expected=%d" % (len(lines), total))
        bad = 0
        for ln in lines:
            try:
                rec = json.loads(ln)
                if rec.get("k") != "proc_start" or "id" not in rec: bad += 1
            except Exception: bad += 1
        check("T2_LINES_VALID_JSON", bad == 0, "invalid=%d" % bad)
        close_handle(obj)


def t3():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        obj = fresh(tmp)
        oc, ok_ = core.TRACE_MAX_BYTES_FILL, getattr(core, "FILL_TRACE_ROTATE_CHECK_SEC", None)
        core.TRACE_MAX_BYTES_FILL = 20000
        core.FILL_TRACE_ROTATE_CHECK_SEC = 0.05
        try:
            for i in range(3000):
                obj._fill_trace("proc_end", make_fill(i))
                if i % 25 == 0: time.sleep(0.002)
            obj._fill_trace_flush(20)
            path = tmp / "fill_trace.jsonl"
            rot = [q.name for q in tmp.iterdir() if q.name.startswith("fill_trace.jsonl.")]
            size = path.stat().st_size if path.exists() else 0
            check("T3_ROTATION_HAPPENED", len(rot) >= 1, "rotated=%s" % rot)
            check("T3_LIVE_FILE_BOUNDED", size < 2 * core.TRACE_MAX_BYTES_FILL, "live size=%d" % size)
        finally:
            core.TRACE_MAX_BYTES_FILL = oc
            if ok_ is not None: core.FILL_TRACE_ROTATE_CHECK_SEC = ok_
            close_handle(obj)


def t4():
    with tempfile.TemporaryDirectory() as td:
        obj = fresh(Path(td) / "does_not_exist" / "deeper")
        good, detail = True, ""
        try:
            obj._fill_trace("proc_start", make_fill(1))
            obj._fill_trace_flush(5)
        except Exception as exc:
            good, detail = False, repr(exc)
        check("T4_NEVER_RAISES", good, detail)
        close_handle(obj)


def t5():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "fill_trace.jsonl"
        core.open = counting_open
        _opens["count"] = 0
        try:
            for i in range(50):
                core.rotate_trace_file(path, core.TRACE_MAX_BYTES_FILL)
                with core.open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": i, "k": "proc_start"}) + "\n")
        finally:
            if hasattr(core, "open"): del core.open
        check("T5_CONTROL_DETECTS_OLD_SHAPE", _opens["count"] == 50, "opens=%d expected=50" % _opens["count"])


def t6():
    with tempfile.TemporaryDirectory() as td:
        obj = fresh(Path(td))
        stop = threading.Event(); started = []
        def hammer():
            started.append(1)
            while not stop.is_set():
                obj._fill_trace("proc_start", make_fill(1))
        ths = [threading.Thread(target=hammer, daemon=True) for _ in range(8)]
        for t in ths: t.start()
        dl = time.time() + 5
        while len(started) < 8 and time.time() < dl: time.sleep(0.01)
        t0 = time.perf_counter()
        obj._fill_trace("proc_end", make_fill(999))
        el = time.perf_counter() - t0
        alive = sum(1 for t in ths if t.is_alive())
        stop.set()
        for t in ths: t.join(10)
        check("T6_MAIN_THREAD_NOT_STARVED", alive >= 1 and el < 5.0, "elapsed=%.3fs alive=%d" % (el, alive))
        close_handle(obj)


def t7():
    with tempfile.TemporaryDirectory() as td:
        obj = fresh(Path(td))
        core._FILL_TRACE_WRITE_HOOK = (lambda batch: time.sleep(0.5))
        nt, nc = 30, 200
        def hammer(ti):
            for i in range(nc):
                obj._fill_trace("proc_start", make_fill(ti * nc + i))
        ths = [threading.Thread(target=hammer, args=(ti,)) for ti in range(nt)]
        t0 = time.perf_counter()
        try:
            for t in ths: t.start()
            for t in ths: t.join(30)
            el = time.perf_counter() - t0
        finally:
            core._FILL_TRACE_WRITE_HOOK = None
        check("T7_CALLER_NEVER_BLOCKS", el < 2.0, "elapsed=%.3fs for %d calls with a 0.5s sink" % (el, nt*nc))
        close_handle(obj)


def t8():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        obj = fresh(tmp)
        nt, nc = 10, 100
        def hammer(ti):
            for i in range(nc):
                obj._fill_trace("proc_start", make_fill(ti * nc + i), {"ti": ti, "n": i})
        ths = [threading.Thread(target=hammer, args=(ti,)) for ti in range(nt)]
        for t in ths: t.start()
        for t in ths: t.join(30)
        obj._fill_trace_flush(20)
        path = tmp / "fill_trace.jsonl"
        recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        counts = {}
        for r in recs:
            key = (r.get("ti"), r.get("n"))
            counts[key] = counts.get(key, 0) + 1
        expected = {(ti, i) for ti in range(nt) for i in range(nc)}
        exactly = set(counts) == expected and all(v == 1 for v in counts.values())
        per = {}
        for r in recs: per.setdefault(r.get("ti"), []).append(r.get("n"))
        mono = all(seq == sorted(seq) for seq in per.values())
        check("T8_ALL_LINES_EXACTLY_ONCE", exactly, "recs=%d expected=%d missing=%d dup=%d" % (len(recs), len(expected), len(expected-set(counts)), sum(1 for v in counts.values() if v>1)))
        check("T8_PER_THREAD_ORDER", mono, "per-thread sequence not increasing")
        close_handle(obj)


def t9():
    with tempfile.TemporaryDirectory() as td:
        old_max = core.FILL_TRACE_QUEUE_MAX
        core.FILL_TRACE_QUEUE_MAX = 5
        release = threading.Event()
        core._FILL_TRACE_WRITE_HOOK = (lambda batch: release.wait(5))
        obj = fresh(Path(td))
        good, detail = False, ""
        try:
            st = obj._fill_trace_state()
            for i in range(60):
                obj._fill_trace("proc_start", make_fill(i))
            dropped = int(st.get("dropped") or 0)
            good = dropped > 0
            detail = "dropped=%d" % dropped
        except Exception as exc:
            detail = repr(exc)
        finally:
            release.set()
            core._FILL_TRACE_WRITE_HOOK = None
            core.FILL_TRACE_QUEUE_MAX = old_max
        check("T9_DROPS_COUNTED_NOT_RAISED", good, detail)
        close_handle(obj)


def t10():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        obj = fresh(tmp)
        for i in range(100):
            obj._fill_trace("proc_start", make_fill(i))
        obj._fill_trace_close()
        path = tmp / "fill_trace.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        check("T10_SHUTDOWN_FLUSHES", len(lines) == 100, "lines=%d expected=100" % len(lines))


def main():
    for fn in (t1_t2, t3, t4, t5, t6, t7, t8, t9, t10):
        try:
            fn()
        except Exception as exc:
            check(fn.__name__ + "_RAISED", False, repr(exc))
    failed = [c for c in checks if not c[1]]
    for n, ok, _ in checks:
        print(("PASS " if ok else "FAIL ") + n)
    print("SUMMARY pass=%d fail=%d" % (len(checks)-len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
