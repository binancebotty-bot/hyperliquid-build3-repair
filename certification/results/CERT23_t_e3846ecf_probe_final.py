import glob, json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

OUT = {}

fs = sorted(glob.glob('env/control_mailbox/inbox/*.json'))
ds = [json.load(open(f, encoding='utf-8-sig')) for f in fs]
vals = set()
for d in ds:
    s = json.dumps(d)
    for m in re.finditer(r'AUTHORITY_SOURCE=([A-Za-z0-9_.:/-]+)', s):
        vals.add(m.group(1))
    if d.get('AUTHORITY_SOURCE'):
        vals.add(str(d['AUTHORITY_SOURCE']))
OUT['AUTHORITY_SOURCE_values'] = sorted(vals)
MODELISH = ('gpt-', 'claude', 'gemini', 'deepseek', 'nvidia', 'openrouter', 'nemotron', 'llama', 'qwen')
OUT['authority_source_model_names'] = [v for v in vals if any(t in v.lower() for t in MODELISH)]
OUT['NOTIFICATION_has_authority_source'] = [d.get('MESSAGE_ID') for d in ds if d.get('TYPE') == 'NOTIFICATION' and d.get('AUTHORITY_SOURCE')]
OUT['types_with_authority_source'] = sorted({str(d.get('TYPE')) for d in ds if d.get('AUTHORITY_SOURCE')})

W = '0x' + '1' * 40
d = Path('probe_out') / 'i05b'
if d.exists():
    shutil.rmtree(d)
(d / 'append_only').mkdir(parents=True)
json.dump({'wallets': {W: {'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 100.0, 'enabled': True}}}, open(d / 'live_config.json', 'w'))
E.configure_paths(d, d / 'fills.csv')
s = E.DryRunLiveCopyService()
s.state['baselines'] = {W: {'wallet': W, 'baseline_ts_ms': 500, 'baseline_fill_id': 'pre'}}
s.state['fixed_sleeves'] = {}
s.processed_ids = set()
E.MASTER_TRUTH_ADDRESS = ''
f = E.LeaderFill(fill_id='g1', wallet=W, coin='BTC', side='BUY', price=100.0, size=1.0, signed_size_delta=1.0, timestamp_ms=1000, timestamp_iso='t', source='ws', recording_method='WS', raw={})
s.process_fill(f, E.LiveWalletConfig(wallet=W, mode='LIVE', copy_mode='fixed', fixed_notional=100.0))
OUT['I05_processed_ids'] = sorted(s.processed_ids)
OUT['I05_leader_event_positions'] = dict(s.state.get('leader_event_positions') or {})
OUT['I05_authority_survived_truth_failure'] = bool(s.state.get('leader_event_positions'))
ws = d / 'append_only' / 'would_send_orders.csv'
OUT['I05_would_send_lines'] = len(ws.read_text(encoding='utf-8', errors='replace').splitlines()) if ws.exists() else 0

print(json.dumps(OUT, indent=1, default=str))
