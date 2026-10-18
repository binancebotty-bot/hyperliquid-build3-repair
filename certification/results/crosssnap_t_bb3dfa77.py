import json, urllib.request, hashlib
P = 'C:/Users/wigmore/.hermes/cache/scratch/b3_cert13/certification/results/UI_LCC_AUD_REC_WS_capture_t_bb3dfa77.json'
d = json.load(open(P, encoding='utf-8'))
dom = d['rendered_recon_rows']
D = '\u2014'
def js(v):
    if v is None: return ''
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, float): return str(int(v)) if v == int(v) else repr(v)
    return str(v)
def sw(w):
    s = js(w)
    return s[:10] + '...' + s[-6:] if len(s) > 18 else (s or 'ACCOUNT_LEVEL_ONLY')
def man(r):
    return (js(r.get('side') or '') + ' ' + js(D if r.get('manual_signed_size') is None else r['manual_signed_size'])).strip()
def exc(r):
    return js(D if r.get('exchange_signed_size') is None else r['exchange_signed_size'])
def iss(r):
    return js(r.get('issue') or 'n/a')
with urllib.request.urlopen('http://127.0.0.1:8031/api/live-audit-summary', timeout=180) as r:
    body = r.read()
live = json.loads(body.decode('utf-8'))
src = live.get('manual_reconciliation_rows') or []
sha = hashlib.sha256(body).hexdigest()
out = {'live_sha': sha, 'live_rows': len(src), 'dom_rows': len(dom), 'live_cache_hit': live.get('cache_hit'), 'dom_capture_sha': d['payload_sha256'], 'same_payload': sha == d['payload_sha256']}
for name, fn, i in (('issue', iss, 3), ('manual', man, 4), ('exchange', exc, 5)):
    out['cross_pos_' + name] = sum(1 for s, r in zip(src, dom) if len(r) > i and r[i] == fn(s))
m = {}
for s in src:
    m.setdefault((js(s.get('coin') or D), sw(s.get('wallet'))), []).append(s)
for name, fn, i in (('issue', iss, 3), ('manual', man, 4), ('exchange', exc, 5)):
    n = 0
    bad = []
    for r in dom:
        k = (r[1], r[2])
        if any(fn(s) == r[i] for s in m.get(k, [])):
            n += 1
        else:
            bad.append({'dom': r[1:6], 'live': [[iss(s), man(s), exc(s)] for s in m.get(k, [])]})
    out['cross_keyed_' + name] = n
    out['cross_bad_' + name] = bad[:8]
m2 = {}
for s in src:
    m2.setdefault((js(s.get('coin') or D), sw(s.get('wallet')), js(s.get('side'))), []).append(s)
n2 = 0
bad2 = []
for r in dom:
    k = (r[1], r[2], (r[4] or '').split(' ')[0])
    if any(man(s) == r[4] for s in m2.get(k, [])):
        n2 += 1
    else:
        bad2.append({'dom': r[1:6], 'live': [[js(s.get('side')), man(s)] for s in m2.get(k, [])]})
out['cross_keyed_manual_side'] = n2
out['bad_manual_side'] = bad2[:8]
out['order_identical'] = [js(s.get('coin') or D) + '|' + sw(s.get('wallet')) for s in src] == [r[1] + '|' + r[2] for r in dom]
print(json.dumps(out, indent=1)[:7000])
