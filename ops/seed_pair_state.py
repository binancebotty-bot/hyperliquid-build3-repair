#!/usr/bin/env python3
"""Seed a FRESH audit dir so a pair start cannot replay leader history.

Why this exists: with no state, Core's per-wallet leader cursor is absent
(clean_core_runtime_state.json -> last_leader_poll_cursor_ms), so Core:13526 takes the
`_cursor == 0` branch and starts the poll at now - POLL_WINDOW_MS (24 h), clamped at
Core:13537 to the retention floor (LEADER_POLL_RETENTION_MS = 100 min). On 2026-10-25 that
replayed ~100 minutes of ten active leaders as if it were live: 38,555 merged fills, 221 send
attempts, 58 positions in 173 seconds.

The arithmetic must mirror the engine EXACTLY, including the poll-interval term (Core:13519):
    _overlap_ms = interval_sec * 1000 + LEADER_POLL_OVERLAP_MS
    _start      = max(_cursor - _overlap_ms, _retention_floor)     if _cursor > 0
Getting this wrong is not cosmetic. Revision 1 of this file used LEADER_POLL_OVERLAP_MS alone and
printed "PRE-START FILLS: 0" on a cursor that left the engine reading one whole poll interval
BEFORE the instance start - a false green in the very check meant to catch it.

`leader_poll_interval_sec` varies (0 with WS off, 120 s with a healthy feed, down to ~5 s while
the feed is unacked, Core:12729-12741), so the cursor is written with the LARGEST plausible
interval. Then _start = cursor - actual_interval - overlap >= T0 for every smaller actual
interval, and no pre-start fill can be read whatever the engine resolves.

A second defence exists and this tool must not break it: the engine stamps live_start_ms at
construction (Core:11233-11234) and marks older fills PRE_CUTOVER_NOT_SENT (Core:12497, 12514).
That guard is what stopped the 25 Oct replay from sending after the first instance; a seed that
wrote a future live_start_ms would disable it, so this tool never writes that key.

    python ops/seed_pair_state.py --state-dir DIR --seed ops/live_config_seed.json --start-ms T0
    python ops/seed_pair_state.py --dry-run ...       # decision table, writes nothing
    python ops/seed_pair_state.py --verify-only ...   # inspect a seeded dir, writes nothing
"""
import argparse
import hashlib
import json
import os
import sys
import time

CHANGE_LOG = os.environ.get('PAIR_LAUNCH_LOG') or os.path.join(os.path.expanduser('~'), '.hermes', 'state', 'pair_launch.log')

KEEP = ('marketable_bps', 'max_asset_directional_exposure_usd', 'max_close_adverse_diff_pct',
        'max_daily_loss_usd', 'max_order_notional_usd', 'max_total_live_exposure_usd',
        'max_wallet_exposure_usd', 'send_mode', 'symbol_allowlist', 'symbol_blocklist')

RETENTION_MS = 100 * 60 * 1000                                          # Core:671
DEFAULT_INTERVAL_SEC = 120                                              # Core:12731
OVERLAP_MS = int(os.getenv('HL_LIVE_LEADER_POLL_OVERLAP_MS', '30000'))   # Core:668


def _sha(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def log_change(rec):
    """Every seed is a config change: append it, never rewrite the log."""
    os.makedirs(os.path.dirname(CHANGE_LOG), exist_ok=True)
    rec = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **rec}
    with open(CHANGE_LOG, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, sort_keys=True) + '\n')


