"""Reusable UI evidence capture: full metric keys, unellipsised text, mutation control.

See EVIDENCE/ui_capture/README.md for the full rationale and the run commands.
READ-ONLY by default (GET only). --mutation refuses port 8031.
"""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path
from typing import Any, Dict, List, Optional

JS = r"""
() => {
  const cl = (s) => (s == null ? null : String(s).replace(/\s+/g, ' ').trim());
  // NEVER call Number() on this blindly: Number('0x7ae3b0...') parses a wallet
  // address as HEX and silently yields 7.0157e+47. Only genuine decimal
  // literals are converted; everything else is kept as the raw string.
  const NUMERIC = /^-?\d+(\.\d+)?([eE][-+]?\d+)?$/;
  const sv = (el) => { const r = el.getAttribute('data-sort'); if (r == null) return null;
    if (!NUMERIC.test(r.trim())) return r;
    const n = Number(r); return Number.isFinite(n) ? n : r; };
  const cell = (el) => {
    const rendered = cl(el.textContent), title = cl(el.getAttribute('title')), aria = cl(el.getAttribute('aria-label'));
    const ds = sv(el);
    // a string data-sort IS the underlying value (wallet rows render a shortened
    // form like 0x7ae3b0...5e9205 and keep the full id only here)
    const c = [title, aria, typeof ds === 'string' ? ds : null, rendered].filter((x) => x != null && x !== '');
    let nested = null;
    for (const n of el.querySelectorAll('*')) { const t = cl(n.textContent);
      if (t && (t.indexOf('\u2026') !== -1 || n.scrollWidth > n.clientWidth + 1)) {
        nested = {rendered: t, title: cl(n.getAttribute('title')), aria: cl(n.getAttribute('aria-label')),
                  scroll_width: n.scrollWidth, client_width: n.clientWidth}; break; } }
    return {rendered_text: rendered, title_attr: title, aria_label_attr: aria,
            underlying_value: c.length ? c.sort((a, b) => b.length - a.length)[0] : null,
            data_sort: sv(el), class_name: cl(el.getAttribute('class')),
            scroll_width: el.scrollWidth, client_width: el.clientWidth,
            css_truncated: el.scrollWidth > el.clientWidth + 1, nested_truncated_node: nested};
  };
  const tables = Array.from(document.querySelectorAll('table')).map((tbl, ti) => ({
    table_index: ti, id: tbl.getAttribute('id'),
    head: Array.from(tbl.querySelectorAll('thead th')).map((th) => {
      const a = th.querySelector('a[href^="/sort/"]'), href = a ? a.getAttribute('href') : null;
      return {full_key: href && href.indexOf('/sort/') === 0 ? href.slice(6) : null,
              rendered_label: cl(th.textContent), title_attr: cl(th.getAttribute('title')),
              sort_href: href, class_name: cl(th.getAttribute('class'))}; }),
    rows: Array.from(tbl.querySelectorAll('tbody tr')).map((tr, ri) => ({
      row_index: ri, class_name: cl(tr.getAttribute('class')),
      cells: Array.from(tr.querySelectorAll('td')).map(cell) }))
  }));
  const inputs = Array.from(document.querySelectorAll('input, select, textarea')).map((el) => ({
    id: el.getAttribute('id'), name: el.getAttribute('name'), type: el.getAttribute('type'),
    value: el.value, title_attr: cl(el.getAttribute('title')),
    checked: el.type === 'checkbox' ? !!el.checked : null}));
  const txt = document.body ? document.body.innerText : '';
  const i = txt.indexOf('CONTRACT WARNING');
  return {url: location.href, title: document.title, captured_at_ms: Date.now(),
          contract_warning_present: i !== -1,
          contract_warning_text: i === -1 ? null : cl(txt.slice(i, i + 700)), tables: tables,
          inputs: inputs};
}
"""


def sha_file(p: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(p, 'rb') as fh:
            for b in iter(lambda: fh.read(1 << 20), b''):
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ps(cmd: str) -> str:
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],
                           capture_output=True, timeout=90)
        return r.stdout.decode('utf-8', 'replace')
    except Exception as e:
        return '__PS_FAILED__ %s: %s' % (type(e).__name__, e)


def bind_process(port: int) -> Dict[str, Any]:
    """Which process serves the port, since when, and the sha256 of the SSOT file it executes."""
    info: Dict[str, Any] = {'port': port, 'pid': None, 'start_time': None, 'command_line': None,
                            'ssot_path': None, 'ssot_sha256': None,
                            'method': 'Get-NetTCPConnection owning PID -> Win32_Process start/cmdline -> sha256 of SSOT on cmdline'}
    out = ps('$c = Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; '
             'if($c){$p = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)"; '
             'Write-Output ("PID=" + $p.ProcessId); Write-Output ("START=" + $p.CreationDate.ToString("o")); '
             'Write-Output ("CMD=" + $p.CommandLine)} else { Write-Output "PID=" }' % port)
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('PID='):
            v = line[4:].strip()
            info['pid'] = int(v) if v.isdigit() else None
        elif line.startswith('START='):
            info['start_time'] = line[6:].strip() or None
        elif line.startswith('CMD='):
            info['command_line'] = line[4:].strip() or None
    for tok in (info.get('command_line') or '').replace('"', ' ').split():
        if tok.lower().endswith('hl_copy_app_ssot.py') and Path(tok).exists():
            info['ssot_path'] = str(Path(tok))
            info['ssot_sha256'] = sha_file(Path(tok))
            break
    return info


