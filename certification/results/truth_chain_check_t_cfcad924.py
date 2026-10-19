"""UI-TRUTH value-chain check for card t_cfcad924 (read-only)."""
import json
import re
import urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:8023'
APP_DIR = Path(r'C:/Users/wigmore/trading_stack/build3-live-screen-0513-view/hl_stage2')
OUT_DIR = APP_DIR / 'hl_live_copy_audit'


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.read().decode('utf-8', 'replace')


html = get('/')
metrics = json.loads(get('/api/metrics'))
state = json.loads(get('/api/state'))
lc = json.loads(get('/api/live-config'))

print('=== files in audit dir')
if OUT_DIR.exists():
    for p in sorted(OUT_DIR.iterdir()):
        print('%-42s %10d' % (p.name, p.stat().st_size))
else:
    print('MISSING', OUT_DIR)

eng = OUT_DIR / 'engine_truth.json'
print('\n=== engine_truth.json (declared truth source)')
print('exists:', eng.exists())

print('\n=== at-a-glance labels in rendered HTML')
for label in ['MASTER REAL ORDERS', 'Last fill', 'Engine', 'WS', 'Integrity', 'Truth', 'freshness']:
    print('%-20s in_html=%s' % (label, label in html))

print('\n=== value chain: first wallet')
w = (metrics.get('wallets') or [{}])[0]
wallet = w.get('wallet')
print('wallet      :', wallet)
print('api lead eq :', (w.get('lead') or {}).get('equity'))
print('api copy eq :', (w.get('copy') or {}).get('equity'))
short = (wallet or '')[:6]
idx = html.find(short)
print('short id %r in HTML: %s' % (short, idx >= 0))
if idx >= 0:
    frag = html[max(0, idx - 400): idx + 2500]
    print('rendered numbers near row:', re.findall(r'>([\-\d\.,]{1,14})<', frag)[:25])

print('\n=== truth tier tokens in rendered HTML')
for tok in ['AUTHORITATIVE_EXCHANGE', 'LOCAL_LEDGER', 'LEADER_SIGNAL', 'DISPLAY_ONLY', 'SKIPPED']:
    print('%-26s in_html=%s' % (tok, tok in html))

print('\n=== staleness/age indicators in rendered HTML')
for tok in ['STALE', 'as of', 'updated']:
    print('%-10s count=%d' % (tok, html.lower().count(tok.lower())))

print('\n=== wallets: config vs metrics')
cfg_w = sorted((lc.get('config') or {}).get('wallets', {}).keys())
m_w = sorted([x.get('wallet') for x in (metrics.get('wallets') or []) if x.get('wallet')])
print('config :', cfg_w)
print('metrics:', m_w)
print('EQUAL  :', cfg_w == m_w)

print('\n=== /api/state gate truth')
print('wallet_gate_on_count:', state.get('wallet_gate_on_count'))
print('wallet_gate_on      :', state.get('wallet_gate_on'))
print('auto_send_enabled   :', state.get('auto_send_enabled'))
print('send_mode           :', (state.get('global_controls') or {}).get('send_mode'))
