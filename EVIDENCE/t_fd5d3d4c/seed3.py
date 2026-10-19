import json, pathlib
AUD = pathlib.Path('C:/Users/wigmore/.hermes/cache/scratch/ui89/audit')
W1 = '0x1111111111111111111111111111111111111111'
W2 = '0x2222222222222222222222222222222222222222'
cfg = {'wallets': {W1: {'mode': 'LIVE', 'copy_mode': 'proportional', 'norm_base': 250.0, 'fixed_notional': 25.0, 'enabled': True},
                   W2: {'mode': 'CLO', 'copy_mode': 'fixed', 'norm_base': 900.0, 'fixed_notional': 77.0, 'enabled': True}},
       'archived_wallets': {},
       'global_controls': {'max_total_live_exposure_usd': 1000.0, 'max_wallet_exposure_usd': 400.0, 'max_order_notional_usd': 50.0, 'marketable_bps': 20.0}}
(AUD / 'live_config.json').write_text(json.dumps(cfg, indent=1), encoding='utf-8')
mp = {'schema': 'manual_live_positions.v2', 'by_wallet': {
    W1: {'BTC': {'signed_size': 0.0123, 'avg_entry_px': 61234.5, 'last_copy_fill_id': 'oid-btc-111', 'last_updated_at': '2026-10-19T04:10:00Z'}},
    W2: {'ETH': {'signed_size': -0.456, 'avg_entry_px': 2456.75, 'last_copy_fill_id': 'oid-eth-222', 'last_updated_at': '2026-10-19T03:40:00Z'}}}}
(AUD / 'manual_live_positions.json').write_text(json.dumps(mp, indent=1), encoding='utf-8')
print('seeded', list(cfg['wallets']))
