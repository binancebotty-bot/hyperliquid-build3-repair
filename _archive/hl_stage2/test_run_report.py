#!/usr/bin/env python3
"""Fixture test for tools/run_report.py. Offline, temp files only, no network, no keys.

Builds a synthetic audit dir, runs the report with an injected (non-network) fill
fetcher, and asserts the counts, the stage medians, the MISSING highlight, the
reconciliation counts, the verify passthrough and the <= 25-line contract.
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_report as rr  # noqa: E402

R = []


def check(n, c, d=""):
    R.append((n, bool(c)))
    print("RESULT::%s_%s%s" % (n, "PASS" if c else "FAIL", (" | " + str(d)) if (d and not c) else ""))


def w(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as f:
        d = csv.DictWriter(f, fieldnames=keys)
        d.writeheader()
        d.writerows(rows)


BASE = 1791000000000  # leader_fill_timestamp_ms (absolute, > 1e12)
ARMED = BASE - 5000
LIVE_W = "0x936cf4fb95c30ce83f658b5bbb247e4bb381bb0f"
CLO_W = "0x1111111111111111111111111111111111111111"
OFF_W = "0x2222222222222222222222222222222222222222"

tmp = Path(tempfile.mkdtemp(prefix="runreport_"))
aud = tmp / "hl_live_copy_audit_testnet"
apd = aud / "append_only"
apd.mkdir(parents=True, exist_ok=True)

# live_config: one LIVE, one CLO, one OFF -> default wallets = LIVE + CLO only
(aud / "live_config.json").write_text(json.dumps({"wallets": {
    LIVE_W: {"mode": "LIVE", "enabled": True},
    CLO_W: {"mode": "CLOSE_ONLY", "enabled": True},
    OFF_W: {"mode": "OFF", "enabled": True},
}}), encoding="utf-8")

# three post-arm send rows: deltas 10/20/30 ms -> upper-middle median = 20, max = 30
def sendrow(delta, status, fid):
    return {"created_at_ms": BASE + delta, "leader_fill_timestamp_ms": BASE,
            "ws_received_ms": BASE + delta, "intent_created_at_ms": BASE + delta,
            "leader_fill_id": fid, "leader_wallet": LIVE_W, "status": status,
            "symbol_resolve_ms": 7, "send_total_ms": delta}

w(apd / "send_attempts.csv", [
    sendrow(10, "ORDER_FILLED", "0xdead01"),
    sendrow(20, "ORDER_FILLED", "0xdead02"),
    sendrow(30, "SEND_BLOCKED_RISK", "0xbeef03"),
    {"created_at_ms": BASE - 100000, "leader_fill_timestamp_ms": BASE, "status": "ORDER_FILLED"},  # pre-arm, excluded
])
w(apd / "order_intents.csv", [{"leader_fill_id": "0xdead01", "notes": ""},
                              {"leader_fill_id": "0xdead02", "notes": ""}])
w(apd / "reconciliation.csv", [
    {"created_at_ms": BASE, "event": "MARGIN_MODE_SET", "status": "ok"},
    {"created_at_ms": BASE, "event": "MARGIN_MODE_SET", "status": "ok"},
    {"created_at_ms": BASE, "event": "LIQ_PARITY_OK", "status": "ok"},
    {"created_at_ms": BASE, "event": "LIQ_PARITY_MISMATCH", "status": "bad"},
    {"created_at_ms": BASE, "event": "FILL_MERGED", "status": "ok"},
])
w(apd / "live_fills.csv", [{"created_at_ms": BASE, "leader_fill_id": "0xdead01"}])

verify_out = tmp / "verify_out.txt"
verify_out.write_text("COIN ... \nRESULT:: MATCH at 12:00:00Z\n", encoding="utf-8")

# ---- injected non-network fills: 0xdead01 -> SENT (in send_attempts), 0xbeef03 -> MISSING
def fake_fetcher(wallets, start_ms, end_ms):
    check("FETCHER_RECEIVES_LIVE_CLO_WALLETS", set(wallets) == {LIVE_W, CLO_W}, wallets)
    return [{"hash": "0xdead01", "time": BASE, "coin": "PAXG", "side": "B", "px": "1", "sz": "1"},
            {"hash": "0xdead01", "time": BASE, "coin": "PAXG", "side": "B", "px": "1", "sz": "1"},  # same-tx dup
            {"hash": "0xunknown99", "time": BASE, "coin": "PAXG", "side": "B", "px": "1", "sz": "1"}]

md = rr.build_report(aud, ARMED, [LIVE_W, CLO_W], outage_stop_ms=BASE - 1000,
                     outage_restart_ms=BASE + 1000, verify_output=verify_out,
                     fill_fetcher=fake_fetcher)

check("REPORT_UNDER_25_LINES", len(md.splitlines()) <= 25, len(md.splitlines()))
check("COPIES_EXCLUDES_PRE_ARM", "copies=3" in md, md)
check("STATUS_HISTOGRAM", "ORDER_FILLED=2" in md and "SEND_BLOCKED_RISK=1" in md, md)
check("STAMP_MEDIAN_MAX", "ws_received_ms=20/30" in md, md)          # deltas 10/20/30 -> p50 20, max 30
check("DURATION_COLUMN", "symbol_resolve_ms=7/7" in md, md)
check("RECON_MARGIN_MODE_SET", "MARGIN_MODE_SET=2" in md, md)
check("RECON_LIQ_PARITY_STAR", "LIQ_PARITY_*=2" in md, md)
check("OUTAGE_FILL_COUNT", "fills=3 ids=2" in md, md)   # raw fills vs unique leader_fill_ids (same-tx dup collapses)
check("OUTAGE_MISSING_HIGHLIGHTED", "MISSING=1" in md and "SILENT LOSS" in md, md)
check("VERIFY_PASSTHROUGH", "verify: RESULT:: MATCH at 12:00:00Z" in md, md)

# live_config default-wallet filter
check("DEFAULTS_LIVE_CLO_ONLY", rr.load_live_config_wallets(aud / "live_config.json") == [CLO_W, LIVE_W]
      or set(rr.load_live_config_wallets(aud / "live_config.json")) == {LIVE_W, CLO_W},
      rr.load_live_config_wallets(aud / "live_config.json"))

# offline mode must not call the exchange and must say so
md_off = rr.build_report(aud, ARMED, [LIVE_W, CLO_W], outage_stop_ms=BASE - 1000,
                         outage_restart_ms=BASE + 1000, offline=True,
                         fill_fetcher=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used in offline mode")))
check("OFFLINE_SKIPS_EXCHANGE", "SKIPPED (offline)" in md_off, md_off)

# stable id mirror: hash preferred
check("STABLE_ID_PREFERS_HASH", rr.leader_fill_ids([{"hash": "0xabc"}]) == ["0xabc"])
check("STABLE_ID_FALLBACK_TID", rr.leader_fill_ids([{"tid": 12345}]) == ["12345"])

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
