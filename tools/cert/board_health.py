"""One-command board health. Credit-free: reads the local SQLite DB and files only, no model calls, no API.

Answers, in one screen:
  - is enough work being fed in at the top      (SUPPLY / FUNNEL / INTAKE)
  - is every job that CAN run stacked and ready (READY AUDIT)
  - which jobs are failing and why              (FAILURES)
  - which are blocked and why                   (BLOCKED)
  - which need review and is anyone reviewing   (REVIEW)
  - is triage progressing                       (TRIAGE)
  - are lanes running optimally                 (LANES)
  - what needs doing right now                  (PUNCH LIST)

    python tools/cert/board_health.py
    python tools/cert/board_health.py --json
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
CONFIG = Path(r"C:/Users/wigmore/.hermes/config.yaml")

# Measured ceilings. A lane absent from here is UNKNOWN, not unlimited.
CAPS = {
    "custom-deepseek-free": 3,
    "openai-codex": 6,      # operator raised from 4, 2026-10-19
    "gemini": 4,
    "nous": 3,
    "openrouter": 2,
    "unset": 2,
}
DEAD = {"openrouter"}       # 429; a card here cannot run and gates its children

RELEASABLE = [
    (re.compile(r"initial_status", re.I), "created blocked by mistake"),
    (re.compile(r"committed (?:locally )?as [0-9a-f]{7,}|locally verified|implemented and", re.I),
     "work DONE, only delivery failed -> patch route"),
    (re.compile(r"cannot (?:verify|publish).{0,60}(?:pushed|artifact)|not verifiably pushed|couldn't find remote ref|no redo branch", re.I),
     "push/ref verification -> patch route solves it"),
    (re.compile(r"git show main:\b|read the register.{0,30}\bmain\b", re.I),
     "reads STALE local main -> must read origin/main"),
]
EXTERNAL = re.compile(r"codex|order interval|third-party|oracle source|missing .{0,25}input|nonce", re.I)


def ago(ts: float | None) -> str:
    if not ts:
        return "?"
    d = time.time() - ts
    if d < 90:
        return "%ds" % d
    if d < 5400:
        return "%dm" % (d / 60)
    if d < 172800:
        return "%dh" % (d / 3600)
    return "%dd" % (d / 86400)


def parse_ts(s) -> float | None:
    """kanban.db stores timestamps as epoch ints, not strings. Handle both."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        v = float(s)
        return v / 1000.0 if v > 1e11 else v  # tolerate ms
    try:
        return float(s)
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return time.mktime(time.strptime(str(s)[:19], fmt))
        except Exception:
            pass
    return None


def caps():
    c = dict(CAPS)
    try:
        t = CONFIG.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^\s*max_in_progress:\s*(\d+)", t, re.M)
        if m:
            c["_board"] = int(m.group(1))
    except Exception:
        pass
    return c


