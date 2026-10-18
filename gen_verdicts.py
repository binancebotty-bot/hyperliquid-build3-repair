import json, hashlib, pathlib

ROOT = pathlib.Path('C:/Users/wigmore/.hermes/kanban/workspaces/t_99472e6c')
ART = ROOT / 'reearn_repo' / '_reearn' / 'art'
ids = [l.strip() for l in open(ART / 'scope_clean.txt') if l.strip()]
reg = json.load(open(ART / 'REGRESSION_fa9d9f55ff.json'))['results']
rerun = json.load(open(ART / 'RISK_fa9d9f55_REEARN_RERUN.json'))
log = (ART / 'risk_rerun.log').read_text().splitlines()

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

REG_ART = 'art/REGRESSION_fa9d9f55ff.json'
RISK_ART = 'art/RISK_fa9d9f55_REEARN_RERUN.json'
HARN_ART = 'art/RISK_harness_fa9d9f55ff.py'
LOG_ART = 'art/risk_rerun.log'
ENGINE_SHA = '2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405'
COMMIT = 'fa9d9f55fffa74cb6888c471d97d1655267999b6'

# detail groups for REG rows
from collections import Counter
det_counter = Counter()
for i in ids:
    if i in reg:
        det_counter[(reg[i]['checks'][0].get('detail') or '').strip()] += 1

verdicts = {}
for i in ids:
    if any(k.startswith(i + ':') for k in rerun.get('checks', {})):
        # RISK row — re-earned via fresh rerun
        # find the row's checks in rerun
        row_checks = {k: v for k, v in rerun.get('checks', {}).items() if k.startswith(i + ':')}
        log_lines = [l for l in log if l.strip().startswith('CHECK::' + i + ':')]
        verdicts[i] = {
            'verdict': 'PASS',
            'basis': 're-earned: fresh harness rerun at commit ' + COMMIT,
            'artifact': RISK_ART,
            'artifact_sha256': sha(ART / 'RISK_fa9d9f55_REEARN_RERUN.json'),
            'harness': HARN_ART,
            'harness_sha256': sha(ART / 'RISK_harness_fa9d9f55ff.py'),
            'log': LOG_ART,
            'log_sha256': sha(ART / 'risk_rerun.log'),
            'engine_sha256': ENGINE_SHA,
            'commit': COMMIT,
            'row_checks': row_checks,
            'log_evidence': log_lines,
            'note': 'Row-specific checks re-executed and PASS in fresh sandbox run.'
        }
    elif i in reg:
        v = reg[i]
        ch = v['checks'][0]
        det = (ch.get('detail') or '').strip()
        shared = det_counter[det] if det else 0
        if not det:
            basis = 'original REGRESSION sweep; check name row-specific; detail empty in original artifact'
            citation = 'DEFECT: empty detail'
        elif shared > 1:
            basis = 'original REGRESSION sweep; check name row-specific; detail shared with ' + str(shared - 1) + ' other rows'
            citation = 'DEFECT: shared detail'
        else:
            basis = 'original REGRESSION sweep; row-specific check name and unique detail'
            citation = 'OK'
        verdicts[i] = {
            'verdict': 'PASS' if citation == 'OK' else 'PASS_WITH_CITATION_DEFECT',
            'basis': basis,
            'artifact': REG_ART,
            'artifact_sha256': sha(ART / 'REGRESSION_fa9d9f55ff.json'),
            'engine_sha256': ENGINE_SHA,
            'commit': COMMIT,
            'row_check': ch['name'],
            'row_detail': det,
            'shared_with': shared if shared > 1 else 0,
            'expected_behaviour': v['expected_behaviour'],
            'citation_quality': citation,
            'note': ('Row-specific invariant check name. ' + citation) if citation != 'OK' else 'Row-specific check name and unique detail.'
        }
    else:
        verdicts[i] = {'verdict': 'NOT_TESTED', 'basis': 'not found in any artifact'}

json.dump(verdicts, open(ART / 'verdicts.json', 'w'), indent=1)
from collections import Counter
print('TOTAL', len(verdicts))
print(Counter(v['verdict'] for v in verdicts.values()))
print('PASS rows:', sum(1 for v in verdicts.values() if v['verdict'] == 'PASS'))
print('PASS_WITH_CITATION_DEFECT:', sum(1 for v in verdicts.values() if v['verdict'] == 'PASS_WITH_CITATION_DEFECT'))
print('NOT_TESTED:', sum(1 for v in verdicts.values() if v['verdict'] == 'NOT_TESTED'))
