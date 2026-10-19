import json, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

WS = Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_4c1478a5/work')
BASE = sys.argv[1]
OUT = Path(sys.argv[2])

DOM_JS = """() => {
  const cards = sel => [...document.querySelectorAll(sel + ' .lc-stat')].map(d => ({
     label: (d.querySelector('.label')||{}).textContent,
     value: (d.querySelector('.value')||{}).textContent,
     title: (d.querySelector('.value')||{}).title || ''
  }));
  const g = id => { const e = document.getElementById(id); return e ? {text: e.textContent.trim(), hidden: !!e.hidden} : null; };
  return {
    truth_status: cards('#lcTruthStatus'),
    real_cards: cards('#lcRealCards'),
    restart_note: g('lcRestartNote'),
    banner_sending: g('lcBannerSending'),
    banner_acct: g('lcBannerAcct'),
    banner_health: g('lcBannerHealth'),
    banner_open: g('lcBannerOpen'),
    ws_overall: g('lcWsOverall'),
    wallet_count: g('lcWalletCount'),
    have_panel: !!document.querySelector('#liveCopyPanel')
  };
}"""


def api(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(BASE + '/live-copy', wait_until='domcontentloaded', timeout=60000)
    for _ in range(60):
        st = pg.evaluate('document.readyState')
        if st == 'complete':
            break
        pg.wait_for_timeout(500)
    # the panel hydrates from /api/live-audit-summary; poll until the strips are populated
    for _ in range(60):
        n = pg.evaluate("document.querySelectorAll('#lcTruthStatus .lc-stat').length + document.querySelectorAll('#lcRealCards .lc-stat').length")
        if n >= 2:
            break
        pg.wait_for_timeout(500)
    pg.wait_for_timeout(2500)
    dom = pg.evaluate(DOM_JS)
    b.close()

payload = api('/api/live-audit-summary')
ts = payload.get('live_top_status') or {}
snap = payload.get('exchange_account_snapshot') or {}
fa = payload.get('follower_account') or {}
mls = payload.get('manual_live_summary') or {}
out = {
    'base': BASE,
    'dom': dom,
    'api': {
        'live_top_status': {k: ts.get(k) for k in ('integrity_status', 'integrity_available', 'ws_status',
                                                   'ws_restart_needed', 'copy_poll_status', 'master_real_orders',
                                                   'sending', 'active_wallets', 'subscribed_wallets', 'live_wallets',
                                                   'health')},
        'last_send': ts.get('last_send'),
        'last_fill': ts.get('last_fill'),
        'last_reject': ts.get('last_reject'),
        'last_latency_warning': ts.get('last_latency_warning'),
        'snapshot': {k: snap.get(k) for k in ('available', 'unified_portfolio_value', 'unrealized_pnl',
                                              'realized_pnl_selected', 'open_positions', 'open_positions_count')},
        'follower_account': fa,
        'manual_live_exposure_estimate': mls.get('manual_live_exposure_estimate'),
    },
}
OUT.write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
print('wrote', OUT)
print(json.dumps(out['api'], indent=1, default=str)[:2600])
