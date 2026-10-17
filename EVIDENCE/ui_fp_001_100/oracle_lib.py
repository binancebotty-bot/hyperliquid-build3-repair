"""Reusable oracle: given a snapshot dir, compute what the UI is supposed to show.
Mirrors the serving build's loaders/formulas. No app import, no HTTP.
"""
import csv, gzip, json, os, datetime, shutil


def _materialize(snap):
    '''Return a dir with plain append_only/*.csv, unpacking committed .gz if needed.'''
    ap = os.path.join(snap, 'append_only')
    if not os.path.isdir(ap):
        return snap
    need = [n for n in ('send_attempts.csv', 'order_intents.csv', 'live_fills.csv')
            if not os.path.exists(os.path.join(ap, n))]
    if not need:
        return snap
    out = os.path.join(snap, '_unpacked')
    os.makedirs(os.path.join(out, 'append_only'), exist_ok=True)
    for n in os.listdir(snap):
        s = os.path.join(snap, n)
        d = os.path.join(out, n)
        if n != 'append_only' and os.path.isfile(s) and not os.path.exists(d):
            shutil.copy2(s, d)
    for n in os.listdir(ap):
        s = os.path.join(ap, n)
        if n.endswith('.gz'):
            d = os.path.join(out, 'append_only', n[:-3])
            if not os.path.exists(d):
                with gzip.open(s, 'rb') as f, open(d, 'wb') as g:
                    shutil.copyfileobj(f, g)
        elif n.endswith('.csv'):
            d = os.path.join(out, 'append_only', n)
            if not os.path.exists(d):
                shutil.copy2(s, d)
    return out


