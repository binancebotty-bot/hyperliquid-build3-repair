"""Adversarial re-check of two UI-TRUTH claims (read-only)."""
import re
import urllib.request

BASE = 'http://127.0.0.1:8023'


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=25) as r:
        return r.read().decode('utf-8', 'replace')


html = get('/live-copy')

print('=== MASTER REAL ORDERS: rendered status card, actual classes')
i = html.find('MASTER REAL ORDERS')
print('index:', i)
if i >= 0:
    seg = html[max(0, i - 500): i + 400]
    print('classes near it:', sorted(set(re.findall(r'lc-(green|red|amber|blue)', seg))))
    print('raw:', re.sub(r'\s+', ' ', seg)[-500:])

print()
print('=== real lc-stat card count (server-rendered, not CSS)')
cards = re.findall(r'<div class="lc-stat">', html)
print('literal <div class="lc-stat"> occurrences:', len(cards))
print('any lc-stat token occurrences:', html.count('lc-stat'))

print()
print('=== green pills actually rendered in body')
for cls in ('lc-pill lc-green', 'lc-green"', 'lc-red', 'lc-amber'):
    print('%-18s %d' % (cls, html.count(cls)))

print()
print('=== does rendered HTML show ACTIVE_RED at all?')
for tok in ('ACTIVE_RED', 'hard_copy', '1012', 'integrity'):
    print('%-14s %d' % (tok, html.count(tok)))
