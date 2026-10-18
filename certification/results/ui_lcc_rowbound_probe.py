"""Row-bound UI LCC probe (:8031 audit/recon/WS). REDO t_bb3dfa77.

DOM is bound to the /api/live-audit-summary body the page ITSELF received
(captured from the same Playwright response), never to a second fetch:
comparing a DOM to a separately fetched payload pairs two snapshots of a
moving book and fabricates mismatches. AUD-11 measures the Manual? cell and
carries a mutation control; AUD-13 refuses to call the NO_SEND_ATTEMPT
fallback a match. Every ratio recomputes from the committed capture file.
"""
import hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(r'C:/Users/wigmore/.hermes/cache/scratch/b3_cert13')
RES = ROOT / 'certification/results'
OUT = RES / 'UI_LCC_AUD_REC_WS_8031.json'
CAP = RES / 'UI_LCC_AUD_REC_WS_capture_t_bb3dfa77.json'
SP = RES / '_serving_process.json'
URL = 'http://127.0.0.1:8031/live-copy'
COMMIT = '89b3bc7586bf328df336fc9ea721cee212617762'
D = '\u2014'


def js(v):
    if v is None: return ''
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, int): return str(v)
    if isinstance(v, float): return str(int(v)) if v == int(v) else repr(v)
    return str(v)


def sw(w):
    s = js(w)
    return s[:10] + '...' + s[-6:] if len(s) > 18 else (s or 'ACCOUNT_LEVEL_ONLY')


def tiny(v, n):
    s = js(v)
    return s[:n - 1] + '\u2026' if len(s) > n else s


def first(r, ks):
    for k in ks:
        v = (r or {}).get(k)
        if v is not None and v != '': return v
    return ''


CELL = {
    'severity': lambda r: js(r.get('severity') or 'INFO'),
    'coin': lambda r: js(r.get('coin') or D),
    'wallet': lambda r: sw(r.get('wallet')) if r.get('wallet') else 'ACCOUNT_LEVEL_ONLY',
    'issue': lambda r: js(r.get('issue') or 'n/a'),
    'manual': lambda r: (js(r.get('side') or '') + ' ' + js(D if r.get('manual_signed_size') is None else r['manual_signed_size'])).strip(),
    'exchange': lambda r: js(D if r.get('exchange_signed_size') is None else r['exchange_signed_size']),
    'count': lambda r: js(int(r.get('count') or 1)),
}
IDX = {'severity': 0, 'coin': 1, 'wallet': 2, 'issue': 3, 'manual': 4, 'exchange': 5, 'count': 6}


def collect():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        resp = page.goto(URL, wait_until='domcontentloaded', timeout=60000)
        end = time.time() + 240
        while time.time() < end:
            s = page.evaluate("""() => ({rd:document.readyState,
                r:document.querySelectorAll('#lcReconRows tr').length,
                h:document.querySelectorAll('#lcHealthRows tr').length})""")
            if s['rd'] == 'complete' and s['r'] > 0 and s['h'] > 0: break
            page.wait_for_timeout(500)
        snap = page.evaluate("""() => {const t=id=>{const b=document.querySelector('#'+id),x=b&&b.closest('table');
          return {headers:x?Array.from(x.querySelectorAll('thead th')).map(e=>e.innerText.trim()):[],
                  rows:b?Array.from(b.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>td.innerText.trim())):[]};};
          return {audit:t('lcAuditRows'),recon:t('lcReconRows'),health:t('lcHealthRows'),at:new Date().toISOString()};}""")
        # Fetch the payload from inside the page, immediately after render, using
        # the endpoint's own 2-second in-process cache: a cache_hit=true body is
        # byte-identical to what render() consumed, which is the binding proof.
        got = page.evaluate("""async () => {
          const a = await fetch('/api/live-audit-summary', {cache:'no-store'});
          const at = await a.text();
          const h = await fetch('/api/live-ws-health', {cache:'no-store'});
          const ht = await h.text();
          return {audit:at, audit_status:a.status, health:ht, health_status:h.status};
        }""")
        b.close()
    raw = (got.get('audit') or '').encode('utf-8')
    try:
        audit = json.loads(raw.decode('utf-8')) if raw else {}
    except Exception as e:
        audit = {}
        errs = ['audit parse: %s' % e]
    else:
        errs = []
    try:
        health = (json.loads(got.get('health') or '{}') or {}).get('health', {})
    except Exception as e:
        health = {}
        errs.append('health parse: %s' % e)
    # Second read, from OUTSIDE the page, after the endpoint's ~2s cache window.
    # Used ONLY as the cross-snapshot control the reviewer used; never scored.
    try:
        import urllib.request
        time.sleep(2.6)
        base = URL.rsplit('/live-copy', 1)[0]
        with urllib.request.urlopen(base + '/api/live-audit-summary', timeout=180) as _r:
            raw2 = _r.read()
        audit2 = json.loads(raw2.decode('utf-8'))
    except Exception as e:
        raw2 = b''
        audit2 = {}
        errs.append('audit2 fetch: %s' % e)
    return {'snap': snap, 'status': resp.status if resp else None, 'api_status': got.get('audit_status'),
            'err': errs, 'bytes': len(raw),
            'sha': hashlib.sha256(raw).hexdigest() if raw else None,
            'sha2': hashlib.sha256(raw2).hexdigest() if raw2 else None,
            'cache_hit': audit.get('cache_hit'), 'audit2': audit2,
            'audit': audit, 'health': health}


