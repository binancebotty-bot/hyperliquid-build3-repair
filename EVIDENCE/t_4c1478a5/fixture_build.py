import csv, json, sys, time
from pathlib import Path

VAR = sys.argv[1]                       # 'A' or 'B'
D = Path(sys.argv[2]).resolve()
D.mkdir(parents=True, exist_ok=True)
(D / 'append_only').mkdir(exist_ok=True)
now_ms = int(time.time() * 1000)
now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

A = VAR == 'A'
W1 = '0x1111111111111111111111111111111111111111'
W2 = '0x2222222222222222222222222222222222222222'

# --- live_config.json -------------------------------------------------------
cfg = {
    'wallets': {
        W1: {'mode': 'LIVE', 'enabled': True},
        W2: {'mode': 'LIVE' if A else 'OFF', 'enabled': True},
    },
    'global_controls': {'send_mode': 'ON' if A else 'OFF'},
}
(D / 'live_config.json').write_text(json.dumps(cfg, indent=1), encoding='utf-8')

# --- live_ws_health.json ----------------------------------------------------
ws = {
    'enabled': True,
    'ws_summary': {
        'ws_status': 'WS_OK' if A else 'DOWN',
        'socket_open': True if A else False,
        'thread_alive': True if A else False,
        'wallet_count': 1,
    },
    'wallets': {W1: {'subscribed': True}},
}
(D / 'live_ws_health.json').write_text(json.dumps(ws, indent=1), encoding='utf-8')

# --- live_service_state.json ------------------------------------------------
svc = {
    'last_state_write_ms': now_ms,
    'copy_account_status': 'POLLED_OK' if A else 'STALE',
    'effective_real_orders_enabled': True if A else False,
    'networks': {'leader': 'mainnet', 'follower': 'testnet'},
}
(D / 'live_service_state.json').write_text(json.dumps(svc, indent=1), encoding='utf-8')

# --- live_integrity_status.json --------------------------------------------
integ = {'status': 'OK' if A else 'RED', 'available': True,
         'reasons': [] if A else ['FIXTURE_RED'], 'counts': {}}
(D / 'live_integrity_status.json').write_text(json.dumps(integ, indent=1), encoding='utf-8')

# --- manual_live_positions.json --------------------------------------------
manual = {'schema': 'manual_live_positions.v2', 'by_wallet': {
    W1: {'BTC': {'signed_size': 0.5, 'coin': 'BTC'} if A else
                {'signed_size': 2.0, 'coin': 'ETH'}}}}
if not A:
    manual['by_wallet'][W1] = {'ETH': {'signed_size': 2.0, 'coin': 'ETH'}}
(D / 'manual_live_positions.json').write_text(json.dumps(manual, indent=1), encoding='utf-8')

# --- append_only/send_attempts.csv -----------------------------------------
cols = ['created_at', 'created_at_ms', 'attempt_id', 'intent_id', 'leader_fill_id',
        'leader_wallet', 'coin', 'side', 'order_type', 'limit_price', 'copy_size',
        'copy_notional', 'reduce_only_sent', 'sleeve_id', 'position_id',
        'wallet_position_before', 'wallet_position_after_expected',
        'coin_net_before', 'coin_net_after_expected', 'status', 'exchange_response',
        'exchange_order_id', 'error', 'reject_category', 'terminal_state',
        'operator_action', 'latency_classification', 'ws_received_ms',
        'leader_fill_timestamp_ms', 'intent_created_at_ms', 'send_decision_started_ms',
        'send_real_started_ms', 'symbol_resolve_started_ms', 'symbol_resolve_finished_ms',
        'sdk_client_started_ms', 'sdk_client_finished_ms', 'exchange_call_ms', 'notes']
rows = []
r1 = {c: '' for c in cols}
r1.update({'created_at': '2026-10-18T10:00:00Z', 'attempt_id': 'a-101', 'leader_wallet': W1,
           'coin': 'BTC' if A else 'SOL', 'side': 'BUY', 'status': 'ORDER_FILLED',
           'exchange_response': json.dumps({'fill_avg_px': 61000.0 if A else 150.0, 'fill_size': 0.01}),
           'exchange_order_id': '900101', 'terminal_state': 'FILLED'})
