#!/usr/bin/env python3
"""Offline test: run_report.fetch_leader_fills pages past the 2,000-fill API cap (no network)."""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import run_report as rr  # noqa: E402

ALL = [{"hash": "h%d" % i, "tid": i, "time": 1000 + i, "oid": i, "sz": "1", "px": "1"} for i in range(4500)]
CALLS = []


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(req, timeout=20):
    p = json.loads(req.data.decode())
    CALLS.append(p["startTime"])
    rows = [f for f in ALL if p["startTime"] <= f["time"] <= p["endTime"]][:2000]
    return Resp(json.dumps(rows).encode())


rr._urlrequest.urlopen = fake_urlopen
out = rr.fetch_leader_fills(["0xabc"], 1000, 10**9, min_interval_s=0)
ok = len(out) == 4500 and len({f["tid"] for f in out}) == 4500 and len(CALLS) == 3
print("RESULT::paging_%s | got=%d calls=%d" % ("PASS" if ok else "FAIL", len(out), len(CALLS)))
sys.exit(0 if ok else 1)
