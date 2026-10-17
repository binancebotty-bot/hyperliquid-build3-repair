import json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

W = '0x' + '1' * 40
OUT = {}


def sb(n):
    d = Path('probe_out') / n
    if d.exists():
        shutil.rmtree(d)
    (d / 'append_only').mkdir(parents=True)
    return d


def new(d):
    json.dump({'wallets': {W: {'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 100.0, 'enabled': True}}}, open(d / 'live_config.json', 'w'))
    E.configure_paths(d, d / 'fills.csv')
    s = E.DryRunLiveCopyService()
    s.state['baselines'] = {W: {'wallet': W, 'baseline_ts_ms': 500, 'baseline_fill_id': 'pre'}}
    s.processed_ids = set()
    s.state['fixed_sleeves'] = {}
    return s


def fill(fid, ts, signed, price=100.0):
    return E.LeaderFill(fill_id=fid, wallet=W, coin='BTC', side=('BUY' if signed > 0 else 'SELL'), price=price, size=abs(signed), signed_size_delta=signed, timestamp_ms=ts, timestamp_iso='t', source='rest', recording_method='REST', raw={})


cfg = E.LiveWalletConfig(wallet=W, mode='LIVE', copy_mode='fixed', fixed_notional=100.0)

d = sb('i04')
s = new(d)
for i, ts in enumerate([1000, 2000, 3000], start=1):
    s.apply_leader_event(cfg, fill('miss%d' % i, ts, 1.0))
OUT['I04_three_missed_increases_slices'] = len((s.state['fixed_sleeves'].get(W, {}) or {}).get('BTC', {}).get('slices', []) or [])

d2 = sb('i04net')
s2 = new(d2)
s2.apply_leader_event(cfg, fill('net1', 4000, 3.0))
OUT['I04_one_net_event_slices'] = len((s2.state['fixed_sleeves'].get(W, {}) or {}).get('BTC', {}).get('slices', []) or [])
OUT['I04_net_equals_missed'] = OUT['I04_three_missed_increases_slices'] == OUT['I04_one_net_event_slices']

src = open('engine.py', encoding='utf-8', errors='replace').read()
OUT['I06_cloid_occurrences'] = src.lower().count('cloid')
OUT['I06_client_order_id_occurrences'] = src.lower().count('client_order_id')

i = src.find('exchange.order(')
pre = src[max(0, i - 2500):i]
import re
OUT['I07_follower_truth_before_order'] = bool(re.search(r'clearinghouse|user_state|sub_accounts', pre, re.I))
OUT['I07_presend_snapshot_is_master_net'] = 'pre_send_master_net' in pre

for k in ['lease', 'fence', 'msvcrt', 'fcntl', 'CreateMutex', 'lock_file', 'lockfile']:
    OUT['I08_count_' + k] = src.lower().count(k.lower())
OUT['I08_order_call_sites'] = src.count('exchange.order(')

print(json.dumps(OUT, indent=1, default=str))
