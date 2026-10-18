"""CERT23 t_e3846ecf authoritative reproduction (single script, no hidden inputs).

Usage (from anywhere):
    python3.11 CERT23_t_e3846ecf_reproduce.py > raw_reproduce.json

Everything is derived from git objects of THIS repo at the tested commit:
  TESTED  = b142cf88d389e791160f691aac3d936852b99975
  MAILBOX = origin/control-mailbox (head recorded in the output)

No env vars, no pre-materialised engine.py, no untracked probe files.
Emits one JSON object: inputs + one section per row, each section carrying
"measured" plus, where the row can be faked, a mutation/negative control.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

TESTED = 'b142cf88d389e791160f691aac3d936852b99975'
ENGINE_PATH = '_archive/hl_stage2/HL_Live_Copy_Service.py'
ENGINE_SHA = 'e2f04fa826958c73169bae2490a6ebb3ebfd09d9aecda513ef0d7bd8a10ec2c6'
MAILBOX = 'origin/control-mailbox'
SELF = Path(__file__).resolve()
HERE = SELF.parent
OUT = {}

REPO = Path(os.environ.get('CERT23_GIT_REPO') or HERE.parents[1]).resolve()


def git(*a):
    p = subprocess.run(['git', '-C', str(REPO)] + list(a), capture_output=True)
    if p.returncode != 0:
        raise SystemExit('git %s failed: %s' % (' '.join(a), p.stderr.decode('utf-8', 'replace')[:400]))
    return p.stdout.decode('utf-8', 'replace')


def blob(rev_path):
    return git('show', rev_path).lstrip('\ufeff')


# ---------------------------------------------------------------- inputs
git('fetch', '-q', 'origin', 'control-mailbox')
engine_src = git('show', TESTED + ':' + ENGINE_PATH)
engine_sha = hashlib.sha256(engine_src.encode('utf-8')).hexdigest()
OUT['inputs'] = {
    'tested_commit': TESTED,
    'engine_path': ENGINE_PATH,
    'engine_blob_sha256': engine_sha,
    'engine_blob_matches_pinned': engine_sha == ENGINE_SHA,
    'mailbox_ref': MAILBOX,
    'mailbox_head': git('rev-parse', MAILBOX).strip(),
    'script_sha256': hashlib.sha256(SELF.read_bytes().replace(bytes([13, 10]), bytes([10]))).hexdigest(),
    'python': sys.version,
}
if engine_sha != ENGINE_SHA:
    raise SystemExit('engine blob mismatch: %s' % engine_sha)

WORK = Path(tempfile.mkdtemp(prefix='cert23_repro_'))
(WORK / 'engine.py').write_text(engine_src, encoding='utf-8')
os.chdir(WORK)
sys.path.insert(0, str(WORK))
import engine as E  # noqa: E402

SRC = engine_src
LINES = SRC.splitlines()
W = '0x' + '1' * 40
CFG_FIXED = E.LiveWalletConfig(wallet=W, mode='LIVE', copy_mode='fixed', fixed_notional=100.0)


def sandbox(name):
    d = WORK / 'sb' / name
    if d.exists():
        shutil.rmtree(d)
    (d / 'append_only').mkdir(parents=True)
    return d


def svc(name, copy_mode='fixed'):
    d = sandbox(name)
    cfg = {'wallets': {W: {'mode': 'LIVE', 'copy_mode': copy_mode, 'enabled': True}}}
    if copy_mode == 'fixed':
        cfg['wallets'][W]['fixed_notional'] = 100.0
    json.dump(cfg, open(d / 'live_config.json', 'w'))
    E.configure_paths(d, d / 'fills.csv')
    s = E.DryRunLiveCopyService()
    s.state['baselines'] = {W: {'wallet': W, 'baseline_ts_ms': 500, 'baseline_fill_id': 'pre'}}
    s.processed_ids = set()
    s.state['fixed_sleeves'] = {}
    return s, d


def fill(fid, ts, signed, price=100.0):
    return E.LeaderFill(fill_id=fid, wallet=W, coin='BTC', side=('BUY' if signed > 0 else 'SELL'),
                        price=price, size=abs(signed), signed_size_delta=signed, timestamp_ms=ts,
                        timestamp_iso='t', source='ws', recording_method='WS', raw={})


def slices_of(s):
    return len((((s.state.get('fixed_sleeves') or {}).get(W) or {}).get('BTC') or {}).get('slices') or [])


# ------------------------------------------------------- B4-I01/I02/I03
s, d = svc('i01')
s.state['baselines'] = {}          # no baseline: pre-baseline fill creates one, mints nothing
r_pre = s.process_ws_fill(fill('f1', 1000, 1.0))
OUT['B4-I01'] = {'measured': {
    'pre_baseline_result': r_pre,
    'leader_event_positions': dict(s.state.get('leader_event_positions') or {}),
    'fixed_sleeves': dict(s.state.get('fixed_sleeves') or {}),
    'processed_ids': sorted(s.processed_ids),
}}
s2, _ = svc('i01mut')
r_mut = s2.process_ws_fill(fill('f1', 1000, 1.0))   # baseline already 500ms -> must process
OUT['B4-I01']['mutation_control'] = {
    'baseline_ts_ms': 500, 'same_fill_result': r_mut,
    'processed_ids': sorted(s2.processed_ids),
    'predicate_non_vacuous': bool(r_mut.get('processed')) and 'f1' in s2.processed_ids,
    'control_works': (not r_pre.get('processed')) and bool(r_mut.get('processed')),
}

s, d = svc('i02')
s.state['baselines'] = {W: {'wallet': W, 'baseline_ts_ms': 2000, 'baseline_fill_id': 'f1'}}
s.persist()
s_restart = E.DryRunLiveCopyService()
r_stale = s_restart.process_ws_fill(fill('stale', 1500, 5.0))
OUT['B4-I02'] = {'measured': {
    'restart_leader_event_positions': dict(s_restart.state.get('leader_event_positions') or {}),
    'stale_fill_result': r_stale,
    'after_leader_event_positions': dict(s_restart.state.get('leader_event_positions') or {}),
    'after_fixed_sleeves': dict(s_restart.state.get('fixed_sleeves') or {}),
}}

s, d = svc('i03')
f = fill('dup1', 1000, 1.0)
a = s.process_ws_fill(f)
b = s.process_fill(f, CFG_FIXED)
OUT['B4-I03'] = {'measured': {
    'ws_result': a, 'rest_result': b,
    'acceptances_of_dup1': sum(1 for x in s.processed_ids if x == 'dup1'),
    'one_logical_stream': sum(1 for x in s.processed_ids if x == 'dup1') == 1,
}}

# --------------------------------------------------------------- B4-I04
s, d = svc('i04missed')
for i, ts in enumerate([1000, 2000, 3000], 1):
    s.apply_leader_event(CFG_FIXED, fill('miss%d' % i, ts, 1.0))
missed = slices_of(s)
s_net, d = svc('i04net')
s_net.apply_leader_event(CFG_FIXED, fill('net1', 4000, 3.0))
net = slices_of(s_net)
OUT['B4-I04'] = {'measured': {
    'three_missed_increases_slices': missed,
    'one_net_event_same_magnitude_slices': net,
    'net_equals_missed': missed == net,
    'inflation_ratio': (missed / net) if net else None,
}}

# --------------------------------------------------------------- B4-I05
s, d = svc('i05')
saved_truth = getattr(E, 'MASTER_TRUTH_ADDRESS', None)
E.MASTER_TRUTH_ADDRESS = ''
try:
    s.process_fill(fill('g1', 1000, 1.0), CFG_FIXED)
    err = None
except Exception as exc:  # noqa: BLE001
    err = repr(exc)[:200]
finally:
    if saved_truth is not None:
        E.MASTER_TRUTH_ADDRESS = saved_truth
recon = d / 'append_only' / 'reconciliation.csv'
OUT['B4-I05'] = {'measured': {
    'master_truth_address': '',
    'exception': err,
    'processed_ids': sorted(s.processed_ids),
    'leader_event_positions': dict(s.state.get('leader_event_positions') or {}),
    'reconciliation_rows_mentioning_event': recon.read_text(encoding='utf-8', errors='replace').count('g1') if recon.exists() else 0,
    'event_consumed_on_truth_failure': 'g1' in s.processed_ids,
    'engine_429_occurrences': SRC.lower().count('429'),
    'engine_retry_after_occurrences': SRC.lower().count('retry-after') + SRC.lower().count('retry_after'),
}}

# --------------------------------------------------------------- B4-I06
at = SRC.find('exchange.order(')
call = re.sub(r'\s+', ' ', SRC[at:SRC.find(')', at) + 1])
def id_tokens(text):
    return {'cloid': text.lower().count('cloid'), 'client_order_id': text.lower().count('client_order_id')}


def call_slice(text):
    i = text.find('exchange.order(')
    return re.sub(r'\s+', ' ', text[i:text.find(')', i) + 1]) if i >= 0 else ''


OUT['B4-I06'] = {'measured': {
    'cloid_occurrences': id_tokens(SRC)['cloid'],
    'client_order_id_occurrences': id_tokens(SRC)['client_order_id'],
    'exchange_order_call_text': call,
    'exchange_order_call_sites': SRC.count('exchange.order('),
    'call_has_client_id_kwarg': bool(re.search(r'cloid|client_order_id|client_id', call, re.I)),
}}
_mut = SRC.replace('exchange.order(', 'exchange.order(cloid="mut", ', 1)
OUT['B4-I06']['mutation_control'] = {
    'injected': 'cloid="mut" as first argument of exchange.order(',
    'mutated_cloid_occurrences': id_tokens(_mut)['cloid'],
    'mutated_call_has_kwarg': bool(re.search(r'cloid', call_slice(_mut), re.I)),
    'control_works': id_tokens(SRC)['cloid'] == 0 and id_tokens(_mut)['cloid'] == 1
                     and not bool(re.search(r'cloid|client_order_id|client_id', call, re.I))
                     and bool(re.search(r'cloid', call_slice(_mut), re.I)),
}


# --------------------------------------------------------------- B4-I07
def scope(lineno):
    start = None
    for k in range(lineno - 1, -1, -1):
        if re.match(r'\s*def\s+\w+', LINES[k]):
            start = k
            break
    if start is None:
        return None, None, ''
    ind = len(LINES[start]) - len(LINES[start].lstrip())
    end = len(LINES)
    for k in range(start + 1, len(LINES)):
        if LINES[k].strip() and (len(LINES[k]) - len(LINES[k].lstrip())) <= ind:
            end = k
            break
    return start + 1, end, '\n'.join(LINES[start:end])


order_line = SRC[:at].count('\n') + 1
s_start, s_end, s_body = scope(order_line)
c_line = next((n for n, l in enumerate(LINES, 1)
               if 'send_hyperliquid_order(' in l and 'def ' not in l), None)
c_start, c_end, c_body = scope(c_line) if c_line else (None, None, '')
TRUTH = re.compile(r'clearinghouse_state|clearinghouseState|user_state|sub_accounts|fetch_positions|account_truth|get_positions|info\.user', re.I)
OUT['B4-I07'] = {'measured': {
    'order_call_line': order_line,
    'send_function': {'start': s_start, 'end': s_end,
                      'follower_truth_calls': sorted({m.group(0) for m in TRUTH.finditer(s_body)})},
    'send_caller_function': {'start': c_start, 'end': c_end,
                             'follower_truth_calls': sorted({m.group(0) for m in TRUTH.finditer(c_body)}),
                             'position_before_source_lines': [l.strip() for l in c_body.splitlines()
                                                              if re.search(r'\bposition_before\s*=', l)],
                             'positions_source_lines': [l.strip() for l in c_body.splitlines()
                                                        if re.search(r'\bpositions\s*=', l)]},
    'repo_wide_follower_truth_call_count': len(re.findall(r'clearinghouse_state|clearinghouseState|user_state|sub_accounts', SRC, re.I)),
    'presend_follower_truth_present': bool(TRUTH.search(s_body) or TRUTH.search(c_body)),
}}
_mut_send = c_body.replace('positions = load_manual_live_positions()',
                          'positions = info.user_state(E.MASTER_TRUTH_ADDRESS)', 1)
OUT['B4-I07']['mutation_control'] = {
    'injected': 'info.user_state(...) replacing the local load_manual_live_positions() read in the send caller scope',
    'injection_point_found': 'load_manual_live_positions()' in c_body,
    'detector_finds_truth_in_mutated_caller_scope': sorted({m.group(0) for m in TRUTH.finditer(_mut_send)}),
    'control_works': (not OUT['B4-I07']['measured']['presend_follower_truth_present'])
                     and 'load_manual_live_positions()' in c_body
                     and bool(TRUTH.search(_mut_send)),
}

# --------------------------------------------------------------- B4-I08
TOKENS = ['fence', 'msvcrt', 'fcntl', 'CreateMutex', 'lock_file', 'lockfile', 'singleton',
          'pidfile', 'already running', 'filelock', 'portalocker']
OUT['B4-I08'] = {'measured': {
    'order_call_sites': SRC.count('exchange.order('),
    'token_counts': {t: SRC.lower().count(t.lower()) for t in TOKENS},
    'lease_occurrences': SRC.lower().count('lease'),
    'lease_contexts': [re.sub(r'\s+', ' ', SRC[max(0, m.start() - 60):m.start() + 60])
                       for m in re.finditer(r'lease', SRC, re.I)],
    'any_exclusion_primitive': any(SRC.lower().count(t.lower()) for t in TOKENS),
}}
_mut_fence = SRC + '\nimport msvcrt\n\n\ndef _sender_fence():\n    return msvcrt.locking(0, 0, 1)\n'
_mut_counts = {t: _mut_fence.lower().count(t.lower()) for t in TOKENS}
OUT['B4-I08']['mutation_control'] = {
    'injected': 'import msvcrt + _sender_fence() using msvcrt.locking appended to source',
    'mutated_token_counts_nonzero': {t: c for t, c in _mut_counts.items() if c},
    'control_works': (not OUT['B4-I08']['measured']['any_exclusion_primitive'])
                     and _mut_counts['msvcrt'] > 0 and _mut_counts['fence'] > 0,
}

# ------------------------------------------- control mailbox: envelopes
paths = sorted(p for p in git('ls-tree', '-r', '--name-only', MAILBOX).splitlines()
               if p.startswith('control_mailbox/inbox/') and p.endswith('.json'))
envs = []
for p in paths:
    d_ = json.loads(blob(MAILBOX + ':' + p))
    d_['__path'] = p
    envs.append(d_)
OUT['inputs']['envelope_count'] = len(envs)
types = Counter(str(e.get('TYPE')) for e in envs)
OUT['type_table'] = {t: types[t] for t in sorted(types)}


def auth_of(env):
    """Authority = non-empty AUTHORITY_SOURCE key, or AUTHORITY_SOURCE= token in text."""
    v = env.get('AUTHORITY_SOURCE')
    if isinstance(v, str) and v.strip():
        return v.strip()
    for m in re.finditer(r'AUTHORITY_SOURCE=([^\s,;"\'\]]+)', json.dumps(env)):
        if m.group(1).strip() and m.group(1).strip() not in ('None', 'null'):
            return m.group(1).strip()
    return None


notifs = [e for e in envs if str(e.get('TYPE')) == 'NOTIFICATION']
notif_detail = [{'message_id': e.get('MESSAGE_ID'), 'path': e['__path'],
                 'keys': sorted(k for k in e if k != '__path'),
                 'authority': auth_of(e),
                 'directive_id': e.get('DIRECTIVE_ID')} for e in notifs]
mut_notifs = []
for e in notifs:
    c = {k: v for k, v in e.items() if k != '__path'}
    c['AUTHORITY_SOURCE'] = 'MUTATION_CONTROL_SHOULD_DETECT'
    if auth_of(c):
        mut_notifs.append(c.get('MESSAGE_ID'))
authority_types = Counter(str(e.get('TYPE')) for e in envs if auth_of(e))
real_auth = [e for e in envs if auth_of(e)]
neg = None
if real_auth:
    probe = {k: v for k, v in real_auth[0].items() if k != '__path'}
    probe.pop('AUTHORITY_SOURCE', None)
    txt = json.dumps(probe)
    stripped = re.sub(r'AUTHORITY_SOURCE=[^\s,;"\'\]]+', 'AUTHORITY_SOURCE=REDACTED', txt)
    neg = {'message_id': probe.get('MESSAGE_ID'), 'flagged_after_strip': auth_of(json.loads(stripped)) is not None}
OUT['CTRL-I22'] = {'measured': {
    'type_table_enumerated': OUT['type_table'],
    'types_total': len(types),
    'notification_count': len(notifs),
    'notification_detail': notif_detail,
    'envelopes_carrying_authority': len(real_auth),
    'authority_by_type': {k: authority_types[k] for k in sorted(authority_types)},
    'authority_types_are_notification': 'NOTIFICATION' in authority_types,
    'mutation_control': {'injected_into_all_notifications': len(notifs),
                         'flagged_ids': sorted(mut_notifs),
                         'negative_control': neg},
    'control_works': bool(notifs) and len(mut_notifs) == len(notifs)
                     and not any(auth_of(e) for e in notifs)
                     and bool(neg) and not neg['flagged_after_strip'],
}}

MODELISH = re.compile(r'gpt-|claude|gemini|deepseek|nvidia|openrouter|nemotron|llama|qwen|mistral|sonnet|opus|haiku|anthropic|openai', re.I)
vals = Counter(a for a in (auth_of(e) for e in envs) if a)
distinct = sorted(vals)
OUT['CTRL-I23'] = {'measured': {
    'authority_occurrences': sum(vals.values()),
    'authority_distinct': len(distinct),
    'authority_values': distinct,
    'value_occurrence_counts': {k: vals[k] for k in distinct},
    'real_model_or_provider_matches': sorted(v for v in distinct if MODELISH.search(v)),
    'mutation_control': {
        'injected_values': ['gpt-6-astra', 'claude-sonnet-4'],
        'matches': sorted(v for v in distinct + ['gpt-6-astra', 'claude-sonnet-4'] if MODELISH.search(v)),
    },
}}
OUT['CTRL-I23']['measured']['control_works'] = (
    OUT['CTRL-I23']['measured']['mutation_control']['matches'] == ['claude-sonnet-4', 'gpt-6-astra']
    and not OUT['CTRL-I23']['measured']['real_model_or_provider_matches'])

# ------------------------------------------------------------- CTRL-EVID
HANDOFF_TYPES = ('RESPONSE', 'RESULT', 'STATUS', 'ACK')
FIELDS = {
    'TASK_ID': r'TASK_ID',
    'COMMIT_SHA': r'COMMIT_SHA|COMMIT',
    'FILES_CHANGED': r'FILES_CHANGED|FILES CHANGED|files_changed',
    'LOC': r'\bLOC\b|\+[0-9]+ ?/ ?-[0-9]+',
    'TESTS': r'TESTS|TEST_EXECUTED|tests? (?:run|executed|pass)',
    'OUTPUT': r'OUTPUT|STDOUT|ARTIFACT',
    'UNCERTAINTY': r'UNCERTAINTY|uncertain',
    'STAND_DOWN_REQUEST': r'STAND_DOWN_REQUEST|STAND DOWN',
}
handoffs = [e for e in envs if str(e.get('TYPE')) in HANDOFF_TYPES]
matrix = {}
for fname, pat in FIELDS.items():
    rx = re.compile(pat, re.I)
    in_hand, out_hand = [], []
    for e in envs:
        body = json.dumps({k: v for k, v in e.items() if k != '__path'})
        keys = ' '.join(e.keys())
        hit = bool(rx.search(keys)) or bool(rx.search(body))
        rec = {'id': e.get('MESSAGE_ID'), 'type': str(e.get('TYPE'))}
        if hit:
            (in_hand if str(e.get('TYPE')) in HANDOFF_TYPES else out_hand).append(rec)
    matrix[fname] = {'in_handoff': in_hand, 'outside_handoff': out_hand,
                     'in_handoff_count': len(in_hand), 'outside_handoff_count': len(out_hand),
                     'total_envelopes_carrying': len(in_hand) + len(out_hand)}
OUT['CTRL-EVID'] = {'measured': {
    'handoff_definition': 'TYPE in %s' % (HANDOFF_TYPES,),
    'handoff_count': len(handoffs),
    'handoff_type_counts': {t: sum(1 for e in handoffs if str(e.get('TYPE')) == t) for t in HANDOFF_TYPES},
    'field_matrix': matrix,
    'fields_absent_on_all_handoffs': sorted(f for f in matrix if matrix[f]['in_handoff_count'] == 0),
    'fields_present_only_outside_handoffs': sorted(f for f in matrix
                                                   if matrix[f]['in_handoff_count'] == 0
                                                   and matrix[f]['outside_handoff_count'] > 0),
    'fields_absent_everywhere': sorted(f for f in matrix
                                       if matrix[f]['in_handoff_count'] == 0
                                       and matrix[f]['outside_handoff_count'] == 0),
}}

# -------------------------------------------------------------- CTRL-HWM
def state(ref):
    d_ = json.loads(blob(ref + ':CONTROL_STATE.json'))
    al = d_.get('adjudication_log') or []
    return {'ref': ref,
            'blob_sha': git('rev-parse', ref + ':CONTROL_STATE.json').strip(),
            'updated_utc': d_.get('updated_utc'),
            'top_level_keys': len(d_),
            'has_adjudication_log': 'adjudication_log' in d_,
            'adjudication_entries': len(al),
            'adjudication_invalidated': sum(1 for e in al if str(e.get('INVALIDATED')).lower() == 'true'),
            'adjudication_disposition_present': bool(d_.get('adjudication_log_disposition'))}


mb = state(MAILBOX)
rp = state(TESTED)
fmt = '%Y-%m-%dT%H:%M:%S'
delta = (datetime.strptime(rp['updated_utc'][:19], fmt) - datetime.strptime(mb['updated_utc'][:19], fmt)).total_seconds() / 86400.0
py_naming = [l for l in git('grep', '-l', '-i', 'CONTROL_STATE', TESTED, '--', '*.py').splitlines() if l]
loaders = [l for l in git('grep', '-n', '-I', '-i', 'CONTROL_STATE', TESTED, '--', '*.py').splitlines()
           if re.search(r'open\(|json\.load|read_text|load\(|Path\(', l)]
OUT['CTRL-HWM'] = {'measured': {
    'mailbox_state': mb,
    'repo_state': rp,
    'delta_days_repo_minus_mailbox': round(delta, 4),
    'staler_copy': MAILBOX if delta > 0 else (TESTED if delta < 0 else 'EQUAL'),
    'mailbox_head': OUT['inputs']['mailbox_head'],
    'python_files_naming_control_state': py_naming,
    'control_state_loaders_in_python': loaders,
    'loader_count': len(loaders),
}}

for row, sec in OUT.items():
    if isinstance(sec, dict) and 'measured' in sec and 'control_works' not in sec:
        sec['control_works'] = 'n/a'
print(json.dumps(OUT, indent=1, sort_keys=True, default=str))
shutil.rmtree(WORK, ignore_errors=True)
