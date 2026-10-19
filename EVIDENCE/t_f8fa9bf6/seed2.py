import csv, json, sys
from pathlib import Path

WS = Path(sys.argv[1]).resolve()
W1 = '0x1111111111111111111111111111111111111111'
W2 = '0x2222222222222222222222222222222222222222'
W3 = '0x3333333333333333333333333333333333333333'

INTENTS = [
    ('i-101', W1, 'BTC', '60900.0', '60900.0', '60900.0'),
    ('i-102', W1, 'ETH', '2460.0', '2460.0', '2460.0'),
    ('i-201', W2, 'BTC', '61900.0', '61900.0', '61900.0'),
]


def ex_resp(fill_px, fill_sz, oid, pos_before=None, pos_after=None, side=None):
    d = {'fill_avg_px': fill_px, 'fill_size': fill_sz, 'oid': oid,
         'price_source': 'book', 'size_source': 'order'}
    if pos_before is not None:
        d['position_before'] = pos_before
    if pos_after is not None:
        d['position_after'] = pos_after
    if side:
        d['side'] = side
    return json.dumps(d)


ATTEMPTS = [
    ('2026-10-18T10:00:00Z', 'a-101', 'i-101', W1, 'BTC', 'BUY', '60900.0', '0.010',
     'false', 'ORDER_FILLED', ex_resp(61000.5, 0.010, '900101', 0.0, 0.010, 'BUY'), '', ''),
    ('2026-10-18T10:30:00Z', 'a-102', 'i-102', W1, 'ETH', 'SELL', '2460.0', '0.20',
     'true', 'ORDER_FILLED', ex_resp(2450.25, 0.20, '900102', 0.20, 0.0, 'SELL'), '', ''),
    ('2026-10-18T11:00:00Z', 'a-103', '', W1, 'SOL', 'BUY', '150.0', '1.0',
     'false', 'ORDER_REJECTED', '', 'MARGIN', 'REJECTED'),
    ('2026-10-18T13:00:00Z', 'a-201', 'i-201', W2, 'BTC', 'SELL', '61900.0', '0.005',
     'true', 'ORDER_FILLED', ex_resp(62000.0, 0.005, '900201', 0.005, 0.0, 'SELL'), '', ''),
]

ATTEMPT_COLS = ['created_at', 'created_at_ms', 'attempt_id', 'intent_id', 'leader_fill_id',
                'leader_wallet', 'coin', 'side', 'order_type', 'limit_price', 'copy_size',
                'copy_notional', 'reduce_only_sent', 'sleeve_id', 'position_id',
                'wallet_position_before', 'wallet_position_after_expected',
                'coin_net_before', 'coin_net_after_expected', 'status', 'exchange_response',
                'exchange_order_id', 'error', 'reject_category', 'terminal_state',
                'operator_action', 'latency_classification', 'ws_received_ms',
                'leader_fill_timestamp_ms', 'intent_created_at_ms', 'send_decision_started_ms',
                'send_real_started_ms', 'symbol_resolve_started_ms', 'symbol_resolve_finished_ms',
                'sdk_client_started_ms', 'sdk_client_finished_ms', 'exchange_call_ms', 'notes']

INTENT_COLS = ['created_at', 'intent_id', 'leader_wallet', 'coin', 'side', 'target_price',
               'leader_price', 'suggested_limit_price', 'size', 'reason', 'status', 'notes']

FILLS = [
    (W1, 'BTC', 'BUY', '0.010', '61000.5', '0.61', '2026-10-18T10:00:00Z', 'i-101', 'cf-101', '0'),
    (W1, 'BTC', 'SELL', '0.010', '61200.0', '0.61', '2026-10-18T10:20:00Z', 'i-101b', 'cf-102', '0.010'),
    (W1, 'ETH', 'SELL', '0.20', '2450.25', '0.20', '2026-10-18T10:30:00Z', 'i-102', 'cf-103', ''),
    (W2, 'BTC', 'SELL', '0.005', '62000.0', '0.15', '2026-10-18T13:00:00Z', 'i-201', 'cf-201', ''),
]
FILL_COLS = ['leader_wallet', 'coin', 'side', 'fill_size', 'fill_price', 'fee', 'created_at',
             'intent_id', 'copy_fill_id', 'wallet_position_before']


def write_fixtures(audit_dir):
    d = Path(audit_dir)
    ao = d / 'append_only'
    ao.mkdir(parents=True, exist_ok=True)
    with (ao / 'order_intents.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(INTENT_COLS)
        for iid, wal, coin, tgt, ldr, sug in INTENTS:
            w.writerow(['2026-10-18T09:59:00Z', iid, wal, coin, 'BUY', tgt, ldr, sug, '', 'leader fill', 'SENT', 'fixture'])
    with (ao / 'send_attempts.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=ATTEMPT_COLS)
        w.writeheader()
        for (ca, aid, iid, wal, coin, side, lim, sz, ro, st, resp, rcat, tstate) in ATTEMPTS:
            row = {c: '' for c in ATTEMPT_COLS}
            row.update({'created_at': ca, 'attempt_id': aid, 'intent_id': iid,
                        'leader_wallet': wal, 'coin': coin, 'side': side,
                        'order_type': 'limit', 'limit_price': lim, 'copy_size': sz,
                        'reduce_only_sent': ro, 'status': st,
                        'exchange_response': resp, 'reject_category': rcat,
                        'terminal_state': tstate, 'notes': 'fixture'})
            w.writerow(row)
    with (ao / 'live_fills.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FILL_COLS)
        w.writeheader()
        for (wal, coin, side, sz, px, fee, ca, iid, cfid, pbefore) in FILLS:
            w.writerow({'leader_wallet': wal, 'coin': coin, 'side': side,
                        'fill_size': sz, 'fill_price': px, 'fee': fee,
                        'created_at': ca, 'intent_id': iid,
                        'copy_fill_id': cfid, 'wallet_position_before': pbefore})
    (ao / 'reconciliation.csv').write_text('created_at,wallet,coin,note\n', encoding='utf-8')
    print('fixtures ->', ao)


if __name__ == '__main__':
    write_fixtures(sys.argv[1])