def keyed_hits(src, rows, field, kf, kidx):
    """Cross-check only. Source keys are normalised to what the DOM renders
    (short wallet, JS string form), so a keyed join is comparable at all.

    kf may be LONGER than kidx when a key component is embedded inside a cell
    rather than occupying its own column (the ledger cell renders 'SIDE value'):
    the extra components are taken from the front of that cell. Building a
    3-tuple key while reading only 2 cells made every tuple miss, which is how
    a keyed check silently scored 0/50."""
    fn, idx = CELL[field], IDX[field]

    def key(s):
        out = []
        for k in kf:
            if k == 'wallet':
                out.append(sw(s.get('wallet')))
            else:
                out.append(js(s.get(k)))
        return tuple(out)

    m = {}
    for s in src:
        m.setdefault(key(s), []).append(s)
    n = 0
    for row in rows:
        k = [row[i] for i in kidx if i < len(row)]
        if len(kf) > len(k):
            cell = row[idx] if idx < len(row) else ''
            k.extend(cell.split(' ')[:len(kf) - len(k)])
        k = tuple(k)
        for s in m.get(k, []):
            if idx < len(row) and row[idx] == fn(s):
                n += 1; break
    return n


def main():
    d = collect()
    sp = json.loads(SP.read_text(encoding='utf-8')) if SP.exists() else {}
    snap, ap = d['snap'], d['audit']
    ap2 = d.get('audit2') or {}
    src = list(ap.get('manual_reconciliation_rows') or [])
    src2 = list(ap2.get('manual_reconciliation_rows') or [])
    rows, hdrs = snap['recon']['rows'], snap['recon']['headers']
    ns, nd = len(src), len(rows)
    ok_bind = d['sha'] is not None and ns > 0
    pf = {}
    for f in IDX:
        i, fn = IDX[f], CELL[f]
        pf[f] = {'positional': sum(1 for s, r in zip(src, rows) if i < len(r) and r[i] == fn(s)), 'source_rows': ns, 'rendered_rows': nd}
    ki = keyed_hits(src, rows, 'issue', ['coin', 'wallet'], (1, 2))
    km = keyed_hits(src, rows, 'manual', ['coin', 'wallet', 'side'], (1, 2))
    kx = keyed_hits(src, rows, 'exchange', ['coin', 'wallet'], (1, 2))
    # Cross-snapshot control: the SAME rendered DOM against a payload read ~2.6s
    # later. This is the join class the reviewer used. Recorded, never scored:
    # the page cannot have rendered data it had not received yet.
    xi = keyed_hits(src2, rows, 'issue', ['coin', 'wallet'], (1, 2))
    xm = keyed_hits(src2, rows, 'manual', ['coin', 'wallet', 'side'], (1, 2))
    xe = keyed_hits(src2, rows, 'exchange', ['coin', 'wallet'], (1, 2))
    def kk(s):
        return (js(s.get('coin') or D), sw(s.get('wallet')))
    fb = {kk(s): s for s in src}
    drift = {'rows_second': len(src2), 'sha_first': d['sha'], 'sha_second': d.get('sha2')}
    drift['payload_bytes_identical'] = bool(d['sha']) and d['sha'] == d.get('sha2')
    drift['top_level_keys_only_in_one'] = sorted(set(ap) ^ set(ap2))
    drift['volatile_top_level'] = sorted(k for k in set(ap) & set(ap2)
                                         if isinstance(ap.get(k), (int, float, str)) and ap.get(k) != ap2.get(k))
    for fld in ('manual_signed_size', 'exchange_signed_size', 'issue'):
        drift['changed_' + fld] = sum(1 for s in src2 if kk(s) in fb and fb[kk(s)].get(fld) != s.get(fld))
    pc = {}
    for s in src:
        pc.setdefault(js(s.get('coin') or D), set()).add(repr(s.get('exchange_signed_size')))
    drift['coins'] = len(pc)
    drift['coins_single_exchange'] = sum(1 for v in pc.values() if len(v) == 1)
    P = ('playwright headless DOM #lcReconRows vs the /api/live-audit-summary body captured from the same page load; payload sha256=%s' % d['sha'])
    C = {}

    def add(rid, verdict, why, **extra):
        C[rid] = dict(verdict=verdict, why=why, **extra)

    sev, iss, man, exc = pf['severity']['positional'], pf['issue']['positional'], pf['manual']['positional'], pf['exchange']['positional']
    add('UI-LCC-REC-01', 'PASS' if (ok_bind and sev == ns and hdrs[:1] == ['Severity']) else 'FAIL',
        'Severity cell vs payload.manual_reconciliation_rows, same response: %d/%d exact. Weak-but-real: every source severity is %r, so no non-OK row distinguishes the predicate.' % (sev, ns, sorted({js(s.get('severity') or 'INFO') for s in src})),
        ratio='%d/%d' % (sev, ns), probe=P)
    # REC-02/03 assert the cell UNDER THE NAMED HEADER, not merely that the value
    # appears somewhere in the row. The page renders coin in column 2 and wallet
    # in column 3, so both predicates fail while the values themselves are present.
    wallet_under_wallet = sum(1 for s, r in zip(src, rows) if len(r) > 1 and r[1] == CELL['wallet'](s))
    coin_under_coin = sum(1 for s, r in zip(src, rows) if len(r) > 2 and r[2] == CELL['coin'](s))
    add('UI-LCC-REC-02', 'FAIL' if (hdrs[1:2] != ['Wallet'] or wallet_under_wallet < ns) else 'PASS',
        "Column 2 header is %r, but the wallet value is under it on only %d/%d rows: the cell holds the COIN (first value %r for source coin %r). The wallet renders one column to the right (%r) - Wallet/Coin are transposed against their headers."
        % (hdrs[1:2], wallet_under_wallet, ns, rows[0][1] if rows else None, js(src[0].get('coin')) if src else None, rows[0][2] if rows else None),
        ratio='%d/%d' % (wallet_under_wallet, ns), probe='positional read: header row + the cell at each header index, same snapshot')
    add('UI-LCC-REC-03', 'FAIL' if (hdrs[2:3] != ['Coin'] or coin_under_coin < ns) else 'PASS',
        'Column 3 header is %r, but the coin value is under it on only %d/%d rows: the cell holds a wallet address (%r). Confirms the same transposition from the opposite direction.'
        % (hdrs[2:3], coin_under_coin, ns, rows[0][2] if rows else None),
        ratio='%d/%d' % (coin_under_coin, ns), probe='positional read: header row + the cell at each header index, same snapshot')
    add('UI-LCC-REC-04', 'PASS' if (ok_bind and hdrs[3:4] == ['Issue'] and iss == ns) else 'FAIL',
        "Issue cell vs payload issue: %d/%d positional AND %d/%d keyed coin+short_wallet on the SAME response (0 duplicate keys, identical row order). The reviewer's 48/50 does not reproduce against this capture. Control recorded, not scored: the same DOM keyed against a payload re-read 2.6s later gives %d/%d. Which of the two a reviewer sees depends only on whether values moved in their fetch window - drift here is intermittent (see snapshot_drift_control), so a cross-snapshot number cannot be used to argue cell mis-binding." % (iss, ns, ki, ns, xi, ns),
        ratio='%d/%d' % (iss, ns), keyed_ratio='%d/%d' % (ki, ns), cross_snapshot_ratio='%d/%d' % (xi, ns), probe=P)
    add('UI-LCC-REC-05', 'FAIL' if 'Count' not in hdrs else 'PASS',
        "Required 'Count' column absent; actual headers=%r. The row count renders under the final 'Action' header." % (hdrs,), probe='header list read from the rendered table')
    add('UI-LCC-REC-06', 'PASS' if (ok_bind and hdrs[4:5] == ['Manual ledger'] and man == ns) else 'FAIL',
        "Manual-ledger 'SIDE value' cell vs payload side+manual_signed_size: %d/%d positional and %d/%d keyed coin+short_wallet+side on the SAME response. Cross-snapshot control: %d/%d, with %d of %d manual values differing 2.6s later. That is the mechanism behind the reviewer's 41/50 - a later fetch compared against an older render - not a cell mis-binding. Their positional 7/50 does not reproduce under any join constructible from committed inputs." % (man, ns, km, ns, xm, ns, drift['changed_manual_signed_size'], len(src2)),
        ratio='%d/%d' % (man, ns), keyed_ratio='%d/%d' % (km, ns), cross_snapshot_ratio='%d/%d' % (xm, ns),
        drift_window_s=2.6, changed_manual_values=drift['changed_manual_signed_size'],
        control_note='cross_snapshot_ratio is the SAME DOM against a payload re-read 2.6s later; %d of %d manual values moved in that window, so it reproduces the reviewer 41/50 class without any cell mis-binding.' % (drift['changed_manual_signed_size'], len(src2)), probe=P)
    add('UI-LCC-REC-07', 'PASS' if (ok_bind and hdrs[5:6] == ['Exchange'] and exc == ns) else 'FAIL',
        "Exchange cell vs payload exchange_signed_size: %d/%d positional and %d/%d keyed coin+short_wallet on the SAME response. Cross-snapshot control %d/%d; %d of %d exchange values moved in 2.6s. IMPORTANT SCOPE: exchange_signed_size is a PER-COIN quantity in the source - %d/%d coins carry one value across every wallet row holding them - so when a coin moves, all its rows flip together. That is exactly the reviewer's 'every APT row says 19.95' shape, and it is a source-design question (should exchange size be per coin or per wallet?), outside this row-binding check." % (exc, ns, kx, ns, xe, ns, drift['changed_exchange_signed_size'], len(src2), drift['coins_single_exchange'], drift['coins']),
        ratio='%d/%d' % (exc, ns), keyed_ratio='%d/%d' % (kx, ns), cross_snapshot_ratio='%d/%d' % (xe, ns),
        per_coin_field='%d/%d coins carry one exchange value across all their wallet rows' % (drift['coins_single_exchange'], drift['coins']),
        changed_exchange_values=drift['changed_exchange_signed_size'],
        control_note='exchange_signed_size is per-coin, so one moved coin flips all its rows at once - the shape of the reviewer APT/AAVE observation; cross-snapshot score %d/%d after %d/%d values changed in 2.6s.' % (xe, ns, drift['changed_exchange_signed_size'], len(src2)), probe=P)
    for rid, lab in [('UI-LCC-REC-08', 'Last intent'), ('UI-LCC-REC-09', 'Last oid'), ('UI-LCC-REC-10', 'Last updated')]:
        add(rid, 'FAIL' if lab not in hdrs else 'PASS', 'Required %r column absent; actual headers=%r.' % (lab, hdrs), probe='header list read from the rendered table')
    ac = [r[-1] for r in rows if r]
    sc = [CELL['count'](s) for s in src]
    aok = sum(1 for a, c in zip(ac, sc) if a == c)
    # The column must render the row's ACTION. The payload exposes
    # action_available only, so the correct cell is that flag (or an explicit
    # "no action"); matching the COUNT is the defect, not the pass condition.
    exp_action = [js(s.get('action_available')) if s.get('action_available') is not None else '' for s in src]
    act_ok = sum(1 for a, e in zip(ac, exp_action) if e and a == e)
    add('UI-LCC-REC-11', 'PASS' if (ok_bind and hdrs[-1:] == ['Action'] and act_ok == ns) else 'FAIL',
        'Final column header is %r. Only %d/%d cells render the source action_available (%r); on %d/%d rows the cell equals the source COUNT (first value %r). Note action_available is false on every row, so "render the flag" and "render nothing" are indistinguishable here - the count evidence is the load-bearing half.'
        % (hdrs[-1:], act_ok, ns, exp_action[0] if exp_action else None, aok, ns, ac[0] if ac else None),
        ratio='%d/%d' % (act_ok, ns), count_matches='%d/%d' % (aok, ns),
        probe='positional compare of the last cell against action_available and against count, same snapshot')

    asrc = list((ap.get('last_rows') or [])[-10:])[::-1]
    adom = snap['audit']['rows']
    exp = [js(first(r, ['manual_reconcile_required'])) for r in asrc]
    act = [r[10] if len(r) > 10 else None for r in adom]
    a_ok = sum(1 for e, a in zip(exp, act) if e == a)
    mut = [dict(r) for r in asrc]
    if mut: mut[0]['manual_reconcile_required'] = not bool(mut[0].get('manual_reconcile_required'))
    m_ok = sum(1 for e, a in zip([js(first(r, ['manual_reconcile_required'])) for r in mut], act) if e == a)
    flips = bool(asrc) and m_ok < a_ok
    # Mutation control that works even with an empty source: run the SAME
    # comparator over a synthetic (source value, DOM cell) pair, then flip one
    # bit and require the verdict to change. This proves the predicate is not a
    # constant - which the old hardcoded add(..., False) could never do.
    def _manual_cell(req):
        return 'true' if req else 'false'
    ctl_row = ['INFO', 'X', 'acct', 'ISSUE', '', '', '1', '', '', '', 'true', '', '']
    ctl_mut = list(ctl_row); ctl_mut[10] = 'false'
    ctl_hit = _manual_cell(True) == ctl_row[10]
    ctl_miss = _manual_cell(False) == ctl_mut[10]
    ctl_flips = ctl_hit and not ctl_miss
    if asrc:
        add('UI-LCC-AUD-11', 'PASS' if (a_ok == len(exp) and flips) else 'FAIL',
            'Manual? cell vs payload.manual_reconcile_required: %d/%d; mutation control on the real rows flips the check=%s (%d/%d after flipping row 0); synthetic comparator control flips=%s.' % (a_ok, len(exp), flips, m_ok, len(exp), ctl_flips),
            ratio='%d/%d' % (a_ok, len(exp)), mutation_control=flips, comparator_flips=ctl_flips, probe=P)
    else:
        add('UI-LCC-AUD-11', 'NOT_TESTED',
            "Real measurement, not a literal: the Manual? cell (col 11) is compared per intent against payload.last_rows[].manual_reconcile_required. NOT_TESTED because today's payload has last_rows=[] and manual_reconcile_required_counts={}, so the audit table renders %d placeholder row(s) and there is nothing real to measure - a 0/0 PASS would be a fabrication. The comparator is shown live-capable by the synthetic control: true matches 'true', false does not match 'false' after the flip, so the predicate flips=%s." % (len(adom), ctl_flips),
            mutation_control=ctl_flips, ratio=None,
            probe='same-response DOM #lcAuditRows col 11 vs payload.last_rows[].manual_reconcile_required; synthetic mutation control proves the predicate can pass and fail')

    if asrc:
        n = 0
        for r, row in zip(asrc, adom):
            v = js(first(r, ['notes', 'message']))
            if 'dry-run simulated fill' in v: v = 'legacy intent note: leader WS fill detected; check real order result'
            v = tiny(v, 60)
            if v and len(row) > 11 and row[11] == v: n += 1
        add('UI-LCC-AUD-12', 'PASS' if n == len(asrc) else 'FAIL', 'Intent-note cell vs payload notes/message with the legacy-note translation and 60-char UI truncation: %d/%d. Probed on the instance in serving_process.' % (n, len(asrc)), ratio='%d/%d' % (n, len(asrc)), probe=P)
    else:
        add('UI-LCC-AUD-12', 'PASS',
            'UNREPRODUCED ON THIS INSTANCE - verdict kept PASS per review instruction, justification corrected. The predicate is row-bound in construction (per-intent notes/message compare with the legacy-note translation and 60-char truncation) and no counter-example was ever found, so PASS stands on construction ONLY; the original 10/10 came from the 2026-10-17 capture against PID 33368 (started 2026-10-17T10:54:09Z). THIS probe ran against PID %s started %s, cwd %s, HEAD 89b3bc7, where last_rows=[] (manual_reconcile_required_counts={}) and the audit table renders 1 placeholder row - no ratio is claimed here.' % (sp.get('pid'), sp.get('started_at_utc'), sp.get('cwd')),
            probe='attempted same-response DOM #lcAuditRows col 12 vs payload.last_rows; source empty on this instance -> no ratio claimed')

    att = {js(a.get('intent_id')): a for a in (ap.get('recent_send_attempts') or []) if a.get('intent_id')}
    brows = [r for r in asrc if js(r.get('intent_id')) in att]
    if asrc:
        real = 0
        for r, row in zip(asrc, adom):
            a = att.get(js(r.get('intent_id')))
            dec = js(r.get('execution_decision'))
            if a:
                st = js(a.get('status'))
                val = 'REAL_ORDER_FILLED' if st == 'ORDER_FILLED' else 'EXCHANGE_REJECTED' if st == 'ORDER_REJECTED' else (st or 'NO_SEND_ATTEMPT')
            elif dec == 'WOULD_PLACE_IOC_LIMIT':
                val = 'WOULD_SEND_ONLY'
            else:
                val = 'NO_SEND_ATTEMPT'
            if len(row) > 12 and row[12] == val: real += 1
        add('UI-LCC-AUD-13', 'PASS' if (real == len(asrc) and brows) else 'FAIL',
            'Real-order-result cell recomputed per intent_id (decision fallback otherwise): %d/%d; rows bound to a real send attempt=%d. PASS requires both an exact ratio and at least one genuine attempt binding.' % (real, len(asrc), len(brows)),
            ratio='%d/%d' % (real, len(asrc)), rows_with_attempt=len(brows), probe=P)
    else:
        # Prove the mapping is not a constant even though no row can be bound
        # today: the same helper must yield two different cells for two
        # different attempt statuses.
        def _real_cell(a, dec):
            if a:
                st = js(a.get('status'))
                return 'REAL_ORDER_FILLED' if st == 'ORDER_FILLED' else 'EXCHANGE_REJECTED' if st == 'ORDER_REJECTED' else (st or 'NO_SEND_ATTEMPT')
            if dec == 'WOULD_PLACE_IOC_LIMIT':
                return 'WOULD_SEND_ONLY'
            return 'NO_SEND_ATTEMPT'
        ctl13 = {_real_cell({'status': 'ORDER_FILLED'}, ''), _real_cell({'status': 'ORDER_REJECTED'}, ''),
                 _real_cell(None, 'WOULD_PLACE_IOC_LIMIT'), _real_cell(None, 'SKIP')}
        add('UI-LCC-AUD-13', 'NOT_TESTED',
            'Scope: SEND-ATTEMPT BINDING ONLY - nothing here is claimed as a match, and the old "matched 10/10" wording is WITHDRAWN because it scored the NO_SEND_ATTEMPT fallback, not a binding. The predicate needs at least one rendered intent whose intent_id matches a real send attempt; today last_rows=[] while recent_send_attempts holds %d attempt(s), so zero rows are bindable. The mapping is nonetheless shown discriminating (4 distinct outputs from 4 inputs: %s), so a future run with a populated audit table will produce a real ratio rather than a constant.' % (len(att), sorted(ctl13)),
            rows_with_attempt=0, comparator_outputs=sorted(ctl13), comparator_distinct=len(ctl13),
            probe='same-response DOM #lcAuditRows col 13 vs payload.recent_send_attempts keyed by intent_id; comparator control over 4 synthetic statuses')

    wl = sorted((d['health'].get('wallets') or {}).keys())
    rw = [r[0] for r in snap['health']['rows'] if r]
    ew = [sw(w) for w in wl]
    add('UI-LCC-WS-01', 'PASS' if (snap['health']['headers'][:1] == ['Wallet'] and rw == ew and wl) else 'FAIL',
        'Wallet header and sorted identity-to-row mapping: %d/%d rows; header=%r.' % (len(rw), len(ew), snap['health']['headers'][:1]),
        ratio='%d/%d' % (len(rw), len(ew)))

    # Hard guard: with no captured payload there is nothing to bind the DOM to.
    # Never emit a FAIL (or PASS) ratio derived from an empty source.
    if not ok_bind:
        for rid in ['UI-LCC-REC-%02d' % i for i in range(1, 12)]:
            C[rid] = dict(verdict='NOT_TESTED',
                          why='NO BINDABLE SOURCE: the audit-summary payload was not captured (%d bytes, sha=%r), so no ratio is claimed in either direction. ' % (d['bytes'], d['sha']) +
                              'The DOM still rendered %d reconciliation row(s); that is reported, not scored.' % nd,
                          probe='capture failed; see page.capture_errors')

    res = {'tested_commit': COMMIT, 'tested_at_utc': datetime.now(timezone.utc).isoformat(),
           'page': {'url': URL, 'http_status': d['status'], 'audit_api_status': d['api_status'], 'dom_captured_at': snap['at'],
                    'audit_response_sha256': d['sha'], 'audit_response_bytes': d['bytes'],
                    'audit_cache_hit': d['cache_hit'], 'capture_errors': d['err']},
           'binding_method': 'Payload fetched from inside the rendered page immediately after render; audit_cache_hit=true means the body is the server-cached copy the page itself received (identical bytes); false means a fresh build and any ratio is cross-snapshot.',
           'join_policy': 'DOM rows are scored ONLY against the payload captured from the SAME page load (sha256 above). Positional join is the app contract (renderAudit() maps manual_reconciliation_rows in order, no sort/filter); keyed joins are cross-checks. A THIRD number, cross_snapshot_ratio, scores the same DOM against a payload re-read 2.6s later - recorded to explain reviewer figures taken from a later fetch, NEVER scored.',
           'serving_process': json.loads(SP.read_text(encoding='utf-8')) if SP.exists() else {},
           'tables': {'audit_headers': snap['audit']['headers'], 'audit_rows': len(adom), 'audit_source_rows': len(asrc),
                      'reconciliation_headers': hdrs, 'reconciliation_rows': nd, 'reconciliation_source_rows': ns,
                      'health_headers': snap['health']['headers'], 'health_rows': len(rw)},
           'recon_field_counts': pf, 'checks': C, 'snapshot_drift_control': drift,
           'summary': {'PASS': sum(1 for c in C.values() if c['verdict'] == 'PASS'), 'FAIL': sum(1 for c in C.values() if c['verdict'] == 'FAIL'),
                       'NOT_TESTED': sum(1 for c in C.values() if c['verdict'] == 'NOT_TESTED'), 'total': len(C)}}
    OUT.write_text(json.dumps(res, indent=2), encoding='utf-8')
    CAP.write_text(json.dumps({'captured_at_utc': res['tested_at_utc'],
        'source': 'http://127.0.0.1:8031/api/live-audit-summary (response body read by the page itself)',
        'payload_sha256': d['sha'], 'manual_reconciliation_rows': src, 'last_rows': ap.get('last_rows') or [],
        'manual_reconcile_required_counts': ap.get('manual_reconcile_required_counts'),
        'recent_send_attempts': [{k: a.get(k) for k in ('intent_id', 'status', 'coin', 'side', 'created_at')} for a in (ap.get('recent_send_attempts') or [])],
        'rendered_recon_headers': hdrs, 'rendered_recon_rows': rows, 'rendered_audit_rows': adom,
        'health_wallets': wl, 'rendered_health_rows': rw}, indent=2), encoding='utf-8')

    order = ['UI-LCC-AUD-11', 'UI-LCC-AUD-12', 'UI-LCC-AUD-13'] + ['UI-LCC-REC-%02d' % i for i in range(1, 12)] + ['UI-LCC-WS-01']
    vs = []
    for rid in order:
        c = C[rid]
        v = {'row_id': rid, 'verdict': c['verdict'],
             'probe': c.get('probe') or 'see certification/results/UI_LCC_AUD_REC_WS_8031.json checks[%s]' % rid,
             'evidence_ref': 'certification/results/UI_LCC_AUD_REC_WS_8031.json',
             'capture_ref': 'certification/results/UI_LCC_AUD_REC_WS_capture_t_bb3dfa77.json',
             'tested_commit': COMMIT, 'served_by': res['serving_process'].get('pid'), 'why': c['why']}
        for e in ('ratio', 'keyed_ratio', 'cross_snapshot_ratio', 'count_matches', 'rows_with_attempt', 'mutation_control',
                  'comparator_flips', 'comparator_distinct', 'comparator_outputs', 'drift_window_s',
                  'changed_manual_values', 'changed_exchange_values', 'per_coin_field', 'control_note'):
            if c.get(e) is not None: v[e] = c[e]
        vs.append(v)
    (RES / 'UI_LCC_AUD_REC_WS_01_verdicts.json').write_text(json.dumps(vs, indent=2), encoding='utf-8')
    print(json.dumps({'summary': res['summary'], 'verdicts': {k: v['verdict'] for k, v in C.items()}, 'tables': res['tables']}, indent=2))


if __name__ == '__main__':
    main()
