"""Acceptance harness for t_80221ee2: the status heartbeat is independent of the cycle.

With the cycle thread deliberately stalled (the on-cycle status write never happens),
live_service_state.json must keep advancing and show a RISING cycle age.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
sys.path.insert(0, str(ROOT / "_archive" / "hl_stage2"))
os.environ.setdefault("HL_LIVE_MOCK_SEND", "1")

import HL_Live_Copy_Service_Core as c  # noqa: E402

STATE = Path(os.environ.get("HB_STATE_FILE", Path.home() / ".hermes" / "cache" / "scratch" / "hb_live_service_state.json"))
STATE.parent.mkdir(parents=True, exist_ok=True)


def read_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        raise SystemExit(f"FAIL: {label}")


def main() -> int:
    c.SERVICE_STATE_FILE = STATE
    # Seed: the cycle's last write was 10 s ago and then stalled, so the age has somewhere to rise from.
    STATE.write_text(json.dumps({'last_cycle_write_ms': c.utc_now_ms() - 10_000}), encoding='utf-8')

    writer = c.ServiceStateWriter()
    # The cycle never publishes: only the heartbeat touches the file (this IS the stalled-cycle harness).
    writer.start_heartbeat(0.5, lambda: 7)

    time.sleep(0.7)  # let the first tick land
    t0 = read_state().get("created_at_ms", 0)
    first = read_state()["heartbeat_seq"]
    age_a = read_state()["cycle_age_ms"]
    for _ in range(6):
        time.sleep(0.5)
    time.sleep(0.4)
    mid = read_state()
    t1 = mid["created_at_ms"]
    time.sleep(1.6)
    last = read_state()

    check("state file advances while the cycle is stalled", t1 > t0, f"created_at_ms {t0} -> {t1}")
    check("heartbeat_seq advances", mid["heartbeat_seq"] > first, f"{first} -> {mid['heartbeat_seq']}")
    check("cycle age rises", last["cycle_age_ms"] > age_a,
          f"cycle_age_ms {age_a} -> {last['cycle_age_ms']}")
    check("queue depth carried", last["hot_queue_depth"] == 7, str(last["hot_queue_depth"]))
    check("thread count carried", last["thread_count"] >= 1, str(last["thread_count"]))
    check("heartbeat only -- no cycle stamp yet", last["cycle_age_ms"] > 0 and last["heartbeat_seq"] >= 2)

    # Revert control: without the heartbeat the file must NOT advance.
    writer.stop_heartbeat()
    time.sleep(0.3)
    frozen = read_state()["created_at_ms"]
    time.sleep(1.5)
    still = read_state()["created_at_ms"]
    check("revert control: no heartbeat -> frozen file", still == frozen, f"{frozen} vs {still}")

    # The cycle's own write resets the age and keeps the heartbeat fields.
    writer.heartbeat(0)
    before = read_state()["heartbeat_seq"]
    writer.write_startup(c.CycleSummary(), c.DedupeStore(), None)
    after = read_state()
    check("cycle write resets cycle_age_ms", after["cycle_age_ms"] == 0, str(after["cycle_age_ms"]))
    check("cycle write keeps heartbeat_seq", after["heartbeat_seq"] == before, f"{before} -> {after['heartbeat_seq']}")
    writer.stop_heartbeat()
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
