"""Reproduces every count in ARMING_REPLAY_AND_EXIT_TIMING_2026-10-17.md.

Read-only: it never writes to the audit directory.

    HL_LIVE_ENV_FILE=/nonexistent python3 -u replay_block_counts.py

Point it at another run with HL_AUDIT_DIR=<...>/append_only.
"""
import collections
import csv
import glob
import os
import sys

csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))

D = os.getenv("HL_AUDIT_DIR") or (
    r"C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/"
    r"hl_live_copy_audit_testnet/append_only")
DAY = os.getenv("HL_REPLAY_DAY", "2026-10-17")
LO = os.getenv("HL_REPLAY_LO", DAY + "T03:48")
HI = os.getenv("HL_REPLAY_HI", DAY + "T05:40")


def _rows(pattern):
    for path in sorted(glob.glob(os.path.join(D, pattern))):
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            yield from csv.DictReader(fh)


def block_counts(lo=LO, hi=HI):
    rows = collections.Counter()
    fills = collections.defaultdict(set)
    for row in _rows("reconciliation*.csv"):
        ts = row.get("created_at") or ""
        if not ts.startswith(DAY) or not (lo <= ts[:16] <= hi):
            continue
        t = row.get("terminal_state") or ""
        rows[t] += 1
        fid = row.get("leader_fill_id") or ""
        if fid:
            fills[t].add(fid)
    return rows, fills


def disarmed_minutes():
    per = collections.Counter()
    for row in _rows("reconciliation*.csv"):
        if (row.get("terminal_state") or "") != "SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED":
            continue
        ts = row.get("created_at") or ""
        if ts.startswith(DAY):
            per[ts[:16]] += 1
    return per


def fill_age(lo=LO, hi=HI):
    ages = []
    for row in _rows("send_attempts*.csv"):
        ts = row.get("created_at") or ""
        if not ts.startswith(DAY) or not (lo <= ts[:16] <= hi):
            continue
        try:
            lft = int(float(row.get("leader_fill_timestamp_ms") or 0))
            cms = int(float(row.get("created_at_ms") or 0))
        except (TypeError, ValueError):
            continue
        if lft > 0 and cms > 0:
            ages.append(cms - lft)
    ages.sort()
    return ages


def intent_sources(lo=LO, hi=DAY + "T05:10"):
    src = collections.Counter()
    fills = set()
    for row in _rows("order_intents*.csv"):
        ts = row.get("created_at") or ""
        if not ts.startswith(DAY) or not (lo <= ts[:16] <= hi):
            continue
        src[row.get("source") or ""] += 1
        fid = row.get("leader_fill_id") or ""
        if fid:
            fills.add(fid)
    return src, len(fills)


def main():
    per = disarmed_minutes()
    if per:
        mins = sorted(per)
        print("disarmed minutes: %d  first %s  last %s" % (len(mins), mins[0], mins[-1]))

    rows, fills = block_counts()
    total = sum(rows.values())
    all_fills = set().union(*fills.values()) if fills else set()
    print("\nwindow %s - %s : %d terminal rows, %d distinct leader fills"
          % (LO, HI, total, len(all_fills)))
    for state, n in rows.most_common(15):
        print("  %7d %5.1f%% %7d fills  %r" % (n, 100.0 * n / total, len(fills[state]), state))

    ages = fill_age()
    if ages:
        n = len(ages)
        print("\nfill age at processing, n = %d" % n)
        print("  p50 %.0fs  p90 %.0fs  p99 %.0fs  max %.0fs" % (
            ages[n // 2] / 1000.0, ages[int(n * 0.9)] / 1000.0,
            ages[int(n * 0.99)] / 1000.0, ages[-1] / 1000.0))
        for a, b, label in [(0, 60000, "<1m"), (60000, 600000, "1-10m"), (600000, 3600000, "10-60m"),
                            (3600000, 7200000, "1-2h"), (7200000, 10 ** 15, ">2h")]:
            c = sum(1 for x in ages if a <= x < b)
            print("  %-7s %7d (%5.1f%%)" % (label, c, 100.0 * c / n))

    src, nf = intent_sources()
    if src:
        print("\nintent sources: %d intents, %d distinct fills" % (sum(src.values()), nf))
        for k, v in src.most_common(8):
            print("  %7d %s" % (v, k))


if __name__ == "__main__":
    main()