def select_start(cursor_ms, t0_ms, interval_ms, overlap_ms, retention_ms=RETENTION_MS):
    """Core:13519 + Core:13525-13537, reproduced exactly, interval term included."""
    if cursor_ms > 0:
        start = max(cursor_ms - interval_ms - overlap_ms, t0_ms - retention_ms)
    else:
        start = max(0, t0_ms - 24 * 60 * 60 * 1000 - 5 * 60 * 1000)   # POLL_WINDOW_MS default
    return max(start, t0_ms - retention_ms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-dir', required=True)
    ap.add_argument('--seed', default='ops/live_config_seed.json')
    ap.add_argument('--start-ms', type=int, default=0)
    ap.add_argument('--interval-sec', type=int, default=DEFAULT_INTERVAL_SEC,
                    help='the LARGEST poll interval the engine may resolve (default 120)')
    ap.add_argument('--send-mode', choices=('off', 'close', 'on'), default='off',
                    help='send_mode written into the seeded config; OFF (observing only) is the default '
                         'and turning sending on is a separate, logged decision')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--verify-only', action='store_true',
                    help='check an already-seeded dir, write nothing, print VERIFIED')
    a = ap.parse_args()

    state = a.state_dir.rstrip('/' + os.sep)
    now_ms = int(time.time() * 1000)
    t0 = a.start_ms or now_ms
    interval_ms = max(0, a.interval_sec) * 1000
    cursor = t0 + interval_ms + OVERLAP_MS
    start = select_start(cursor, t0, interval_ms, OVERLAP_MS)

    seed_abs = os.path.abspath(a.seed)
    try:
        if os.path.commonpath([os.path.abspath(state), os.path.dirname(seed_abs)]) == os.path.abspath(state):
            print('REFUSING: the seed %s lives inside the state dir - the seed must survive the wipe it '
                  'protects against, so it lives outside any state dir' % seed_abs)
            return 5
    except ValueError:
        pass  # different drives cannot nest
    seed = json.load(open(seed_abs, encoding='utf-8'))
    seed.setdefault('global_controls', {})['send_mode'] = a.send_mode.upper()
    wallets = seed.get('wallets') or {}
    missing_caps = [k for k in KEEP if k not in (seed.get('global_controls') or {})]
    gc = seed.get('global_controls') or {}

    worst = cursor - OVERLAP_MS        # earliest read if the engine resolved interval 0
    early = t0 - worst                 # >0 means pre-start fills are reachable

    print('SEED PLAN  (state=%s)' % state)
    print('  instance start T0      %d (%s)' % (t0, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t0 / 1000))))
    print('  assumed max interval   %d ms  (engine may resolve any value <= this)' % interval_ms)
    print('  overlap constant       %d ms' % OVERLAP_MS)
    print('  cursor written         %d  (T0 + interval + overlap)' % cursor)
    print('  engine starts at       %s  (matches T0: %s)'
          % (time.strftime('%H:%M:%SZ', time.gmtime(start / 1000)), start == t0))
    print('  earliest read possible %s  (interval=0 case)' % time.strftime('%H:%M:%SZ', time.gmtime(worst / 1000)))
    print('  wallets in seed        %d' % len(wallets))
    print('  caps present           %s' % ('YES' if not missing_caps else 'MISSING %s' % missing_caps))
    print('  send_mode              %s  (flag --send-mode, wins over any auto_send_enabled key, Core:3885)'
          % (seed.get('global_controls') or {}).get('send_mode'))
    print('  PRE-START FILLS REACHABLE AT ANY INTERVAL <= ASSUMED: %d' % max(0, early // 1000))

    ok = (start == t0) and early <= 0
    if a.dry_run:
        print('DRY RUN - nothing written. VERDICT=%s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1

    if missing_caps:
        print('REFUSING: the seed is missing cap keys %s - a seed without caps is not a seed' % missing_caps)
        return 2

    cfg_path = os.path.join(state, 'live_config.json')
    cursors = os.path.join(state, 'clean_core_runtime_state.json')
    lock = os.path.join(state, 'instance.lock')

    if a.verify_only:
        if not (os.path.exists(cfg_path) and os.path.exists(cursors)):
            print('NOT VERIFIED: %s is missing' % (cfg_path if not os.path.exists(cfg_path) else cursors))
            return 6
        got = json.load(open(cursors, encoding='utf-8')).get('last_leader_poll_cursor_ms')
        if not isinstance(got, dict) or len(got) != len(wallets):
            print('NOT VERIFIED: cursor map is %s with %d entries for %d wallets'
                  % (type(got).__name__, len(got or {}), len(wallets)))
            return 7
        bad = [w for w, v in got.items() if not isinstance(v, int) or isinstance(v, bool) or v <= 0]
        if bad:
            print('NOT VERIFIED: %d cursor values are not positive ints (e.g. %s)' % (len(bad), bad[0]))
            return 7
        now_start = select_start(min(got.values()), now_ms, interval_ms, OVERLAP_MS)
        if now_start < now_ms - interval_ms - OVERLAP_MS:
            print('NOT VERIFIED: cursors are stale - the engine would start at %s, before now'
                  % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now_start / 1000)))
            return 7
        written = json.load(open(cfg_path, encoding='utf-8'))
        if written != seed:
            diff = [k for k in set(list(written) + list(seed)) if written.get(k) != seed.get(k)]
            print('NOT VERIFIED: the config in the state dir no longer equals the seed (differs in %s)' % diff)
            return 21
        print('  config sha256    %s (equals the seed)' % _sha(cfg_path))
        print('  cursors          %d wallets, engine would start %s'
              % (len(got), time.strftime('%H:%M:%SZ', time.gmtime(now_start / 1000))))
        print('VERIFIED')
        return 0

    if a.start_ms and not a.force:
        drift = now_ms - a.start_ms
        if drift > 120_000 or drift < -300_000:
            print('REFUSING: --start-ms is %+.0f s from now. Seed immediately before the engine start '
                  '(within 120 s), or the cursor sits in the past and the retention window reopens.'
                  % (drift / 1000.0))
            return 9
    if os.path.exists(cursors) and not a.force:
        print('REFUSING: %s already exists, so this is not a fresh dir (--force to overwrite)' % cursors)
        return 3
    if os.path.exists(lock):
        print('REFUSING: %s exists - an engine is running against this dir' % lock)
        return 4

    os.makedirs(state, exist_ok=True)
    prior_sha = _sha(cfg_path)
    tmp_cfg = cfg_path + '.tmp'
    with open(tmp_cfg, 'w', encoding='utf-8') as fh:
        json.dump(seed, fh, indent=2, sort_keys=True)
    if json.load(open(tmp_cfg, encoding='utf-8')) != seed:
        print('FAIL LOUD: the staged config does not parse back to the seed')
        return 8
    os.replace(tmp_cfg, cfg_path)

    seeded = {
        'last_leader_poll_cursor_ms': {w: cursor for w in wallets},
        'last_leader_poll_outage_gap_floor_ms': {},
        'seed': {'written_at_ms': now_ms, 't0_ms': t0, 'interval_ms': interval_ms,
                 'overlap_ms': OVERLAP_MS, 'source': os.path.basename(seed_abs)},
    }
    tmp_cur = cursors + '.tmp'
    with open(tmp_cur, 'w', encoding='utf-8') as fh:
        json.dump(seeded, fh, indent=2, sort_keys=True)
    os.replace(tmp_cur, cursors)

    if json.load(open(cfg_path, encoding='utf-8')) != seed:
        print('FAIL LOUD: the written config does not equal the seed')
        return 8
    written_sha = _sha(cfg_path)
    log_change({'state_dir': state, 'seed': seed_abs, 'seed_sha256': _sha(seed_abs),
                'config_sha_before': prior_sha, 'config_sha_after': written_sha,
                'send_mode': (seed.get('global_controls') or {}).get('send_mode'),
                'cursors_written': len(seeded['last_leader_poll_cursor_ms']), 't0_ms': t0,
                'interval_ms': interval_ms, 'overlap_ms': OVERLAP_MS})
    print('  config sha before/after  %s -> %s' % ((prior_sha or 'ABSENT')[:16], written_sha[:16]))
    print('  change log       %s' % CHANGE_LOG)
    print('  WROTE live_config.json (%d wallets) and clean_core_runtime_state.json (%d cursors)'
          % (len(wallets), len(seeded['last_leader_poll_cursor_ms'])))
    print('  send_mode written        %s' % (seed.get('global_controls') or {}).get('send_mode'))
    print('VERDICT=PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
