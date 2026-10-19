"""UI-TRUTH source scan for card t_cfcad924 (read-only).

Prints the source anchors needed to rule on the 5 UI-TRUTH rows.
"""
import re

APP = r'C:/Users/wigmore/trading_stack/build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py'

with open(APP, 'r', encoding='utf-8', errors='replace') as fh:
    lines = fh.read().split('\n')


def show(title, pattern, limit=12, window=0):
    rx = re.compile(pattern)
    print('=== ' + title)
    n = 0
    for i, ln in enumerate(lines):
        if rx.search(ln):
            print('%d: %s' % (i + 1, ln.strip()[:220]))
            for k in range(1, window + 1):
                if i + k < len(lines):
                    print('    +%d: %s' % (k, lines[i + k].strip()[:220]))
            n += 1
            if n >= limit:
                break
    if n == 0:
        print('(no match)')
    print()


show('truth tier tokens', r'AUTHORITATIVE_EXCHANGE|LOCAL_LEDGER|LEADER_SIGNAL|DISPLAY_ONLY|SKIPPED', 20)
show('GREEN-ONLY / gate', r'GREEN-ONLY|GREEN_ONLY|master_gate|master gate', 10)
show('freshness / age', r'age_sec|freshness|_age\(|max_age_sec|STALE', 20)
show('order placement', r'place_order|market_open|usd_class_transfer|submit_order|/exchange', 10)
show('hyperliquid import', r'import hyperliquid|from hyperliquid|Exchange\(', 10)
show('state build / truth source', r'def build_model_state|def get_model_state|def _model_state|source_truth|ledger', 15)
show('read-only claim', r'read.only|observer|never writes position|no authority', 10)

print('=== import block (1-45)')
for i in range(0, min(45, len(lines))):
    print('%d: %s' % (i + 1, lines[i][:200]))
