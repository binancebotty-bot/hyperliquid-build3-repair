#!/usr/bin/env python3
"""CC-1 M3 - independent read-only reconciliation oracle for Build 3 (a1acc28).

expected = target - actual - in_flight
  target    genuine post-baseline LEADER fills from the leader's own mainnet account
  actual    FRESH follower-master clearinghouseState across every DEX
  in_flight only PROVEN open orders (orderStatus == 'order'); an unreadable order
            makes the row UNRESOLVED, never in_flight = 0

Second implementation: imports no engine code (GUT I26 / VERIFY-008). Stdlib only,
read-only. CSV parsing and leader replay scaffolding reused from oracle_v1.
"""
import argparse, collections, csv, json, os, sys, time
from decimal import Decimal as D, getcontext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hl_readonly as hl

getcontext().prec = 40
AUD = 'C:/Users/wigmore/tmp/ui_iso_audit'
ST = 'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run19/state_20261027'

# 120 s: observed leader->follower gap p50 3.4 s, p90 5.3 s, p99 224 s. Kept short
# on purpose - calling a stuck copy PENDING is the false-green this oracle exists to catch.
PENDING_DELAY_MS = 120_000
# 5.00 USD: copy_mode fixed 12.00 USD per entry, so >40% of a copy unit; not dust.
MATERIAL_USD = D('5.00')
EPS = D('0.000001')


def rd(p):
    with open(p, newline='', encoding='utf-8', errors='replace') as fh:
        return list(csv.DictReader(fh))


def iv(s):
    if s is None or str(s).strip() in ('', '0'):
        return None
    try:
        return int(float(str(s).strip()))
    except ValueError:
        return None


def dec(s, d=None):
    if s is None or str(s).strip() == '':
        return d
    try:
        return D(str(s).strip())
    except Exception:
        return d


def q4(x):
    return None if x is None else str(x.quantize(D('0.0001')))


