import json, csv, time, urllib.request
from pathlib import Path

WS = Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_f8fa9bf6')
FULL = 'http://127.0.0.1:8119'
SHORT = 'http://127.0.0.1:8121'


def api(base, path, payload=None):
    if payload is None:
        return json.load(urllib.request.urlopen(base + path, timeout=60))
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={'content-type': 'application/json'}, method='POST')
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return {'status': r.status, 'body': json.loads(r.read().decode() or '{}')}
    except Exception as e:
        b = ''
        try:
            b = e.read().decode()[:300]
        except Exception:
            pass
        return {'status': getattr(e, 'code', None), 'body': b, 'err': str(e)[:200]}


def numpath(s):
    out = []
    for pair in (s or '').split(' '):
        if not pair:
            continue
        x, y = pair.split(',')
        out.append((float(x), float(y)))
    return out


def maxdelta(a, b):
    if len(a) != len(b):
        return {'len_a': len(a), 'len_b': len(b), 'max_abs_delta': None}
    d = max((max(abs(p[0] - q[0]), abs(p[1] - q[1])) for p, q in zip(a, b)), default=0.0)
    return {'n': len(a), 'max_abs_delta': round(d, 9)}


def rows(name, base=None):
    p = (base or (WS / 'iso_full' / 'append_only')) / name
    with open(p, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


E = {}
full = json.loads((WS / 'probe_f8fa9bf6.json').read_text(encoding='utf-8'))
short = json.loads((WS / 'probe_short_f8.json').read_text(encoding='utf-8'))
payload = api(FULL, '/api/live-audit-summary')
dom = full['dom']
o = full['oracle']

E['graph'] = {
    'axis': {'dom': [dom['ymax'], dom['ymid'], dom['ymin']],
             'oracle': [o['ymax'], o['ymid'], o['ymin']],
             'match': [dom['ymax'], dom['ymid'], dom['ymin']] == [o['ymax'], o['ymid'], o['ymin']]},
    'exchange_path': maxdelta(numpath(dom['exchangePath']), numpath(o['exchange_pts'])),
    'realized_path': maxdelta(numpath(dom['realizedPath']), numpath(o['realized_pts'])),
    'drawdown_path': maxdelta(numpath(dom['drawdownPath']), numpath(o['drawdown_pts'])),
    'subtitle': dom['subtitle'],
    'points': o['n_points'], 'fills': o['n_fills'],
    'ticks': {'n_line': sum(1 for t in dom['ticks'] if t['tag'] == 'line'),
              'labels': [t['text'] for t in dom['ticks'] if t['tag'] == 'text'],
              'x': [t['x'] for t in dom['ticks'] if t['tag'] == 'line'],
              'expected_x': [round(58 + 918 * i / 4, 4) for i in range(5)]},
    'reset': full['reset'],
    'empty_instance': {'subtitle': short['dom']['subtitle'], 'points': short['dom']['exchangePath'],
                       'ymax': short['dom']['ymax'], 'ticks': len(short['dom']['ticks']),
                       'oracle_ok': short['oracle_ok']},
}

W = '0x1111111111111111111111111111111111111111'
atts = rows('send_attempts.csv')
intents = {r['intent_id']: r for r in rows('order_intents.csv')}
detail = []
for a in atts:
    if a.get('leader_wallet', '').lower() != W or a.get('status') != 'ORDER_FILLED':
        continue
    resp = json.loads(a.get('exchange_response') or '{}')
    fp = float(resp.get('fill_avg_px') or 0)
    sz = abs(float(resp.get('fill_size') or 0))
    it = intents.get(a.get('intent_id'), {})
    lp = float(it.get('leader_price') or 0)
    if fp <= 0 or lp <= 0:
        continue
    side = (a.get('side') or '').upper()
    du = (fp - lp) * sz if side == 'BUY' else (lp - fp) * sz
    detail.append({'attempt': a['attempt_id'], 'coin': a.get('coin'), 'side': side,
                   'fill': fp, 'leader': lp, 'size': sz,
                   'diff_usd': round(du, 6), 'bps': round(abs(fp - lp) / lp * 10000, 2)})

filled = [a for a in atts if a.get('leader_wallet', '').lower() == W and a.get('status') == 'ORDER_FILLED']
exits = [a for a in filled if str(a.get('reduce_only_sent')).lower() == 'true']
rej = [a for a in atts if a.get('leader_wallet', '').lower() == W and a.get('status') == 'ORDER_REJECTED']
E['exec'] = {'filled': len(filled), 'exits': len(exits), 'rejects_total': len(rej), 'dom_cell': dom['rows'][0]['cells'][5]}

fills = [r for r in rows('live_fills.csv') if r['leader_wallet'].lower() == W]
fills.sort(key=lambda r: r['created_at'])
st, realized, fees, series = {}, 0.0, 0.0, []
for r in fills:
    px, sz = float(r['fill_price']), abs(float(r['fill_size']))
    fees += float(r['fee'] or 0)
    pos, avg = st.get(r['coin'], (0.0, 0.0))
    delta = sz if r['side'].upper() == 'BUY' else -sz
    if abs(pos) < 1e-9 or pos * delta > 0:
        new = pos + delta
        avg = (avg * abs(pos) + px * abs(delta)) / abs(new)
        pos = new
    else:
        closed = min(abs(delta), abs(pos))
        realized += (px - avg) * closed * (1 if pos > 0 else -1)
        newp = pos + delta
        if abs(newp) < 1e-9:
            newp, avg = 0.0, 0.0
        elif newp * pos < 0:
            avg = px
        pos = newp
    st[r['coin']] = (pos, avg)
    series.append(round(realized - fees, 6))
peak = series[0]
dd = 0.0
mdd = 0.0
for v in series:
    peak = max(peak, v)
    dd = v - peak
    mdd = min(mdd, dd)
E['risk'] = {'realized': round(realized, 4), 'fees': round(fees, 4), 'net': round(realized - fees, 4),
             'series': series, 'drawdown': round(dd, 4), 'max_drawdown': round(mdd, 4),
             'open': {k: v[0] for k, v in st.items() if abs(v[0]) > 1e-9},
             'dom_cell': dom['rows'][0]['cells'][6]}
E['diff'] = {'fills': detail, 'total': round(sum(d['diff_usd'] for d in detail), 4),
             'avg': round(sum(d['diff_usd'] for d in detail) / len(detail), 4),
             'avg_bps': round(sum(d['bps'] for d in detail) / len(detail), 1),
             'worst_bps': round(max(d['bps'] for d in detail), 1),
             'dom_cell': dom['rows'][0]['cells'][4]}
E['wallets'] = [{'wallet': r['wallet'], 'cells': r['cells'], 'controls': r['controls']} for r in dom['rows']]
E['thead'] = dom['thead']
E['api_rows'] = [{'wallet': r['wallet'], 'mode': r['mode'], 'mode_label': r.get('mode_label'),
                  'net_pnl': r.get('net_pnl'), 'realized_pnl': r.get('realized_pnl'),
                  'unrealized_pnl': r.get('unrealized_pnl'), 'fees': r.get('fees'),
                  'total_diff_usd': r.get('total_diff_usd'), 'avg_diff_usd': r.get('avg_diff_usd'),
                  'avg_diff_bps': r.get('avg_diff_bps'), 'worst_diff_bps': r.get('worst_diff_bps'),
                  'filled_count': r.get('filled_count'), 'exits_count': r.get('exits_count'),
                  'recent_reject_count': r.get('recent_reject_count'),
                  'recent_block_count': r.get('recent_block_count'),
                  'current_exposure': r.get('current_exposure'),
                  'open_position_count': r.get('open_position_count'),
                  'drawdown': r.get('drawdown'), 'max_drawdown': r.get('max_drawdown'),
                  'last_fill': r.get('last_fill'), 'pnl_status': r.get('pnl_status'),
                  'pnl_status_label': r.get('pnl_status_label'),
                  'copy_mode': r.get('copy_mode'), 'norm_base': r.get('norm_base'),
                  'fixed_notional': r.get('fixed_notional'), 'ws_state': r.get('ws_state')}
                 for r in payload['live_wallet_rows']]
E['config'] = json.loads((WS / 'iso_full' / 'live_config.json').read_text(encoding='utf-8-sig'))
E['ws_health'] = json.loads((WS / 'iso_full' / 'live_ws_health.json').read_text(encoding='utf-8-sig'))

cfg_path = WS / 'iso_short' / 'live_config.json'
before = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
third = '0x3333333333333333333333333333333333333333'
r1 = api(SHORT, '/api/live-config/set-mode', {'wallet': third, 'mode': 'CLO'})
time.sleep(1.0)
after = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
live = api(SHORT, '/api/live-audit-summary')
mode_now = [x['mode'] for x in live['live_wallet_rows'] if x['wallet'].lower() == third]
r2 = api(SHORT, '/api/live-config/set-mode', {'wallet': third, 'mode': 'OFF'})
time.sleep(0.6)
restored = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
E['write_test'] = {'config_path': str(cfg_path), 'port': 8121,
                   'before': before['wallets'][third]['mode'],
                   'post': r1, 'after_file': after['wallets'][third]['mode'],
                   'api_mode_no_restart': mode_now,
                   'restore': r2, 'restored_file': restored['wallets'][third]['mode']}

(WS / 'final_evidence.json').write_text(json.dumps(E, indent=1), encoding='utf-8')
print('wrote final_evidence.json')
print('axis_match', E['graph']['axis']['match'])
print('paths', E['graph']['exchange_path'], E['graph']['realized_path'], E['graph']['drawdown_path'])
print('diff', E['diff']['total'], E['diff']['avg'], E['diff']['avg_bps'], E['diff']['worst_bps'], 'dom', E['diff']['dom_cell'])
print('exec', E['exec'])
print('risk', E['risk'])
print('write', E['write_test']['before'], E['write_test']['after_file'], E['write_test']['api_mode_no_restart'], E['write_test']['restored_file'])
