#!/usr/bin/env python3
'''MO#5 replay-cursor restart safety.

Four shapes must never skip or double-process a leader fill:
  ABSENT  - cursor state file missing
  CORRUPT - state file present but unparseable
  STALE   - cursor older than the catch-up window
  SAME-TS - page boundary inside a same-timestamp group larger than one page

Invariant: polled ids contain every outage fill, and no id twice.

Run: python test_core_replay_cursor_restart_safety.py   # RESULT:: markers, exit 0/1
'''
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix='mo5_replay_'))
os.environ.update({'HL_LIVE_AUDIT_DIR': str(TMP), 'HL_LEADER_NETWORK': 'testnet',
                   'HL_FOLLOWER_NETWORK': 'testnet', 'HL_LIVE_ENV_FILE': str(TMP / 'none.env')})

import HL_Live_Copy_Service_Core as c

W = '0x' + 'a1' * 20
PAGE = 2000
R = []


def ck(n, ok, d=''):
    R.append(bool(ok))
    print('RESULT::%s %s%s' % (n, 'PASS' if ok else 'FAIL', (' | ' + str(d)) if (d and not ok) else ''))


class _Rsp:
    def __init__(self, rows): self.rows = rows
    def json(self): return self.rows


class Ex:
    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda r: (r['time'], r['tid']))
        self.starts = []
    def post(self, url, json=None, timeout=None):
        st = int(json['startTime'])
        self.starts.append(st)
        return _Rsp([dict(r) for r in self.rows if r['time'] >= st][:PAGE])


def fill(tid, ts):
    return {'user': W, 'coin': 'ETH', 'side': 'B', 'px': '3000', 'sz': '0.01', 'time': ts, 'tid': tid}


def poll(rows, start_ms, end_ms):
    ex = Ex(rows)
    orig = c.requests
    c.requests = ex
    try:
        fills, status = c.LeaderFillIngestor().poll_hyperliquid_fills(W, start_ms, end_ms)
    finally:
        c.requests = orig
    return [f.leader_fill_id for f in fills], status, ex.starts


def no_skip_no_dup(name, rows, ids):
    want = {str(r['tid']) for r in rows}  # stable_leader_fill_id prefers raw['tid'] verbatim
    have = set(ids)
    ck(name + '_none_skipped', want <= have, 'missing=%d/%d' % (len(want - have), len(want)))
    ck(name + '_none_double_processed', len(ids) == len(have), 'returned=%d distinct=%d' % (len(ids), len(have)))


def start_for(cur):
    fn = getattr(c, 'leader_poll_start_ms', None)
    if fn is not None:
        return int(fn(cur)), True
    now = c.utc_now_ms()
    catchup = max(c.POLL_WINDOW_MS, int(os.getenv('HL_LIVE_POLL_MAX_CATCHUP_MS', str(7 * 86400000))))
    if cur > 0:
        return int(max(cur - c.LEADER_POLL_OVERLAP_MS, now - catchup)), False
    return int(max(0, now - c.POLL_WINDOW_MS - c.POLL_OVERLAP_MS)), False


def read_state():
    fn = getattr(c, 'load_json_checked', None)
    if fn is not None:
        return fn(c.CORE_RUNTIME_STATE_FILE)
    try:
        return c.load_json(c.CORE_RUNTIME_STATE_FILE, {}), False
    except Exception:
        return {}, False


def cur_of(state):
    if not isinstance(state, dict):
        return 0
    raw = state.get('last_leader_poll_cursor_ms')
    return int((raw or {}).get(W.lower(), 0)) if isinstance(raw, dict) else 0


def main():
    now = c.utc_now_ms()
    if c.CORE_RUNTIME_STATE_FILE.exists():
        c.CORE_RUNTIME_STATE_FILE.unlink()

    old = [fill(100 + i, now - 40 * 86400000 + i) for i in range(5)]
    recent = [fill(200 + i, now - 60000 + i) for i in range(5)]
    all_f = old + recent

    state, corrupt = read_state()
    ck('absent_state_not_corrupt', corrupt is False, corrupt)
    cur = cur_of(state)
    ck('absent_cursor_zero', cur == 0, cur)
    st, used = start_for(cur)
    print('NOTE::absent helper=%s start=%d' % (used, st))
    ids, status, _ = poll(all_f, st, now)
    no_skip_no_dup('absent', all_f, ids)
    ck('absent_status_ok', status == 'POLL_OK', status)

    c.CORE_RUNTIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    c.CORE_RUNTIME_STATE_FILE.write_text('{not json', encoding='utf-8')
    state, corrupt = read_state()
    ck('corrupt_state_reported', corrupt is True, corrupt)
    cur = cur_of(state)
    st, used = start_for(cur)
    print('NOTE::corrupt helper=%s start=%d' % (used, st))
    ids, status, _ = poll(all_f, st, now)
    no_skip_no_dup('corrupt', all_f, ids)
    ck('corrupt_status_ok', status == 'POLL_OK', status)

    gap = [fill(300 + i, now - 10 * 86400000 + i * 1000) for i in range(5)]
    stale = now - 10 * 86400000 - 1000
    catchup = max(c.POLL_WINDOW_MS, int(os.getenv('HL_LIVE_POLL_MAX_CATCHUP_MS', str(7 * 86400000))))
    ck('stale_cursor_is_stale', stale - c.LEADER_POLL_OVERLAP_MS < now - catchup)
    st, used = start_for(stale)
    print('NOTE::stale helper=%s start=%d' % (used, st))
    ck('stale_start_not_clamped_past_gap', st <= stale - c.LEADER_POLL_OVERLAP_MS + 1, st)
    ids, status, _ = poll(gap, st, now)
    no_skip_no_dup('stale', gap, ids)

    # 4a. a same-timestamp group that EXACTLY fills a page must still be read exactly once
    ts = now - 120000
    exact = [fill(500 + i, ts) for i in range(PAGE)]
    ids, status, starts = poll(exact, ts, now)
    no_skip_no_dup('same_ts_exact_page', exact, ids)
    ck('same_ts_exact_page_bounded', len(starts) <= c.POLL_MAX_PAGES_PER_WALLET, len(starts))

    # 4b. a group BIGGER than a page cannot be paged by userFillsByTime (time is the only cursor).
    # Prove the conservative consequence: it is reported stuck, never silently skipped or duplicated,
    # and the saved cursor does not move past it.
    over = [fill(9000 + i, ts) for i in range(PAGE + 1)]
    ids, status, starts = poll(over, ts, now)
    ck('same_ts_over_page_is_stuck', status == 'POLL_STUCK', status)
    ck('same_ts_over_page_no_dup', len(ids) == len(set(ids)), len(ids) - len(set(ids)))
    ck('same_ts_over_page_no_forward_skip', all(s <= ts for s in starts), starts[:3])
    adv = getattr(c, 'leader_cursor_advance', None)
    ck('same_ts_over_page_cursor_held', adv is None or adv('POLL_STUCK', [], now) == 0,
       adv and adv('POLL_STUCK', [], now))

    total = len(R)
    failed = sum(1 for r in R if not r)
    print('TOTAL=%d FAILED=%d' % (total, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
