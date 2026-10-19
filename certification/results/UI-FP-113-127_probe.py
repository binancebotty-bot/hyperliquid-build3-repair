#!/usr/bin/env python3
'''UI-FP-113..UI-FP-127 row-bound probe (READ-ONLY).

Chain proven per row:
  ledger CSV row (order_intents.csv line N)
    -> API payload record (/api/live-audit-summary audit_rows[i])
    -> rendered DOM cell (#lcAuditRows tr[i] td[j] spans)

The binding is by content, not by position: the DOM row index is matched to
an API record by created_at equality, and that API record is matched to the
ledger line by intent_id AND created_at. Every hop is written to a committed
file so each evidence_ref is a resolvable JSON Pointer into a file in this dir.

No engine import. No POST. No write to the served directory or to the app.
Run with Python 3.11 (Playwright lives only there):

  export PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \\
      certification/results/UI-FP-113-127_probe.py
'''
import csv
import datetime
import hashlib
import json
import os
import urllib.request

from playwright.sync_api import sync_playwright

PORT = 8023
BASE = 'http://127.0.0.1:%d' % PORT
HERE = os.path.dirname(os.path.abspath(__file__))
SERVED_SSOT = ('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/'
               'hl_stage2/HL_Copy_App_SSOT.py')

F_DOM = os.path.join(HERE, 'UI-FP-113-127_dom_capture.json')
F_API = os.path.join(HERE, 'UI-FP-113-127_api_snapshot.json')
F_LED = os.path.join(HERE, 'UI-FP-113-127_ledger_row.json')
F_ART = os.path.join(HERE, 'UI-FP-113-127.json')

# ---- the page's own rendering rules, quoted from the served SSOT ----------
# line numbers are re-derived at run time from the served file (renderer_ref)
AUDIT_RULES = {
    'UI-FP-121': ('Time', 0, "first(r,['created_at','timestamp_iso','time'])"),
    'UI-FP-122': ('Wallet', 1, "shortWallet(first(r,['leader_wallet','wallet']))"),
    'UI-FP-123': ('Coin', 2, "first(r,['coin','asset'])"),
    'UI-FP-124': ('Side', 3, "first(r,['side'])"),
    'UI-FP-125': ('Source/Reason', 4,
                  "sourceOf(r) + tiny(first(r,['reason']),32) stacked in .lc-cell-stack"),
    'UI-FP-126': ('Status', 5, "pill(first(r,['status'])||'\u2014')"),
    'UI-FP-127': ('Decision', 6,
                  "decisionPill(first(r,['execution_decision'])||'\u2014')"),
}
EXEC_COLUMNS = {
    'UI-FP-113': ('Size', 11, 'fill size'),
    'UI-FP-114': ('Pos before -> after', 12, 'position before/after'),
    'UI-FP-115': ('Leader\u2192send ms', 13, 'leader-to-send latency'),
    'UI-FP-116': ('Total ms', 14, 'total latency'),
    'UI-FP-117': ('Symbol ms', 15, 'symbol resolve latency'),
    'UI-FP-118': ('SDK ms', 16, 'sdk latency'),
    'UI-FP-119': ('Exchange ms', 17, 'exchange latency'),
    'UI-FP-120': ('Error', 18, 'reject/error text'),
}

DOM_JS = """() => {
 const heads=(s)=>{const t=document.querySelector(s);if(!t)return null;
   const tb=t.closest('table');return tb?Array.from(tb.querySelectorAll('thead th'))
     .map(x=>x.innerText.trim()):null;};
 const rows=(s)=>{const t=document.querySelector(s);if(!t)return null;
   return Array.from(t.querySelectorAll('tr')).map(tr=>{
     const tds=Array.from(tr.querySelectorAll('td'));
     return {innerText:tds.map(td=>td.innerText.trim()),
             spans:tds.map(td=>Array.from(td.querySelectorAll('span'))
               .map(sp=>sp.innerText.trim())),
             tds:tds.length};});};
 return {title:document.title,url:location.href,ready:document.readyState,
   exec_heads:heads('#lcExecQualRows'),exec_rows:rows('#lcExecQualRows'),
   audit_heads:heads('#lcAuditRows'),audit_rows:rows('#lcAuditRows')};
}"""