def fnum(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def iso_ms(s):
    try:
        return int(datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp() * 1000)
    except Exception:
        return 0


def load_attempts(snap, limit):
    p = os.path.join(snap, 'append_only', 'send_attempts.csv')
    with open(p, newline='', encoding='utf-8', errors='replace') as f:
        rows = list(csv.DictReader(f))[-(limit * 4):]
    latest = {}
    for n, row in enumerate(rows):
        latest[str(row.get('attempt_id') or '') or ('row%d' % n)] = row
    out = []
    for row in list(latest.values())[-limit:]:
        r = dict(row)
        rt = str(row.get('exchange_response') or row.get('response') or '')
        if rt:
            try:
                resp = json.loads(rt)
                if not isinstance(resp, dict):
                    resp = {}
            except Exception:
                resp = {}
            pay = resp.get('payload') or {}
            for k in ('fill_avg_px', 'fill_size', 'oid', 'position_before', 'position_after',
                      'leader_price', 'limit_price', 'auto_send_wallet'):
                v = resp.get(k)
                if v is None:
                    v = pay.get(k)
                if v is not None:
                    r[k] = v
            side = resp.get('side') or pay.get('side') or row.get('side')
            if side:
                r['actual_side'] = side
        if 'oid' not in r and row.get('exchange_order_id'):
            r['oid'] = str(row['exchange_order_id'])
        out.append(r)
    return out


def load_intents(snap):
    p = os.path.join(snap, 'append_only', 'order_intents.csv')
    with open(p, newline='', encoding='utf-8', errors='replace') as f:
        return {str(r.get('intent_id')): r for r in csv.DictReader(f)}


def tail_csv(snap, name, limit):
    p = os.path.join(snap, 'append_only', name)
    with open(p, newline='', encoding='utf-8', errors='replace') as f:
        return list(csv.DictReader(f))[-limit:]


def compute(snap):
    snap = _materialize(snap)

    def L(n):
        return json.load(open(os.path.join(snap, n), encoding='utf-8-sig'))
    cfg, ws, man = L('live_config.json'), L('live_ws_health.json'), L('manual_live_positions.json')
    ex, hist = L('exchange_account_snapshot.json'), L('exchange_account_history.json')
    integ, svc = L('live_integrity_status.json'), L('live_service_state.json')
    metric = load_attempts(snap, 5000)
    intents = load_intents(snap)
    cutoff = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000) - 3600000

    wallets = cfg['wallets']
    perf = {}
    for k in wallets:
        perf[k.lower()] = {'filled': 0, 'exits': 0, 'rejected': 0, 'blocked': 0, 'previews': 0,
                           'recent_reject': 0, 'recent_block': 0, 'diff': [], 'lbps': [], 'fbps': [],
                           'friction': [], 'fees': 0.0}

    for a in metric:
        w = str(a.get('leader_wallet') or a.get('auto_send_wallet') or '').lower()
        if w not in perf:
            continue
        st = str(a.get('status') or '')
        if st == 'ORDER_FILLED':
            perf[w]['filled'] += 1
            px = fnum(a.get('fill_avg_px'))
            sz = fnum(a.get('fill_size'))
            side = str(a.get('actual_side') or a.get('side') or '').upper()
            if str(a.get('reduce_only', '')).lower() in ('1', 'true', 'yes'):
                perf[w]['exits'] += 1
            elif abs(fnum(a.get('position_after'))) < abs(fnum(a.get('position_before'))):
                perf[w]['exits'] += 1
            iid = str(a.get('intent_id') or '')
            it = intents.get(iid, {})
            lim = fnum(a.get('limit_price') or a.get('limit_px'))
            if lim == 0 and iid:
                lim = fnum(it.get('suggested_limit_price') or it.get('target_price'))
            fb = None
            if px > 0 and lim > 0:
                fb = round((px - lim) / lim * 10000 if side == 'BUY' else (lim - px) / lim * 10000, 2)
                perf[w]['fbps'].append(fb)
            lead = fnum(it.get('leader_price') or it.get('target_price') or it.get('suggested_limit_price'))
            du = db = None
            if px > 0 and lead > 0:
                b = (px - lead) / lead * 10000 if side == 'BUY' else (lead - px) / lead * 10000
                db = round(b, 2)
                perf[w]['lbps'].append(db)
                du = round((px - lead) * abs(sz) if side == 'BUY' else (lead - px) * abs(sz), 6)
                perf[w]['diff'].append(du)
            perf[w]['friction'].append({'time': a.get('created_at', ''), 'coin': a.get('coin', ''),
                                        'side': side, 'leader_px': lead or None, 'fill_px': px or None,
                                        'size': sz or None, 'diff_usd': du, 'diff_bps': db,
                                        'limit_px': lim or None, 'fill_vs_limit_bps': fb,
                                        'oid': a.get('oid', '')})
        elif st == 'ORDER_REJECTED':
            perf[w]['rejected'] += 1
            if iso_ms(a.get('created_at')) >= cutoff:
                perf[w]['recent_reject'] += 1
        elif st == 'CONFIRM_REQUIRED':
            perf[w]['previews'] += 1
        elif st:
            perf[w]['blocked'] += 1
            if iso_ms(a.get('created_at')) >= cutoff:
                perf[w]['recent_block'] += 1

    for r in tail_csv(snap, 'live_fills.csv', 500):
        w = str(r.get('leader_wallet') or '').lower()
        if w in perf:
            perf[w]['fees'] += fnum(r.get('fee'))

    for w, coins in (man.get('by_wallet') or {}).items():
        wl = w.lower()
        if wl not in perf:
            continue
        expo = 0.0
        n = 0
        for c, s in coins.items():
            sz = fnum(s.get('signed_size'))
            if abs(sz) <= 1e-12:
                continue
            n += 1
            expo += abs(sz) * fnum(s.get('avg_entry_px'))
        perf[wl]['sleeves'] = len(coins)
        perf[wl]['open_positions'] = n
        perf[wl]['row_exposure'] = round(expo, 2)

    for w, p in perf.items():
        p['total_diff_usd'] = round(sum(p['diff']), 4) if p['diff'] else None
        p['avg_diff_usd'] = round(sum(p['diff']) / len(p['diff']), 4) if p['diff'] else None
        p['avg_leader_bps'] = round(sum(p['lbps']) / len(p['lbps']), 1) if p['lbps'] else None
        p['worst_leader_bps'] = round(max(p['lbps']), 1) if p['lbps'] else None
        p['avg_fill_bps'] = round(sum(p['fbps']) / len(p['fbps']), 1) if p['fbps'] else None
        p['worst_fill_bps'] = round(max(p['fbps']), 1) if p['fbps'] else None
        p['fees'] = round(p['fees'], 2)

    raw = ex.get('raw') or {}
    msum = raw.get('marginSummary') or {}
    upnl = 0.0
    npos = 0
    ex_upnl = {}
    for a in (raw.get('assetPositions') or []):
        pp = (a or {}).get('position') or {}
        upnl += fnum(pp.get('unrealizedPnl'))
        if fnum(pp.get('szi')):
            npos += 1
        c = str(pp.get('coin') or '').upper()
        if c:
            ex_upnl[c] = {'mark_px': fnum(pp.get('markPx')), 'entry_px': fnum(pp.get('entryPx')),
                          'unrealized_pnl': fnum(pp.get('unrealizedPnl')),
                          'position_value': fnum(pp.get('positionValue')),
                          'signed_size': fnum(pp.get('szi'))}

    shared = {}
    for w, coins in (man.get('by_wallet') or {}).items():
        for c in coins:
            shared.setdefault(c.upper(), set()).add(w.lower())

    detail = {}
    for w, coins in (man.get('by_wallet') or {}).items():
        wl = w.lower()
        cur_expo = 0.0
        pos_rows = []
        for c, s in coins.items():
            signed = fnum(s.get('signed_size'))
            if abs(signed) <= 1e-12:
                continue
            cu = c.upper()
            coin_shared = len(shared.get(cu, set())) > 1
            e = ex_upnl.get(cu, {})
            mark = e.get('mark_px', 0.0)
            posval = e.get('position_value', 0.0)
            est = abs(signed) * mark if mark > 0 else posval
            cur_expo += est
            if coin_shared:
                match = 'AMBIGUOUS_COIN_SHARED'
            elif e:
                match = 'MATCH' if abs(e.get('signed_size', 0) - signed) <= 1e-8 else 'MISMATCH'
            else:
                match = 'EXCHANGE_UNAVAILABLE'
            pos_rows.append({'coin': cu, 'signed_size': signed,
                             'side': 'LONG' if signed > 0 else 'SHORT',
                             'entry_px': fnum(s.get('avg_entry_px')) or None,
                             'mark_px': mark or None,
                             'unrealized_pnl': e.get('unrealized_pnl') if e else None,
                             'exposure': round(est, 4) if est > 0 else None,
                             'exchange_match': match})
        detail[wl] = {'current_exposure': round(cur_expo, 4), 'positions': pos_rows}

    return {
        'header': {
            'wallets_total': len(wallets),
            'mode_LIVE': sum(1 for v in wallets.values() if str(v.get('mode', '')).upper() == 'LIVE'),
            'mode_CLO': sum(1 for v in wallets.values() if str(v.get('mode', '')).upper() == 'CLO'),
            'mode_OFF': sum(1 for v in wallets.values() if str(v.get('mode', '')).upper() == 'OFF'),
            'auto_send_enabled': bool(cfg.get('auto_send_enabled')),
            'ws_status': (ws.get('ws_summary') or {}).get('ws_status'),
            'ws_wallet_count': (ws.get('ws_summary') or {}).get('wallet_count'),
            'integrity_status': integ.get('status'),
            'active_wallets': svc.get('active_wallets'),
            'copy_account_status': svc.get('copy_account_status'),
            'master_real_orders_enabled': svc.get('master_real_orders_enabled'),
            'global_controls': cfg.get('global_controls'),
        },
        'account': {
            'portfolio_value': fnum(msum.get('accountValue'), None),
            'unrealized_pnl_sum': round(upnl, 6),
            'open_positions_asset': npos,
            'open_positions_by_coin': len(ex.get('positions_by_coin') or {}),
            'history_points': len(hist),
            'history_last_pv': hist[-1].get('portfolio_value') if hist else None,
            'history_first_pv': hist[0].get('portfolio_value') if hist else None,
            'realized_selected_last': hist[-1].get('realized_pnl_selected') if hist else None,
            'realized_label_last': hist[-1].get('realized_pnl_selected_label') if hist else None,
            'withdrawable': fnum(raw.get('withdrawable'), None),
        },
        'per_wallet': perf,
        'detail': detail,
        'exchange': ex_upnl,
        'positions_by_coin': ex.get('positions_by_coin') or {},
    }
