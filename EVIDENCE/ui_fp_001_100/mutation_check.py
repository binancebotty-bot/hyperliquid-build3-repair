import copy, json, os, subprocess, sys
OUT = 'EVIDENCE/ui_fp_001_100'
WORK = OUT + '/mutation_work'
BASE = json.load(open(OUT + '/dom_capture.json', encoding='utf-8'))
ART = json.load(open(OUT + '/UI_FP_001_100_cert.json', encoding='utf-8'))
DECL = {r['row_id']: r['verdict'] for r in ART['rows']}

def setid(cap, k, v, exp=False):
    t = cap['dom_expanded' if exp else 'dom']['idmap']
    if k not in t:
        raise SystemExit('missing idmap ' + k)
    t[k] = v

def wrow(cap):
    for r in cap['dom']['rows']:
        c = r.get('cells') or []
        if c and '0x010461c1' in (c[0] or ''):
            return c
    raise SystemExit('no wallet row')

def prow(cap, coin):
    for r in cap['dom_expanded']['rows']:
        c = r.get('cells') or []
        if len(c) >= 8 and c[0] == coin and c[1] in ('LONG', 'SHORT'):
            return c
    raise SystemExit('no position row ' + coin)

def frow(cap):
    for r in cap['dom_expanded']['rows']:
        c = r.get('cells') or []
        if len(c) >= 9 and (c[0] or '')[:4].isdigit() and c[2] in ('BUY', 'SELL'):
            return c
    raise SystemExit('no friction row')

def dedit(cap, a, b):
    v = cap['dom_expanded']['idmap']['lcWalletRows']
    if a not in v:
        raise SystemExit('detail lacks ' + a)
    setid(cap, 'lcWalletRows', v.replace(a, b), True)

MUT = {
 'UI-FP-001': (lambda c: setid(c, 'lcWalletCount', '17 / 10'), 'lcWalletCount 16/10 -> 17/10'),
 'UI-FP-002': (lambda c: setid(c, 'lcModeCounts', 'Live wallets: 11 Close-only wallets: 0 Off: 5'), 'LIVE 10 -> 11'),
 'UI-FP-003': (lambda c: setid(c, 'lcModeCounts', 'Live wallets: 10 Close-only wallets: 1 Off: 5'), 'CLO 0 -> 1'),
 'UI-FP-004': (lambda c: setid(c, 'lcModeCounts', 'Live wallets: 10 Close-only wallets: 0 Off: 7'), 'OFF 6 -> 7'),
 'UI-FP-005': (lambda c: setid(c, 'lcBannerSending', 'OFF'), 'sending ON -> OFF'),
 'UI-FP-006': (lambda c: setid(c, 'lcWsOverall', 'Websocket DEGRADED'), 'ws OK -> DEGRADED'),
 'UI-FP-007': (lambda c: setid(c, 'lcBannerResting', '1'), 'resting 0 -> 1'),
 'UI-FP-026': (lambda c: setid(c, 'lcGraphSubtitle', 'Exchange account graph. ALL range - 227 portfolio pts.'), 'drop realized-fills clause'),
 'UI-FP-027': (lambda c: c['dom']['svg']['lcEquityChart'].update(paths=0), 'svg paths -> 0'),
 'UI-FP-028': (lambda c: setid(c, 'lcGraphSubtitle', 'Selected wallet exposure graph.'), 'drop graph subtitle'),
 'UI-FP-032': (lambda c: wrow(c).__setitem__(0, '0x010461c1...1c703a OFF'), 'wallet Live -> OFF'),
 'UI-FP-033': (lambda c: wrow(c).__setitem__(0, '0x010461c1...1c703a OFF'), 'wallet Live -> OFF'),
 'UI-FP-034': (lambda c: wrow(c).__setitem__(2, 'Websocket DEGRADED'), 'cell2 WS -> DEGRADED'),
 'UI-FP-038': (lambda c: wrow(c).__setitem__(1, '-'), 'drop partial label'),
 'UI-FP-044': (lambda c: wrow(c).__setitem__(5, wrow(c)[5].replace('0 exits', '3 exits')), '0 exits -> 3'),
 'UI-FP-047': (lambda c: wrow(c).__setitem__(6, wrow(c)[6].replace('$1,999.72', '$0.01')), 'exposure -> 0.01'),
 'UI-FP-051': (lambda c: wrow(c).__setitem__(7, 'none yet'), 'last fill -> none yet'),
 'UI-FP-063': (lambda c: dedit(c, 'Partial record', 'Record'), 'drop Partial record'),
 'UI-FP-064': (lambda c: dedit(c, 'ENGINE_LEDGER_SLEEVES_PARTIAL', 'X'), 'drop attribution code'),
 'UI-FP-065': (lambda c: dedit(c, 'Exchange closedPnl on matched orders', 'Y'), 'drop closedPnl row'),
 'UI-FP-066': (lambda c: dedit(c, 'Cumulative rejects:', 'Rejects:'), 'drop cumulative rejects'),
 'UI-FP-067': (lambda c: prow(c, '0G').__setitem__(0, 'ZZZNOTACOIN'), 'coin 0G -> ZZZ'),
 'UI-FP-068': (lambda c: prow(c, '0G').__setitem__(1, 'LONG'), 'side SHORT -> LONG'),
 'UI-FP-069': (lambda c: prow(c, '0G').__setitem__(2, '-77'), 'size -76 -> -77'),
 'UI-FP-070': (lambda c: prow(c, '0G').__setitem__(3, '0.999'), 'entry px -> 0.999'),
 'UI-FP-071': (lambda c: prow(c, '0G').__setitem__(4, '0.5'), 'mark n/a -> 0.5'),
 'UI-FP-077': (lambda c: frow(c).__setitem__(2, 'BUY'), 'friction side SELL -> BUY'),
}

