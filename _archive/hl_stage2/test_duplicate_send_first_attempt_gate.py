#!/usr/bin/env python3
"""Behavioural duplicate-send gate witnesses using the C1-G13 harness pattern."""
from __future__ import annotations
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_c1_g13_sequences as h


def record_prior_attempts(fid):
    path = h.c.SEND_ATTEMPTS_CSV
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=h.c._SEND_ROW_KEYS)
        writer.writeheader()
        for attempt in ("prior-1", "prior-2"):
            writer.writerow({"attempt_id": attempt, "leader_fill_id": fid,
                             "status": "ORDER_FILLED"})
    h.c._SEND_ROWS_CACHE.update(path=None, ino=None, size=0, mtime=None,
                                tail=b"", rows=None, fields=None,
                                by_oid=None, recovery=None)


def scenario(name, exchange_net, prior):
    root, led, net, ex, gw, intent, fid = h.make(
        name, 1.0, 0.0, exchange_net, side="SELL", qty=1.0)
    if prior:
        record_prior_attempts(fid)
    reasons = []
    original_plan = gw._close_wire_plan
    def capture_plan(*args, **kwargs):
        result = original_plan(*args, **kwargs)
        reasons.append(result[2])
        return result
    gw._close_wire_plan = capture_plan
    ok, status = gw.send_if_allowed(intent)
    return ok, status, ex.calls, reasons


def main():
    results = []
    for name, actual in (("DUP_EQUAL_NET", 1.0), ("DUP_SAFE_FOREIGN", 2.0)):
        ok, status, calls, reasons = scenario(name, actual, True)
        passed = (not ok and not calls and
                  "CLOSE_PROOF_HOLD_DUPLICATE_SEND_ATTEMPT" in reasons)
        results.append(passed)
        print("RESULT::%s_%s | reason=%r status=%r wire=%r" %
              (name, "PASS" if passed else "FAIL", reasons, status, calls), flush=True)
    ok, status, calls, reasons = scenario("FIRST_SEND_CONTROL", 1.0, False)
    passed = ok and status == "ORDER_FILLED" and len(calls) == 1
    results.append(passed)
    print("RESULT::FIRST_SEND_CONTROL_%s | status=%r wire=%r" %
          ("PASS" if passed else "FAIL", status, calls), flush=True)
    failed = len([x for x in results if not x])
    print("TOTAL=%d FAILED=%d" % (len(results), failed), flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
