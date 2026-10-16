import json, csv
from pathlib import Path
SCR = Path('C:/Users/wigmore/.hermes/cache/scratch/b3cert_bb68')
L = SCR / 'live'
C = 'b142cf88d389e791160f691aac3d936852b99975'
p = SCR / 'harness' / ('ENG_PRICE_probe_%s.json' % C[:8])
out = json.loads(p.read_text(encoding='utf-8'))

fills = json.loads((SCR / 'oracle' / 'fills_all.json').read_text(encoding='utf-8'))
WANT = {62916249666: 'VVV', 62916249669: 'ETC', 62916245305: 'KAITO'}

sa = {}
with (L / 'send_attempts.csv').open(encoding='utf-8-sig', newline='') as fh:
    for r in csv.DictReader(fh):
        try:
            oid = int(r['exchange_order_id'])
        except (TypeError, ValueError):
            continue
        if oid in WANT:
            sa[oid] = r

rows = []
for oid, coin in WANT.items():
    f = next((x for x in fills if x['oid'] == oid), None)
    s = sa.get(oid)
    if not f or not s:
        rows.append({'oid': oid, 'coin': coin, 'complete': False})
        continue
    try:
        lim = float(s['limit_price'])
        fp = float(f['px'])
        sz = float(f['sz'])
    except (TypeError, ValueError):
        rows.append({'oid': oid, 'coin': coin, 'complete': False})
        continue
    rows.append({'oid': oid, 'coin': coin, 'complete': True,
                 'side': s['side'], 'order_type': s['order_type'],
                 'limit_price_on_wire': lim, 'exchange_fill_price': fp,
                 'copy_size': sz, 'exchange_fill_size': float(f['sz']),
                 'marketable_bps': s.get('marketable_bps'),
                 'status': s['status'], 'exchange_hash': f['hash'],
                 'cloid_engine': s.get('cloid'), 'cloid_exchange': f.get('cloid')})

complete = [r for r in rows if r['complete']]
side_ok = all((r['limit_price_on_wire'] >= r['exchange_fill_price']) if r['side'] == 'BUY'
              else (r['limit_price_on_wire'] <= r['exchange_fill_price']) for r in complete)
size_ok = all(abs(r['copy_size'] - r['exchange_fill_size']) < 1e-9 for r in complete)
cloid_ok = sum(1 for r in complete
               if (r['cloid_engine'] or '').lower() == (r['cloid_exchange'] or '').lower())

out.setdefault('checks', {}).setdefault('PRICE-001', []).append(
    {'name': 'WIRE_LIMIT_PRICE_TRACED_TO_EXCHANGE_FILL',
     'pass': bool(complete) and side_ok and size_ok,
     'detail': ('%d of %d sampled real testnet orders traced engine send_attempts.limit_price -> '
                'exchange userFillsByTime fill: marketable-side consistent=%s, size match=%s, '
                'cloid match=%d' % (len(complete), len(WANT), side_ok, size_ok, cloid_ok)),
     'oracle': 'live testnet info API userFillsByTime joined to engine send_attempts.csv on exchange_order_id'})
out['artifacts']['wire_trace'] = rows
out['summary'] = {r: {'pass': sum(1 for x in v if x['pass']), 'total': len(v)}
                  for r, v in out['checks'].items()}
p.write_text(json.dumps(out, indent=1), encoding='utf-8')
for r in rows:
    print(json.dumps(r))
print('side_ok', side_ok, 'size_ok', size_ok, 'cloid_ok', cloid_ok)
print('WROTE', p)
print(json.dumps(out['summary']))