def run(cap, tag):
    os.makedirs(WORK, exist_ok=True)
    ci = WORK + '/cap_' + tag + '.json'
    co = WORK + '/out_' + tag + '.json'
    json.dump(cap, open(ci, 'w'))
    env = dict(os.environ)
    env['UI_FP_CAPTURE'] = ci
    env['UI_FP_OUT'] = co
    p = subprocess.run([sys.executable, OUT + '/evaluate.py'], capture_output=True, text=True, env=env)
    if p.returncode != 0 or not os.path.exists(co):
        return None, (p.stderr or p.stdout or '')[-300:]
    return {r['row_id']: r['verdict'] for r in json.load(open(co))['rows']}, ''


def main():
    dem = set(json.load(open('EVIDENCE/ui_fp_001_100/demoted_scope.json', encoding='utf-8-sig'))['ids'])
    scope = [r['row_id'] for r in ART['rows'] if r['verdict'] == 'PASS' and r['row_id'] in dem]
    base, err = run(copy.deepcopy(BASE), 'base')
    if base is None:
        raise SystemExit('baseline evaluate failed: ' + err)
    ok = all(base[r] == DECL[r] for r in DECL)
    recs = []
    vac = []
    for rid in scope:
        if rid not in MUT:
            recs.append({'row_id': rid, 'mutation': None, 'declared': DECL[rid],
                         'mutated_verdict': None, 'killed': False, 'error': 'NO_MUTATION_DEFINED'})
            vac.append(rid)
            continue
        fn, desc = MUT[rid]
        cap = copy.deepcopy(BASE)
        try:
            fn(cap)
        except SystemExit as e:
            recs.append({'row_id': rid, 'mutation': desc, 'declared': DECL[rid],
                         'mutated_verdict': None, 'killed': False, 'error': str(e)})
            vac.append(rid)
            continue
        got, err = run(cap, rid.replace('-', ''))
        mv = got.get(rid) if got else None
        k = (mv == 'FAIL')
        recs.append({'row_id': rid, 'mutation': desc, 'declared': DECL[rid],
                     'mutated_verdict': mv, 'killed': k, 'error': err})
        if not k:
            vac.append(rid)
    art = {'card_id': 't_b9d358f4',
           'purpose': 'prove every in-scope PASS predicate can fail (schema hard requirement 6)',
           'method': 'one targeted mutation of the frozen DOM capture per row, re-run evaluate.py, row must flip PASS->FAIL',
           'reproduces': 'python EVIDENCE/ui_fp_001_100/mutation_check.py',
           'scope_rows': len(scope),
           'baseline_reproduces_artifact': ok,
           'killed': sum(1 for r in recs if r['killed']),
           'vacuous': vac,
           'rows': recs}
    json.dump(art, open(OUT + '/mutation_check.json', 'w'), indent=1)
    print('scope PASS rows:', len(scope))
    print('baseline matches:', ok)
    print('killed:', art['killed'], '/', len(scope))
    print('VACUOUS:', vac if vac else 'none')
    for r in recs:
        print(' ', r['row_id'], r['declared'], '->', r['mutated_verdict'],
              'KILLED' if r['killed'] else '*** SURVIVED ***')


if __name__ == '__main__':
    main()
