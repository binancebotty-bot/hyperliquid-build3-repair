import json, time, urllib.request, asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = 'http://127.0.0.1:8037'
PROBE = Path('C:/Users/wigmore/.hermes/cache/scratch/t2341_probe')
AUD = PROBE / 'run' / 'audit'
SNAP = AUD / 'exchange_account_snapshot_app.json'

# Fixtures use the EXACT schema HL_Copy_App_SSOT._fetch_exchange_account_snapshot writes
# (positions_by_coin -> signed_size / entry_px / mark_px / unrealized_pnl).
def pos(coin, signed, entry, mark, upnl, pv):
    return {'coin': coin, 'signed_size': signed, 'position_value': pv, 'entry_px': entry,
            'mark_px': mark, 'unrealized_pnl': upnl, 'margin_used': 0.0}


def snap(positions, available=True, reason=None):
    d = {
        'ok': available, 'available': available,
        'status': 'OK' if available else 'UNAVAILABLE',
        'updated_at': '2026-10-19T12:00:00Z', 'fetched_at_ms': int(time.time() * 1000),
        'account_value_source': 'probe_fixture', 'raw_total_usd_source': 'probe_fixture',
        'spot_account_source': 'probe_fixture',
        'realized_pnl_since_baseline_source': 'probe_fixture',
        'realized_pnl_selected_source': 'probe_fixture',
        'realized_fills_paging': {},
        'positions_by_coin': positions,
    }
    if reason:
        d['reason'] = reason
    return d


ORP = pos('SENTORP', 7.5, 101.11, 202.22, 758.325, 1516.65)
SHARE10 = pos('SENTSHARE', 10.0, 111.11, 222.22, 777.77, 2222.2)
SHARE8 = pos('SENTSHARE', 8.0, 111.11, 222.22, 777.77, 1777.76)
SHARE1 = pos('SENTSHARE', 1.0, 111.11, 222.22, 77.77, 222.22)
# sleeves come from manual_live_positions.json: leaderaa 3.0 + leaderbb 2.0 => ledger net 5.0 on SENTSHARE

MODES = [
    ('base', snap({'SENTORP': ORP, 'SENTSHARE': SHARE10})),
    ('total8', snap({'SENTORP': ORP, 'SENTSHARE': SHARE8})),
    ('shortfall', snap({'SENTORP': ORP, 'SENTSHARE': SHARE1})),
    ('orphan_only', snap({'SENTORP': ORP})),
    ('unavailable', snap({}, available=False, reason='ACCOUNT_ADDRESS_UNAVAILABLE')),
]

JS = '''() => {
  const t = document.querySelector('#lcOrphanPositionRows').closest('table');
  const heads = [...t.querySelectorAll('thead th')].map(x => x.innerText.trim());
  const trs = [...t.querySelectorAll('tbody tr')];
  return {
    heads, n_heads: heads.length, n_rows: trs.length,
    rows: trs.map(tr => {
      const tds = [...tr.querySelectorAll('td')];
      const pill = tr.querySelector('td:nth-child(6) span');
      const ctx = tds[9] || null;
      return {
        coin: tds[0] ? tds[0].innerText.trim() : null,
        n_cells: tds.length,
        cells: tds.map(td => td.innerText.trim()),
        td6_status_title_attr: tds[5] ? tds[5].getAttribute('title') : null,
        td6_pill_visible_text: pill ? pill.innerText.trim() : null,
        td10_context_visible_text: ctx ? ctx.innerText.trim() : null,
        td10_context_title_attr: ctx ? ctx.getAttribute('title') : null,
      };
    })
  };
}'''


async def dom_capture():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page(viewport={'width': 1900, 'height': 1400})
        await pg.goto(BASE + '/live-copy', wait_until='domcontentloaded', timeout=120000)
        for _ in range(120):
            if await pg.evaluate('document.readyState') == 'complete':
                break
            await pg.wait_for_timeout(500)
        for _ in range(80):
            if await pg.evaluate("document.querySelectorAll('#lcOrphanPositionRows tr td').length"):
                break
            await pg.wait_for_timeout(500)
        res = await pg.evaluate(JS)
        res['url'] = pg.url
        res['title'] = await pg.title()
        html = await pg.content()
        await b.close()
    return res, html


async def main():
    results = []
    for mode, fixture in MODES:
        SNAP.write_text(json.dumps(fixture, indent=1), encoding='utf-8')
        time.sleep(3.2)  # clear the app's 2s in-process audit cache
        with urllib.request.urlopen(BASE + '/api/live-audit-summary', timeout=180) as r:
            api = json.loads(r.read().decode('utf-8'))
        rows = [{k: x.get(k) for k in ('coin', 'ledger_vs_exchange', 'provenance',
                                       'orphan_classification', 'reconciliation_note',
                                       'exchange_signed_size', 'exchange_total_size',
                                       'signed_size', 'engine_shortfall')}
                for x in (api.get('orphan_exchange_positions') or [])]
        dom, html = await dom_capture()
        (PROBE / ('dom_%s.html' % mode)).write_text(html, encoding='utf-8')
        rec = {'mode': mode,
               'fixture_written': fixture,
               'api': {'exchange_snapshot_status': api.get('exchange_snapshot_status'),
                       'cache_hit': api.get('cache_hit'), 'orphan_rows': rows},
               'dom': dom}
        results.append(rec)
        print('==== MODE', mode, '| api', rec['api']['exchange_snapshot_status'],
              '| dom rows', dom['n_rows'])
        for row in dom['rows']:
            print('  DOM', row['coin'], 'ncells', row['n_cells'])
            print('    td6 title       :', repr(row['td6_status_title_attr']))
            print('    td6 pill text   :', repr(row['td6_pill_visible_text']))
            print('    td10 text       :', repr(row['td10_context_visible_text']))
            print('    td10 title attr :', repr(row['td10_context_title_attr']))
    out = PROBE / 'ui_fp_100_101_capture.json'
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding='utf-8')
    print('WROTE', out)

asyncio.run(main())