def capture(url: str, out_dir: Path, tag: str) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={'width': 1400, 'height': 1000})
        r = pg.goto(url, wait_until='networkidle', timeout=90000)
        st = r.status if r is not None else None
        pg.wait_for_timeout(1500)
        data = pg.evaluate(JS)
        html = pg.content()
        b.close()
    hp = out_dir / ('dom_%s.html' % tag)
    hp.write_text(html, encoding='utf-8')
    data.update({'http_status': st, 'served_html_sha256': sha_bytes(html.encode('utf-8')),
                 'served_html_path': str(hp), 'served_html_bytes': len(html.encode('utf-8'))})
    return data


def flatten(cap: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for t in cap.get('tables', []):
        keys = [h.get('full_key') or ('col%d' % i) for i, h in enumerate(t.get('head', []))]
        flat['t%d.__headers__' % t['table_index']] = keys
        for r in t.get('rows', []):
            for i, c in enumerate(r.get('cells', [])):
                flat['t%d.r%d.%s' % (t['table_index'], r['row_index'], keys[i] if i < len(keys) else i)] = c.get('underlying_value')
    # form controls carry served truth too (global controls: gcMaxOrder etc.)
    for el in cap.get('inputs', []) or []:
        key = el.get('id') or el.get('name')
        if key:
            flat['input.%s' % key] = el.get('value')
    return flat


def key_integrity(cap: Dict[str, Any], expected: List[str]) -> Dict[str, Any]:
    keys = [h['full_key'] for t in cap.get('tables', []) for h in t.get('head', []) if h.get('full_key')]
    res: Dict[str, Any] = {'all_header_keys': keys, 'expected_keys': {}, 'truncated_forms_present': []}
    for k in expected:
        pre = [x for x in keys if x != k and k.startswith(x)]
        res['expected_keys'][k] = {'present_full': k in keys, 'also_seen_as_prefix': pre}
        res['truncated_forms_present'].extend(pre)
    res['all_expected_present_full'] = all(v['present_full'] for v in res['expected_keys'].values())
    res['no_truncated_prefixes'] = not res['truncated_forms_present']
    return res


def truncation_report(cap: Dict[str, Any]) -> Dict[str, Any]:
    clipped, rec = [], []
    n = 0
    for t in cap.get('tables', []):
        keys = [h.get('full_key') or ('col%d' % i) for i, h in enumerate(t.get('head', []))]
        for r in t.get('rows', []):
            for i, c in enumerate(r.get('cells', [])):
                n += 1
                txt = c.get('rendered_text') or ''
                if c.get('css_truncated') or '\u2026' in txt or c.get('nested_truncated_node'):
                    e = {'table': t['table_index'], 'row': r['row_index'], 'column': keys[i] if i < len(keys) else i,
                         'rendered_text': txt, 'underlying_value': c.get('underlying_value'),
                         'title_attr': c.get('title_attr'), 'aria_label_attr': c.get('aria_label_attr'),
                         'scroll_width': c.get('scroll_width'), 'client_width': c.get('client_width'),
                         'nested': c.get('nested_truncated_node')}
                    clipped.append(e)
                    if c.get('underlying_value') and c.get('underlying_value') != txt:
                        rec.append(e)
    return {'cells_examined': n, 'cells_clipped': len(clipped), 'cells_recovered_from_attributes': len(rec),
            'clipped': clipped[:50], 'recovered': rec[:50]}


def metric_focus(cap: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in keys:
        hit: Dict[str, Any] = {'full_key': k, 'header': None, 'cells': []}
        for t in cap.get('tables', []):
            for i, h in enumerate(t.get('head', [])):
                if h.get('full_key') == k:
                    hit['header'] = h
                    for r in t.get('rows', []):
                        if i < len(r.get('cells', [])):
                            c = r['cells'][i]
                            hit['cells'].append({'row_index': r['row_index'], 'row_class': r.get('class_name'),
                                                 'rendered_text': c.get('rendered_text'),
                                                 'underlying_value': c.get('underlying_value'),
                                                 'data_sort': c.get('data_sort'),
                                                 'css_truncated': c.get('css_truncated')})
                    break
            if hit['header']:
                break
        out[k] = hit
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8031/')
    ap.add_argument('--out', required=True)
    ap.add_argument('--expect-key', action='append', default=None)
    ap.add_argument('--mutation', action='store_true')
    ap.add_argument('--mutation-config')
    ap.add_argument('--mutation-key', default='global_controls.max_order_notional_usd')
    ap.add_argument('--mutation-delta', type=float, default=37.0)
    ap.add_argument('--serve-path')
    a = ap.parse_args()

    expect = a.expect_key or ['pct_entries_ge10']
    out_dir = Path(a.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    port = 8031
    try:
        port = int(a.url.split('//', 1)[1].split('/', 1)[0].split(':')[1])
    except Exception:
        pass

    art: Dict[str, Any] = {'harness': 'tools/ui_capture_harness.py', 'version': '1.0.0',
                           'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'url': a.url, 'port': port,
                           'python': sys.executable,
                           'playwright_browsers_path': os.environ.get('PLAYWRIGHT_BROWSERS_PATH'),
                           'capture_mode': 'READ_ONLY_GET'}
    art['serving_process'] = bind_process(port)
    if a.serve_path:
        p = Path(a.serve_path).resolve()
        art['serving_process'].update({'declared_serve_path': str(p),
                                       'declared_serve_path_sha256': sha_file(p),
                                       'declared_matches_process': art['serving_process'].get('ssot_sha256') == sha_file(p)})

    base = capture(a.url, out_dir, 'baseline')
    art['baseline'] = base
    art['key_integrity'] = key_integrity(base, expect)
    art['truncation_check'] = truncation_report(base)
    art['metric_focus'] = metric_focus(base, expect)

    if a.mutation:
        art['capture_mode'] = 'ISOLATED_MUTATION_CONTROL'
        mc: Dict[str, Any] = {'requested': True, 'verdict': None, 'notes': [], 'steps': []}
        if port == 8031:
            mc['verdict'] = 'REFUSED'
            mc['notes'].append('refused: the mutation control may not run against the live :8031 dashboard')
        elif not a.mutation_config:
            mc['verdict'] = 'REFUSED'
            mc['notes'].append('refused: --mutation-config is required and must be the isolated copy')
        elif not Path(a.mutation_config).exists():
            mc['verdict'] = 'REFUSED'
            mc['notes'].append('config not found: %s' % a.mutation_config)
        else:
            cfg = Path(a.mutation_config).resolve()
            orig_bytes = cfg.read_bytes()
            orig = json.loads(orig_bytes.decode('utf-8-sig'))
            before = flatten(base)
            parts = a.mutation_key.split('.')
            node: Any = orig
            ok = True
            try:
                for k in parts[:-1]:
                    node = node[k]
                old = node[parts[-1]]
                new = float(old) + a.mutation_delta
                node[parts[-1]] = new
            except Exception as e:
                ok = False
                mc['verdict'] = 'REFUSED'
                mc['notes'].append('cannot bump %s: %s: %s' % (a.mutation_key, type(e).__name__, e))
            if ok:
                cfg.write_text(json.dumps(orig, indent=2), encoding='utf-8')
                bumped = capture(a.url, out_dir, 'bumped')
                art['bumped'] = bumped
                cfg.write_bytes(orig_bytes)
                restored = capture(a.url, out_dir, 'restored')
                art['restored'] = restored
                after, back = flatten(bumped), flatten(restored)

                def d(x, y):
                    return {k: {'baseline': x.get(k), 'other': y.get(k)} for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)}

                bd, rd = d(before, after), d(before, back)
                mc.update({'bump_diff_count': len(bd), 'restore_residual_count': len(rd),
                           'bump_diff': dict(list(bd.items())[:25]),
                           'restore_residual': dict(list(rd.items())[:25]),
                           'steps': [{'step': 'baseline', 'value': old},
                                     {'step': 'bumped', 'value': new, 'diff_keys': list(bd)[:15]},
                                     {'step': 'restored', 'residual_keys': list(rd)[:15]}],
                           'config_file': str(cfg), 'config_sha256_before': sha_bytes(orig_bytes),
                           'config_sha256_after_restore': sha_file(cfg)})
                if not bd:
                    mc['verdict'] = 'FAIL'
                    mc['notes'].append('the bump produced NO observable diff: this capture is not observing the value')
                elif rd:
                    mc['verdict'] = 'PARTIAL'
                    mc['notes'].append('bump observed; restore left residuals (inspect the keys)')
                else:
                    mc['verdict'] = 'PASS'
                    mc['notes'].append('bump observed in the capture and fully reverted by the restore')
        art['mutation_control'] = mc

    art['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    apath = out_dir / 'capture.json'
    apath.write_text(json.dumps(art, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'artifact': str(apath),
                      'serving_pid': art['serving_process'].get('pid'),
                      'serving_start': art['serving_process'].get('start_time'),
                      'ssot_sha256': art['serving_process'].get('ssot_sha256'),
                      'full_keys_ok': art['key_integrity']['all_expected_present_full'],
                      'truncated_prefixes': art['key_integrity']['truncated_forms_present'],
                      'cells_clipped': art['truncation_check']['cells_clipped'],
                      'cells_recovered': art['truncation_check']['cells_recovered_from_attributes'],
                      'contract_warning_present': base.get('contract_warning_present'),
                      'mutation_verdict': (art.get('mutation_control') or {}).get('verdict'),
                      'pct_entries_ge10_cells': [c['rendered_text'] for c in art['metric_focus'].get('pct_entries_ge10', {}).get('cells', [])]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
