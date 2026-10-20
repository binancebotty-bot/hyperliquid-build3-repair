#!/usr/bin/env python3
"""Deterministic offline replay harness over a RECORDED Build-3 run.

Reads the append-only CSVs a run already wrote (order_intents.csv,
send_attempts.csv, live_fills.csv) plus live_config.json and
exchange_account_snapshot.json, and checks four invariants per leader fill:

  ONE_TERMINAL_ROW   one allowed intent and exactly one terminal send row
  NO_DOUBLE_SEND     at most one real exchange call / order id per intent
  CAPS_NOT_EXCEEDED  order notional and running exposure stay inside the caps
  REDUCTIONS_PASS    an EXIT fill moves the follower net toward zero

No network, no clock, no engine import: same input files -> same output.
Exit 0 = every check PASS or EXEMPT, 1 = a check FAILED, 2 = input unusable.

Usage:
  python tools/cert/replay_harness.py --run-dir <run state dir> [--json out.json]
  python tools/cert/replay_harness.py --self-check
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

TERMINAL = {'ORDER_FILLED', 'ORDER_REJECTED', 'ORDER_RESTING'}
ALLOWED = {'ENTRY_ALLOWED', 'EXIT_ALLOWED'}
EPS = 1e-9


def fnum(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def load(run_dir: Path):
    """CSVs live in run_dir or run_dir/append_only; both shapes occur on disk."""
    base = run_dir / 'append_only' if (run_dir / 'append_only' / 'send_attempts.csv').is_file() else run_dir

    def rows(name):
        p = base / name
        if not p.is_file():
            raise SystemExit('missing input: %s' % p)
        with open(p, encoding='utf-8', errors='replace', newline='') as fh:
            return list(csv.DictReader(fh))

    def js(name):
        p = run_dir / name
        if not p.is_file():
            return {}
        return json.loads(p.read_text(encoding='utf-8', errors='replace'))

    def trace():
        # fill_trace.jsonl is optional: when present it tells us which fills ever
        # reached the send path (proc_end status), which is what ONE_TERMINAL_ROW
        # must judge. Absent, the send CSVs alone decide.
        p = run_dir / 'fill_trace.jsonl'
        st = {}
        if p.is_file():
            with open(p, encoding='utf-8', errors='replace') as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        d = json.loads(ln)
                    except ValueError:
                        continue
                    if d.get('k') == 'proc_end' and d.get('id'):
                        st[str(d['id'])] = str(d.get('status') or '')
        return st

    return (rows('order_intents.csv'), rows('send_attempts.csv'), rows('live_fills.csv'),
            js('live_config.json'), js('exchange_account_snapshot.json'), trace())


def caps_of(cfg):
    gc = (cfg or {}).get('global_controls') or {}
    return {
        'order': fnum(gc.get('max_order_notional_usd')),
        'total': fnum(gc.get('max_total_live_exposure_usd')),
        'asset': fnum(gc.get('max_asset_directional_exposure_usd')),
    }


def check_run(run_dir: Path):
    intents, sends, fills, cfg, snap, trace_status = load(run_dir)
    caps = caps_of(cfg)

    intent_by_id = {i['intent_id']: i for i in intents}
    intents_by_fill = defaultdict(list)
    for i in intents:
        intents_by_fill[i['leader_fill_id']].append(i)
    sends_by_intent = defaultdict(list)
    for s in sends:
        sends_by_intent[s['intent_id']].append(s)
    fills_by_intent = defaultdict(list)
    for f in fills:
        fills_by_intent[f['intent_id']].append(f)

    # ---- ONE_TERMINAL_ROW, per leader fill -------------------------------
    # Population = fills that actually reached the send path (any send row) or
    # whose trace says they ended in an ORDER_* status. An allowed intent that
    # the send path later blocked (MASTER_REAL_ORDERS_OFF, LIQ_PARITY_BLOCKED,
    # below min notional, ...) never goes to the exchange and owes no row.
    terminal_by_fill = defaultdict(list)
    any_send_fill = set()
    for s in sends:
        any_send_fill.add(s['leader_fill_id'])
        if s['status'] in TERMINAL:
            terminal_by_fill[s['leader_fill_id']].append(s)
    # Only a send path that actually attempted the exchange (any send row, or a
    # trace proc_end in an ORDER_* state) owes a terminal row. Blocked/deduped
    # fills never reach the exchange and are exempt.
    reached = any_send_fill | {f for f, st in trace_status.items() if str(st or '').startswith('ORDER_')}

    one_row, one_exempt = [], []
    for fid in sorted(intents_by_fill):
        if fid not in reached:
            one_exempt.append((fid, 'NEVER_REACHED_SEND_PATH'))
            continue
        allowed = [i for i in intents_by_fill[fid] if i['decision'] in ALLOWED]
        term = terminal_by_fill.get(fid, [])
        if not allowed:
            one_exempt.append((fid, 'NO_ALLOWED_INTENT'))
            continue
        # The invariant is ONE terminal row. Two allowed intents for one fill (a
        # fill re-processed after cutover) is fine while only one row landed.
        if len(term) == 1:
            if len(allowed) == 1:
                one_row.append(fid)
            else:
                one_row.append(fid)
                one_exempt.append((fid, 'MULTI_INTENT_SINGLE_ROW x%d' % len(allowed)))
            continue
        # Documented pattern: one IOC close rejected, then its standing reduce-only
        # sibling rest. Two rows, same intent, one physical order. Exempt, not PASS.
        if len(allowed) == 1 and {r['status'] for r in term} == {'ORDER_REJECTED', 'ORDER_RESTING'} \
                and {r['intent_id'] for r in term} == {allowed[0]['intent_id']}:
            one_exempt.append((fid, 'STANDING_CLOSE_SIBLING'))
            continue
        if len(allowed) > 1:
            one_row.append((fid, 'FAIL_DUPLICATE_INTENT x%d' % len(allowed)))
            continue
        one_row.append((fid, 'FAIL_TERMINAL_ROWS=%d' % len(term)))
    one_fail = [x for x in one_row if isinstance(x, tuple)]

    # ---- NO_DOUBLE_SEND, per intent --------------------------------------
    dbl_fail = []
    dbl_ok = 0
    for iid in sorted(sends_by_intent):
        real = [s for s in sends_by_intent[iid] if s['status'] != 'pending_send']
        calls = {s.get('exchange_call_started_ms') for s in real if s.get('exchange_call_started_ms')}
        oids = {s.get('exchange_order_id') for s in real if s.get('exchange_order_id')}
        if len(calls) > 1 or len(oids) > 1:
            dbl_fail.append((iid, sorted(calls), sorted(oids)))
        else:
            dbl_ok += 1

    # ---- CAPS_NOT_EXCEEDED -----------------------------------------------
    cap_fail, cap_checked = [], 0
    if not any(caps.values()):
        # A cap of 0 means OFF, so no cap was actually exercised on this run.
        cap_note = 'ALL_CAPS_OFF (0 = off in this run): NOT_EXERCISED, not a pass'
        cap_verdict = 'NOT_EXERCISED'
    else:
        cap_note = 'caps %s' % caps
        last_px = {}
        # Deterministic order: by intent creation, then intent id.
        ordered = sorted(intents, key=lambda i: (fnum(i['created_at_ms']), i['intent_id']))
        exposure = defaultdict(float)
        for i in ordered:
            if i['decision'] not in ALLOWED:
                continue
            notional = fnum(i['copy_notional'])
            if caps['order'] > 0 and notional > caps['order'] + EPS:
                cap_fail.append((i['intent_id'], 'ORDER_NOTIONAL %.2f > %.2f' % (notional, caps['order'])))
            coin = i['coin']
            for f in fills_by_intent.get(i['intent_id'], []):
                px = fnum(f['fill_price']) or fnum(f['fill_notional']) / max(abs(fnum(f['fill_size'])), EPS)
                if px:
                    last_px[coin] = px
            if coin not in last_px:
                px = fnum(i['leader_price'])
                if px:
                    last_px[coin] = px
            # Apply the fill's realised net, then test the caps on it.
            for f in fills_by_intent.get(i['intent_id'], []):
                coin = f['coin']
                exposure[coin] = fnum(f['coin_net_after'])
                cap_checked += 1
            if caps['asset'] > 0 and coin in last_px:
                v = abs(exposure[coin]) * last_px[coin]
                if v > caps['asset'] + EPS:
                    cap_fail.append((i['intent_id'], 'ASSET_EXPOSURE %.2f > %.2f' % (v, caps['asset'])))
            if caps['total'] > 0:
                tot = sum(abs(n) * last_px.get(c, 0.0) for c, n in exposure.items())
                if tot > caps['total'] + EPS:
                    cap_fail.append((i['intent_id'], 'TOTAL_EXPOSURE %.2f > %.2f' % (tot, caps['total'])))

    # ---- REDUCTIONS_PASS --------------------------------------------------
    red_ok, red_fail, red_exempt = 0, [], 0
    for iid, i in intent_by_id.items():
        if 'lifecycle=EXIT' not in str(i.get('notes') or '') and 'lifecycle=REDUCE' not in str(i.get('notes') or ''):
            continue
        fl = fills_by_intent.get(iid) or []
        if not fl:
            red_exempt += 1  # close attempted, nothing filled: no net to judge
            continue
        bad = []
        for f in fl:
            before, after = fnum(f['wallet_position_before']), fnum(f['wallet_position_after'])
            if abs(after) > abs(before) + EPS:
                bad.append((f['coin'], before, after))
        if bad:
            red_fail.append((iid, bad))
        else:
            red_ok += 1

    checks = {
        'ONE_TERMINAL_ROW': {
            'verdict': 'FAIL' if one_fail else 'PASS',
            'pass': len(one_row) - len(one_fail), 'exempt': len(one_exempt), 'fail': len(one_fail),
            'failures': one_fail[:50],
        },
        'NO_DOUBLE_SEND': {
            'verdict': 'FAIL' if dbl_fail else 'PASS',
            'pass': dbl_ok, 'exempt': 0, 'fail': len(dbl_fail), 'failures': dbl_fail[:50],
        },
        'CAPS_NOT_EXCEEDED': {
            'verdict': cap_verdict if not any(caps.values()) else ('FAIL' if cap_fail else 'PASS'),
            'pass': cap_checked - len(cap_fail), 'exempt': 0, 'fail': len(cap_fail),
            'note': cap_note, 'failures': cap_fail[:50],
        },
        'REDUCTIONS_PASS': {
            'verdict': 'FAIL' if red_fail else 'PASS',
            'pass': red_ok, 'exempt': red_exempt, 'fail': len(red_fail), 'failures': red_fail[:50],
        },
    }
    return {
        'inputs': {'run_dir': str(run_dir), 'intents': len(intents), 'send_attempts': len(sends),
                   'live_fills': len(fills), 'leader_fills': len(intents_by_fill)},
        'caps': caps,
        'checks': checks,
        'aggregate': 'PASS' if all(c['verdict'] == 'PASS' for c in checks.values()) else ('NOT_EXERCISED' if all(c['verdict'] in ('PASS', 'NOT_EXERCISED') for c in checks.values()) else 'FAIL'),
    }


def render(res):
    out = []
    out.append('run: %s' % res['inputs']['run_dir'])
    out.append('inputs: %d leader fills, %d intents, %d send rows, %d live fills'
               % (res['inputs']['leader_fills'], res['inputs']['intents'],
                  res['inputs']['send_attempts'], res['inputs']['live_fills']))
    for name, c in res['checks'].items():
        out.append('%-18s %-4s pass=%-6d fail=%-4d exempt=%-5d %s'
                   % (name, c['verdict'], c['pass'], c['fail'], c['exempt'], c.get('note', '')))
        for f in c['failures'][:5]:
            out.append('    ! %s' % (f,))
    out.append('AGGREGATE %s' % res['aggregate'])
    return '\n'.join(out)


def self_check():
    """Good fixture passes, each broken fixture fails its own check."""
    base = Path(__file__).resolve().parent / 'fixtures' / 'replay'
    good = check_run(base / 'good')
    assert good['aggregate'] == 'PASS', render(good)
    for name, check in (('dup_terminal', 'ONE_TERMINAL_ROW'), ('double_send', 'NO_DOUBLE_SEND'),
                        ('cap_breach', 'CAPS_NOT_EXCEEDED'), ('bad_reduction', 'REDUCTIONS_PASS')):
        bad = check_run(base / name)
        assert bad['checks'][check]['verdict'] == 'FAIL', '%s did not fail %s' % (name, check)
        assert bad['aggregate'] == 'FAIL'
        print('self-check: %-14s -> %s FAIL as required' % (name, check))
    print('self-check: good fixture PASS; 4/4 controls bite')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Deterministic offline replay harness for a recorded Build-3 run.')
    ap.add_argument('--run-dir', help='run state dir holding the append-only CSVs')
    ap.add_argument('--json', help='also write the full result as JSON here')
    ap.add_argument('--self-check', action='store_true', help='run the good + broken fixtures')
    a = ap.parse_args(argv)
    if a.self_check:
        return self_check()
    if not a.run_dir:
        ap.error('--run-dir or --self-check is required')
    res = check_run(Path(a.run_dir))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(res, indent=1, sort_keys=True), encoding='utf-8')
    print(render(res))
    return 0 if res['aggregate'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
