#!/usr/bin/env python3
"""A fresh pair start must never read before its anchor, and a restart must still recover its own misses.

FAILING FIRST: this file calls `leader_poll_start_ms` and `read_pair_start_anchor_ms`, which did not
exist before this branch, so it cannot even import against the previous Core. The behaviours it pins:

  (1) fresh seed with a future cursor: three cycles of starts all land on the anchor and the cursor
      never decreases - the backwards ratchet that walked 150 s per poll on 2026-10-25 cannot happen;
  (2) a restart whose cursor is older than live_start_ms but newer than the anchor STILL fetches the
      fills it missed - the anchor must not become a second live_start_ms;
  (3) a pre-cutover fill does not pin the cursor (leader_cursor_next ignores it), while a post-cutover
      fill still does.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

T0 = 1_792_974_130_657          # the 2026-10-25 pair start
INTERVAL, OVERLAP = 120_000, 30_000
RETENTION = 100 * 60 * 1000
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


# ---------------- (1) fresh seed, future cursor, three cycles
anchor = T0
cursor = T0 + INTERVAL + OVERLAP          # what the seeder writes
starts, cursors = [], [cursor]
now = T0 + 7_000                          # engine starts a few seconds after T0
for _ in range(3):
    start = C.leader_poll_start_ms(cursors[-1], now, INTERVAL, OVERLAP, RETENTION, anchor)
    starts.append(start)
    cursors.append(now)                   # a clean poll advances the cursor to now
    now += 113_000                        # next cycle
check('FRESH_SEED_NEVER_READS_BEFORE_THE_ANCHOR', all(s >= anchor for s in starts), starts)
check('FRESH_SEED_STARTS_LAND_ON_THE_ANCHOR', all(s == anchor for s in starts), starts)
# the first stored cursor is the seeded FUTURE value, so the first clean poll legitimately lowers it
# to now; from then on it must never go backwards, and it must never fall below the anchor
check('CURSOR_NEVER_DECREASES_AFTER_THE_FIRST_POLL',
      all(b >= a for a, b in zip(cursors[1:], cursors[2:])), cursors)
check('CURSOR_NEVER_FALLS_BELOW_THE_ANCHOR', all(c >= anchor for c in cursors[1:]), cursors)

# without the anchor the same sequence reproduces the ratchet - this is what was fixed
unanchored = []
cur = cursor
n = T0 + 7_000
for _ in range(3):
    unanchored.append(C.leader_poll_start_ms(cur, n, INTERVAL, OVERLAP, RETENTION, 0))
    cur, n = n, n + 113_000
check('WITHOUT_THE_ANCHOR_THE_RATCHET_IS_REPRODUCIBLE',
      unanchored[1] < unanchored[0], unanchored)

# ---------------- (2) a restart keeps its ability to recover missed fills
restart_anchor = T0
live_start = T0 + 3_600_000               # a later instance started an hour after the pair
restart_cursor = T0 + 1_800_000           # its own cursor: after the anchor, before live_start
restart_now = T0 + 3_660_000
rstart = C.leader_poll_start_ms(restart_cursor, restart_now, INTERVAL, OVERLAP, RETENTION, restart_anchor)
check('RESTART_FETCHES_ITS_MISSED_FILLS', rstart < restart_cursor and rstart <= restart_now, rstart)
check('RESTART_WINDOW_REACHES_BACK_PAST_LIVE_START', rstart < live_start, (rstart, live_start))
check('RESTART_STILL_RESPECTS_THE_ANCHOR', rstart >= restart_anchor, rstart)

# ---------------- (3) a pre-cutover fill must not pin the cursor
def cursor_owner(pending_ts, cutover):
    s = types.SimpleNamespace()
    s._queued_lock = __import__('threading').RLock()
    s._pending_ts = pending_ts
    s._deferred_lock = __import__('threading').RLock()
    s._deferred = {}
    s.dedupe = types.SimpleNamespace(live_start_ms=cutover)
    return s

cutover = T0 + 10_000
pre = {'k1': ('0xabc', T0 - 60_000)}       # a fill from before this instance could ever send
post = {'k2': ('0xabc', T0 + 60_000)}
proposed = T0 + 120_000
check('PRE_CUTOVER_FILL_DOES_NOT_PIN_THE_CURSOR',
      C.LiveCopyCore.leader_cursor_next(cursor_owner(pre, cutover), '0xabc', proposed) == proposed,
      C.LiveCopyCore.leader_cursor_next(cursor_owner(pre, cutover), '0xabc', proposed))
check('POST_CUTOVER_FILL_STILL_PINS_THE_CURSOR',
      C.LiveCopyCore.leader_cursor_next(cursor_owner(post, cutover), '0xabc', proposed) == T0 + 60_000,
      C.LiveCopyCore.leader_cursor_next(cursor_owner(post, cutover), '0xabc', proposed))

# ---------------- (4) the seeder writes the anchor, and verify-only requires it
state = Path(tempfile.mkdtemp(prefix='anchor_'))
seed_tool = HERE.parent.parent / 'ops' / 'seed_pair_state.py'
py = sys.executable
t = int(time.time() * 1000)
r = subprocess.run([py, str(seed_tool), '--state-dir', str(state), '--seed',
                    str(HERE.parent.parent / 'ops' / 'live_config_seed.json'),
                    '--start-ms', str(t)], capture_output=True, text=True)
anchor_file = state / 'PAIR_START_ANCHOR.json'
got = json.loads(anchor_file.read_text(encoding='utf-8')).get('t0_ms') if anchor_file.exists() else None
check('SEEDER_WRITES_THE_ANCHOR', r.returncode == 0 and got == t, got)
v = subprocess.run([py, str(seed_tool), '--state-dir', str(state), '--seed',
                    str(HERE.parent.parent / 'ops' / 'live_config_seed.json'), '--verify-only',
                    '--interval-sec', '1'], capture_output=True, text=True)
check('VERIFY_ONLY_PASSES_WITH_THE_ANCHOR', v.returncode == 0 and 'VERIFIED' in v.stdout, v.stdout[-120:])
anchor_file.unlink()
v2 = subprocess.run([py, str(seed_tool), '--state-dir', str(state), '--seed',
                     str(HERE.parent.parent / 'ops' / 'live_config_seed.json'), '--verify-only',
                     '--interval-sec', '1'], capture_output=True, text=True)
check('VERIFY_ONLY_FAILS_WITHOUT_THE_ANCHOR', v2.returncode == 22, v2.stdout[-120:])

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