rows.append(r1)
r2 = {c: '' for c in cols}
r2.update({'created_at': '2026-10-18T11:00:00Z', 'attempt_id': 'a-102', 'leader_wallet': W1,
           'coin': 'ETH' if A else 'DOGE', 'side': 'SELL', 'status': 'ORDER_REJECTED',
           'reject_category': 'MARGIN' if A else 'PRICE_BAND', 'terminal_state': 'REJECTED',
           'exchange_response': ''})
rows.append(r2)
# newest row (last_send) = ORDER_FILLED in B, ORDER_REJECTED in A
if not A:
    r3 = {c: '' for c in cols}
    r3.update({'created_at': '2026-10-18T12:00:00Z', 'attempt_id': 'a-103', 'leader_wallet': W1,
               'coin': 'BTC', 'side': 'BUY', 'status': 'ORDER_FILLED',
               'exchange_response': json.dumps({'fill_avg_px': 61500.0, 'fill_size': 0.02}),
               'exchange_order_id': '900103', 'terminal_state': 'FILLED'})
    rows.append(r3)
with (D / 'append_only' / 'send_attempts.csv').open('w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)

# --- append_only/live_fills.csv --------------------------------------------
fcols = ['leader_wallet', 'coin', 'side', 'fill_size', 'fill_price', 'fee', 'created_at',
         'intent_id', 'copy_fill_id', 'wallet_position_before']
with (D / 'append_only' / 'live_fills.csv').open('w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=fcols)
    w.writeheader()
    w.writerow({'leader_wallet': W1, 'coin': 'ETH' if A else 'BTC',
                'side': 'SELL' if A else 'BUY', 'fill_size': 0.2 if A else 0.01,
                'fill_price': 2450.25 if A else 61200.0, 'fee': 0.61,
                'created_at': '2026-10-18T10:30:00Z', 'intent_id': 'i-102',
                'copy_fill_id': 'cf-103', 'wallet_position_before': 0.2})

# --- append_only/reconciliation.csv ---------------------------------------
with (D / 'append_only' / 'reconciliation.csv').open('w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['created_at', 'created_at_ms', 'event', 'status', 'notes', 'wallet', 'coin'])
    w.writerow(['2026-10-18T12:00:00Z', '', 'SEND_LATENCY_WARN', 'WARN',
                'LAT_A' if A else 'LAT_B', W1, 'BTC'])

# --- exchange_account_snapshot_app.json (fresh cache => used verbatim) -----
snap = {
    'ok': True, 'available': True, 'status': 'OK',
    'updated_at': now_iso, 'fetched_at_ms': now_ms,
    'account_value': 1000.0, 'account_value_source': 'fixture',
    'raw_total_usd': 1000.0, 'raw_total_usd_source': 'fixture',
    'spot_account_source': 'fixture',
    'unified_portfolio_value': 12345.67 if A else 99999.99,
    'unified_portfolio_value_source': 'fixture',
    'unrealized_pnl': 42.5 if A else -7.25,
    'realized_pnl_selected': 12.34 if A else 55.50,
    'realized_pnl_selected_label': 'fixture window',
    'realized_pnl_since_baseline_source': '',
    'realized_pnl_selected_source': 'fixture',
    'realized_fills_paging': {'complete': True},
    'open_positions': ([{'coin': 'BTC'}] if A else [{'coin': 'ETH'}, {'coin': 'SOL'}]),
    'positions_by_coin': ({'BTC': {'mark_px': 60000.0, 'signed_size': 0.5}} if A else
                          {'ETH': {'mark_px': 2500.0, 'signed_size': 2.0}}),
}
(D / 'exchange_account_snapshot_app.json').write_text(json.dumps(snap, indent=1), encoding='utf-8')

# --- network stamp so the app binds this dir to mainnet-leader/testnet-follower
(D / 'network.json').write_text(json.dumps({'leader': 'mainnet', 'follower': 'testnet',
                                            'prior_state': []}, indent=1), encoding='utf-8')
print('fixture', VAR, '->', D)