def main() -> int:
    as_json = "--json" in sys.argv
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    now = time.time()
    out: list[str] = []
    punch: list[str] = []

    caps_d = caps()
    board_cap = caps_d.pop("_board", 18)

    rows = [dict(r) for r in conn.execute("select * from tasks")]
    by_status: dict[str, list[dict]] = {}
    for r in rows:
        by_status.setdefault(r["status"], []).append(r)

    n = lambda s: len(by_status.get(s, []))

    # ---- INTAKE / THROUGHPUT -------------------------------------------------
    def within(items, key, secs):
        return sum(1 for x in items if (parse_ts(x.get(key)) or 0) > now - secs)

    created_1h = sum(within(by_status.get(s, []), "created_at", 3600)
                     for s in ("todo", "ready", "running", "blocked", "review", "done"))
    done_1h = within(by_status.get("done", []), "completed_at", 3600)
    done_24h = within(by_status.get("done", []), "completed_at", 86400)

    # failures in the last hour, from events
    fail_1h = conn.execute(
        "select count(*) from task_events where kind in ('failed','blocked') and rowid > "
        "(select coalesce(max(rowid),0)-4000 from task_events)").fetchone()[0]

    out.append("FLOW      done last 1h=%d   last 24h=%d   recent fail/block events=%d" %
               (done_1h, done_24h, fail_1h))

    # ---- FUNNEL --------------------------------------------------------------
    funnel = "  ".join("%s=%d" % (s, n(s)) for s in
                       ("triage", "todo", "ready", "running", "review", "blocked", "done"))
    out.append("FUNNEL    " + funnel)

    # ---- LANES / SUPPLY ------------------------------------------------------
    running = by_status.get("running", [])
    per_lane = Counter((r.get("provider_override") or "unset") for r in running)
    ready = by_status.get("ready", [])
    ready_lane = Counter((r.get("provider_override") or "unset") for r in ready)
    free = max(0, board_cap - len(running))

    out.append("")
    out.append("LANES     running / cap")
    for lane, cap in sorted(caps_d.items(), key=lambda kv: -per_lane.get(kv[0], 0)):
        r_ = per_lane.get(lane, 0)
        mark = ""
        if lane in DEAD and r_:
            mark = "  *** DEAD LANE - cards cannot run ***"
            punch.append("%d card(s) on DEAD lane %s - move them" % (r_, lane))
        elif r_ > cap:
            if ready_lane.get(lane):
                mark = "  OVER by %d, %d queued" % (r_ - cap, ready_lane[lane])
                punch.append("lane %s over cap with %d queued - re-route" % (lane, ready_lane[lane]))
            else:
                mark = "  over by %d (draining)" % (r_ - cap)
        elif r_ < cap:
            mark = "  %d free" % (cap - r_)
        out.append("          %-22s %2d / %-2d%s" % (lane, r_, cap, mark))

    supply = "STARVED" if (free and len(ready) < free) else ("FULL" if free == 0 else "FED")
    out.append("SUPPLY    free slots=%d  ready=%d  -> %s" % (free, len(ready), supply))
    if supply == "STARVED":
        punch.append("STARVED: %d free slot(s), only %d ready card(s) - the board needs intake" % (free, len(ready)))

    for r_ in ready:
        if (r_.get("provider_override") or "unset") in DEAD:
            punch.append("%s queued on DEAD lane %s" % (r_["id"], r_.get("provider_override")))

    # ---- READY AUDIT: is everything runnable actually ready? -----------------
    links = {}
    for l in conn.execute("select parent_id, child_id from task_links"):
        links.setdefault(l["child_id"], []).append(l["parent_id"])
    status_of = {r["id"]: r["status"] for r in rows}

    promotable = []
    for r_ in by_status.get("todo", []):
        parents = links.get(r_["id"], [])
        if not parents:
            promotable.append((r_["id"], "no parents"))
        elif all(status_of.get(p) == "done" for p in parents):
            promotable.append((r_["id"], "all parents done"))
        elif any(p not in status_of for p in parents):
            promotable.append((r_["id"], "dangling parent link"))
    out.append("READY AU. todo cards that should be ready: %d" % len(promotable))
    for tid, why in promotable:
        punch.append("%s is in todo but %s - promote it" % (tid, why))

    gated = [(r_["id"], [p for p in links.get(r_["id"], []) if status_of.get(p) != "done"])
             for r_ in by_status.get("todo", [])]
    gated = [(t, ps) for t, ps in gated if ps and t not in [p[0] for p in promotable]]
    if gated:
        out.append("          correctly gated: %d (waiting on live parents)" % len(gated))

    # ---- FAILURES ------------------------------------------------------------
    fails = list(conn.execute(
        "select task_id, kind, payload, created_at from task_events "
        "where kind in ('failed','error') order by rowid desc limit 200"))
    if fails:
        out.append("")
        out.append("FAILURES  %d recent" % len(fails))
        cls = Counter()
        for f in fails[:60]:
            try:
                reason = (json.loads(f["payload"] or "{}").get("error")
                          or json.loads(f["payload"] or "{}").get("reason") or "")
            except Exception:
                reason = ""
            key = ("rate_limit" if re.search(r"429|rate.?limit", reason, re.I) else
                   "auth" if re.search(r"auth|403|401|credential", reason, re.I) else
                   "timeout" if re.search(r"timeout|timed out", reason, re.I) else
                   "crash" if re.search(r"traceback|exception", reason, re.I) else "other")
            cls[key] += 1
        for k, v in cls.most_common():
            out.append("          %-12s %d" % (k, v))
        if cls.get("rate_limit", 0) >= 10:
            punch.append("%d rate-limit failures recently - a lane is saturated or a provider is capped"
                         % cls["rate_limit"])

    # ---- BLOCKED -------------------------------------------------------------
    blocked = by_status.get("blocked", [])
    releasable = []
    out.append("")
    out.append("BLOCKED   %d" % len(blocked))
    for r_ in blocked:
        ev = conn.execute(
            "select payload, created_at from task_events where task_id=? and kind='blocked' "
            "order by rowid desc limit 1", (r_["id"],)).fetchone()
        reason = ""
        ts = None
        if ev:
            try:
                reason = json.loads(ev["payload"] or "{}").get("reason") or ""
            except Exception:
                reason = ""
            ts = parse_ts(ev["created_at"])
        verdict = "external" if EXTERNAL.search(reason) else "needs a decision"
        # A card explicitly parked as needs_input is not releasable, whatever its last block event said.
        if r_.get("block_kind") == "needs_input":
            verdict = "needs_input (parked)"
        else:
            for rx, label in RELEASABLE:
                if rx.search(reason):
                    verdict = "RELEASABLE: " + label
                    releasable.append((r_["id"], reason))
                    break
        out.append("          %-12s %-4s %-8s %s" %
                   (r_["id"], ago(ts), verdict.split(":")[0][:8],
                    (r_["title"] or "")[:44]))
        # Every blocked card needs a DECISION, not just a record. Anything not positively identified as an external
        # dependency I cannot influence goes on the punch list, including unclassified ("?") blocks.
        if not verdict.startswith("external"):
            punch.append("%s is blocked (%s) - %s" % (r_["id"], verdict[:26], (reason[:80].replace(chr(10), " ") or "no reason recorded")))
    for tid, reason in releasable:
        punch.append("%s is blocked but %s" % (tid, RELEASABLE and next(
            l for rx, l in RELEASABLE if rx.search(reason))))

    # ---- REVIEW --------------------------------------------------------------
    review = by_status.get("review", [])
    out.append("")
    out.append("REVIEW    %d" % len(review))
    # A card in review is WORK STOPPED until a verdict is applied. Counting "any card with REVIEW in its title" as a
    # reviewer is wrong: unrelated review cards make it look staffed while these sit. Flag every one.
    for r_ in review:
        out.append("          %-12s %-4s %s" % (r_["id"], ago(parse_ts(r_.get("started_at"))), (r_["title"] or "")[:44]))
    if review:
        punch.append("%d card(s) in review - apply the verdict (pass->done, fail->redo card) or raise its reviewer; "
                     "a review that returned a verdict and was never applied is indistinguishable from no review"
                     % len(review))

    # ---- TRIAGE --------------------------------------------------------------
    triage = by_status.get("triage", [])
    if triage:
        oldest = min((parse_ts(t.get("created_at")) or now) for t in triage)
        out.append("TRIAGE    %d  oldest %s" % (len(triage), ago(oldest)))
        if now - oldest > 3600:
            punch.append("%d triage card(s), oldest %s - triage is not progressing" % (len(triage), ago(oldest)))
    else:
        out.append("TRIAGE    0")

    # ---- CARD PREP (brief) ---------------------------------------------------
    gaps = 0
    for r_ in rows:
        if r_["status"] not in ("ready", "todo", "running"):
            continue
        b = (r_["body"] or "").lower()
        miss = []
        if "clone" not in b:
            miss.append("clone")
        if "git show main:" in b:
            miss.append("stale-main")
        # NOTE: "ui-" also matches UI-LCC-* ROW IDS, which are evidence-assessment work, not browser capture. Only a
        # card that actually drives a browser needs the 3.11 path and the netstat liveness command.
        ui_browser = ("playwright" in b or "selenium" in b or "dom capture" in b)
        if ui_browser and "python311" not in b:
            miss.append("py311")
        if ui_browser and "netstat" not in b:
            miss.append("netstat")
        if miss:
            gaps += 1
            punch.append("%s card prep: %s" % (r_["id"], ", ".join(miss)))
    out.append("CARD PREP %d active card(s) with a gap" % gaps)

    # ---- WATCH: is anyone listening to what I posted? ------------------------
    watch_lock = Path(r"C:/Users/wigmore/.hermes/state/kanban_notify_watch.lock")
    pending_f = Path(r"C:/Users/wigmore/.hermes/state/controller_posts_pending.json")
    lock_age = (now - watch_lock.stat().st_mtime) if watch_lock.exists() else None
    alive = lock_age is not None and lock_age < 120
    try:
        pending = [p for p in json.loads(pending_f.read_text(encoding="utf-8")) if not p.get("answered")]
    except Exception:
        pending = []
    out.append("")
    out.append("WATCH     watcher %s%s   pending controller posts=%d" %
               ("ALIVE" if alive else "NOT ARMED",
                "" if lock_age is None else " (lock %s)" % ago(now - lock_age),
                len(pending)))
    if not alive:
        punch.append("WATCHER NOT ARMED - nothing will wake me; relaunch kanban_notify_watch.py --exit-on-event")
    for p in pending:
        out.append("          awaiting reply: %s  %s  %s" %
                   (p.get("ref", "?"), ago(p.get("posted_at")), p.get("note", "")))
    if pending and not alive:
        punch.append("%d post(s) awaiting a reply with NO watcher armed - the request cannot be received"
                     % len(pending))

    # ---- PUNCH ---------------------------------------------------------------
    out.append("")
    if punch:
        out.append("PUNCH LIST  (%d)" % len(punch))
        for i, p in enumerate(punch, 1):
            out.append("  %2d. %s" % (i, p))
    else:
        out.append("PUNCH LIST  empty - supply fed, lanes balanced, nothing releasable, no orphans, cards prepared")

    if as_json:
        print(json.dumps({"punch": punch, "funnel": {s: n(s) for s in
                          ("triage", "todo", "ready", "running", "review", "blocked", "done")},
                          "done_1h": done_1h, "supply": supply}))
    else:
        print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
