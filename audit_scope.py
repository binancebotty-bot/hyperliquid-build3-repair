import json, collections, sys
base = 'art/'
d = json.load(open(base + 'REGRESSION_fa9d9f55ff.json'))
r = d['results']
risk = json.load(open(base + 'RISK_fa9d9f55.json'))
ids = [l.strip() for l in open(base + 'scope_clean.txt') if l.strip()]
rows = []
for i in ids:
    if i in r:
        ch = r[i]['checks'][0]
        det = (ch.get('detail') or '').strip()
        rows.append({'id': i, 'src': 'REGRESSION_fa9d9f55ff.json', 'category': r[i]['category'], 'check': ch['name'], 'detail': det, 'expected': r[i]['expected_behaviour']})
    else:
        rows.append({'id': i, 'src': 'RISK_fa9d9f55.json', 'category': 'risk', 'check': '(see RISK json checks)', 'detail': '(row-bound checks in RISK json)', 'expected': ''})
json.dump(rows, open(base + 'scope_extract.json', 'w'), indent=1)
empty = [x['id'] for x in rows if not x['detail']]
print('TOTAL', len(rows))
print('EMPTY-DETAIL', len(empty))
print(' '.join(empty))
det = collections.Counter(x['detail'] for x in rows)
shared = sorted([(k, v) for k, v in det.items() if v > 1], key=lambda x: -x[1])
print('SHARED-DETAIL GROUPS', len(shared))
for k, v in shared:
    who = [x['id'] for x in rows if x['detail'] == k]
    print(v, '|', k[:120])
    print('    ', ' '.join(who))
print('CHECKNAME-COLLISIONS')
cn = collections.Counter(x['check'] for x in rows)
for k, v in cn.items():
    if v > 1:
        print(v, '|', k, '|', ' '.join([x['id'] for x in rows if x['check'] == k]))
