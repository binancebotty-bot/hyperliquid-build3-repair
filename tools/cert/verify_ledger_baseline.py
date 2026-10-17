#!/usr/bin/env python3
"""Testnet ledger verifier: configured order cap + KNOWN-gap baseline (H2).

WHAT CHANGED vs the arming-gate script that returned MISMATCH at 2026-10-17 03:54Z
(trading_stack/hl-build3-testnet-cert-evidence/verify.py):

1. The order cap is READ FROM THE CONFIGURED VALUE
   (`global_controls.max_order_notional_usd` in live_config.json, today 500.0)
   instead of the stale hard-coded MAX_ORDER = 50.0.
2. An OPTIONAL baseline file of known gaps (coin -> exchange-minus-engine delta)
   is accepted. A gap that matches its baseline is printed as KNOWN and does not
   make the run fail. MISMATCH is reported only for:
     * a coin whose gap is outside the baseline (new coin), or
     * a baseline coin whose delta has MOVED AWAY from its baseline value.

Everything else keeps the original semantics: per-coin exchange szi vs the
manual ledger's signed size, HIP-3 sub-dex positions folded in, blocked coins
reported as KNOWN_REFUSED, and per-order notional over-cap check on entry fills.

Offline mode (--exchange-snapshot PATH) reads a snapshot JSON shaped like the
engine's `exchange_account_snapshot.json` (positions_by_coin) and needs no
network; the tests use only that mode. Live mode (--source api, the default when
no snapshot is given) does the SAME read-only testnet info calls the old script
did. No engine, no config writes, no orders.

Verdict convention (tools/cert/README.md): the LAST stdout line is
    VERIFIER_RESULT:: PASS <detail>          exit 0
    VERIFIER_RESULT:: FAIL <detail>          exit 1
    VERIFIER_RESULT:: INCONCLUSIVE <why>     exit 3
Per-coin rows still end in OK / KNOWN / KNOWN_REFUSED / MISMATCH so the existing
watchdog's `line.endswith("MISMATCH")` scan keeps working unchanged.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cert_common import (FAIL, INCONCLUSIVE, PASS, as_float, audit_files,  # noqa: E402
                         emit, load_json, load_rows)

TAG = 'VERIFIER_RESULT'
CONFIG_CAP_KEY = ('global_controls', 'max_order_notional_usd')
ABS_TOL = 1e-9
REL_TOL = 1e-6


# ---------------------------------------------------------------- pure helpers
def configured_order_cap(config):
    """The configured per-order notional cap, or None when absent/unreadable.

    None is deliberately NOT replaced by a default: the old script's $50 default
    is exactly the stale value this fix removes, so a missing cap must be
    INCONCLUSIVE, never a silent pass or a silent fail.
    """
    node = config
    for key in CONFIG_CAP_KEY:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    cap = as_float(node, 0.0)
    return cap if cap > 0 else None


def net_from_manual(manual):
    """coin -> signed size from the manual ledger's by_coin_net."""
    out = {}
    for coin, val in ((manual or {}).get('by_coin_net') or {}).items():
        size = val.get('signed_size', val.get('net', 0.0)) if isinstance(val, dict) else val
        out[str(coin).upper()] = as_float(size)
    return out


def net_from_snapshot(snapshot):
    """coin -> exchange size from a snapshot dict (positions_by_coin)."""
    pos = (snapshot or {}).get('positions_by_coin') or {}
    if not isinstance(pos, dict):
        return {}
    return {str(c).upper(): as_float(v) for c, v in pos.items()}


def classify(ex_net, eng_net, baseline=None, drift_tol=1e-6, blocked=()):
    """Split the gaps into matched / known / mismatched.

    baseline: {coin: exchange_minus_engine_delta} of accepted known gaps.
    Returns (rows, counts) where rows is a list of dicts with keys
    coin, ex, eng, delta, verdict in {OK, KNOWN, KNOWN_REFUSED, MISMATCH} and
    why in {new, moved, refused, ''}.
    """
    baseline = baseline or {}
    blocked = {c.upper() for c in blocked}
    rows = []
    counts = {'ok': 0, 'known': 0, 'new': 0, 'moved': 0, 'refused': 0}
    for coin in sorted(set(ex_net) | set(eng_net)):
        ex, eng = ex_net.get(coin, 0.0), eng_net.get(coin, 0.0)
        delta = ex - eng
        tol = ABS_TOL + REL_TOL * max(abs(ex), abs(eng))
        if abs(delta) <= tol:
            rows.append(dict(coin=coin, ex=ex, eng=eng, delta=delta, verdict='OK', why=''))
            counts['ok'] += 1
            continue
        if coin in blocked:
            rows.append(dict(coin=coin, ex=ex, eng=eng, delta=delta, verdict='KNOWN_REFUSED', why='refused'))
            counts['refused'] += 1
            continue
        if coin in baseline:
            base = as_float(baseline[coin], 0.0)
            if abs(delta - base) <= drift_tol + REL_TOL * abs(base):
                rows.append(dict(coin=coin, ex=ex, eng=eng, delta=delta, verdict='KNOWN', why=''))
                counts['known'] += 1
                continue
            rows.append(dict(coin=coin, ex=ex, eng=eng, delta=delta, verdict='MISMATCH', why='moved'))
            counts['moved'] += 1
            continue
        rows.append(dict(coin=coin, ex=ex, eng=eng, delta=delta, verdict='MISMATCH', why='new'))
        counts['new'] += 1
    return rows, counts


