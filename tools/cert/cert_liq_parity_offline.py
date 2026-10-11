#!/usr/bin/env python3
"""GAP-3 (liquidation parity vs the exchange `liquidationPx`) OFFLINE check.

Written by the free deepseek worker (deepseek-v4-flash-nosearch) from a fixed spec,
then reviewed in-session: the `math` import was unused and per-position lines leaked
into --json mode. Both fixed. See tools/cert/README.md for the split.

The live half of GAP-3 needs an open position and one exchange read each for the
follower (testnet, per dex) and the leaders (mainnet, read-only). This script does
the arithmetic on COPIES of those reads, so a captured run can be re-scored offline
and the parity rule can be regression-tested:

  safe_distance(coin)   = max over leaders of |mark - liquidationPx| / mark
                          (no liq price => 0.25, fully collateralised = the floor)
  follower_distance     = |mark - follower liquidationPx| / mark
  ratio                 = follower_distance / safe_distance
  PASS iff every checked position has ratio >= 1 (the follower is never closer to
  liquidation than the SAFEST leader), unchecked == 0, and checked >= --min-positions.

It also reports the GAP-3 wiring finding from the J4 spec as a non-gating line:
`exchange_reported_liquidation_px_used` is False until ExchangeReconciler.fetch_snapshot
starts writing `liquidation_px_by_coin`.

Inputs (read-only, all copies):
  --audit-dir DIR   containing mids.json, leader_states.json, follower_states.json,
                    exchange_account_snapshot.json, reconciliation.csv
                    (see tests/fixtures/liq_ok for the exact schemas)
Pass line (last line, exit 0):
  GAP3_RESULT:: PASS positions_checked=<n> unchecked=<m> worst_margin_ratio=<r>
FAIL exits 1; a missing input exits 3 with GAP3_RESULT:: INCONCLUSIVE_NO_DATA missing=<name>.

Offline: no network, no engine, no keys, no orders.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REQUIRED = (
    'leader_states.json',
    'follower_states.json',
    'mids.json',
    'exchange_account_snapshot.json',
    'reconciliation.csv',
)
FLOOR_DIST = 0.25


def load_json(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def position_distance(mark, liq):
    if mark is None or liq is None or mark <= 0 or liq <= 0:
        return FLOOR_DIST
    return abs(mark - liq) / mark


def collect_leader_distances(leader_states, mids):
    """coin -> safest (max) distance across all leaders."""
    safest = {}
    for _wallet, state in (leader_states or {}).items():
        for entry in (state or {}).get('assetPositions', []) or []:
            pos = entry.get('position', {}) if isinstance(entry, dict) else {}
            coin = pos.get('coin')
            if not coin:
                continue
            mark = to_float(mids.get(coin))
            liq = to_float(pos.get('liquidationPx'))
            dist = position_distance(mark, liq)
            if coin not in safest or dist > safest[coin]:
                safest[coin] = dist
    return safest


def first_follower_positions(follower_states):
    """Union by coin across follower dexes, keeping the FIRST occurrence."""
    by_coin = {}
    for _dex, state in (follower_states or {}).items():
        for entry in (state or {}).get('assetPositions', []) or []:
            pos = entry.get('position', {}) if isinstance(entry, dict) else {}
            coin = pos.get('coin')
            if not coin or coin in by_coin:
                continue
            by_coin[coin] = pos
    return by_coin


def count_liq_parity_blocked_rows(csv_path):
    blocked = 0
    with open(csv_path, 'r', encoding='utf-8', newline='') as fh:
        for row in csv.DictReader(fh):
            fields = (row.get('reject_category', ''), row.get('status', ''),
                      row.get('terminal_state', ''), row.get('event', ''))
            if any('LIQ_PARITY' in (f or '') for f in fields):
                blocked += 1
    return blocked


def check_positions(mids, leader_dist, follower_positions, min_positions, quiet=False):
    checked = 0
    unchecked = 0
    violations = []
    per_coin = []

    for coin in sorted(follower_positions):
        pos = follower_positions[coin]
        mark = to_float(mids.get(coin))
        liq = to_float(pos.get('liquidationPx'))
        safe = leader_dist.get(coin)

        if mark is None or mark <= 0 or liq is None or liq <= 0 or safe is None:
            unchecked += 1
            per_coin.append({'coin': coin, 'state': 'UNCHECKED'})
            if not quiet:
                print('%s %s <- UNCHECKED' % (coin, pos.get('szi')))
            continue

        checked += 1
        fdist = position_distance(mark, liq)
        ratio = fdist / safe if safe != 0 else 1.0
        violated = ratio < 1.0 - 1e-9
        per_coin.append({'coin': coin, 'state': 'CHECKED', 'ratio': ratio})
        if violated:
            violations.append(coin)
            if not quiet:
                print('%s ratio=%.6f <- VIOLATED' % (coin, ratio))
        elif not quiet:
            print('%s ratio=%.6f' % (coin, ratio))

    ratios = [e['ratio'] for e in per_coin if e.get('state') == 'CHECKED']
    worst = min(ratios) if ratios else 1.0
    passed = (not violations) and (checked >= min_positions) and (unchecked == 0)
    return {
        'checked': checked,
        'unchecked': unchecked,
        'worst': worst,
        'violations': violations,
        'per_coin': per_coin,
        'passed': passed,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline liquidation-parity check (GAP-3).')
    parser.add_argument('--audit-dir', required=True)
    parser.add_argument('--min-positions', type=int, default=1)
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args(argv)

    audit_dir = Path(args.audit_dir)

    for name in REQUIRED:
        if not (audit_dir / name).is_file():
            sys.stderr.write('SKIP: missing %s\n' % name)
            sys.stdout.write('GAP3_RESULT:: INCONCLUSIVE_NO_DATA missing=%s\n' % name)
            return 3

    mids = load_json(audit_dir / 'mids.json')
    leader_states = load_json(audit_dir / 'leader_states.json')
    follower_states = load_json(audit_dir / 'follower_states.json')
    snapshot = load_json(audit_dir / 'exchange_account_snapshot.json')

    liq_map = snapshot.get('liquidation_px_by_coin') if isinstance(snapshot, dict) else None
    exchange_liq_used = bool(liq_map)
    snapshot_keys = sorted(snapshot.keys()) if isinstance(snapshot, dict) else []
    blocked_rows = count_liq_parity_blocked_rows(audit_dir / 'reconciliation.csv')

    leader_dist = collect_leader_distances(leader_states, mids)
    follower_positions = first_follower_positions(follower_states)

    result = check_positions(mids, leader_dist, follower_positions, args.min_positions, quiet=args.as_json)

    if args.as_json:
        sys.stdout.write(json.dumps({
            'checked': result['checked'],
            'unchecked': result['unchecked'],
            'worst': result['worst'],
            'violations': result['violations'],
            'per_coin': result['per_coin'],
        }, sort_keys=True) + '\n')

    sys.stdout.write(
        'GAP3_GAP:: WIRING exchange_reported_liquidation_px_used=%s snapshot_keys=%s liq_parity_blocked_rows=%d\n'
        % (exchange_liq_used, snapshot_keys, blocked_rows)
    )
    verdict = 'PASS' if result['passed'] else 'FAIL'
    sys.stdout.write(
        'GAP3_RESULT:: %s positions_checked=%d unchecked=%d worst_margin_ratio=%.3f\n'
        % (verdict, result['checked'], result['unchecked'], result['worst'])
    )
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
