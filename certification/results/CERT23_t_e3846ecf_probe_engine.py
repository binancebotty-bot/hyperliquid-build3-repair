import os, sys, json, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

WALLET = '0x' + '1' * 40
COIN = 'BTC'
OUT = {}

def sb(name):
    d = Path('probe_out') / name
    if d.exists():
        shutil.rmtree(d)
    (d / 'append_only').mkdir(parents=True)
    return d

def mkcfg(d):
    json.dump({'wallets': {WALLET: {'mode': 'LIVE', 'copy_mode': 'proportional', 'enabled': True}}},
              open(d / 'live_config.json', 'w'))

def fill(fid, ts, signed, price=100.0):
    return E.LeaderFill(fill_id=fid, wallet=WALLET, coin=COIN,
                        side=('BUY' if signed > 0 else 'SELL'), price=price, size=abs(signed),
                        signed_size_delta=signed, timestamp_ms=ts, timestamp_iso='t',
                        source='ws', recording_method='WS', raw={})

def new(d):
    E.configure_paths(d, d / 'fills.csv')
    mkcfg(d)
    return E.DryRunLiveCopyService()

# P1 I01: pre-baseline fill must create baseline and mint ZERO authority
d = sb('i01')
s = new(d)
r1 = s.process_ws_fill(fill('f1', 1000, 1.0))
OUT['I01'] = {'r': r1, 'leader_pos': dict(s.state.get('leader_event_positions') or {}),
              'slices': dict(s.state.get('fixed_sleeves') or {}),
              'processed': list(s.processed_ids)}
# mutation control: baseline already exists and is EARLIER -> same fill now processes
d2 = sb('i01m')
s2 = new(d2)
s2.state['baselines'] = {WALLET: {'wallet': WALLET, 'baseline_ts_ms': 500, 'baseline_fill_id': 'pre'}}
r2 = s2.process_ws_fill(fill('f1', 1000, 1.0))
OUT['I01_MUTATED_BASELINE'] = {'r': r2, 'processed': list(s2.processed_ids)}

# P2 I02: restart creates no authority; pre-baseline/current-position replay yields zero events
d = sb('i02')
s = new(d)
s.process_ws_fill(fill('f1', 1000, 1.0))
s.state['baselines'] = {WALLET: {'wallet': WALLET, 'baseline_ts_ms': 2000, 'baseline_fill_id': 'f1'}}
s.persist()
s3 = new(d)  # restart
before = dict(s3.state.get('leader_event_positions') or {})
r = s3.process_ws_fill(fill('stale', 1500, 5.0))  # <= baseline: startup/current-position style
OUT['I02'] = {'restart_leader_pos': before, 'stale_r': r,
              'after_leader_pos': dict(s3.state.get('leader_event_positions') or {})}

# P3 I03: WS and REST carrying the same fill_id enter ONE logical stream (processed once)
d = sb('i03')
s = new(d)
s.state['baselines'] = {WALLET: {'wallet': WALLET, 'baseline_ts_ms': 500, 'baseline_fill_id': 'pre'}}
s.processed_ids = set()
f = fill('dup1', 1000, 1.0)
a = s.process_ws_fill(f)
b = s.process_fill(f, E.LiveWalletConfig(wallet=WALLET, mode='LIVE'))
OUT['I03'] = {'ws_result': a, 'rest_result': b,
              'processed_count': len([x for x in s.processed_ids if x == 'dup1'])}

# P5 I05: truth failure must NOT consume the genuine event
d = sb('i05')
s = new(d)
s.state['baselines'] = {WALLET: {'wallet': WALLET, 'baseline_ts_ms': 500, 'baseline_fill_id': 'pre'}}
E.MASTER_TRUTH_ADDRESS = ''
s.processed_ids = set()
try:
    s.process_fill(fill('genuine1', 1000, 1.0), E.LiveWalletConfig(wallet=WALLET, mode='LIVE'))
    err = None
except Exception as e:
    err = repr(e)[:200]
OUT['I05'] = {'exception': err, 'event_still_processed': 'genuine1' in s.processed_ids,
              'processed': list(s.processed_ids),
              'recon_rows': (d / 'append_only' / 'reconciliation.csv').read_text(encoding='utf-8', errors='replace').count('genuine1') if (d / 'append_only' / 'reconciliation.csv').exists() else 0}

print(json.dumps(OUT, indent=1, default=str)[:6000])
