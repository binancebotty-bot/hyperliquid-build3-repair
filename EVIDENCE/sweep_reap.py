#!/usr/bin/env python
"""sweep_reap.py - find GENUINELY stuck kanban workers; never reap a spawn window.

Why this exists: a naive sweep kills a worker, the dispatcher respawns it, and the next
sweep catches the replacement mid-spawn and calls it "dead" - so the sweep reaps workers it
just created and churns forever (observed repeatedly on this board).

A card is STUCK only if all three hold:
  1. it is still `running`,
  2. it carries the SAME worker_pid across two probes separated by PAUSE_S,
  3. that pid is not alive in the process table - confirmed once more after a short delay.

Anything that changed pid between probes is mid-spawn/rollover and is LEFT ALONE.

usage:  python sweep_reap.py [pause_seconds]   # prints stuck ids, one per line
        python sweep_reap.py --reap            # also reclaim them
Read-only unless --reap is passed.
"""
import sqlite3
import subprocess
import sys
import time

DB = 'C:/Users/wigmore/.hermes/kanban.db'


def running_pids():
    con = sqlite3.connect(DB)
    return {r[0]: str(r[1]) for r in
            con.execute("select id, worker_pid from tasks where status='running'")}


def alive(pid):
    out = subprocess.run(['tasklist', '/FI', 'PID eq %s' % pid, '/FO', 'CSV'],
                         capture_output=True, text=True).stdout
    return '"' in (out or '')


def main():
    reap = '--reap' in sys.argv
    pause = next((int(a) for a in sys.argv[1:] if a.isdigit()), 20)

    p1 = running_pids()
    time.sleep(pause)
    p2 = running_pids()

    stuck = []
    for cid, pid in p2.items():
        if not pid.isdigit():
            continue
        if p1.get(cid) != pid:
            continue                      # pid changed => spawn/rollover, leave alone
        if alive(pid):
            continue
        time.sleep(5)                     # third confirmation defeats timing races
        if not alive(pid):
            stuck.append(cid)

    for cid in stuck:
        print(cid)
    if reap:
        for cid in stuck:
            subprocess.run(['hermes', 'kanban', '--board', 'default', 'reclaim', cid],
                           capture_output=True, text=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
