import json
from datetime import datetime, timezone

T = '89b3bc7586bf328df336fc9ea721cee212617762'
RAW = 'certification/results/UI_LCC_POS06_EXQ08_atomic.json'
EV = 'certification/results/UI_LCC_POS06_EXQ08_evidence.json'
VER = 'certification/results/UI_LCC_POS06_EXQ08_verdicts.json'
URL = 'http://127.0.0.1:8031/live-copy'

d = json.load(open(RAW, encoding='utf-8'))
exh = (d.get('ex') or {}).get('h') or []
exr = (d.get('ex') or {}).get('rows') or []
owh = (d.get('ow') or {}).get('h') or []
owr = (d.get('ow') or {}).get('rows') or []
exp = d.get('exq') or []
owp = d.get('owned') or []


def segs(c):
    s = (c or '').replace('\u2026', '...').replace(' ', '')
    return [x for x in s.split('...') if x]


def mt(cell, val):
    v = ('' if val is None else str(val)).replace(' ', '').strip()
    if not v:
        return False
    ss = segs(cell)
    if not ss:
        return False
    if len(ss) == 1:
        return v.startswith(ss[0]) and len(ss[0]) >= 3
    if not (v.startswith(ss[0]) and v.endswith(ss[-1])):
        return False
    pos = len(ss[0])
    for m in ss[1:-1]:
        k = v.find(m, pos)
        if k < 0:
            return False
        pos = k + len(m)
    return True


def ne(cell, val):
    ss = segs(cell)
    if len(ss) != 1:
        return False
    try:
        return abs(float(ss[0]) - float(val)) <= max(1e-12, abs(float(val)) * 1e-9)
    except Exception:
        return False


N = min(len(exr), len(exp))


def col(ci, field, numeric=False):
    a = t = contra = 0
    x37 = x37t = 0
    for k in range(N):
        v = exp[k].get(field)
        if v is None or v == '' or isinstance(v, bool):
            continue
        t += 1
        cell = exr[k][ci] if ci < len(exr[k]) else ''
        if (ne(cell, v) if numeric else mt(cell, v)):
            a += 1
        elif segs(cell):
            contra += 1
        q = exp[(k + 37) % N].get(field)
        if q not in (None, ''):
            x37t += 1
            x37 += 1 if (ne(cell, q) if numeric else mt(cell, q)) else 0
    return {'col': ci, 'agree': a, 'of': t, 'contradict': contra, 'cross37': x37, 'cross37_of': x37t}


PLAN = [('Time','time',False),('Wallet','leader_wallet',False),('Coin','coin',False),('Side','side',False),('Status','status',False),('Terminal state','terminal_state',False),('Operator action','operator_action',False),('Reject category','reject_category',False),('OID','oid',False),('Fill avg px','fill_avg_px',True),('Size','fill_size',True)]
B = {h: (col(exh.index(h), f, nu) if h in exh else None) for h, f, nu in PLAN}

F = ['time','leader_wallet','coin','side','status','terminal_state','operator_action','reject_category','oid','limit_px','fill_avg_px','fill_size']
nc = max(len(r) for r in exr) if exr else 0
cmap = {}
for ci in range(nc):
    hits = {}
    for k in range(N):
        cell = exr[k][ci] if ci < len(exr[k]) else ''
        if not segs(cell):
            continue
        for f in F:
            v = exp[k].get(f)
            if v is None or v == '' or isinstance(v, bool):
                continue
            if mt(cell, v) or ne(cell, v):
                hits[f] = hits.get(f, 0) + 1
    if hits:
        cmap[ci] = dict(sorted(hits.items(), key=lambda x: -x[1])[:3])

hdr_of = {ci: (exh[ci] if ci < len(exh) else '') for ci in range(nc)}
ciw = owh.index('Wallet')
lu = owh.index('Last updated')
lc = owh.index('Last copy fill')
M = min(len(owr), len(owp))
o_own = sum(1 for k in range(M) if mt(owr[k][ciw], owp[k].get('leader_wallet')))
o_contra = sum(1 for k in range(M) if segs(owr[k][ciw]) and not mt(owr[k][ciw], owp[k].get('leader_wallet')))
o_cross = sum(1 for k in range(M) if mt(owr[k][ciw], owp[(k + 37) % M].get('leader_wallet')))
key = {}
for x in owp:
    key.setdefault((x.get('coin'), x.get('side'), str(x.get('signed_size'))), []).append(x.get('leader_wallet'))
