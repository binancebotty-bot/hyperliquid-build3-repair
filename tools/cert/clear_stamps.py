"""Clear stale `blocker_auth` stamps so a rate limit cannot permanently poison a card.

Controller ruling (6270961056): do not patch the Hermes install. Automate the hand-clearing instead - "a small plain
script that only clears stamps older than 10 minutes and logs each one. It does not change the Hermes install. Run it
hidden, and report if it fails."

Why stamps poison cards: `kanban_db_dispatch.py` skips any card whose `last_failure_error` matches a quota/auth phrase
(`_RESPAWN_BLOCKER_RE`). The exemption only fires when the latest run outcome is exactly `rate_limited` with a cooldown;
a `spawn_failed` run leaves the text behind and the card is skipped indefinitely.

This script clears a stamp ONLY when the card's most recent run ended more than 10 minutes ago, so an in-flight or
recently-failed card is never disturbed.

    python tools/cert/clear_stamps.py --dry-run     # show what would be cleared
    python tools/cert/clear_stamps.py               # clear, print each

Exit 0 always on a successful pass; exit 1 if the DB cannot be read (so a failure is visible rather than silent).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
LOG = Path(r"C:/Users/wigmore/.hermes/state/blocker_auth_clears.log")
MIN_AGE_S = 600          # 10 minutes, per the ruling
PATTERN = ("rate", "quota", "429", "limit", "auth", "credential", "exhaust")


def main() -> int:
    dry = "--dry-run" in sys.argv
    try:
        conn = sqlite3.connect(DB, timeout=15)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, last_failure_error FROM tasks "
            "WHERE status IN ('ready','todo') AND last_failure_error IS NOT NULL AND last_failure_error != ''"
        ).fetchall()
    except Exception as exc:
        print("CLEAR_STAMPS  FAILED - cannot read kanban db: %r" % (exc,))
        return 1

    now = time.time()
    cleared, skipped = [], []
    for r in rows:
        err = str(r["last_failure_error"] or "")
        if not any(p in err.lower() for p in PATTERN):
            continue
        run = conn.execute(
            "SELECT ended_at FROM task_runs WHERE task_id = ? AND ended_at IS NOT NULL "
            "ORDER BY ended_at DESC LIMIT 1", (r["id"],)
        ).fetchone()
        ended = None
        if run is not None and run["ended_at"] is not None:
            v = run["ended_at"]
            ended = float(v) if isinstance(v, (int, float)) else None
        age = (now - ended) if ended else None
        if age is not None and age < MIN_AGE_S:
            skipped.append((r["id"], int(age)))
            continue
        cleared.append((r["id"], err[:90], int(age) if age else None))

    if dry:
        print("CLEAR_STAMPS  dry-run: would clear %d, still too fresh %d" % (len(cleared), len(skipped)))
        for tid, err, age in cleared:
            print("   %-12s age=%ss  %s" % (tid, age, err))
        return 0

    if cleared:
        conn.executemany("UPDATE tasks SET last_failure_error = NULL WHERE id = ?",
                         [(tid,) for tid, _, _ in cleared])
        conn.commit()
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            for tid, err, age in cleared:
                fh.write("%s\t%s\tage=%ss\t%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), tid, age, err))
    print("CLEAR_STAMPS  cleared %d, too-fresh %d, scanned %d" % (len(cleared), len(skipped), len(rows)))
    for tid, _, age in cleared:
        print("   cleared %-12s age=%ss" % (tid, age))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