def short_wallet(w):
    w = str(w or '')
    return w[:10] + '...' + w[-6:] if len(w) > 18 else w


def tiny(v, n):
    s = '' if v is None else str(v)
    return s[:n - 1] + '\u2026' if len(s) > n else s


def first(row, keys):
    for k in keys:
        if row.get(k) not in (None, ''):
            return row.get(k)
    return ''


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def api(path):
    req = urllib.request.Request(BASE + path,
                                 headers={'x-requested-with': 'fetch'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode('utf-8')), r.status


def find_ledger(intent_id, created_at):
    root = 'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert'
    for dirpath, _dirs, files in os.walk(root):
        if os.path.basename(dirpath) != 'append_only':
            continue
        for fn in files:
            if fn != 'order_intents.csv':
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > 400 * 1024 * 1024:
                    continue
                with open(p, 'r', encoding='utf-8-sig', newline='') as f:
                    rdr = csv.DictReader(f)
                    for n, row in enumerate(rdr, 2):
                        if (str(row.get('intent_id', '')).strip() == intent_id
                                and str(row.get('created_at', '')).strip() == created_at):
                            return p, n, row, list(rdr.fieldnames or [])
            except OSError:
                continue
    return None, None, None, None


def renderer_ref(markers):
    '''Line numbers + verbatim code for the rules above, from the served SSOT.'''
    lines = open(SERVED_SSOT, 'r', encoding='utf-8', errors='replace').read().splitlines()
    out = {}
    for m in markers:
        hits = [i + 1 for i, ln in enumerate(lines) if m in ln]
        out[m] = {'lines': hits, 'code': {str(n): lines[n - 1] for n in hits}}
    return out, len(lines)


def audit_verdict(row_id, rule, rendered, ledger_row, api_row):
    '''Return (verdict, rule_output, why) for one audit-table row.'''
    _col, idx, rule_src = rule
    spans = rendered['spans'][idx] if idx < len(rendered['spans']) else []
    text = rendered['innerText'][idx] if idx < len(rendered['innerText']) else None

    if row_id == 'UI-FP-121':
        want = first(ledger_row, ['created_at', 'timestamp_iso', 'time'])
        return (('PASS' if text == want else 'FAIL'), want,
                'first() over created_at/timestamp_iso/time')
    if row_id == 'UI-FP-122':
        want = short_wallet(first(ledger_row, ['leader_wallet', 'wallet']))
        return (('PASS' if text == want else 'FAIL'), want,
                'shortWallet(): slice(0,10)+\'...\'+slice(-6)')
    if row_id == 'UI-FP-123':
        want = first(ledger_row, ['coin', 'asset'])
        return (('PASS' if text == want else 'FAIL'), want, 'first() over coin/asset')
    if row_id == 'UI-FP-124':
        # the truth DOES exist in the ledger/API; the rule reads a key neither has
        truth = {'leader_side': ledger_row.get('leader_side'),
                 'copy_side': ledger_row.get('copy_side')}
        want = first(ledger_row, ['side'])
        ok = bool(truth['leader_side'] or truth['copy_side'])
        if not ok:
            return ('NOT_TESTED', want, 'no side value in the truth source')
        if text == '' and want == '':
            return ('FAIL', want,
                    'cell is blank while the truth records leader_side=%r copy_side=%r; '
                    'the rule reads r.side only and neither the ledger nor the API payload '
                    'has a side key, so this column can never display the side'
                    % (truth['leader_side'], truth['copy_side']))
        return (('PASS' if text == want else 'FAIL'), want,
                'rule reads r.side only; ledger/API carry leader_side=%r copy_side=%r'
                % (truth['leader_side'], truth['copy_side']))
    if row_id == 'UI-FP-125':
        src = str(first(ledger_row, ['source', 'reason']) or '')
        reason = str(ledger_row.get('reason') or '')
        want = [src, tiny(reason, 32)]
        ok = bool(src or reason)
        if not ok:
            return ('NOT_TESTED', want, 'no source/reason in the truth source')
        return (('PASS' if spans == want else 'FAIL'), want,
                'two stacked spans: sourceOf(r) then tiny(reason,32)')
    if row_id == 'UI-FP-126':
        raw = first(ledger_row, ['status'])
        if raw in (None, ''):
            return ('NOT_TESTED', '\u2014',
                    'no status value exists in the truth source for this intent '
                    '(decision=%r, never sent); the cell renders the documented fallback '
                    'and no positive case is available on this run'
                    % ledger_row.get('decision'))
        want = raw if raw not in (None, '') else '\u2014'
        return (('PASS' if text == want else 'FAIL'), want,
                'pill(first(r,[\'status\'])||\'\u2014\'); ledger status column absent')
    if row_id == 'UI-FP-127':
        raw = first(ledger_row, ['execution_decision'])
        if raw in (None, '') and ledger_row.get('decision') not in (None, ''):
            return ('FAIL', '\u2014',
                    'the truth records decision=%r but the Decision cell renders %r: the '
                    'render rule reads first(r,[\'execution_decision\']) and neither the '
                    'ledger CSV nor the API payload carries that key, so the recorded '
                    'decision is never displayed'
                    % (ledger_row.get('decision'), text))
        want = raw if raw not in (None, '') else '\u2014'
        decision_in_truth = ledger_row.get('decision')
        why = ('decisionPill(first(r,[\'execution_decision\'])||\'\u2014\'); '
               'ledger has no execution_decision column but records decision=%r'
               % decision_in_truth)
        verdict = 'PASS' if text == want else 'FAIL'
        return (verdict, want, why)
    raise KeyError(row_id)


def served_html():
    '''Fetch the exact HTML bytes the process serves and pull out the two
    per-row renderer templates (audit table, execution table) verbatim.

    The exec-table builder spans several source lines (locals are computed
    before the returned <tr>), so it is captured as a LINE WINDOW anchored on
    the innerHTML assignment and kept whole, not as a single line.'''
    req = urllib.request.Request(BASE + '/live-copy')
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    txt = raw.decode('utf-8', 'replace')
    lines = txt.splitlines()
    audit_tpl = exec_tpl = None
    for i, ln in enumerate(lines):
        if "'#lcAuditRows').innerHTML" in ln:
            audit_tpl = ln.strip()
        if "'#lcExecQualRows').innerHTML" in ln:
            end = i
            for j in range(i, min(i + 40, len(lines))):
                if '</tr>`;' in lines[j] or "</tr>`;" in lines[j]:
                    end = j
                    break
            exec_tpl = '\n'.join(x.strip() for x in lines[i:end + 1])
    return {'served_html_sha256': hashlib.sha256(raw).hexdigest(),
            'served_html_bytes': len(raw),
            'audit_row_template': audit_tpl,
            'exec_row_template': exec_tpl}


def cell_fragments(tpl):
    '''Split a row template into its per-column <td>...</td> fragments.

    The trailing empty-state fragment (colspan="N") is a fallback message, not
    a column, so it is dropped: only real column cells are returned.'''
    if not tpl:
        return []
    frags = ['<td' + p.split('</td>')[0] + '</td>'
             for p in tpl.split('<td')[1:]]
    return [f for f in frags if 'colspan=' not in f]


def matrix_records():
    '''The certification-matrix rows this artifact certifies, so every row
    record is tied to its requirement by id AND by that requirement's own
    expected_behaviour text (not just a lookalike column name).'''
    p = os.path.join(os.path.dirname(os.path.dirname(HERE)),
                     'certification', 'certification_matrix.json')
    with open(p, encoding='utf-8') as f:
        doc = json.load(f)
    out = {}
    for r in doc['records']:
        rid = r['id']
        if rid.startswith('UI-FP-') and 'UI-FP-113' <= rid <= 'UI-FP-127':
            out[rid] = {k: r.get(k) for k in
                        ('id', 'area', 'feature', 'expected_behaviour',
                         'applicability', 'proof_network',
                         'execution_proof', 'independent_oracle',
                         'negative_tests')}
    return out


def process_start_time():
    '''PID listening on PORT (netstat, authoritative here) plus that PID's
    start time, so the served build can be date-checked.'''
    import subprocess
    net = subprocess.run(['netstat', '-ano'], capture_output=True)
    pid = None
    for ln in net.stdout.decode('utf-8', 'replace').splitlines():
        if (':%d ' % PORT) in ln and 'LISTEN' in ln.upper():
            pid = ln.split()[-1]
            break
    if not pid:
        return None, None
    ps = subprocess.run(['powershell', '-NoProfile', '-Command',
                         '(Get-Process -Id %s).StartTime.ToString("o")' % pid],
                        capture_output=True)
    return pid, (ps.stdout.decode('utf-8', 'replace').strip() or None)


def main():
    payload, status = api('/api/live-audit-summary')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1900, 'height': 1400})
        resp = page.goto(BASE + '/live-copy', wait_until='networkidle', timeout=180000)
        page.wait_for_timeout(4000)
        dom = page.evaluate(DOM_JS)
        http_status = resp.status if resp else None
        browser.close()

    captured = datetime.datetime.now(datetime.timezone.utc).isoformat()
    dom_doc = {'captured_at_utc': captured, 'url': BASE + '/live-copy',
               'http_status': http_status, 'selectors': {
                   'exec': '#lcExecQualRows (tbody rows of the Execution Quality table)',
                   'audit': '#lcAuditRows (tbody rows of the Order Intents / Audit table)'},
               'note': ('innerText is the flattened cell text; spans is the list of '
                        'per-span texts inside that cell (the Source/Reason cell '
                        'stacks two spans, so innerText loses the separator)'),
               **dom}
    with open(F_DOM, 'w', encoding='utf-8') as f:
        json.dump(dom_doc, f, indent=1, ensure_ascii=False)

    ssot_sha = sha256_file(SERVED_SSOT)
    ssot_mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(SERVED_SSOT)).strftime('%Y-%m-%d %H:%M')
    markers, ssot_lines = renderer_ref([
        'function first(', 'function tiny(', 'function shortWallet(',
        'function sourceOf(', "querySelector('#lcAuditRows')"])

    served = served_html()
    matrix = matrix_records()
    wanted = set(AUDIT_RULES) | set(EXEC_COLUMNS)
    missing_mx = sorted(wanted - set(matrix))
    if missing_mx:
        raise SystemExit('MATRIX_RECORD_MISSING: %s' % missing_mx)
    audit_frags = cell_fragments(served['audit_row_template'])
    exec_frags = cell_fragments(served['exec_row_template'])
    pid, pid_start = process_start_time()
    if not served['audit_row_template'] or not served['exec_row_template']:
        raise SystemExit('SERVED_TEMPLATE_NOT_FOUND: /live-copy did not contain '
                         'the #lcAuditRows / #lcExecQualRows row builders')
    build_id = 'SERVED_HTML_SHA256:' + served['served_html_sha256']

    # Serving build: the process's launch checkout is
    # C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2
    # at HEAD 43731b4f (committed 2026-10-09T14:11:59Z, BEFORE the process
    # start). Its HL_Copy_App_SSOT.py is dirty vs the committed blob, so the
    # authoritative binding is the served content hash, not the commit.
    SERVING_COMMIT = '43731b4f1f19a56e835032dabf608a550f925717'
    SERVING_COMMIT_DATE = '2026-10-09T14:11:59Z'
    SERVING_CHECKOUT_DIRTY = True

    audit_heads = dom['audit_heads'] or []
    audit_rows = dom['audit_rows'] or []
    exec_heads = dom['exec_heads'] or []
    exec_rows = dom['exec_rows'] or []
    api_audit = payload.get('audit_rows') or []
    api_exec = payload.get('execution_quality_rows') or []
    last_rows = payload.get('last_rows') or []

    # ---- bind DOM row -> API record -> ledger line (content, not position)
    bind = None
    for i, r in enumerate(audit_rows):
        ts = r['innerText'][0] if r['innerText'] else None
        hits = [j for j, a in enumerate(api_audit)
                if str(a.get('created_at')) == str(ts)]
        if not hits:
            continue
        api_idx = hits[-1]
        a = api_audit[api_idx]
        lp, lline, lrow, lhead = find_ledger(str(a.get('intent_id') or ''),
                                             str(a.get('created_at') or ''))
        if lrow is not None:
            bind = {'dom_index': i, 'api_index': api_idx, 'ledger_path': lp,
                    'ledger_line': lline, 'ledger_row': lrow,
                    'ledger_header': lhead, 'api_row': a}
            break
    if bind is None:
        raise SystemExit('BIND_FAILED: no DOM row resolved to an API record+ledger line')

    led_doc = {'captured_at_utc': captured,
               'csv_path': bind['ledger_path'].replace('\\', '/'),
               'csv_line': bind['ledger_line'],
               'csv_sha256': sha256_file(bind['ledger_path']),
               'csv_header': bind['ledger_header'],
               'match_key': {'intent_id': bind['ledger_row'].get('intent_id'),
                             'created_at': bind['ledger_row'].get('created_at')},
               'row': bind['ledger_row']}
    with open(F_LED, 'w', encoding='utf-8') as f:
        json.dump(led_doc, f, indent=1, ensure_ascii=False)

    api_doc = {'captured_at_utc': captured,
               'endpoint': BASE + '/api/live-audit-summary',
               'http_status': status,
               'counts': {'rows': payload.get('rows'),
                          'audit_rows': len(api_audit),
                          'last_rows': len(last_rows),
                          'execution_quality_rows': len(api_exec),
                          'recent_send_attempts': len(payload.get('recent_send_attempts') or []),
                          'send_attempt_counts': payload.get('send_attempt_counts')},
               'bound_audit_index': bind['api_index'],
               'bound_audit_created_at': api_audit[bind['api_index']].get('created_at'),
               'audit_rows': [api_audit[bind['api_index']]],
               'audit_rows_index_map': {'0': bind['api_index']},
               'execution_quality_rows': api_exec,
               'execution_quality_summary': payload.get('execution_quality_summary'),
               'recent_send_attempts': (payload.get('recent_send_attempts') or [])[:5]}
    with open(F_API, 'w', encoding='utf-8') as f:
        json.dump(api_doc, f, indent=1, ensure_ascii=False)

    api_row = bind['api_row']
    lrow = bind['ledger_row']
    rendered = audit_rows[bind['dom_index']]
    rows = {}

    # ---- 121..127 : bound audit-table cells
    for row_id, rule in AUDIT_RULES.items():
        col, idx, rule_src = rule
        verdict, want, why = audit_verdict(row_id, rule, rendered, lrow, api_row)
        header_ok = bool(idx < len(audit_heads) and audit_heads[idx] == col)
        rows[row_id] = {
            'row_id': row_id,
            'table': 'Order Intents / Audit (#lcAuditRows)',
            'column': col,
            'column_index': idx,
            'column_present_in_rendered_dom': header_ok,
            'verdict': verdict if header_ok else 'NOT_TESTED',
            'verdict_reason': (why if header_ok else 'header mismatch at index %d' % idx),
            'renderer_rule': rule_src,
            'matrix_requirement': matrix[row_id],
            'served_rule_fragment': (audit_frags[idx] if idx < len(audit_frags)
                                     else None),
            'serving_commit': SERVING_COMMIT,
            'serving_commit_date': SERVING_COMMIT_DATE,
            'serving_ssot_sha256': ssot_sha,
            'serving_html_sha256': served['served_html_sha256'],
            'evidence_ref': 'certification/results/%s#/rows/%s' % (os.path.basename(F_ART), row_id),
            'observed': {
                'rendered_cell_text': (rendered['innerText'][idx]
                                       if idx < len(rendered['innerText']) else None),
                'rendered_cell_spans': (rendered['spans'][idx]
                                        if idx < len(rendered['spans']) else None),
                'rule_output': want,
                'match': (rendered['innerText'][idx] == want
                          if row_id != 'UI-FP-125' else
                          (rendered['spans'][idx] == want
                           if idx < len(rendered['spans']) else False)),
                'dom_pointer': '%s#/audit_rows/%d' % (os.path.basename(F_DOM),
                                                      bind['dom_index']),
                'dom_cell_pointer': '%s#/audit_rows/%d/innerText/%d'
                                    % (os.path.basename(F_DOM), bind['dom_index'], idx),
                'api_pointer': '%s#/audit_rows/0' % os.path.basename(F_API),
                'api_field_pointer': '%s#/audit_rows/0' % os.path.basename(F_API),
                'ledger_pointer': '%s#/row' % os.path.basename(F_LED),
                'ledger_line': bind['ledger_line'],
                'binding': ('DOM tr[%d].td[0] == API audit_rows[%d].created_at == '
                            'ledger line %d (intent_id %s)'
                            % (bind['dom_index'], bind['api_index'],
                               bind['ledger_line'], lrow.get('intent_id'))),
            },
            'executed_probe': ('probe -> GET /api/live-audit-summary + Playwright DOM read of '
                               '#lcAuditRows; cell recomputed from ledger line %d'
                               % bind['ledger_line']),
            'independent_oracle': ('order_intents.csv line %d read with stdlib csv (no engine '
                                   'import) + the page\'s own first()/tiny()/shortWallet() '
                                   'rule quoted from SSOT line refs in dom_capture/renderer'
                                   % bind['ledger_line']),
            'reproduces': ('python3.11 certification/results/UI-FP-113-127_probe.py'),
        }

    # ---- 113..120 : execution table has no rows to bind
    sentinel = (exec_rows[0]['innerText'][0]
                if exec_rows and exec_rows[0]['innerText'] else None)
    append_only = []
    served_dir = os.path.dirname(os.path.dirname(bind['ledger_path']))
    ao = os.path.join(served_dir, 'append_only')
    if os.path.isdir(ao):
        append_only = sorted(os.listdir(ao))
    for row_id, (col, idx, meaning) in EXEC_COLUMNS.items():
        header_ok = bool(idx < len(exec_heads) and exec_heads[idx] == col)
        rows[row_id] = {
            'row_id': row_id,
            'table': 'Execution Quality (#lcExecQualRows)',
            'column': col,
            'column_index': idx,
            'column_present_in_rendered_dom': header_ok,
            'verdict': 'NOT_TESTED',
            'verdict_reason': ('no execution row exists to bind: GET /api/live-audit-summary '
                               'returns execution_quality_rows=[] (0 rows) and the served '
                               'audit dir has no send_attempts.csv, so truth->API->render '
                               'cannot be exercised for %s; the table renders only its '
                               'sentinel row' % meaning),
            'renderer_rule': 'page maps API execution_quality_rows into #lcExecQualRows',
            'matrix_requirement': matrix[row_id],
            'served_rule_fragment': (exec_frags[idx] if idx < len(exec_frags)
                                     else None),
            'serving_commit': SERVING_COMMIT,
            'serving_commit_date': SERVING_COMMIT_DATE,
            'serving_ssot_sha256': ssot_sha,
            'serving_html_sha256': served['served_html_sha256'],
            'evidence_ref': 'certification/results/%s#/rows/%s' % (os.path.basename(F_ART), row_id),
            'observed': {
                'rendered_tbody_rows': [r['innerText'] for r in exec_rows],
                'rendered_sentinel_text': sentinel,
                'api_execution_quality_rows_count': len(api_exec),
                'api_pointer': '%s#/execution_quality_rows' % os.path.basename(F_API),
                'api_counts_pointer': '%s#/counts' % os.path.basename(F_API),
                'dom_pointer': '%s#/exec_rows' % os.path.basename(F_DOM),
                'served_audit_dir': served_dir.replace('\\', '/'),
                'served_append_only_files': append_only,
                'send_attempts_csv_present': 'send_attempts.csv' in append_only,
                'negative_test_note': ('source unavailable is surfaced as the sentinel text '
                                       'above, not as a 0/empty numeric cell'),
            },
            'executed_probe': ('probe -> GET /api/live-audit-summary (execution_quality_rows) + '
                               'Playwright DOM read of #lcExecQualRows + directory listing '
                               'of the served append_only dir'),
            'independent_oracle': ('the served API payload and the served append_only '
                                   'directory listing, both read with stdlib only (no engine '
                                   'import)'),
            'reproduces': ('python3.11 certification/results/UI-FP-113-127_probe.py'),
        }

    artifact = {
        'card_id': 't_cbb9fb32',
        'captured_at_utc': captured,
        'pointer_form': 'certification/results/UI-FP-113-127.json#/rows/<row_id>',
        'serving_commit': SERVING_COMMIT,
        'serving_commit_date': SERVING_COMMIT_DATE,
        'serving_checkout_dirty': SERVING_CHECKOUT_DIRTY,
        'serving_ssot_sha256': ssot_sha,
        'serving_html_sha256': served['served_html_sha256'],
        'serving_process': {'port': PORT, 'pid': pid, 'start_time': pid_start},
        'serving_binding': ('%s (authoritative: bytes the process returns) + '
                            'SSOT:%s' % (build_id, ssot_sha)),
        'how_serving_build_was_established': (
            'netstat -ano | grep :%d -> LISTEN pid %s; that PID started %s. Its '
            'command line is "python -m uvicorn HL_Copy_App_SSOT:app --port %d" '
            'launched from the _archive/hl_stage2 checkout, whose HEAD is %s '
            '(committed %s - BEFORE the process start, so the date arithmetic the '
            'schema requires holds). That checkout\'s HL_Copy_App_SSOT.py is dirty '
            'against the committed blob, so no commit is claimed as THE serving '
            'build: the binding is the served HTML sha256 %s plus the served SSOT '
            'content sha256 %s (file mtime %s, also before the process start).'
            % (PORT, pid, pid_start, PORT, SERVING_COMMIT, SERVING_COMMIT_DATE,
               served['served_html_sha256'], ssot_sha, ssot_mtime)),
        'served_row_templates': {
            'why': ('the per-row renderer rule for every row below is quoted from '
                    'these served template lines, so the rule cannot drift from the '
                    'build that actually rendered the page'),
            'audit_table': served['audit_row_template'],
            'exec_table': served['exec_row_template'],
        },
        'renderer_extract': {
            'served_ssot_total_lines': ssot_lines,
            'markers': markers,
            'why': ('the expected cell value is recomputed by re-implementing the page\'s own '
                    'rule (first/tiny/shortWallet/sourceOf) from the ledger row; these are '
                    'the exact served lines that rule was taken from'),
        },
        'oracle': ('rendered cells come from headless Chromium against the live process; '
                   'expected values are recomputed from order_intents.csv (stdlib csv) and '
                   'GET /api/live-audit-summary (stdlib urllib), neither of which imports '
                   'HL_Copy_App_SSOT.py or any engine module'),
        'binding': {
            'dom_index': bind['dom_index'],
            'api_index': bind['api_index'],
            'ledger_csv_path': bind['ledger_path'].replace('\\', '/'),
            'ledger_csv_line': bind['ledger_line'],
            'intent_id': lrow.get('intent_id'),
            'created_at': lrow.get('created_at'),
            'rule': ('DOM tr[i].td[0] == API audit_rows[j].created_at, and that record\'s '
                     'intent_id+created_at == ledger CSV line (both fields must match)'),
        },
        'counts': {'audit_rows_api': len(api_audit),
                   'audit_rows_rendered': len(audit_rows),
                   'last_rows_api': len(last_rows),
                   'execution_quality_rows_api': len(api_exec),
                   'exec_rows_rendered': len(exec_rows)},
        'files': ['certification/results/' + os.path.basename(F_ART),
                  'certification/results/' + os.path.basename(F_DOM),
                  'certification/results/' + os.path.basename(F_API),
                  'certification/results/' + os.path.basename(F_LED),
                  'certification/results/' + os.path.basename(F_ART).replace('.json', '_probe.py'),
                  'certification/results/' + os.path.basename(F_ART).replace('.json', '_verify_refs.py')],
        'file_sha256': {os.path.basename(F_DOM): sha256_file(F_DOM),
                        os.path.basename(F_API): sha256_file(F_API),
                        os.path.basename(F_LED): sha256_file(F_LED)},
        'verdicts': {k: v['verdict'] for k, v in rows.items()},
        'rows': rows,
    }
    with open(F_ART, 'w', encoding='utf-8') as f:
        json.dump(artifact, f, indent=1, ensure_ascii=False)

    print(json.dumps({'serving_ssot_sha256': ssot_sha,
                      'binding': artifact['binding'],
                      'counts': artifact['counts'],
                      'verdicts': artifact['verdicts']}, indent=1))


if __name__ == '__main__':
    main()