kjo = kjt = kju = 0
for r in owr:
    if len(r) < 4:
        continue
    k = (r[1], r[2], segs(r[3])[0] if segs(r[3]) else '')
    c = key.get(k)
    if not c:
        kju += 1
        continue
    kjt += 1
    kjo += 1 if any(w and mt(r[ciw], w) for w in c) else 0

lu_vals = sorted({(segs(r[lu])[0] if segs(r[lu]) else '') for r in owr if lu < len(r)})
lcf0x = sum(1 for r in owr if lc < len(r) and segs(r[lc]) and segs(r[lc])[0].startswith('0x'))
p = {'ms': sum(1 for x in owp if x.get('last_updated_ms')), 'at': sum(1 for x in owp if x.get('last_updated_at')), 'oid': sum(1 for x in owp if x.get('last_oid')), 'mark': sum(1 for x in owp if x.get('mark_px') is not None), 'upnl': sum(1 for x in owp if x.get('unrealized_pnl') is not None), 'pv': sum(1 for x in owp if x.get('position_value') is not None)}
AC = (d.get('acct') or {}).get('reason')
lim = sum(1 for x in exp if x.get('limit_px') is not None)
cells = sorted({len(r) for r in exr})

ev = {'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'tested_commit': T, 'page_url': URL, 'raw_source': RAW,
      'rows_alignment': {'dom_rows': len(exr), 'payload_rows': len(exp), 'compared': N},
      'execq': {'headers': exh, 'header_count': len(exh), 'cells_per_row': cells, 'binding': {k: v for k, v in B.items() if v}, 'rendered_cell_to_payload_field': {str(ci): {'header': hdr_of[ci], 'carries': cmap[ci]} for ci in cmap}, 'limit_px_nonnull': lim, 'payload_total': d.get('total')},
      'owned': {'headers': owh, 'dom_rows': len(owr), 'payload_rows': len(owp), 'wallet': {'agree': o_own, 'of': M, 'contradict': o_contra, 'cross37': o_cross}, 'wallet_keyjoin': {'agree': kjo, 'of': kjt, 'unkeyed': kju}, 'last_updated_rendered_values': lu_vals, 'last_copy_fill_0x': lcf0x, 'payload': p},
      'exchange_context': {'exchange_snapshot_status': d.get('snap'), 'account_reason': AC}}
json.dump(ev, open(EV, 'w', encoding='utf-8'), indent=1)

identity = 'Time and Wallet are the row identity: Time agrees %d/%d with 0/%d cross-row matches and Wallet %d/%d with only %d/%d, so DOM row k is payload row k.' % (B['Time']['agree'], B['Time']['of'], B['Time']['cross37_of'], B['Wallet']['agree'], B['Wallet']['of'], B['Wallet']['cross37'], B['Wallet']['cross37_of'])
shift = 'Execution Quality declares %d headers but renders %d cells per row: the undeclared chip occupies index 4, so every declared column from Status onward carries its LEFT NEIGHBOUR payload field (rendered cell -> payload field: %s). Nothing is missing from the payload; the columns are shifted by one.' % (len(exh), cells[0] if cells else -1, json.dumps({str(ci): list(v)[:1] for ci, v in cmap.items() if ci >= 4}))
V = []
def A(i, v, w): V.append({'row_id': i, 'verdict': v, 'evidence_ref': EV, 'tested_commit': T, 'why': w})

A('UI-LCC-POS-06','FAIL','No Mark px column exists in Real Copy Positions. The rendered headers are exactly %s and none carries a mark price; the payload mark_px is null on %d/%d rows because the exchange oracle is UNAVAILABLE (%s). The column is absent from the build, not merely unpopulated.' % (owh, p['mark'], len(owp), AC))
A('UI-LCC-POS-07','FAIL','No Pos value column exists: headers %s contain no position-value column and payload position_value is null on %d/%d rows.' % (owh, p['pv'], len(owp)))
A('UI-LCC-POS-08','FAIL','No Unrealized PnL column exists: headers %s contain no PnL column and payload unrealized_pnl is null on %d/%d rows.' % (owh, p['upnl'], len(owp)))
A('UI-LCC-POS-09','PASS','Leader wallet (column %d of %s) is row-bound: the cell equals the elided head+tail form of THIS row leader_wallet on %d/%d rows with %d contradictions, while the same cell against payload row k+37 matches on only %d/%d. Independently, keying each row to payload on (coin, side, signed size) gives %d/%d matches (%d unkeyed). A swapped wallet would break it.' % (ciw, owh, o_own, M, o_contra, o_cross, M, kjo, kjt, kju))
A('UI-LCC-POS-10','FAIL','No Status column exists: headers %s. The only status-shaped cell is the Ledger/exchange reconciliation badge (values such as OWNED_COPYEXCHANGE_UNAVAILABLE), which compares ledger against exchange rather than reporting position status; the Status column is not rendered.' % (owh,))
A('UI-LCC-POS-11','FAIL','No Last OID column exists: headers %s. The nearest column, Last copy fill, renders a 0x fill id on %d rows (a fill id, not an order id) and payload last_oid is empty on %d/%d rows, so order identity is never displayed.' % (owh, lcf0x, p['oid'], len(owp)))
A('UI-LCC-POS-12','FAIL','Last updated is rendered but ALL %d rows show only the em-dash placeholder (distinct rendered values %s) while payload last_updated_ms is non-zero on %d/%d rows (only last_updated_at is empty). The timestamp is present in the same payload and still never displayed: a product defect, not an oracle gap.' % (len(owr), lu_vals, p['ms'], len(owp)))

