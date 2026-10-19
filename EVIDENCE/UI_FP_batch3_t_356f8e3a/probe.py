#!/usr/bin/env python3
'''UI-FP batch 3 (rows 101-150) reproduction probe.

Independent oracle: never imports HL_Copy_App_SSOT.py. Reads the served HTML,
the served /api/live-audit-summary JSON, the append-only CSVs, and re-derives
every claim in UI_FP_batch3_t_356f8e3a.json.

  python probe.py          # offline, from committed captures
  python probe.py --live   # re-fetch captures from 127.0.0.1:8023 first
'''
import argparse, csv, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.environ.get('UI_FP_INSTANCE',
    'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/'
    'build3_live_screen_0513_8023_instance_20261019T074010Z')
SSOT = os.path.join(INSTANCE, 'HL_Copy_App_SSOT.py')
APPO = os.path.join(INSTANCE, 'hl_live_copy_audit', 'append_only')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def rows_of(p):
    if not os.path.exists(p):
        return None
    with open(p, 'r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def line_of(src, needle, after=0):
    for i, ln in enumerate(src.splitlines(), 1):
        if i > after and needle in ln:
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', action='store_true')
    a = ap.parse_args()
    if a.live:
        import urllib.request
        for url, name in (('http://127.0.0.1:8023/live-copy', 'live_copy.html'),
                          ('http://127.0.0.1:8023/api/live-audit-summary',
                           'audit_summary.json')):
            r = urllib.request.Request(url, headers={'x-requested-with': 'fetch'})
            open(os.path.join(HERE, name), 'wb').write(
                urllib.request.urlopen(r, timeout=180).read())

    html = open(os.path.join(HERE, 'live_copy.html'), encoding='utf-8').read()
    api = json.load(open(os.path.join(HERE, 'audit_summary.json'), encoding='utf-8'))
    dom = json.load(open(os.path.join(HERE, 'dom_capture.json'), encoding='utf-8'))
    src = open(SSOT, 'rb').read().decode('utf-8', 'replace')

    o = {'serving_ssot_path': SSOT,
         'serving_ssot_sha256': sha256(SSOT),
         'serving_ssot_mtime': os.path.getmtime(SSOT)}

    pid = None
    net = subprocess.run(['netstat', '-ano'], capture_output=True, text=True).stdout
    for ln in net.splitlines():
        if '127.0.0.1:8023' in ln and 'LISTENING' in ln:
            pid = int(ln.split()[-1]); break
    o['serving_pid'] = pid
    if pid:
        o['serving_pid_start_utc'] = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-Process -Id %d).StartTime.ToUniversalTime()."
             "ToString('o')" % pid], capture_output=True, text=True).stdout.strip()

    keys = ['last_rows', 'execution_quality_rows', 'send_terminal_rows',
            'legacy_terminal_rows', 'manual_reconciliation_rows',
            'owned_copy_positions', 'orphan_exchange_positions',
            'real_copy_positions', 'recent_send_attempts', 'reconciliation_rows']
    o['api_counts'] = {k: len(api.get(k) or []) for k in keys}
    o['exchange_snapshot'] = {k: (api.get('exchange_account_snapshot') or {}).get(k)
                              for k in ('ok', 'available', 'status', 'reason')}

    files = {}
    for n in ('order_intents.csv', 'reconciliation.csv',
              'send_attempts.csv', 'live_fills.csv'):
        p = os.path.join(APPO, n)
        files[n] = {'exists': os.path.exists(p),
                    'bytes': os.path.getsize(p) if os.path.exists(p) else 0}
    o['append_only'] = files

    oi = rows_of(os.path.join(APPO, 'order_intents.csv')) or []
    rec = rows_of(os.path.join(APPO, 'reconciliation.csv')) or []
    o['order_intents_rows'] = len(oi)
    o['order_intents_columns'] = list(oi[0].keys()) if oi else []
    ev = {}
    for r in rec:
        ev[r.get('event', '')] = ev.get(r.get('event', ''), 0) + 1
    o['reconciliation_event_counts'] = ev
    o['send_terminal_event_rows'] = sum(v for k, v in ev.items()
                                        if k in ('SEND_TERMINAL', 'SEND_REJECTED'))

    for k in ('auditHeaders', 'auditRows', 'execRows', 'execHeaders', 'ownedRows',
              'orphanRows', 'critRows', 'warnRows', 'chipsExec', 'realOrders'):
        v = dom.get(k)
        o['dom_' + k] = len(v) if isinstance(v, list) else v
    o['dom_audit_first_row'] = (dom.get('auditRows') or [None])[0]

    # NOTE: the '<td' needle below is a text search over the served HTML file on
    # disk, not a DOM write. Nothing here injects HTML into a page.
    i = html.find("#lcExecQualRows').innerHTML=rows.map")
    tpl = html[i:html.find('</tr>`', i)]
    o['exec_template_td_count'] = tpl.count('<td')
    o['exec_template_source_offset'] = i
    # second-row cross-check: DOM row 1 must be the second-newest CSV intent
    o['cross_check_row1'] = (dom.get('auditRows') or [None, None])[1]
    if len(oi) >= 2:
        prev = oi[-2]
        o['cross_check_csv_prev'] = [prev.get('created_at'),
                                     (prev.get('leader_wallet') or '')[:10] + '...'
                                     + (prev.get('leader_wallet') or '')[-6:],
                                     prev.get('coin'), prev.get('source')]

    want = ['side', 'status', 'execution_decision', 'decision_reason',
            'suggested_limit_price', 'target_price', 'adverse_diff_pct',
            'diff_pct', 'real_diff_pct', 'price_diff_pct',
            'manual_reconcile_required']
    o['audit_field_presence'] = {w: (w in (oi[0] if oi else {})) for w in want}

    o['engine_lines'] = {
        'api_live_audit_summary': line_of(src, '@app.get("/api/live-audit-summary")'),
        'audit_summary_builder': line_of(src, 'def _live_audit_summary()'),
        'last_rows_cap_20': line_of(src, 'last_rows.pop(0)'),
        'render_audit_last10': line_of(
            src, 'const rows=(lcAudit.last_rows||[]).slice(-10).reverse();'),
        'render_audit_row_template': line_of(
            src, "root.querySelector('#lcAuditRows').innerHTML=rows.map"),
        'render_exec_row_template': line_of(
            src, "root.querySelector('#lcExecQualRows').innerHTML=rows.map"),
        'exec_rows_builder': line_of(src, 'def _build_execution_quality_rows('),
        'orphan_gate_exchange_available': line_of(src, 'if exchange_available:', 2591),
        'owned_row_type': line_of(src, '"row_type": "OWNED_COPY"'),
        'terminal_row_filter': line_of(
            src, 'send_terminal_rows = [r for r in reconciliation_rows'),
        'render_recon_critical': line_of(
            src, 'if(cbox) cbox.innerHTML=critical.map(terminalRow)'),
        'render_recon_warning': line_of(
            src, 'if(wbox) wbox.innerHTML=warnings.map(terminalRow)'),
    }

    o['assertions'] = {
        'exec_rows_present': bool(api.get('execution_quality_rows')),
        'send_attempts_file_exists': files['send_attempts.csv']['exists'],
        'live_fills_file_exists': files['live_fills.csv']['exists'],
        'exchange_snapshot_available': bool(
            (api.get('exchange_account_snapshot') or {}).get('available')),
        'orphan_rows_present': bool(api.get('orphan_exchange_positions')),
        'owned_rows_present': bool(api.get('owned_copy_positions')),
        'terminal_rows_present': bool(api.get('send_terminal_rows')),
        'audit_rows_rendered': len(dom.get('auditRows') or []),
        'exec_columns_match': o['exec_template_td_count'] == len(
            dom.get('execHeaders') or []),
    }
    print(json.dumps(o, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
