"""Pre-flight for the build3-repair board. Run at the START of every cycle - it catches the three things that drift.

Why: the three recurring failures are (1) cards not prepared, (2) blockages not monitored, (3) misallocation to dead
lanes or against known ceilings. Each was being found separately, late, usually by the operator. This reports all three
in one deterministic pass with a punch list. It is a CHECK, not a poller - no daemon, no timer, no background process.

    python tools/cert/preflight.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
CONFIG = Path(r"C:/Users/wigmore/.hermes/config.yaml")

# Measured ceilings - EVIDENCE/ORCHESTRATION_PLAYBOOK.md section 5. A lane not listed here is unknown, not unlimited.
CAPS = {
    "custom-deepseek-free": 3,   # 3 accounts x 1 in-flight; proxy 503s beyond
    "openai-codex": 4,           # operator cap
    "gemini": 4,                 # rate-limits at 5-6
    "nous": 3,                   # 50 req/min account-wide
    "openrouter": 2,             # free tier, 1000 requests/DAY budget
    "unset": 2,
}
DEAD = {"openrouter"}            # 429 at last probe; a card here cannot run and gates anything behind it

STALE_BLOCK_S = 45 * 60          # a block older than this needs a fresh look

RELEASABLE = [
    (re.compile(r"initial_status", re.I), "created blocked by mistake - release"),
    (re.compile(r"committed as [0-9a-f]{7,}|locally verified|implemented and", re.I),
     "work was DONE, only delivery failed - release with the patch rule"),
    (re.compile(r"cannot verify.{0,60}pushed|not verifiably pushed|couldn't find remote ref|not found on the remote", re.I),
     "push/ref verification - the patch-folder route solves this"),
    (re.compile(r"git show main:|read the register.{0,40}main\b", re.I),
     "card reads local main (STALE) - must read origin/main"),
]
EXTERNAL = re.compile(r"codex|order interval|third-party|oracle source|missing .{0,20}input|nonce", re.I)


def load_caps():
    caps = dict(CAPS)
    try:
        text = CONFIG.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"max_in_progress:\s*(\d+)", text)
        if m:
            caps["_board"] = int(m.group(1))
    except Exception:
        pass
    return caps


def latest_block(c, tid):
    row = c.execute(
        "select payload, created_at from task_events where task_id=? and kind='blocked' "
        "order by rowid desc limit 1", (tid,)).fetchone()
    if not row:
        return "", None
    try:
        reason = json.loads(row[0] or "{}").get("reason") or ""
    except Exception:
        reason = ""
    return reason, row[1]


def main():
    c = sqlite3.connect(DB)
    caps = load_caps()
    board_cap = caps.pop("_board", 16)
    now = time.time()

    counts = dict(c.execute("select status,count(*) from tasks group by status").fetchall())
    running = list(c.execute(
        "select id, provider_override, model_override, worker_started_at from tasks where status='running'"))
    ready = list(c.execute("select id, provider_override, priority from tasks where status='ready'"))
    blocked = list(c.execute("select id, substr(title,1,46) from tasks where status='blocked'"))
    todo = list(c.execute("select id from tasks where status='todo'"))

    out = []
    punch = []

    # ---------- 1. LANES ----------
    per_lane = Counter((p or "unset") for _, p, _, _ in running)
    ready_on_lane = Counter((p or "unset") for _, p, _ in ready)
    out.append("LANES  (running / cap)")
    for lane, cap in sorted(caps.items(), key=lambda kv: -per_lane.get(kv[0], 0)):
        n = per_lane.get(lane, 0)
        mark = ""
        if n > cap:
            # Over cap only matters if more work is queued behind it. Running workers are left to drain - killing
            # them to hit a number destroys work in flight, which cost more than the overshoot every time.
            if ready_on_lane.get(lane, 0):
                mark = "  OVER by %d with %d queued" % (n - cap, ready_on_lane[lane])
                punch.append("lane %s is %d over cap with %d card(s) queued - re-route the queue"
                             % (lane, n - cap, ready_on_lane[lane]))
            else:
                mark = "  over by %d (draining, nothing queued)" % (n - cap)
        elif n < cap:
            mark = "  %d free" % (cap - n)
        dead = "  *** DEAD LANE ***" if lane in DEAD and n else ""
        out.append("   %-22s %d / %-2d%s%s" % (lane, n, cap, mark, dead))

    for lane in DEAD:
        n = per_lane.get(lane, 0)
        if n:
            punch.append("%d card(s) running on DEAD lane %s - move them to a live lane" % (n, lane))

    # ---------- 2. QUEUE ----------
    free = max(0, board_cap - len(running))
    out.append("")
    out.append("QUEUE  running %d / %d board cap | ready %d | todo %d | blocked %d"
               % (len(running), board_cap, len(ready), len(todo), len(blocked)))
    if free and len(ready) < free:
        punch.append("STARVED: %d free slot(s) but only %d ready card(s)" % (free, len(ready)))

    # cards sitting on a dead lane in ready/todo
    for tid, p, _ in c.execute(
            "select id, provider_override, priority from tasks where status in ('ready','todo')"):
        if (p or "unset") in DEAD:
            punch.append("%s is queued on DEAD lane %s" % (tid, p))

    # ---------- 3. BLOCKED ----------
    out.append("")
    out.append("BLOCKED  (%d)" % len(blocked))
    for tid, title in blocked:
        reason, created = latest_block(c, tid)
        age = ""
        if created:
            try:
                ts = time.mktime(time.strptime(created[:19], "%Y-%m-%d %H:%M:%S"))
                age = "%4dm" % ((now - ts) / 60)
            except Exception:
                age = "   ?"
        cls = "external" if EXTERNAL.search(reason) else "?"
        for rx, label in RELEASABLE:
            if rx.search(reason):
                cls = "RELEASABLE: " + label
                punch.append("%s (%s) %s" % (tid, title, label))
                break
        out.append("   %-12s %-5s %-46s %s" % (tid, age, title, cls[:60]))

    # ---------- 4. CARD PREPAREDNESS ----------
    out.append("")
    offenders = []
    for tid, body in c.execute("select id, body from tasks where status in ('ready','todo','running')"):
        b = (body or "").lower()
        missing = []
        if "clone" not in b:
            missing.append("no clone instructions")
        if "git show main:" in b or re.search(r"read the register.{0,30}\bmain\b", b):
            missing.append("reads STALE local main (use origin/main)")
        ui_card = ("playwright" in b or "rendered" in b or "dom" in b or "ui-" in b)
        if ui_card and "python311" not in b:
            missing.append("UI work but no Python 3.11 interpreter path")
        # Only UI cards need the liveness instruction - that is where the process-scan blind spot cost us a run.
        if ui_card and "netstat" not in b:
            missing.append("UI card with no netstat liveness instruction")
        if missing:
            offenders.append((tid, missing))
            punch.append("%s: %s" % (tid, "; ".join(missing)))
    out.append("CARD PREP  %d active card(s) with a gap" % len(offenders))

    # ---------- PUNCH LIST ----------
    out.append("")
    if punch:
        out.append("PUNCH LIST  (%d)" % len(punch))
        for i, item in enumerate(punch, 1):
            out.append("  %2d. %s" % (i, item))
    else:
        out.append("PUNCH LIST  empty - lanes balanced, queue fed, no releasable blocks, cards prepared")

    print("\n".join(out))


if __name__ == "__main__":
    main()