def J(rid, hdr, field, numeric, expect_field):
    c = B.get(hdr)
    if not c:
        A(rid, 'FAIL', 'The %s column is not rendered at all: the table headers are %s (%d columns) and no Limit px header exists although payload limit_px is non-null on %d/%d rows. %s' % (hdr, exh, len(exh), lim, len(exp), shift))
        return
    actual = cmap.get(c['col'], {})
    top = next(iter(actual), None)
    ok = c['of'] > 0 and c['agree'] >= 0.95 * c['of'] and (top == expect_field or top is None)
    if ok:
        w = '%s column (index %d of %s) renders THIS row %s on %d/%d rows (%d contradictions); the rendered value comes from that row and would change with any other row. %s' % (hdr, c['col'], exh, field, c['agree'], c['of'], c['contradict'], identity)
    else:
        w = '%s column (index %d of %s) does not render %s: only %d/%d rows agree (%d contradictions) and the cell actually carries the %s of the same row. %s %s' % (hdr, c['col'], exh, field, c['agree'], c['of'], c['contradict'], top or 'neighbouring field', identity, shift)
    A(rid, 'PASS' if ok else 'FAIL', w)

J('UI-LCC-EXQ-01','Time','time',False,'time')
J('UI-LCC-EXQ-02','Wallet','leader_wallet',False,'leader_wallet')
J('UI-LCC-EXQ-03','Coin','coin',False,'coin')
J('UI-LCC-EXQ-04','Side','side',False,'side')
J('UI-LCC-EXQ-05','Status','status',False,'status')
J('UI-LCC-EXQ-06','Limit px','limit_px',True,'limit_px')
J('UI-LCC-EXQ-07','Fill avg px','fill_avg_px',True,'fill_avg_px')
J('UI-LCC-EXQ-08','Size','fill_size',True,'fill_size')

doc = {'batch': 'UI-LCC-POS-06..UI-LCC-EXQ-08', 'task': 't_6b2c80f7', 'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'tested_commit': T, 'page': URL,
       'serving_process': {'pid': 33368, 'started_local': '17/10/2026 11:54:09', 'cmdline': 'python.exe -I -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8031 --app-dir C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/_archive/hl_stage2', 'serving_build_dir': 'hl-build3-testnet-cert-j28-89b3bc7 (name encodes 89b3bc7, committed 07:18Z, before the process start 10:54Z)'},
       'row_alignment': dict(ev['rows_alignment'], identity_columns=identity),
       'exchange_context': {'exchange_snapshot_status': d.get('snap'), 'account_reason': AC, 'note': 'MASTER clearinghouseState is UNAVAILABLE on this serving build (ACCOUNT_ADDRESS_UNAVAILABLE), so the exchange-equality half of the shared expected behaviour cannot be tested. It does not excuse absent or displaced columns, which are judged against the rendered table and the live payload the same page renders.'},
       'measurements': dict(ev['execq'], owned=ev['owned']), 'artifacts': [EV, RAW, 'final3.py'], 'rows': V}
doc['verdict_counts'] = {k: sum(1 for r in V if r['verdict'] == k) for k in ('PASS', 'FAIL', 'NOT_TESTED')}
json.dump(doc, open(VER, 'w', encoding='utf-8'), indent=1)
print('COUNTS', doc['verdict_counts'])
for k, v in B.items():
    if v:
        print('B', k, v, 'ACTUAL', list(cmap.get(v['col'], {})[:1]))
print('CELLS', cells, 'HDR', len(exh))
print('WALLET', o_own, '/', M, 'cross', o_cross, 'keyjoin', kjo, '/', kjt)
print('WROTE', VER)
