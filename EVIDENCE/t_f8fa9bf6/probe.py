import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

WS = Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_f8fa9bf6')
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8119'
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else WS / 'dom_probe.json'


def api(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=30))


def js_fmt_axis(n):
    sign = '-' if n < 0 else ''
    a = abs(n)
    if a >= 1000:
        return sign + '$' + format(round(a), ',')
    if a < 10:
        s = ('%.2f' % a).rstrip('0').rstrip('.')
        return sign + '$' + s
    s = ('%.1f' % a).rstrip('0').rstrip('.')
    return sign + '$' + s


def ts_ms(v):
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    if isinstance(v, str) and v.strip():
        s = v.strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(s).replace(tzinfo=datetime.fromisoformat(s).tzinfo or timezone.utc).timestamp() * 1000
        except Exception:
            return 0.0
    return 0.0


def expected_series(payload):
    hist = payload.get('exchange_account_history') or []
    has_unified = any(isinstance(p.get('unified_portfolio_value'), (int, float)) for p in hist)
    vis = []
    for p in hist:
        v = p.get('unified_portfolio_value') if has_unified else p.get('account_value')
        if not isinstance(v, (int, float)):
            continue
        ts = ts_ms(p.get('timestamp') or p.get('updated_at'))
        if ts <= 0:
            continue
        vis.append({'ts': ts, 'value': float(v)})
    vis.sort(key=lambda x: x['ts'])
    if len(vis) < 2:
        return None
    base = vis[0]['value']
    points = [{'ts': p['ts'], 'value': p['value'] - base} for p in vis]
    raw = ((payload.get('live_graph') or {}).get('realized_pnl_points') or [])
    fills = []
    for p in raw:
        ts = p.get('ts') or p.get('timestamp_ms')
        pnl = p.get('pnl')
        if isinstance(ts, (int, float)) and ts > 0 and isinstance(pnl, (int, float)):
            fills.append({'ts': float(ts), 'pnl': float(pnl)})
    fills.sort(key=lambda x: x['ts'])
    start, end = vis[0]['ts'], vis[-1]['ts']
    base_real = sum(f['pnl'] for f in fills if f['ts'] <= start)
    run = base_real
    in_range = [f for f in fills if start < f['ts'] <= end]
    realized = [{'ts': start, 'value': 0.0}]
    for f in in_range:
        run += f['pnl']
        realized.append({'ts': f['ts'], 'value': run - base_real})
    realized.append({'ts': end, 'value': run - base_real})
    peak = 0.0
    drawdown = []
    for p in points:
        peak = max(peak, p['value'])
        drawdown.append({'ts': p['ts'], 'value': p['value'] - peak})
    allv = [p['value'] for p in points + realized + drawdown] + [0.0]
    mn, mx = min(allv), max(allv)
    pad = max(abs(mx - mn) * 0.12, 1)
    ymin, ymax = mn - pad, mx + pad
    rng = (ymax - ymin) or 1
    plot = {'left': 58, 'right': 976, 'top': 24, 'bottom': 280}

    def get_y(v):
        return plot['bottom'] - ((v - ymin) / rng) * (plot['bottom'] - plot['top'])

    min_ts = min(p['ts'] for p in points)
    max_ts = max(p['ts'] for p in points)
    trng = (max_ts - min_ts) or 1

    def get_x(ts):
        return plot['left'] + (((ts or min_ts) - min_ts) / trng) * (plot['right'] - plot['left'])

    def line(series):
        return ' '.join(str(get_x(p['ts'])) + ',' + str(get_y(p['value'])) for p in series)

    return {'points': points, 'realized': realized, 'drawdown': drawdown,
            'exchange_pts': line(points), 'realized_pts': line(realized), 'drawdown_pts': line(drawdown),
            'ymax': js_fmt_axis(ymax), 'ymid': js_fmt_axis(ymin + rng / 2), 'ymin': js_fmt_axis(ymin),
            'n_points': len(points), 'n_fills': len(in_range), 'min_ts': min_ts, 'max_ts': max_ts,
            'tick_ts': [min_ts + (max_ts - min_ts) * i / 4 for i in range(5)],
            'realized_final': realized[-1]['value'], 'drawdown_final': drawdown[-1]['value']}


