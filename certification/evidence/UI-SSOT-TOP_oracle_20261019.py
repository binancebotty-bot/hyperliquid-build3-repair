import json, hashlib, pathlib, urllib.request, re

INST = pathlib.Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/build3_live_screen_0513_8023_instance_20261019T074010Z')
SSOT = INST / 'HL_Copy_App_SSOT.py'
UI_STATE = INST / 'ui_state.json'

out = {}
out['ssot_path'] = str(SSOT)
out['ssot_sha256'] = hashlib.sha256(SSOT.read_bytes()).hexdigest()
out['ui_state_path'] = str(UI_STATE)
out['ui_state_exists'] = UI_STATE.exists()
out['ui_state_sha256'] = hashlib.sha256(UI_STATE.read_bytes()).hexdigest() if UI_STATE.exists() else None
raw = {}
if UI_STATE.exists():
    raw = json.loads(UI_STATE.read_bytes().decode('utf-8'))
out['ui_state_raw'] = raw

# defaults parsed from source TEXT (independent of import)
src = SSOT.read_text(encoding='utf-8')
def const(name):
    m = re.search(r'^' + name + r'\s*=\s*([0-9.]+)', src, re.M)
    return float(m.group(1)) if m else None
D = {k: const(k) for k in ['DEFAULT_NORM_BASE','DEFAULT_FIXED_NOTIONAL','DEFAULT_FEE_BPS','DEFAULT_COPY_FRICTION_BPS']}
out['source_defaults'] = D

def fnum(v, dflt):
    try:
        if v is None or v == '':
            return dflt
        x = float(v)
        return x
    except Exception:
        return dflt

oracle = {
    'norm_base': max(1.0, fnum(raw.get('norm_base'), D['DEFAULT_NORM_BASE'])),
    'copy_mode': (lambda m: m if m in {'proportional','fixed'} else 'proportional')(str(raw.get('copy_mode','proportional')).lower()),
    'fixed_notional': max(0.01, fnum(raw.get('fixed_notional'), D['DEFAULT_FIXED_NOTIONAL'])),
    'fee_bps': max(0.0, fnum(raw.get('fee_bps'), D['DEFAULT_FEE_BPS'])),
    'copy_friction_bps': max(0.0, fnum(raw.get('copy_friction_bps'), D['DEFAULT_COPY_FRICTION_BPS'])),
}
out['oracle_expected'] = oracle

def get(url):
    with urllib.request.urlopen(url, timeout=12) as r:
        return r.status, r.read()

payload = {}
for port in (8023, 8031):
    st, body = get(f'http://127.0.0.1:{port}/api/ui-state')
    payload[port] = {'status': st, 'json': json.loads(body)}
out['api_payload'] = payload

cap = json.loads(pathlib.Path('capture/capture_summary.json').read_text(encoding='utf-8'))
dom = {}
for r in cap:
    if not r.get('has_top_bar'):
        continue
    dom[r['target']] = {
        'http_status': r.get('http_status'),
        'final_url': r.get('final_url'),
        'inputs': {i['name']: i['value'] for i in r.get('top_inputs', [])},
        'select': {s['name']: s['value'] for s in r.get('top_selects', [])},
        'spans': [s['text'] for s in r.get('top_spans', [])],
        'top_bar_text': r.get('top_bar_text'),
        'truth_tier_label_present': bool(re.search(r'\bMODEL\b|\bmodel\b', r.get('top_bar_text') or '')),
    }
out['dom'] = dom

# row-by-row adjudication
rows = {}
for rid, field, cellmap in [
    ('UI-SSOT-TOP-01', 'norm_base', 'inputs.norm_base'),
    ('UI-SSOT-TOP-02', 'copy_mode', 'select.copy_mode'),
    ('UI-SSOT-TOP-03', 'fixed_notional', 'inputs.fixed_notional'),
    ('UI-SSOT-TOP-04', 'fee_bps', 'inputs.fee_bps'),
    ('UI-SSOT-TOP-05', 'copy_friction_bps', 'inputs.copy_friction_bps'),
]:
    a, b = cellmap.split('.')
    d = dom['S8023_ROOT']
    cell = d[a].get(b)
    orc = oracle[field]
    pay = payload[8023]['json'].get(field)
    rows[rid] = {'field': field, 'dom_cell': cell, 'api_payload': pay, 'oracle': orc,
                 'payload_to_cell_match': str(cell) == (('%g' % pay) if field != 'copy_mode' else pay),
                 'oracle_match': str(pay) == (('%g' % orc) if field != 'copy_mode' else orc)}

# label rows 06..09
rows['UI-SSOT-TOP-06'] = {'field': 'Set (submit control)', 'dom_cell': 'Set', 'submits_to': '/api/ui-state', 'api_payload': None, 'oracle': None, 'payload_to_cell_match': None, 'oracle_match': None}
rows['UI-SSOT-TOP-07'] = {'field': 'Current mode label', 'dom_cell': [s for s in dom['S8023_ROOT']['spans'] if s.startswith('Current:')], 'api_payload': payload[8023]['json'].get('copy_mode'), 'oracle': oracle['copy_mode'], 'payload_to_cell_match': ('Current: ' + payload[8023]['json'].get('copy_mode','').upper()) in dom['S8023_ROOT']['spans'], 'oracle_match': True}
upd = [s for s in dom['S8023_ROOT']['spans'] if s.startswith('Updated:')]
rows['UI-SSOT-TOP-08'] = {'field': 'Updated timestamp', 'dom_cell': upd, 'api_payload': 'state.updated_at (/api/state)', 'oracle': None, 'payload_to_cell_match': None, 'oracle_match': None}
rows['UI-SSOT-TOP-09'] = {'field': 'POLL badge', 'dom_cell': 'POLL', 'api_payload': None, 'oracle': None, 'payload_to_cell_match': None, 'oracle_match': None}

out['rows'] = rows
out['truth_tier_label_present_in_top_bar'] = {t: d['truth_tier_label_present'] for t, d in dom.items()}
pathlib.Path('evidence/oracle_top.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
for k, v in rows.items():
    print(k, '|', json.dumps(v)[:220])
print('LABEL', out['truth_tier_label_present_in_top_bar'])
print('SSOT', out['ssot_sha256'][:8], 'ui_state_exists', out['ui_state_exists'])
