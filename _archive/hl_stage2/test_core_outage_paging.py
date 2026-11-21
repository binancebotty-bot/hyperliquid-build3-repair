#!/usr/bin/env python3
"""Offline leader-poll retention regression, including a 14,000-fill history."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="outage_paging_"))
    os.environ.update({"HL_LIVE_ENV_FILE": str(tmp / "missing.env"), "HL_LIVE_AUDIT_DIR": str(tmp),
                       "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet"})
    import HL_Live_Copy_Service_Core as c

    wallet = "0x" + "a" * 40
    end_ms = 1_800_000_000_000
    start_ms = end_ms - 7 * 60 * 60 * 1000
    fills = [{"coin": "BTC", "px": "100", "sz": "1", "side": "B", "time": start_ms + i * 1800,
              "hash": f"h{i}", "tid": i + 1} for i in range(14_000)]
    calls = []

    class Response:
        def __init__(self, data): self.data = data
        def json(self): return self.data

    def fake_post(_url, json=None, **_kwargs):
        calls.append(dict(json))
        page = [row for row in fills if json["startTime"] <= row["time"] <= json["endTime"]]
        return Response(page[:2000])

    c.requests.post = fake_post
    got, status = c.LeaderFillIngestor().poll_hyperliquid_fills(wallet, start_ms, end_ms)
    retention_ms = 100 * 60 * 1000
    floor_ms = end_ms - retention_ms
    expected = sum(row["time"] >= floor_ms for row in fills)
    assert status == "POLL_OK", status
    unique = {fill.leader_fill_id: fill for fill in got}
    assert len(unique) == expected, f"expected {expected} unique fills inside retained window, got {len(unique)} of 14,000"
    assert calls and max(call["endTime"] - call["startTime"] for call in calls) <= retention_ms
    assert min(fill.timestamp_ms for fill in unique.values()) >= floor_ms

    fills[:] = [{**row, "time": floor_ms + i * retention_ms // 13_999} for i, row in enumerate(fills)]
    calls.clear()
    got, status = c.LeaderFillIngestor().poll_hyperliquid_fills(wallet, start_ms, end_ms)
    dense = {fill.leader_fill_id: fill for fill in got}
    assert status == "POLL_OK" and len(dense) == 14_000, f"14,000-fill retained window: {status}, {len(dense)} unique"
    assert len(calls) >= 8, f"expected time paging across 14,000 fills, got {len(calls)} pages"
    assert max(call["endTime"] - call["startTime"] for call in calls) <= retention_ms
    print(f"PASS retained={len(unique)}/14000 dense={len(dense)}/14000 pages={len(calls)}")


if __name__ == "__main__":
    main()