DOM_JS = """() => {
  const q=s=>document.querySelector(s);
  const g=id=>{const e=document.getElementById(id);return e?e.getAttribute('points'):null};
  const t=id=>{const e=document.getElementById(id);return e?e.textContent:null};
  const ticks=[...document.querySelectorAll('#lcXAxisTicks > *')].map(e=>({tag:e.tagName,text:e.textContent,x:e.getAttribute('x1')||e.getAttribute('x')}));
  const thead=[...document.querySelectorAll('.lc-wallet-table thead th')].map(e=>e.textContent.trim());
  const rows=[...document.querySelectorAll('#lcWalletRows tr.lc-wallet-row')].map(tr=>({
    wallet:tr.dataset.wallet,
    cells:[...tr.querySelectorAll('td')].map(td=>td.innerText.replace(/\\s+/g,' ').trim()),
    controls:{mode:tr.querySelector('select[name=mode]')?tr.querySelector('select[name=mode]').value:null,
              copy:tr.querySelector('select[name=copy_mode]')?tr.querySelector('select[name=copy_mode]').value:null,
              fixed:tr.querySelector('input[name=fixed_notional]')?tr.querySelector('input[name=fixed_notional]').value:null,
              norm:tr.querySelector('input[name=norm_base]')?tr.querySelector('input[name=norm_base]').value:null,
              buttons:[...tr.querySelectorAll('button')].map(b=>b.textContent.trim())}
  }));
  return {subtitle:t('lcGraphSubtitle'), exchangePath:g('lcExchangePath'), realizedPath:g('lcRealizedPath'),
          drawdownPath:g('lcDrawdownPath'), ymax:t('lcYMax'), ymid:t('lcYMid'), ymin:t('lcYMin'),
          ticks, thead, rows, zeroLine:document.getElementById('lcZeroLine')?document.getElementById('lcZeroLine').getAttribute('y1'):null};
}"""

RESET_JS = """() => {
  const out={};
  const sub=()=>document.getElementById('lcGraphSubtitle').textContent;
  const act=()=>[...document.querySelectorAll('[data-lc-graph-scale].active')].map(b=>b.dataset.lcGraphScale);
  const npts=()=>(document.getElementById('lcExchangePath').getAttribute('points')||'').split(' ').filter(Boolean).length;
  out.baseline_sub=sub(); out.baseline_active=act(); out.baseline_npts=npts();
  const s=document.querySelector('[data-lc-graph-scale=\"7d\"]'); if(s) s.click();
  out.after7d_sub=sub(); out.after7d_active=act(); out.after7d_npts=npts();
  const st=document.getElementById('lcGraphStart'), en=document.getElementById('lcGraphEnd');
  if(st) st.value='2026-10-18T00:00'; if(en) en.value='2026-10-18T12:00';
  const ap=document.getElementById('lcGraphApplyRange'); if(ap) ap.click();
  out.afterApply_sub=sub(); out.afterApply_active=act(); out.afterApply_npts=npts();
  const r=document.getElementById('lcGraphResetRange'); if(r) r.click();
  out.afterReset_sub=sub(); out.afterReset_active=act(); out.afterReset_npts=npts();
  out.afterReset_start=(document.getElementById('lcGraphStart')||{}).value;
  out.afterReset_end=(document.getElementById('lcGraphEnd')||{}).value;
  return out;
}"""


def main():
    payload = api('/api/live-audit-summary')
    exp = expected_series(payload)
    res = {'base': BASE, 'oracle_ok': exp is not None}
    if exp:
        res['oracle'] = exp
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        reqs = []
        pg.on('request', lambda r: reqs.append(r.url))
        pg.goto(BASE + '/live-copy', wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_function("() => { const el=document.querySelector('#lcGraphSubtitle'); return el && el.textContent && !/Portfolio value change from exchange snapshots/.test(el.textContent); }", timeout=60000)
        pg.wait_for_timeout(500)
        res['dom'] = pg.evaluate(DOM_JS)
        res['reset'] = pg.evaluate(RESET_JS)
        pg.wait_for_timeout(300)
        res['dom_after_reset'] = pg.evaluate("() => ({points:(document.getElementById('lcExchangePath').getAttribute('points')||''), sub:document.getElementById('lcGraphSubtitle').textContent, npts:(document.getElementById('lcExchangePath').getAttribute('points')||'').split(' ').filter(Boolean).length})")
        res['requests'] = reqs
        b.close()
    OUT.write_text(json.dumps(res, indent=1), encoding='utf-8')
    print('wrote', OUT)


if __name__ == '__main__':
    main()
