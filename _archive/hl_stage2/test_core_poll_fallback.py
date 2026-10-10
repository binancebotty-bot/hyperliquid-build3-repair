#!/usr/bin/env python3
"""Idle-path detection: when the live feed is not delivering (down, or open but never acked), the leader poll runs
fast enough to be the detector (scaled to the info rate limit) instead of every 30 s.

Run: python test_core_poll_fallback.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
W = ["0x%040x" % i for i in range(1, 13)]


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pollfb_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_HOT_SEND_WORKERS": "2"})
    for k in ("HL_LIVE_LEADER_POLL_NOFEED_SEC", "HL_LIVE_LEADER_POLL_INTERVAL_SEC"):
        os.environ.pop(k, None)
    import HL_Live_Copy_Service_Core as c

    def cfg(n):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
            w: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12} for w in W[:n]}})
    cfg(3)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    ws = core.ws
    ws.enabled = True

    ws._socket_open, ws._subscribed = True, set(W[:3])
    check("feed_ok_30s", core.leader_poll_interval_sec() == 30.0, str(core.leader_poll_interval_sec()))
    ws._socket_open, ws._subscribed = True, set(W[:2])
    check("partial_feed_still_fast_poll", core.leader_poll_interval_sec() < 30.0, str(core.leader_poll_interval_sec()))
    ws._socket_open, ws._subscribed = True, set()
    check("open_but_unacked_is_fast", core.leader_poll_interval_sec() == 6.6000000000000005 or abs(core.leader_poll_interval_sec() - 6.6) < 1e-9,
          str(core.leader_poll_interval_sec()))
    ws._socket_open, ws._subscribed = False, set()
    check("socket_down_is_fast", core.leader_poll_interval_sec() < 30.0)
    cfg(10)
    core.cfg = c.ConfigManager()
    check("ten_leaders_scales_to_rate_limit", abs(core.leader_poll_interval_sec() - 22.0) < 1e-9, str(core.leader_poll_interval_sec()))
    cfg(1)
    core.cfg = c.ConfigManager()
    check("never_under_2s", core.leader_poll_interval_sec() == 2.2 or core.leader_poll_interval_sec() == 2.0, str(core.leader_poll_interval_sec()))
    os.environ["HL_LIVE_LEADER_POLL_NOFEED_SEC"] = "3"
    check("env_override", core.leader_poll_interval_sec() == 3.0, str(core.leader_poll_interval_sec()))
    os.environ.pop("HL_LIVE_LEADER_POLL_NOFEED_SEC")
    ws.enabled = False
    check("no_feed_configured_polls_every_cycle", core.leader_poll_interval_sec() == 0.0)
    # HL refusal is kept verbatim and degrades the status
    import json
    ws.enabled = True
    ws.wallets = W[:3]
    ws._socket_open = True
    ws._subscribed = {W[0]}
    ws._on_message(json.dumps({"channel": "error", "data": "Cannot track more than 15 total users"}))
    h = (ws.write_health() or {}).get("ws_summary", {})
    check("refusal_text_kept", "15 total users" in str(h.get("last_refusal")) and h.get("subscribe_refused") == 1, str(h)[:200])
    check("refusal_degrades_status", h.get("ws_status") == "WS_DEGRADED", str(h.get("ws_status")))
    check("wallets_without_feed_counted", h.get("wallets_without_feed") == 2, str(h.get("wallets_without_feed")))
    core.stop()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
