#!/usr/bin/env python3
"""Seed a FRESH audit dir so a pair start cannot replay leader history.

Why this exists: with no state, Core's per-wallet leader cursor is absent
(clean_core_runtime_state.json -> last_leader_poll_cursor_ms), so Core:13526 takes the
`_cursor == 0` branch and starts the poll at now - POLL_WINDOW_MS (24 h), clamped at
Core:13537 to the retention floor (LEADER_POLL_RETENTION_MS = 100 min). On 2026-10-25 that
replayed ~100 minutes of ten active leaders as if it were live: 38,555 merged fills, 221 real
send attempts, 58 positions in 173 seconds.

What this writes, and nothing else:
  <state>/live_config.json               - the non-secret seed (roster, modes, global_controls)
  <state>/clean_core_runtime_state.json  - last_leader_poll_cursor_ms set for every wallet
The cursor is set to  T0 + overlap + one poll interval,  where T0 is the instance start, so that
Core's own formula  _start = max(_cursor - _overlap, retention_floor)  yields exactly T0.
Nothing before T0 can be fetched, and nothing after it is skipped by more than the overlap.

    python ops/seed_pair_state.py --state-dir DIR --seed ops/live_config_seed.json --start-ms T0
    python ops/seed_pair_state.py --dry-run ...        # prints the decision table, writes nothing
"""
import argparse
import json
import os
import sys
import time

KEEP = ('marketable_bps', 'max_asset_directional_exposure_usd', 'max_close_adverse_diff_pct',
        'max_daily_loss_usd', 'max_order_notional_usd', 'max_total_live_exposure_usd',
        'max_wallet_exposure_usd', 'send_mode', 'symbol_allowlist', 'symbol_blocklist')


def poll_interval_ms(seed):
    """Mirror Core's leader poll interval, from the env the launcher will use."""
    return int(os.getenv('HL_LIVE_LEADER_POLL_INTERVAL_SEC', '10')) * 1000


def overlap_ms():
    return int(os.getenv('HL_LIVE_LEADER_POLL_OVERLAP_MS', '30000'))


def select_start(cursor_ms, t0_ms, interval_ms, overlap, retention_ms):
    """Core:13525-13537, reproduced exactly so the seed can be checked without running Core."""
    if cursor_ms > 0:
        start = max(cursor_ms - overlap, t0_ms - retention_ms)
    else:
        start = max(0, t0_ms - 24 * 60 * 60 * 1000 - 5 * 60 * 1000)  # POLL_WINDOW_MS default
    return max(start, t0_ms - retention_ms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-dir', required=True)
    ap.add_argument('--seed', default='ops/live_config_seed.json')
    ap.add_argument('--start-ms', type=int, default=0)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    state = a.state_dir.rstrip('/')
    t0 = a.start_ms or int(time.time() * 1000)
    interval, overlap = poll_interval_ms(None), overlap_ms()
    retention = 100 * 60 * 1000
    cursor = t0 + overlap                    # so that cursor - overlap == t0 exactly: nothing before T0, nothing skipped
    start = select_start(cursor, t0, interval, overlap, retention)

    seed = json.load(open(a.seed, encoding='utf-8'))
    wallets = seed.get('wallets') or {}
    active = [w for w, v in wallets.items() if (v.get('mode') or '').upper() != 'OFF']
    missing_caps = [k for k in KEEP if k not in (seed.get('global_controls') or {})]

    print('SEED PLAN  (state=%s)' % state)
    print('  instance start T0      %d (%s)' % (t0, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t0 / 1000))))
    print('  overlap / interval     %d / %d ms' % (overlap, interval))
    print('  cursor written         %d  (T0 + overlap)' % cursor)
    print('  Core would start at    %d  -> %s  (== T0: %s)' % (
        start, time.strftime('%H:%M:%SZ', time.gmtime(start / 1000)), start == t0))
    print('  wallets in seed        %d (%d active)' % (len(wallets), len(active)))
    print('  caps present           %s' % ('YES' if not missing_caps else 'MISSING %s' % missing_caps))
    print('  send_mode              %s' % (seed.get('global_controls') or {}).get('send_mode'))

    # the decision table: every one of these fills is judged by the same rule Core uses
    probes = [t0 - 3_600_000, t0 - 60_000, t0 - 1, t0, t0 + 1, t0 + 60_000]
    print('  fill timestamps vs the computed start:')
    pre = 0
    for ts in probes:
        fetched = ts >= start
        if ts < t0 and fetched:
            pre += 1
        print('     %s  %s' % (time.strftime('%H:%M:%SZ', time.gmtime(ts / 1000)),
                               'FETCHED' if fetched else 'not fetched'))
    print('  PRE-START FILLS THAT WOULD BE FETCHED: %d' % pre)

    if a.dry_run:
        print('DRY RUN - nothing written. VERDICT=%s' % ('PASS' if pre == 0 and start == t0 else 'FAIL'))
        return 0 if pre == 0 and start == t0 else 1

    if missing_caps:
        print('REFUSING: the seed is missing cap keys %s - a seed without caps is not a seed' % missing_caps)
        return 2
    lock = os.path.join(state, 'instance.lock')
    cursors = os.path.join(state, 'clean_core_runtime_state.json')
    if os.path.exists(cursors) and not a.force:
        print('REFUSING: %s already exists, so this is not a fresh dir (--force to overwrite)' % cursors)
        return 3
    if os.path.exists(lock):
        print('REFUSING: %s exists - an engine is running against this dir' % lock)
        return 4

    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, 'live_config.json'), 'w', encoding='utf-8') as fh:
        json.dump(seed, fh, indent=2, sort_keys=True)
    seeded = {
        'last_leader_poll_cursor_ms': {w: cursor for w in wallets},
        'last_leader_poll_outage_gap_floor_ms': {},
        'seed': {'written_at_ms': int(time.time() * 1000), 't0_ms': t0,
                 'source': os.path.basename(a.seed)},
    }
    tmp = cursors + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(seeded, fh, indent=2, sort_keys=True)
    os.replace(tmp, cursors)
    print('  WROTE live_config.json (%d wallets) and clean_core_runtime_state.json (%d cursors)'
          % (len(wallets), len(seeded['last_leader_poll_cursor_ms'])))
    print('VERDICT=PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
