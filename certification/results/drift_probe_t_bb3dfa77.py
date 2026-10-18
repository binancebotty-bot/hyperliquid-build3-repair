import json, time, urllib.request, hashlib
U = 'http://127.0.0.1:8031/api/live-audit-summary'
def get():
    with urllib.request.urlopen(U, timeout=180) as r:
        b = r.read()
    return b, hashlib.sha256(b).hexdigest()
def rows(b):
    d = json.loads(b.decode('utf-8'))
    return (d.get('manual_reconciliation_rows') or []), d.get('cache_hit')
def key(r):
    w = str(r.get('wallet') or '')
    return (str(r.get('coin') or ''), (w[:10] + '...' + w[-6:]) if len(w) > 18 else w)
b1, h1 = get(); r1, c1 = rows(b1)
time.sleep(35)
b2, h2 = get(); r2, c2 = rows(b2)
m1 = {key(r): r for r in r1}
changed = []
for r in r2:
    k = key(r)
    a = m1.get(k)
    if a is None:
        changed.append({'k': k, 'why': 'row_absent_in_first'}); continue
    for f in ('manual_signed_size', 'exchange_signed_size', 'issue', 'side'):
        if a.get(f) != r.get(f):
            changed.append({'k': k, 'field': f, 'first': a.get(f), 'second': r.get(f)})
out = {'sha_first': h1, 'sha_second': h2, 'bytes_same': h1 == h2,
       'cache_hit_first': c1, 'cache_hit_second': c2,
       'rows_first': len(r1), 'rows_second': len(r2),
       'row_order_identical': [key(r) for r in r1] == [key(r) for r in r2],
       'changed_values': changed[:15], 'n_changed': len(changed), 'gap_seconds': 35}
print(json.dumps(out, indent=1)[:4000])
