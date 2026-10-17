#!/usr/bin/env python3
'''B3-CERT t_a78e24ee - UI-FP 030/041/048/052/054/055 re-probe against the SERVING build.

READ-ONLY. No engine import, no state-mutating POST, no contact with Edge/CDP 9223 or the
:8031 process. Route: playwright.chromium headless (py3.11) -> http://127.0.0.1:8031/live-copy.
Independent oracle: the served JSON APIs + an on-disk state_dir snapshot.

Run (from repo root C:/Users/wigmore/hyperliquid-build3-repair):
  export PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \
      EVIDENCE/ui_fp/scripts/probe_ui_fp_6rows_t_a78e24ee.py
'''
import json, os, sys, hashlib, subprocess, datetime, urllib.request

BASE = 'http://127.0.0.1:8031'
SERVING_CHECKOUT = 'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert'
SSOT_REL = '_archive/hl_stage2/HL_Copy_App_SSOT.py'
SSOT_ABS = SERVING_CHECKOUT + '/' + SSOT_REL
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.normpath(os.path.join(HERE, '..', 'raw'))
OUT = os.path.join(RAW, 'probe_t_a78e24ee_raw.json')


def jget(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def measure_serving_build():
    '''Measure, do not copy: commit + SSOT sha256 of the checkout that serves /live-copy.'''
    commit = subprocess.check_output(['git', '-C', SERVING_CHECKOUT, 'rev-parse', 'HEAD']).decode().strip()
    disk_sha = sha256_file(SSOT_ABS)
    head_blob = subprocess.check_output(['git', '-C', SERVING_CHECKOUT, 'show', 'HEAD:' + SSOT_REL])
    head_sha = hashlib.sha256(head_blob).hexdigest()
    st = os.stat(SSOT_ABS)
    return {
        'serving_checkout': SERVING_CHECKOUT,
        'ssot_path': SSOT_ABS,
        'serving_commit': commit,
        'serving_ssot_sha256': disk_sha,
        'head_blob_sha256': head_sha,
        'worktree_matches_HEAD': disk_sha == head_sha,
        'ssot_bytes': st.st_size,
        'ssot_mtime_utc': datetime.datetime.utcfromtimestamp(st.st_mtime).isoformat() + 'Z',
        'how_measured': 'git -C %s rev-parse HEAD ; hashlib.sha256 over %s ; git show HEAD:%s' % (
            SERVING_CHECKOUT, SSOT_ABS, SSOT_REL),
    }


JS_DOM = r'''() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const rows = [];
  document.querySelectorAll('tr').forEach(tr => {
    const w = tr.dataset.wallet;
    if (!w) return;
    const txt = tr.innerText || '';
    const cells = Array.from(tr.querySelectorAll('td')).map(td => norm(td.innerText));
    rows.push({
      wallet: w,
      avg_bps_text: (txt.match(/Avg bps:\s*([^\n|]+)/) || [])[1] || null,
      open_pos_text: (txt.match(/Open pos:\s*([^\n|]+)/) || [])[1] || null,
      selects: Array.from(tr.querySelectorAll('select')).map(s => ({name: s.name || '', value: s.value || '', options: Array.from(s.options).map(o => o.value)})),
      inputs: Array.from(tr.querySelectorAll('input')).map(i => ({name: i.name || '', value: i.value || '', type: i.type || ''})),
      cells: cells.slice(0, 12),
    });
  });
  const panel = document.querySelector('#liveCopyPanel');
  const ptxt = panel ? (panel.innerText || '') : '';
  return {
    n_wallet_rows: rows.length,
    rows: rows,
    has_lcGraphScale: document.documentElement.outerHTML.indexOf('lcGraphScale') >= 0,
    graph_start_inputs: document.querySelectorAll('input#lcGraphStart').length,
    graph_end_inputs: document.querySelectorAll('input#lcGraphEnd').length,
    graph_scale_buttons: Array.from(document.querySelectorAll('button[data-lc-graph-scale]')).map(b => b.getAttribute('data-lc-graph-scale')),
    graph_label: (ptxt.match(/Exchange account graph[^\n]*/) || [null])[0],
  };
}'''


def main():
    os.makedirs(RAW, exist_ok=True)
    r = {'tested_at_utc': datetime.datetime.utcnow().isoformat() + 'Z', 'card_id': 't_a78e24ee'}
    r['serving_build'] = measure_serving_build()

    # --- oracle: served JSON APIs (no engine import) ---
    r['api_live_config'] = jget('/api/live-config')
    r['api_ui_state'] = jget('/api/ui-state')
    r['api_state'] = jget('/api/state')
    aud = jget('/api/live-audit-summary')
    lp = aud.get('live_leader_performance') or {}
    r['api_leader_perf'] = {w: {'avg_diff_bps': v.get('avg_diff_bps'),
                                'open_position_count': v.get('open_position_count')}
                            for w, v in lp.items() if isinstance(v, dict)}

    # --- oracle: on-disk state_dir snapshot (path self-reported by the serving app) ---
    nets = (jget('/api/global-controls') or {}).get('networks') or {}
    r['api_networks'] = nets
    sdir = (nets.get('state_dir') or '').replace('\\', '/')
    r['state_dir'] = sdir
    for nm in ('live_config.json', 'ui_state.json'):
        p = sdir + '/' + nm
        try:
            r['disk_' + nm.replace('.json', '')] = json.load(open(p, encoding='utf-8'))
            r['disk_' + nm.replace('.json', '') + '_sha256'] = sha256_file(p)
        except Exception as e:
            r['disk_' + nm.replace('.json', '') + '_err'] = '%s: %r' % (type(e).__name__, e)
    # the account snapshot is huge and no row uses its body: record identity, not bytes
    p = sdir + '/exchange_account_snapshot_app.json'
    try:
        snap = json.load(open(p, encoding='utf-8'))
        r['disk_exchange_account_snapshot_app'] = {
            'sha256': sha256_file(p),
            'bytes': os.path.getsize(p),
            'fetched_at_ms': snap.get('fetched_at_ms'),
            'open_position_count': snap.get('open_position_count'),
            'note': 'body omitted deliberately - 2.8MB, unused by these six rows; identity fields kept',
        }
    except Exception as e:
        r['disk_exchange_account_snapshot_app_err'] = '%s: %r' % (type(e).__name__, e)

    # --- runtime: rendered DOM + full request log (proves read-only) ---
    from playwright.sync_api import sync_playwright
    reqs = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            pg.on('request', lambda q: reqs.append({'method': q.method, 'url': q.url}))
            pg.goto(BASE + '/live-copy', wait_until='networkidle', timeout=45000)
            r['page_title'] = pg.title()
            r['dom'] = pg.evaluate(JS_DOM)
            n_before = len(reqs)
            for scale in ('7d', '1d'):
                try:
                    pg.click("button[data-lc-graph-scale='%s']" % scale, timeout=5000)
                    pg.wait_for_timeout(900)
                    r['graph_after_' + scale] = pg.evaluate(
                        "() => {const t=document.querySelector('#liveCopyPanel');const m=(t?t.innerText:'').match(/Exchange account graph[^\\n]*/);return m?m[0]:null;}")
                except Exception as e:
                    r['graph_after_' + scale + '_err'] = '%s: %r' % (type(e).__name__, e)
            r['active_scale'] = pg.evaluate(
                "() => {const b=document.querySelector('button[data-lc-graph-scale].active');return b?b.getAttribute('data-lc-graph-scale'):null;}")
            r['reqs_during_interaction'] = len(reqs) - n_before
        finally:
            b.close()
    r['requests'] = reqs
    r['requests_non_get'] = [q for q in reqs if q['method'] != 'GET']

    # --- per-row binding + verdicts ---
    cfg_wallets = ((r['api_live_config'] or {}).get('config') or {}).get('wallets') or {}
    us = r['api_ui_state'] or {}
    perf = {k.lower(): v for k, v in r['api_leader_perf'].items()}
    res = {'n_rows': 0, 'bps_match': 0, 'bps_mismatch': 0, 'bps_na': 0, 'op_match': 0, 'op_mismatch': 0,
           'mode_match': 0, 'mode_mismatch': 0, 'fixed_notional_match': 0, 'fixed_notional_mismatch': 0,
           'norm_base_match': 0, 'norm_base_mismatch': 0, 'mismatch_detail': []}
    for d in (r['dom'] or {}).get('rows') or []:
        w = d['wallet']; wl = w.lower(); res['n_rows'] += 1
        ap = perf.get(wl); cw = cfg_wallets.get(w) or cfg_wallets.get(wl) or {}
        if ap and d['avg_bps_text'] and d['avg_bps_text'] != 'n/a' and ap['avg_diff_bps'] is not None:
            if abs(float(d['avg_bps_text']) - float(ap['avg_diff_bps'])) < 0.06:
                res['bps_match'] += 1
            else:
                res['bps_mismatch'] += 1; res['mismatch_detail'].append(['bps', w, d['avg_bps_text'], ap['avg_diff_bps']])
        elif d['avg_bps_text'] == 'n/a':
            res['bps_na'] += 1
        if ap and d['open_pos_text'] and ap['open_position_count'] is not None:
            if str(d['open_pos_text']) == str(ap['open_position_count']):
                res['op_match'] += 1
            else:
                res['op_mismatch'] += 1; res['mismatch_detail'].append(['open_pos', w, d['open_pos_text'], ap['open_position_count']])
        mv = [s['value'] for s in d['selects'] if s['name'] == 'mode']
        if mv and cw.get('mode'):
            if mv[0] == cw['mode']:
                res['mode_match'] += 1
            else:
                res['mode_mismatch'] += 1; res['mismatch_detail'].append(['mode', w, mv[0], cw.get('mode')])
        fv = [i['value'] for i in d['inputs'] if i['name'] == 'fixed_notional']
        if fv and cw.get('fixed_notional') is not None:
            if abs(float(fv[0]) - float(cw['fixed_notional'])) < 0.01:
                res['fixed_notional_match'] += 1
            else:
                res['fixed_notional_mismatch'] += 1; res['mismatch_detail'].append(['fixed_notional', w, fv[0], cw.get('fixed_notional')])
        nv = [i['value'] for i in d['inputs'] if i['name'] == 'norm_base']
        if nv and us.get('norm_base') is not None:
            if abs(float(nv[0]) - float(us['norm_base'])) < 0.01:
                res['norm_base_match'] += 1
            else:
                res['norm_base_mismatch'] += 1; res['mismatch_detail'].append(['norm_base', w, nv[0], us.get('norm_base')])
    r['bind_tally'] = res

    with open(OUT, 'w', encoding='utf-8', newline='\n') as _f:
        json.dump(r, _f, indent=1, ensure_ascii=False)
    print('wrote', OUT)
    print('serving_commit', r['serving_build']['serving_commit'])
    print('serving_ssot_sha256', r['serving_build']['serving_ssot_sha256'], 'matches_HEAD', r['serving_build']['worktree_matches_HEAD'])
    print('title', r.get('page_title'), 'dom_rows', (r['dom'] or {}).get('n_wallet_rows'))
    print('non_get_requests', r['requests_non_get'], 'reqs', len(r['requests']))
    print('bind_tally', json.dumps(res))
    print('graph_label', (r['dom'] or {}).get('graph_label'))
    print('graph_after_7d', r.get('graph_after_7d'))
    print('graph_after_1d', r.get('graph_after_1d'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