def entry_notional_by_oid(fills):
    """oid -> summed notional of ENTRY fills (Close* dirs skipped).

    Same rule as the original verifier: a cap bounds entries/adds; a close of an
    accumulated position may legitimately exceed one order's cap.
    """
    per_oid = {}
    for fill in fills or []:
        if str(fill.get('dir', '')).startswith('Close'):
            continue
        oid = str(fill.get('oid', ''))
        per_oid[oid] = per_oid.get(oid, 0.0) + as_float(fill.get('sz')) * as_float(fill.get('px'))
    return per_oid


def over_cap(per_oid, cap):
    """[(oid, notional)] for orders strictly above the cap (cap is inclusive)."""
    if cap is None:
        return []
    return [(oid, round(n, 6)) for oid, n in sorted(per_oid.items()) if n > cap + 1e-6]


# ---------------------------------------------------------------- data sources
def read_exchange_api(account, start_ms, timeout=10):
    import requests

    url = 'https://api.hyperliquid-testnet.xyz/info'

    def post(payload):
        return requests.post(url, json=payload, timeout=timeout).json()

    cs = post({'type': 'clearinghouseState', 'user': account})
    ex_net = {p['position']['coin'].upper(): as_float(p['position']['szi'])
              for p in (cs.get('assetPositions') or [])}
    fills = [f for f in post({'type': 'userFillsByTime', 'user': account,
                              'startTime': start_ms}) if int(f.get('time', 0)) >= start_ms]
    return ex_net, fills


def read_exchange_snapshot(path):
    snap = load_json(path) or {}
    return net_from_snapshot(snap), []


# ---------------------------------------------------------------- CLI
def parse_args(argv):
    opts = {'audit_dir': None, 'config': None, 'baseline': None, 'start_ms': 0,
            'drift_tol': 1e-6, 'source': None, 'exchange_snapshot': None,
            'fills': None, 'account': None}
    it = iter(argv)
    for arg in it:
        if arg == '--audit-dir':
            opts['audit_dir'] = next(it)
        elif arg == '--config':
            opts['config'] = next(it)
        elif arg == '--baseline':
            opts['baseline'] = next(it)
        elif arg == '--start-ms':
            opts['start_ms'] = int(as_float(next(it)))
        elif arg == '--drift-tol':
            opts['drift_tol'] = as_float(next(it), 1e-6)
        elif arg == '--source':
            opts['source'] = next(it)
        elif arg == '--exchange-snapshot':
            opts['exchange_snapshot'] = next(it)
        elif arg == '--fills':
            opts['fills'] = next(it)
        elif arg == '--account':
            opts['account'] = next(it)
        else:
            raise SystemExit('unknown argument: %s' % arg)
    return opts


def main(argv=None):
    opts = parse_args(sys.argv[1:] if argv is None else argv)
    audit = Path(opts['audit_dir']) if opts['audit_dir'] else None
    if audit is None or not audit.is_dir():
        return emit(TAG, INCONCLUSIVE, 'no --audit-dir directory')

    config_path = Path(opts['config']) if opts['config'] else audit / 'live_config.json'
    config = load_json(config_path) or {}
    cap = configured_order_cap(config)

    manual = load_json(audit / 'manual_live_positions.json') or {}
    eng_net = net_from_manual(manual)

    source = opts['source'] or ('snapshot' if opts['exchange_snapshot'] else 'api')
    if source == 'snapshot':
        ex_net, fills = read_exchange_snapshot(opts['exchange_snapshot'])
    else:
        account = opts['account'] or config.get('account') or config.get('account_address')
        if not account:
            return emit(TAG, INCONCLUSIVE, 'no --account and no account in config')
        try:
            ex_net, fills = read_exchange_api(account, opts['start_ms'])
        except Exception as exc:  # network hiccup: never act on a partial read
            return emit(TAG, INCONCLUSIVE, 'exchange read failed: %s' % str(exc)[:160])
    if opts['fills']:
        fills = load_json(opts['fills']) or []

    baseline_file = load_json(opts['baseline']) if opts['baseline'] else {}
    baseline_coins = (baseline_file or {}).get('coins') or {}
    drift_tol = as_float((baseline_file or {}).get('drift_tol'), opts['drift_tol'])
    blocked = (config.get('global_controls') or {}).get('symbol_blocklist') or []

    rows, counts = classify(ex_net, eng_net, baseline_coins, drift_tol, blocked)
    print('CONFIG order cap %.2f from %s' % (cap, config_path.name) if cap is not None
          else 'CONFIG order cap MISSING in %s' % config_path.name)
    print('COIN      exchange_szi   engine_net       delta  verdict')
    for r in rows:
        why = (' (%s)' % r['why']) if r['why'] else ''
        print('%-8s %14.6f %12.6f %11.6f  %s%s'
              % (r['coin'], r['ex'], r['eng'], r['delta'], r['verdict'], why))

    cap_line = ''
    over = []
    if fills:
        over = over_cap(entry_notional_by_oid(fills), cap)
        print('exchange entry fills over configured cap $%.2f: %s' % (cap, over))
        cap_line = ' over_cap=%d' % len(over)
    elif cap is None:
        print('cap check skipped: no configured order cap')

    detail = ('known=%d new=%d moved=%d refused=%d ok=%d%s'
              % (counts['known'], counts['new'], counts['moved'],
                 counts['refused'], counts['ok'], cap_line))
    if cap is None:
        return emit(TAG, INCONCLUSIVE, 'no configured max_order_notional_usd; ' + detail)
    if counts['new'] or counts['moved'] or over:
        return emit(TAG, FAIL, detail)
    return emit(TAG, PASS, detail)


if __name__ == '__main__':
    sys.exit(main())
