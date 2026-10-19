import json, time, hashlib, urllib.request, asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = 'http://127.0.0.1:8037'
PROBE = Path('C:/Users/wigmore/.hermes/cache/scratch/t2341_probe')
SNAP = PROBE / 'run' / 'audit' / 'exchange_account_snapshot_app.json'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


JS = '''() => {
  const t = document.querySelector('#lcOrphanPositionRows').closest('table');
  const trs = [...t.querySelectorAll('tbody tr')];
  return {n_rows: trs.length,
          rows: trs.map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))};
}'''


async def main():
    fixture = {'ok': False, 'available': False, 'status': 'UNAVAILABLE',
               'reason': 'ACCOUNT_ADDRESS_UNAVAILABLE',
               'updated_at': '2026-10-19T12:00:00Z', 'fetched_at_ms': int(time.time() * 1000),
               'positions_by_coin': {}}
    SNAP.write_text(json.dumps(fixture, indent=1), encoding='utf-8')
    before = sha(SNAP)
    time.sleep(3.2)
    with urllib.request.urlopen(BASE + '/api/live-audit-summary', timeout=180) as r:
        api = json.loads(r.read().decode('utf-8'))
    after = sha(SNAP)
    snap_api = api.get('exchange_account_snapshot') or {}
    rec = {'fixture_sha_before': before, 'fixture_sha_after': after,
           'fixture_survived': before == after,
           'api_exchange_snapshot_status': api.get('exchange_snapshot_status'),
           'api_snapshot_status_field': snap_api.get('status'),
           'api_snapshot_reason': snap_api.get('reason'),
           'api_snapshot_available': snap_api.get('available'),
           'api_orphan_count': len(api.get('orphan_exchange_positions') or [])}
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
        rec['dom'] = await pg.evaluate(JS)
        await b.close()
    (PROBE / 'unavailable_verified.json').write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rec, indent=1, ensure_ascii=False))

asyncio.run(main())
