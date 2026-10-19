"""UI-TRUTH part 2: where do the at-a-glance surfaces actually live (read-only)."""
import json
import urllib.request

BASE = 'http://127.0.0.1:8023'


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=25) as r:
        return r.read().decode('utf-8', 'replace')


TOKENS = [
    'MASTER REAL ORDERS', 'Last fill', 'lc-status', 'lc-stat',
    'AUTHORITATIVE_EXCHANGE', 'LOCAL_LEDGER', 'LEADER_SIGNAL', 'DISPLAY_ONLY',
    'STALE', 'send_mode', 'ws_health', 'integrity',
]

for path in ['/', '/model', '/live-copy', '/live-copy.json', '/api/live-audit-summary']:
    body = get(path)
    print('=== %s  bytes=%d' % (path, len(body)))
    for t in TOKENS:
        c = body.count(t)
        if c:
            print('   %-24s %d' % (t, c))
    print()

print('=== live-audit-summary shape')
s = json.loads(get('/api/live-audit-summary'))
print('top keys:', sorted(s.keys()))
for k in ('integrity', 'health', 'ws', 'wallets', 'perf', 'performance', 'status'):
    if k in s:
        v = s[k]
        print('  %s -> %s' % (k, (sorted(v.keys()) if isinstance(v, dict) else type(v).__name__)))

print()
print('=== ws health')
print(get('/api/live-ws-health')[:600])
