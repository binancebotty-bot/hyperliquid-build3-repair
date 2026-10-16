#!/usr/bin/env python3
'''B3-CERT MIXED 61-row corrective harness (task t_34859113) -- REAL EXECUTION.

Offline-deterministic rows are EXECUTED for real against the pinned engine source with
per-check pass/fail + non-vacuous negatives. Sibling-executed rows are carried from their
committed artifacts. Live-network rows stay STILL_NOT_TESTED with the exact blocker.
No widened accept sets, no source-substring fallback; FAILs kept FAIL.
Run: /c/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe <this file>
'''
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys, math
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
WT = HERE.parents[1]
MAIN = Path('C:/Users/wigmore/hyperliquid-build3-repair')
OVERLAY = MAIN / '.worktrees' / 't_dc69fe0c_cert' / 'certification'
REG = OVERLAY / 'certification_matrix.json'
RES = OVERLAY / 'results'
ENGINE = WT / '_archive' / 'hl_stage2' / 'HL_Live_Copy_Service_Core.py'  # worktree engine == tested_commit
SIB_UI = MAIN / '.worktrees' / 't_1fb73bd2' / 'certification' / 'results' / 'UI_NT_b3e6d66651.json'
SIB_ENG = MAIN / '.worktrees' / 't_ae39db9b' / 'certification' / 'results' / 'ENGINE_FAIL_9eb2d40f69.json'

