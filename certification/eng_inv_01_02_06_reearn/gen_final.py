#!/usr/bin/env python3
"""Assemble the t_20e1cb6d deliverable. Every quote is read programmatically
from the cited artifacts as they exist on origin/cert/local-main-b142cf8
(copied into ./cited/, sha256-pinned in cited/SHA256SUMS.txt)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CITED = HERE / 'cited'
RES = json.loads((HERE / 'result.json').read_text(encoding='utf-8'))
A0102 = json.loads((CITED / 'ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json').read_text(encoding='utf-8-sig'))
A06 = json.loads((CITED / 'ENG-INV-06-09_43731b4.json').read_text(encoding='utf-8-sig'))
HARNESS = CITED / 'ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py'
CENSUS = CITED / 'census_inv_06_09.py'


def lines(p, a, b):
    return '\n'.join(p.read_text(encoding='utf-8-sig').splitlines()[a - 1:b])


def ctl(row, prefix):
    return [c for c in RES['mutation_controls'] if c['row'] == row and c['mutation'].startswith(prefix)]


def rr(row):
    return [r for r in RES['rows'] if r['row'] == row][0]


rows = []
rows.append({
    'row_id': 'ENG-INV-01',
    'verdict': 'PASS',
    'quoted_evidence': {
        'artifact': 'certification/eng_inv_01_02_06_reearn/cited/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json',
        'artifact_location': 'origin/cert/local-main-b142cf8',
        'artifact_key': "checks['ENG-INV-01']",
        'quote': json.dumps(A0102['checks']['ENG-INV-01'], ensure_ascii=False),
        'why_row_specific': 'The artifact stores results in a check list keyed by row id. ENG-INV-01 owns exactly one entry, NO_PROCESS_SPAWNS; no sibling row in the same file (ENG-INV-02, ENG-010..014, SEM-B1..B4) declares that check in its own list. A sibling therefore cannot ride on this record, which is the failure mode that disqualified the 03/04/05 attempt.',
        'independent_recheck': json.dumps(rr('ENG-INV-01'), ensure_ascii=False),
        'recheck_scope_widened': 'the cited harness parsed only Core + Service; this re-run parsed all five production sources in _archive/hl_stage2 at the same commit and still found zero spawn sites',
    },
    'mutation_control': (ctl('ENG-INV-01', 'inv01') or [None])[0],
    'extra_mutations': ctl('ENG-INV-01', 'inv01')[1:],
    'why': 'Both tests met. SPECIFICITY: the cited row record is a one-element check list owned by ENG-INV-01 alone, so it is not one shared result labelled twice. NON-VACUITY: appending subprocess.Popen to the engine flips NO_PROCESS_SPAWNS to FAIL, and a second multiprocessing.Process variant flips it too; both were re-executed here rather than copied from the artifact. LIMIT STATED HONESTLY: the runtime-process-count half of the row execution_proof is NOT claimed. The probe is static-census only. The OS process list on this host carries unrelated Hermes/agent processes that cannot be bound to commit 43731b4f, so no process-count observation is asserted.',
})
rows.append({
    'row_id': 'ENG-INV-02',
    'verdict': 'FAIL',
    'quoted_evidence': {
        'artifact': 'certification/eng_inv_01_02_06_reearn/cited/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json',
        'artifact_location': 'origin/cert/local-main-b142cf8',
        'artifact_key': "checks['ENG-INV-02']",
        'quote': json.dumps(A0102['checks']['ENG-INV-02'], ensure_ascii=False),
        'predicate_that_produced_it': lines(HARNESS, 220, 235),
        'why_row_specific': 'The check is keyed ENG-INV-02 and no sibling declares ONE_PHYSICAL_ORDER_SITE, so the record is row-keyed. But the quoted detail contradicts itself in one string: it reports the physical set as [2703] while admitting "total all: 2". The predicate on lines 232-233 keeps only .order() nodes with 2700<line<2800 and is passed the Core file only, so it cannot speak about any other production file.',
        'independent_recheck': json.dumps(rr('ENG-INV-02'), ensure_ascii=False),
    },
    'mutation_control': (ctl('ENG-INV-02', 'inv02_add_site_other_file') or [None])[0],
    'extra_mutations': ctl('ENG-INV-02', 'inv02'),
    'why': 'SPECIFICITY FAILS and the evidence contradicts the row as written. The row reads "One physical production .order() call site" with no file qualifier. At the cited commit 43731b4f the production sources of _archive/hl_stage2 contain TWO physical Attribute-call .order() nodes: HL_Live_Copy_Service.py:1036 and HL_Live_Copy_Service_Core.py:2703. The cited predicate sees one because it is line-window bound (2700<line<2800, harness L232) and file bound (Core only). Proven rather than argued: appending a genuine second send path to HL_Live_Copy_Service.py leaves the cited predicate PASSING, while the unwindowed whole-tree predicate flips to FAIL. The predicate does carry a real negative control - a site inserted inside its own window flips it to FAIL - which is why the defect is scoping, not fabrication. SCOPE DECISION NEEDED: if the Controller/Architect rules that "production" means the Core engine only, the cited predicate becomes admissible once its window is replaced by a whole-file count. That ruling is not mine to make silently, so the row is returned FAIL rather than PASS under a private assumption. CONTEXT: the legacy service already existed in the branch point 89b3bc7 with the same site at line 1036, so this is a pre-existing scope question, not a regression introduced by the certify branch.',
})
c06 = A06['invariants']['ENG-INV-06']
rows.append({
    'row_id': 'ENG-INV-06',
    'verdict': 'PASS',
    'quoted_evidence': {
        'artifact': 'certification/eng_inv_01_02_06_reearn/cited/ENG-INV-06-09_43731b4.json',
        'artifact_location': 'origin/cert/local-main-b142cf8',
        'artifact_key': "invariants['ENG-INV-06']",
        'quote': json.dumps({'id': c06['id'], 'result': c06['result'], 'checks': c06['checks'], 'order_call_sites': c06['order_call_sites'], 'process_spawns': c06['process_spawns'], 'persistent_stores': c06['persistent_stores'], 'total_py_files_scanned': c06['total_py_files_scanned']}, ensure_ascii=False),
        'artifact_negative_test': json.dumps(A06['mutation_tests']['INV-06_second_order_site'], ensure_ascii=False),
        'why_row_specific': 'ENG-INV-06 owns a four-check record (single_order_call_site, no_process_spawns, no_new_third_party_imports, no_persistent_store) plus its own order_call_sites list. ENG-INV-01 and ENG-INV-02 carry neither no_persistent_store nor no_new_third_party_imports, so the two rows cannot be standing on one result.',
        'known_limitation_of_the_cited_run': 'total_py_files_scanned=1. The shipped census sets py_files = [core_file] (census_inv_06_09.py L86), so it never enumerated the other production files and on its own cannot exclude a runtime added elsewhere.',
        'limitation_quote': lines(CENSUS, 84, 88),
        'independent_recheck': json.dumps(rr('ENG-INV-06'), ensure_ascii=False),
    },
    'mutation_control': (ctl('ENG-INV-06', 'inv06_add_runtime_file') or [None])[0],
    'extra_mutations': ctl('ENG-INV-06', 'inv06'),
    'why': 'PASS on what the row actually asserts: "No NEW engine/runtime around Build 3". Measured against the branch point 89b3bc7, the production .py set gains ZERO files (five removed, none added), no new .order() send site appears (the same two sites exist at both commits), and no new authoritative store constructor is introduced. The cited artifact is row-specific and its INV-06_second_order_site negative test is non-vacuous (expected FAIL / actual FAIL). My independent mutations add a runtime file and add sqlite3.connect, and the row flips to FAIL in both cases. LIMITS STATED: (1) the cited run scanned only the Core file, so the whole-file-set comparison above, not the artifact, is what closes that gap; (2) the row asserts no NEW runtime, and the manual CLI send path at HL_Live_Copy_Service.py:1036 predates the baseline, so it is not a violation of this row - it is what sinks ENG-INV-02. The two rows are therefore not interchangeable, which is why they are verdicted separately.',
})
out = {'schema': 'eng_inv_01_02_06_verdicts/v1', 'card': 't_20e1cb6d', 'repo': 'binancebotty-bot/hyperliquid-build3-repair', 'branch': 'hermes/eng-inv-01-02-06-rowbound-t_20e1cb6d', 'branch_base': RES['branch_base'], 'tested_commit': RES['tested_commit'], 'probe': 'certification/eng_inv_01_02_06_reearn/probe.py', 'raw_result': 'certification/eng_inv_01_02_06_reearn/result.json', 'summary': {'ENG-INV-01': 'PASS', 'ENG-INV-02': 'FAIL', 'ENG-INV-06': 'PASS'}, 'rows': rows}
(HERE / 'verdicts.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(out['summary'], indent=1))
