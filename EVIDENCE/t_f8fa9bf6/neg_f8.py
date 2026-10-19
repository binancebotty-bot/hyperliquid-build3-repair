import json, shutil, time
from pathlib import Path
from playwright.sync_api import sync_playwright

WS = Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_f8fa9bf6')
import launch

out = {}

# ---- stale engine truth: service state 15 min old -> banner must say Stopped
stale = WS / 'iso_stale'
stale.mkdir(exist_ok=True)
for f in ('live_config.json', 'exchange_account_history.json', 'live_ws_health.json', 'manual_live_positions.json'):
    src = WS / 'iso_short' / f
    if src.exists():
        shutil.copyfile(src, stale / f)
now = int(time.time() * 1000)
(stale / 'live_service_state.json').write_text(json.dumps({
    'last_state_write_ms': now - 15 * 60 * 1000,
    'started_at_ms': now - 3600 * 1000,
    'networks': {'follower': 'testnet'},
}), encoding='utf-8')
p = launch.launch('iso_stale', 8122, 'iso_stale.log')
time.sleep(11)


def grab(base, abort_audit=False):
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page()
        if abort_audit:
            pg.route('**/api/live-audit-summary', lambda r: r.abort())
        pg.goto(base + '/live-copy', wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(2500)
        d = pg.evaluate("() => { const b=document.querySelector('#lcTruthStatus'); const s=document.getElementById('lcStatus'); return {banner:b?b.innerText.replace(/\\s+/g,' ').slice(0,400):null, status:s?{text:s.textContent,cls:s.className}:null}; }")
        b.close()
        return d


out['stale'] = grab('http://127.0.0.1:8122')
out['stale_pid'] = p.pid
out['api_error'] = grab('http://127.0.0.1:8121', abort_audit=True)
(WS / 'neg_evidence.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
print(json.dumps(out, indent=1)[:1500])