COMMIT = subprocess.run(['git', '-C', str(WT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
C10 = COMMIT[:10]
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
ENGINE_SHA = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
TG = {'NOT_TESTED': {'UI': 23, 'WALLET': 5, 'ORDER': 4, 'HEALTH': 3, 'CONTROL': 2, 'ENGINE': 7, 'SETTLE': 1},
      'FAIL': {'ENGINE': 6, 'ORDER': 5, 'SETTLE': 4, 'LIFECYCLE': 1}}

def _load_engine():
    for k in list(os.environ):
        if k.startswith('HL_'):
            os.environ.pop(k, None)
    os.environ['HL_LIVE_AUTO_SEND_ENABLED'] = '0'
    spec = importlib.util.spec_from_file_location('hlcore_mix', str(ENGINE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['hlcore_mix'] = mod
    spec.loader.exec_module(mod)
    return mod

CORE = _load_engine()
CHECKS = []
def check(row, name, expected, actual, passed, note=''):
    CHECKS.append({'row': row, 'check': name, 'expected': expected, 'actual': actual, 'pass': bool(passed), 'note': note})
    print('  %-12s %-34s %s' % (row, name, 'PASS' if passed else 'FAIL'))

def _mk_fill(coin='BTC', side='BUY', price=50000.0, size=0.01):
    return CORE.LeaderFill(leader_fill_id='lf-1', leader_wallet='0xL', coin=coin, side=side, price=price, size=size, timestamp_ms=1, source='TEST')

def _mk_intent(price=50000.0, size=0.01, copy_notional=500.0, reduce_only=False, decision='ENTRY_ALLOWED', notes=''):
    return CORE.Intent(intent_id='int-1', fill=_mk_fill(price=price, size=size), copy_side='BUY', copy_size=size, copy_notional=copy_notional, wallet_mode='proportional', copy_mode='proportional', decision=decision, reason='t', sleeve_id='s1', position_id='p1', position_direction_before='FLAT', wallet_position_before=0.0, coin_net_before=0.0, reduce_only_intended=reduce_only, reduce_only_sent_planned=reduce_only, notes=notes)

def _gate():
    from types import SimpleNamespace
    sg = CORE.SenderGateway.__new__(CORE.SenderGateway)
    sg.cfg = SimpleNamespace(min_notional=lambda: 10.0)
    return sg

def rows_pass(rid):
    return all(c['pass'] for c in CHECKS if c['row'] == rid)

def exec_ORD_004():
    c3 = CORE.SenderGateway._ceil_wire_size(1.23456, 3); f3 = CORE.SenderGateway._floor_wire_size(1.23456, 3)
    check('ORD-004', 'ceil@3dp==1.235', 1.235, c3, abs(c3 - 1.235) < 1e-12)
    check('ORD-004', 'floor@3dp==1.234', 1.234, f3, abs(f3 - 1.234) < 1e-12)
    f0 = CORE.SenderGateway._floor_wire_size(1.23456, 0)
    check('ORD-004', 'NEG floor@0==1.0', 1.0, f0, abs(f0 - 1.0) < 1e-12)
    check('ORD-004', 'NEG floor@0 != ceil@3', True, f0 != c3, f0 != c3)
    return 'PASS' if rows_pass('ORD-004') else 'FAIL'

def exec_ORD_003():
    sg = _gate(); it = _mk_intent(copy_notional=5.0, size=0.0001)
    ok, res = sg._validate_final_wire_order(it, {'raw_coin': 'BTC', 'sdk_coin': 'BTC'}, 'BTC', 0.0001, 50000.0, {})
    check('ORD-003', 'sub-min blocked', False, ok, ok is False)
    check('ORD-003', 'status BELOW_MIN_NOTIONAL', 'SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL', res.get('status'), res.get('status') == 'SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL')
    check('ORD-003', 'exchange_called False', False, res.get('exchange_called'), res.get('exchange_called') is False)
    it2 = _mk_intent(copy_notional=500.0, size=0.01)
    ok2, _ = sg._validate_final_wire_order(it2, {'raw_coin': 'BTC', 'sdk_coin': 'BTC'}, 'BTC', 0.01, 50000.0, {})
    check('ORD-003', 'NEG notional>=min opens', True, ok2, ok2 is True)
    return 'PASS' if rows_pass('ORD-003') else 'FAIL'

def exec_ENG_VAL_02():
    sg = _gate(); it = _mk_intent()
    for bad, tag in ((float('nan'), 'nan'), (float('inf'), 'inf')):
        ok, res = sg._validate_final_wire_order(it, {'raw_coin': 'BTC', 'sdk_coin': 'BTC'}, 'BTC', bad, 50000.0, {})
        check('ENG-VAL-02', 'wire_size=%s blocked' % tag, False, ok, ok is False and res.get('status') == 'SEND_NOT_ATTEMPTED_INVALID_SIZE')
        ok2, res2 = sg._validate_final_wire_order(it, {'raw_coin': 'BTC', 'sdk_coin': 'BTC'}, 'BTC', 0.01, bad, {})
        check('ENG-VAL-02', 'limit_px=%s blocked' % tag, False, ok2, ok2 is False and res2.get('status') == 'SEND_NOT_ATTEMPTED_PRICE_SANITY')
    check('ENG-VAL-02', 'fnum(nan)==0.0', 0.0, CORE.fnum(float('nan')), CORE.fnum(float('nan')) == 0.0)
    check('ENG-VAL-02', 'fnum(inf,7.5)==7.5', 7.5, CORE.fnum(float('inf'), 7.5), CORE.fnum(float('inf'), 7.5) == 7.5)
    ok3, _ = sg._validate_final_wire_order(it, {'raw_coin': 'BTC', 'sdk_coin': 'BTC'}, 'BTC', 0.01, 50000.0, {})
    check('ENG-VAL-02', 'NEG finite size passes', True, ok3, ok3 is True)
    return 'PASS' if rows_pass('ENG-VAL-02') else 'FAIL'

def exec_ENG_VAL_01():
    check('ENG-VAL-01', 'fnum(None)==0.0', 0.0, CORE.fnum(None), CORE.fnum(None) == 0.0)
    check('ENG-VAL-01', 'fnum(None,3.3)==3.3', 3.3, CORE.fnum(None, 3.3), CORE.fnum(None, 3.3) == 3.3)
    check('ENG-VAL-01', 'fnum-empty,4.4==4.4', 4.4, CORE.fnum('', 4.4), CORE.fnum('', 4.4) == 4.4)
    check('ENG-VAL-01', 'fnum-junk,5.5==5.5', 5.5, CORE.fnum('junk', 5.5), CORE.fnum('junk', 5.5) == 5.5)
    check('ENG-VAL-01', 'NEG fnum(12.5,9.9)==12.5', 12.5, CORE.fnum(12.5, 9.9), CORE.fnum(12.5, 9.9) == 12.5 and CORE.fnum(12.5, 9.9) != 9.9)
    return 'PASS' if rows_pass('ENG-VAL-01') else 'FAIL'

def exec_ENG_VAL_04():
    def oracle(av, mu, now, after, mark, ml):
        l = 1.0 / (2.0 * ml); ma = max(0.0, mu - abs(now) * mark * l + abs(after) * mark * l)
        avail = av - ma; side = 1.0 if after > 0 else -1.0
        return mark - side * avail / abs(after) / (1.0 - side * l)
    got = CORE.project_liquidation_px(1000.0, 50.0, 0.0, 0.1, 50000.0, 20.0)
    exp = oracle(1000.0, 50.0, 0.0, 0.1, 50000.0, 20.0)
    check('ENG-VAL-04', 'liq == oracle(20x)', round(exp, 6), round(got, 6), abs(got - exp) < 1e-6)
    got10 = CORE.project_liquidation_px(1000.0, 50.0, 0.0, 0.1, 50000.0, 10.0)
    check('ENG-VAL-04', 'NEG leverage changes liq', True, got10 != got, abs(got10 - got) > 1e-6)
    flat = CORE.project_liquidation_px(1000.0, 50.0, 0.0, 0.0, 50000.0, 20.0)
    check('ENG-VAL-04', 'NEG flat-after -> None', None, flat, flat is None)
    return 'PASS' if rows_pass('ENG-VAL-04') else 'FAIL'

EXEC = {'ORD-003': exec_ORD_003, 'ORD-004': exec_ORD_004, 'ENG-VAL-01': exec_ENG_VAL_01, 'ENG-VAL-02': exec_ENG_VAL_02, 'ENG-VAL-04': exec_ENG_VAL_04}

def load(p):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    except Exception:
        return None

def walk(node, target, path, hits):
    if isinstance(node, dict):
        if target in node and isinstance(node[target], dict):
            sub = node[target]; v = None
            for k in ('verdict', 'result', 'status', 'outcome'):
                if isinstance(sub.get(k), str):
                    v = sub[k].strip().upper(); break
            hits.append({'path': path + '::' + target, 'verdict': v})
        for k, v in node.items():
            walk(v, target, path + '/' + str(k), hits)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, target, path + '[%d]' % i, hits)

reg = load(REG)
rows = [r for r in reg['records'] if r.get('result') in TG and r.get('area') in TG[r['result']]]
assert len(rows) == 61, len(rows)
ev = []
for fn in sorted(os.listdir(RES)):
    if fn.endswith('.json'):
        j = load(RES / fn)
        if j is not None:
            ev.append((fn, j))
for sib in (SIB_UI, SIB_ENG):
    j = load(sib)
    if j is not None:
        ev.append((sib.name, j))
VT = ('PASS', 'FAIL', 'BLOCKED', 'NOT_TESTED', 'STILL_NOT_TESTED')
LIVE_NEED = {'ENGINE', 'SETTLE', 'HEALTH', 'WALLET', 'CONTROL'}
BLOCKER_LIVE = ('requires the live testnet engine running + real exchange orders; engine not running '
                '(last core_start_record 2026-10-15T09:54Z) and no real-order authority in this card')

# Engine self-test evidence (real runtime, subprocess, isolated audit dir).
ST = {'ran': False}
try:
    import tempfile
    _aud = tempfile.mkdtemp(prefix='b3mix_st_')
    _env = dict(os.environ); _env['HL_LIVE_AUDIT_DIR'] = _aud
    for k in list(_env):
        if k.startswith('HL_'):
            _env.pop(k, None)
    _env['HL_LIVE_AUDIT_DIR'] = _aud
    _p = subprocess.run([sys.executable, str(ENGINE), '--self-test'], capture_output=True, text=True, env=_env, timeout=600)
    _tail = (_p.stdout or '')[-3000:] + (_p.stderr or '')[-3000:]
    ST = {'ran': True, 'exit_code': _p.returncode, 'pass': _p.returncode == 0,
          'tail': _tail[-1200:], 'engine_sha256': ENGINE_SHA}
    print('=== ENGINE --self-test exit=%s ===' % _p.returncode)
except Exception as _e:
    ST = {'ran': False, 'error': str(_e)[:300]}

print('=== REAL EXECUTION (offline-deterministic rows) ===')
exec_done = {}
for rid, fn in EXEC.items():
    print('--', rid)
    exec_done[rid] = fn()

out_rows = []
for r in rows:
    rid = r['id']; area = r['area']
    rec = {'id': rid, 'area': area, 'register_result': r.get('result'), 'applicability': r.get('applicability'),
           'execution_proof': r.get('execution_proof'), 'independent_oracle': r.get('independent_oracle'),
           'tested_commit': COMMIT, 'tested_at_utc': NOW}
    if rid in exec_done:
        rec['verdict'] = exec_done[rid]
        rec['evidence_ref'] = 'MIXED_NT_FAIL_%s.json/checks::%s (REAL EXECUTION this run)' % (C10, rid)
        rec['checks'] = [c for c in CHECKS if c['row'] == rid]
    else:
        hits = []
        for fn, j in ev:
            walk(j, rid, fn, hits)
        good = [h for h in hits if h['verdict'] in VT]
        if area in LIVE_NEED and not good:
            rec['verdict'] = 'STILL_NOT_TESTED'; rec['blocker'] = BLOCKER_LIVE
            rec['evidence_ref'] = 'no executed evidence artifact (live-network)'
        elif good:
            rec['verdict'] = good[0]['verdict']
            rec['evidence_ref'] = good[0]['path'] + ' (committed sibling artifact, carried)'
        else:
            rec['verdict'] = 'STILL_NOT_TESTED'
            rec['blocker'] = BLOCKER_LIVE if area in LIVE_NEED else 'no executed evidence artifact found'
            rec['evidence_ref'] = 'no executed evidence artifact found for this row'
    out_rows.append(rec)

vc = Counter(x['verdict'] for x in out_rows)
neg_ok = all(c['pass'] for c in CHECKS if c['check'].startswith('NEG'))
out = {'schema': 'b3cert.mixed_nt_fail.v2', 'task_id': 't_34859113',
       'title': 'B3-CERT MIXED NOT_TESTED+FAIL corrective (61 rows)',
       'register_of_record': 'certification/certification_matrix.json @ main b142cf8',
       'tested_commit': COMMIT, 'tested_at_utc': NOW, 'engine_source': str(ENGINE), 'engine_sha256': ENGINE_SHA,
       'method': ('offline-deterministic rows executed for real against the pinned engine source with per-check '
                  'pass/fail + non-vacuous negatives; sibling-executed rows carried from committed artifacts; '
                  'live-network rows kept STILL_NOT_TESTED with blocker'),
       'evidence_artifacts_scanned': [fn for fn, _ in ev], 'real_execution_rows': sorted(exec_done.keys()),
       'checks': CHECKS, 'negative_tests_pass': neg_ok, 'engine_self_test': ST,
       'carried_evidence_note': ('carried verdicts come from committed sibling artifacts; the FAIL sibling was pinned '
                                 'to engine sha 2dfbd571..., while the CURRENT engine at tested_commit is c5a40384... '
                                 'whose own --self-test is RED, so carried FAILs are NOT re-passed here'),
       'summary': {'n': len(out_rows), 'verdict_counts': dict(vc), 'real_executed': len(exec_done)}, 'rows': out_rows}

json.dump(out, open(HERE / ('MIXED_NT_FAIL_%s.json' % C10), 'w', encoding='utf-8'), indent=1)
with open(HERE / ('PROGRESS_t_34859113.jsonl'), 'w', encoding='utf-8') as fh:
    for x in out_rows:
        fh.write(json.dumps({'id': x['id'], 'verdict': x['verdict'], 'evidence_ref': x.get('evidence_ref', ''), 'tested_at_utc': NOW}) + '\n')
with open(HERE / ('MIXED_NT_FAIL_%s.summary.txt' % C10), 'w', encoding='utf-8') as fh:
    fh.write('n=%d counts=%s real_executed=%d negatives_pass=%s\n' % (len(out_rows), json.dumps(dict(vc)), len(exec_done), neg_ok))
    for x in out_rows:
        fh.write('%s|%s|%s|%s\n' % (x['id'], x.get('register_result'), x['verdict'], str(x.get('evidence_ref', ''))[:70]))
print('WROTE', HERE / ('MIXED_NT_FAIL_%s.json' % C10), dict(vc), 'real_executed', len(exec_done))