def k(c):
    return (c or '').lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audit', default=AUD)
    ap.add_argument('--state', default=ST)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runs'))
    ap.add_argument('--follower')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())

    intents = rd(os.path.join(a.audit, 'append_only', 'order_intents.csv'))
    fills = rd(os.path.join(a.audit, 'append_only', 'live_fills.csv'))
    intents.sort(key=lambda r: iv(r['created_at_ms']) or 0)
    fills.sort(key=lambda r: iv(r['created_at_ms']) or 0)
    wcfg = json.load(open(os.path.join(a.audit, 'live_config.json'), encoding='utf-8')).get('wallets') or {}

    runtime = {}
    for nm in ('clean_core_runtime_state.json', 'live_service_state.json'):
        p = os.path.join(a.state, nm)
        if os.path.exists(p):
            runtime = json.load(open(p, encoding='utf-8'))
            if runtime.get('copy_account_baseline_at_ms'):
                break
    baseline = iv(runtime.get('copy_account_baseline_at_ms'))
    if not baseline:
        sys.exit('no copy baseline in state dir')
    acct = a.follower or json.load(open(os.path.join(a.state, 'exchange_account_snapshot_app.json'),
                                        encoding='utf-8')).get('account_address')
    if not acct:
        sys.exit('no follower master address')

    # leader rows: one row per leader fill (earliest receipt row wins)
    lrows = {}
    for r in intents:
        lrows.setdefault(r['leader_fill_id'], r)
    lrows = list(lrows.values())

    lc, lmeta, lnow, lerr = {}, {}, collections.defaultdict(dict), collections.defaultdict(list)
    for w in sorted({r['leader_wallet'] for r in lrows if r.get('leader_wallet')}):
        try:
            lf, pages, capped = hl.leader_fills(w, baseline, hl.MAINNET)
            lmeta[w] = {'pages': pages, 'fills': len(lf), 'capped': capped, 'error': None}
        except Exception as e:
            lmeta[w] = {'pages': 0, 'fills': 0, 'capped': False, 'error': str(e)[:160]}
            lf = []
        for c, st in hl.replay(lf).items():
            lc[(w, c)] = st
        try:
            lp, _o, rep = hl.read_positions(w, hl.MAINNET)
            for c, s in lp.items():
                lnow[w][k(c)] = s
            for f in rep['dexes_failed']:
                lerr[w].append('%s: %s' % (f['dex'], f['error']))
        except Exception as e:
            lerr[w].append('all: %s' % str(e)[:120])

    pos, orders, dexrep = hl.read_positions(acct, hl.TESTNET)
    proven = hl.prove_orders(orders, acct, hl.TESTNET)
    pos_by = {k(c): s for c, s in pos.items()}
    inf, det, unk = collections.defaultdict(D), collections.defaultdict(list), []
    for o in proven:
        c = k(o.get('coin'))
        sz = o.get('sz') or D(0)
        sg = -sz if o.get('side') == 'A' else sz
        if o.get('status') == 'order':
            inf[c] += sg
            det[c].append({'dex': o['dex'] or '(default)', 'oid': o['oid'], 'cloid': o.get('cloid'),
                           'signed_sz': str(sg), 'status': 'order'})
        else:
            x = dict(o); x['signed_sz'] = str(sg); x['proven'] = False
            unk.append(x)
            det[c].append({'dex': o['dex'] or '(default)', 'oid': o['oid'], 'cloid': o.get('cloid'),
                           'status': o.get('status') or o.get('status_error'), 'proven': False})

    px = {k(x): v for x, v in hl.price_map(hl.TESTNET, 'xyz').items()}
    lfpx = {}
    for r in fills:
        pv = dec(r.get('fill_price'))
        if pv:
            lfpx[k(r['coin'])] = pv

    fol = collections.defaultdict(list)
    pairs = set()
    for r in fills:
        fol[(r['leader_wallet'], r['coin'])].append(r)
        pairs.add((r['leader_wallet'], r['coin']))
    for r in lrows:
        pairs.add((r['leader_wallet'], r['coin']))

    now = int(time.time() * 1000)
    rows = []
    for w, coin in sorted(pairs):
        ck = k(coin)
        act, infc = pos_by.get(ck, D(0)), inf.get(ck, D(0))
        p = px.get(ck) or lfpx.get(ck)
        fr = fol.get((w, coin), [])
        u = abs(dec(fr[-1].get('fill_size'), D(0))) if fr else None
        wc = wcfg.get(w) or {}
        miss, sub, src = [], '', ''
        target = tunits = None

        lm = lmeta.get(w) or {}
        if lm.get('error'):
            miss.append('leader fills unreadable for %s: %s' % (w[:10], lm['error']))
        elif lm.get('capped'):
            miss.append('leader fill history hit the page cap for %s' % w[:10])
        if lerr.get(w):
            miss.append('leader live position unreadable on %d mainnet DEX(s): %s'
                        % (len(lerr[w]), ';'.join(lerr[w])[:160]))

        st = lc.get((w, coin))
        pbn = st['net'] if st else D(0)
        ln = lnow.get(w, {}).get(ck)
        if not miss:
            if pbn is None:
                miss.append('leader fill rows for %s carry no usable sz' % coin)
            elif ln is None:
                # absent from every leader DEX == leader flat on the exchange now
                target = D(0)
                src = ('leader flat on live mainnet position (post-baseline fills netted %s)' % pbn
                       if pbn else 'leader flat on live mainnet position')
            elif pbn != 0 and (pbn > 0) != (ln > 0):
                miss.append('contradictory leader direction: post-baseline fills net %s but the '
                            'live mainnet position is %s' % (pbn, ln))
            else:
                # fixed-notional copying copies direction and open/closed only, so the live
                # leader position fixes the target state; fills corroborate it
                target = ln
                if pbn == 0:
                    src = 'live mainnet leader position, no post-baseline fill (pre-baseline inventory)'
                elif pbn == ln:
                    src = 'live mainnet leader position == post-baseline leader net'
                else:
                    src = ('live mainnet leader position; post-baseline net %s same sign '
                           '(pre-baseline inventory)' % pbn)

        if dexrep['dexes_failed']:
            miss.append('%d follower DEX unreadable: %s' % (
                len(dexrep['dexes_failed']),
                ','.join(sorted({x['dex'] for x in dexrep['dexes_failed']}))[:180]))
        mine = [o for o in unk if k(o.get('coin')) == ck]
        if mine:
            miss.append('%d open order(s) on %s with UNKNOWN CLOID/orderStatus: %s' % (
                len(mine), coin, '; '.join('%s oid %s status=%s' % (o['dex'], o['oid'],
                                                                   o.get('status') or o.get('status_error'))
                                           for o in mine)[:200]))
        if target is not None and target != 0:
            if u:
                tunits = (D(1) if target > 0 else D(-1)) * u
            else:
                miss.append('no follower fill on this pair, copy unit cannot be sized')

        exp = dl = dusd = ausd = None
        if target is not None and tunits is not None:
            exp = tunits - act - infc
            dl = -exp
            dusd = abs(dl) * p if p else None
            ausd = abs(act) * p if p else None
        mat = dusd is not None and dusd >= MATERIAL_USD

        if miss:
            label = 'UNRESOLVED'
        elif target == 0:
            if abs(act) < EPS and abs(infc) < EPS:
                label = 'OK'
            elif ausd is None or ausd >= MATERIAL_USD:
                label, sub = 'LOST_OBLIGATION', 'leader_flat_follower_holds'
            else:
                label, sub = 'OK', 'leader_flat_follower_dust_residual'
        else:
            gap = now - (st['last_ms'] if st else 0)
            hold = abs(act + infc) * (p or D(1)) >= MATERIAL_USD
            if not hold:
                label = 'PENDING' if gap <= PENDING_DELAY_MS else 'LOST_OBLIGATION'
                sub = '' if label == 'PENDING' else 'leader_open_follower_never_opened'
            elif (act + infc) * tunits < 0:
                label, sub = 'LOST_OBLIGATION', 'sign_inversion'
            elif mat:
                label, sub = 'LOST_OBLIGATION', 'quantity_short_of_one_unit'
            else:
                label = 'OK'

        rows.append({'wallet': w, 'coin': coin,
                     'target': None if target is None else str(target), 'target_source': src,
                     'target_units': None if tunits is None else str(tunits),
                     'actual': str(act), 'in_flight': str(infc),
                     'expected': None if exp is None else str(exp),
                     'delta': None if dl is None else str(dl),
                     'price': None if p is None else str(p),
                     'actual_usd': q4(ausd), 'delta_usd': q4(dusd),
                     'label': label, 'subclass': sub,
                     'leader_postbaseline_net': None if pbn is None else str(pbn),
                     'leader_fill_count': st['n'] if st else 0,
                     'leader_last_fill_ms': st['last_ms'] if st else None,
                     'leader_live_pos': None if ln is None else str(ln),
                     'follower_fill_count': len(fr),
                     'wallet_mode': wc.get('mode'), 'wallet_enabled': wc.get('enabled'),
                     'missing_input': ' | '.join(miss),
                     'in_flight_detail': json.dumps(det.get(ck, []))[:600]})

    counts = collections.Counter(r['label'] for r in rows)
    subs = collections.Counter('%s/%s' % (r['label'], r['subclass'] or '-') for r in rows)
    causes = collections.Counter((r['missing_input'] or '').split(' | ')[0][:110]
                                 for r in rows if r['label'] == 'UNRESOLVED')
    meta = {'run_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'build3_live_commit': 'a1acc28', 'audit_dir': a.audit, 'state_dir': a.state,
            'baseline_ms': baseline, 'follower_master': acct[:6] + '...' + acct[-4:],
            'params': {'PENDING_DELAY_MS': PENDING_DELAY_MS,
                       'MATERIAL_USD': str(MATERIAL_USD), 'EPS': str(EPS)},
            'follower_dex_report': dexrep, 'orders_total': len(proven),
            'orders_proven': sum(1 for o in proven if o.get('status') == 'order'),
            'orders_unknown_status': len(unk), 'unknown_order_detail': unk,
            'leader_fill_wallets': lmeta,
            'leader_live_position_errors': {x: y for x, y in lerr.items() if y},
            'pairs': len(rows), 'counts': dict(counts), 'subcounts': dict(subs),
            'unresolved_causes': dict(causes)}
    base = os.path.join(a.out, 'm3_oracle_%s' % stamp)
    json.dump({'meta': meta, 'rows': rows}, open(base + '.json', 'w', encoding='utf-8'), indent=1, default=str)
    with open(base + '.csv', 'w', newline='', encoding='utf-8') as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    cols = ['wallet', 'coin', 'target', 'actual', 'in_flight', 'expected', 'delta', 'label', 'missing_input']
    with open(base + '.md', 'w', encoding='utf-8') as fh:
        fh.write('# CC-1 M3 oracle - %s\n\n' % meta['run_at_utc'])
        fh.write('build3 live commit `a1acc28`; %d wallet/coin pairs; follower master `%s`; '
                 'baseline_ms `%s`.\n\n' % (len(rows), meta['follower_master'], baseline))
        fh.write('DEXs read %d, failed %d, with positions %s. Open orders %d, proven %d, '
                 'UNKNOWN status %d.\n\n' % (len(dexrep['dexes_read']), len(dexrep['dexes_failed']),
                                             dexrep['dexes_with_positions'], len(proven),
                                             meta['orders_proven'], len(unk)))
        fh.write('Thresholds: MATERIAL_USD %s, PENDING_DELAY_MS %d, EPS %s.\n\n'
                 % (MATERIAL_USD, PENDING_DELAY_MS, EPS))
        fh.write('| label | n |\n|---|---|\n')
        for x, n in sorted(counts.items(), key=lambda y: -y[1]):
            fh.write('| %s | %d |\n' % (x, n))
        fh.write('\n| label/subclass | n |\n|---|---|\n')
        for x, n in sorted(subs.items(), key=lambda y: -y[1]):
            fh.write('| %s | %d |\n' % (x, n))
        fh.write('\n## every wallet/coin pair\n\n| ' + ' | '.join(cols) + ' |\n|'
                 + '---|' * len(cols) + '\n')
        for r in rows:
            fh.write('| ' + ' | '.join('' if r[c] is None else str(r[c]) for c in cols) + ' |\n')

    print(json.dumps({'counts': dict(counts), 'subcounts': dict(subs), 'pairs': len(rows),
                      'orders_total': len(proven), 'orders_proven': meta['orders_proven'],
                      'orders_unknown': len(unk), 'dexes_read': len(dexrep['dexes_read']),
                      'dexes_failed': len(dexrep['dexes_failed']),
                      'dexes_with_positions': dexrep['dexes_with_positions'], 'out': base}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
