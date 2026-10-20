#!/usr/bin/env python3
"""Regenerate the replay-harness fixtures. Run once; the CSVs are committed so the
harness self-check needs no generator at check time.

Five dirs: good (all four checks pass) and one per check, broken in exactly that way.
"""
from pathlib import Path
import copy

HERE = Path(__file__).resolve().parent

INTENT_COLS = ['created_at_ms', 'intent_id', 'leader_fill_id', 'coin', 'copy_side', 'copy_size',
               'copy_notional', 'leader_price', 'decision', 'notes']
SEND_COLS = ['intent_id', 'leader_fill_id', 'status', 'exchange_call_started_ms', 'exchange_order_id']
FILL_COLS = ['intent_id', 'coin', 'fill_price', 'fill_size', 'fill_notional',
             'wallet_position_before', 'wallet_position_after', 'coin_net_after']

# fill 1 = entry (flat -> long), fill 2 = exit (long -> flat).
INTENTS = [
    dict(created_at_ms=1, intent_id='i1', leader_fill_id='f1', coin='BTC', copy_side='BUY', copy_size='0.001',
         copy_notional='100.0', leader_price='100000', decision='ENTRY_ALLOWED', notes='lifecycle=ENTRY'),
    dict(created_at_ms=2, intent_id='i2', leader_fill_id='f2', coin='BTC', copy_side='SELL', copy_size='0.001',
         copy_notional='100.0', leader_price='100000', decision='EXIT_ALLOWED', notes='lifecycle=EXIT'),
]
SENDS = [
    dict(intent_id='i1', leader_fill_id='f1', status='ORDER_FILLED', exchange_call_started_ms='10', exchange_order_id='o1'),
    dict(intent_id='i2', leader_fill_id='f2', status='ORDER_FILLED', exchange_call_started_ms='20', exchange_order_id='o2'),
]
FILLS = [
    dict(intent_id='i1', coin='BTC', fill_price='100000', fill_size='0.001', fill_notional='100',
         wallet_position_before='0', wallet_position_after='0.001', coin_net_after='0.001'),
    dict(intent_id='i2', coin='BTC', fill_price='100000', fill_size='0.001', fill_notional='100',
         wallet_position_before='0.001', wallet_position_after='0', coin_net_after='0'),
]
CONFIG = '{\n "global_controls": {\n  "max_order_notional_usd": 500.0,\n  "max_total_live_exposure_usd": 1000.0,\n  "max_asset_directional_exposure_usd": 1000.0\n },\n "auto_send_enabled": true\n}\n'


def write(d, intents, sends, fills):
    d.mkdir(parents=True, exist_ok=True)
    for name, cols, rows in (('order_intents.csv', INTENT_COLS, intents),
                             ('send_attempts.csv', SEND_COLS, sends),
                             ('live_fills.csv', FILL_COLS, fills)):
        with open(d / name, 'w', encoding='utf-8', newline='') as fh:
            fh.write(','.join(cols) + '\n')
            for r in rows:
                fh.write(','.join(str(r.get(c, '')) for c in cols) + '\n')
    (d / 'live_config.json').write_text(CONFIG, encoding='utf-8')


def main():
    write(HERE / 'good', INTENTS, SENDS, FILLS)

    # Two terminal rows on one leader fill, same intent (not the documented
    # IOC + standing-close sibling pattern, which uses two intents).
    s = copy.deepcopy(SENDS)
    s.append(dict(s[0], status='ORDER_RESTING', exchange_call_started_ms='11', exchange_order_id='o9'))
    write(HERE / 'dup_terminal', INTENTS, s, FILLS)

    # Same intent, two distinct real exchange calls / order ids.
    s = copy.deepcopy(SENDS)
    s.append(dict(s[0], status='ORDER_REJECTED', exchange_call_started_ms='12', exchange_order_id='o3'))
    write(HERE / 'double_send', INTENTS, s, FILLS)

    # Entry notional 100 -> 1000, cap is 500.
    i = copy.deepcopy(INTENTS)
    i[0]['copy_notional'] = '1000.0'
    write(HERE / 'cap_breach', i, SENDS, FILLS)

    # Exit grows the position instead of reducing it.
    f = copy.deepcopy(FILLS)
    f[1]['wallet_position_before'] = '0.001'
    f[1]['wallet_position_after'] = '0.003'
    f[1]['coin_net_after'] = '0.003'
    write(HERE / 'bad_reduction', INTENTS, SENDS, f)
    print('wrote 5 fixture dirs under %s' % HERE)


if __name__ == '__main__':
    main()
