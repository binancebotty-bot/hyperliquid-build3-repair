#!/usr/bin/env python3
"""Offline: append_csv keeps one handle open per audit CSV (no open/close per row) and stays correct across rotation,
removal, a short write and the old per-row mode; canonical_coin_key re-stats the universe file at most once a second."""
import csv, os, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as C

d = Path(tempfile.mkdtemp()); p = d / "order_intents.csv"; F = C.ORDER_INTENT_FIELDS; A, B = F[0], F[1]
def n_rows(): return len(list(csv.DictReader(p.open(newline="", encoding="utf-8"))))
opens = []
real_open = Path.open
def spy(self, *a, **k):
    if self == p and (a and a[0] == "a" or k.get("mode") == "a"): opens.append(1)
    return real_open(self, *a, **k)
Path.open = spy
try:
    for i in range(50): C.append_csv(p, F, {A: i, B: "x"})
    assert n_rows() == 50 and len(opens) == 1, (n_rows(), len(opens))  # one open for 50 rows, all on disk at once
    ts = [threading.Thread(target=lambda: [C.append_csv(p, F, {A: 1, B: "t"}) for _ in range(100)]) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert n_rows() == 650
    p.unlink(); C.append_csv(p, F, {A: 9, B: "again"})  # removed by someone else: recreated with its header
    assert n_rows() == 1 and p.read_text(encoding="utf-8").startswith(A + "," + B)
    C.AUDIT_ROTATE_BYTES = 200  # rotation: handle closed first, new file gets a header and the next row
    for i in range(30): C.append_csv(p, F, {A: i, B: "rotate-me-please-" * 4})
    assert any(q.name != p.name for q in d.glob("order_intents*.csv")), list(d.iterdir())
    assert p.exists() and p.read_text(encoding="utf-8").startswith(A + "," + B)
    C.AUDIT_ROTATE_BYTES = 0; C.AUDIT_KEEP_OPEN = False; opens.clear()  # old per-row mode still works
    for i in range(3): C.append_csv(p, F, {A: i, B: "o"})
    assert len(opens) == 3
finally:
    Path.open = real_open
# coin map: one stat per second at most
calls = []; real_stat = os.stat
C.os.stat = lambda *a, **k: (calls.append(1), real_stat(*a, **k))[1]
try:
    C._COIN_KEY_RECHECK_SEC = 60.0
    for _ in range(1000): C.canonical_coin_key("btc")
    assert len(calls) <= 2, len(calls)
finally:
    C.os.stat = real_stat
print("RESULT::audit_keep_open_PASS")
