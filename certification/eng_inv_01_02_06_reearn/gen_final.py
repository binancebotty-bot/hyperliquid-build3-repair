#!/usr/bin/env python3
# Assemble the t_43fbb222 deliverable.
#
# Defect 1 (citation resolution): every evidence_ref below names a path that
#   EXISTS on this branch. The two certification/results/ paths cited by the
#   previous attempt are replaced by their sha256-pinned copies under cited/.
#   CITATION_RESOLUTION.json is produced separately by verify_citations.py and
#   resolves every path against the branch object.
#
# Defect 2 (ENG-INV-02 over-scoped predicate): measured on the CERTIFIED ENGINE
#   SCOPE with the scope authority quoted, and BOTH counts published
#   (certified_scope=1, all=2). The excluded legacy site is identified with its
#   enclosing function, caller chain and runtime gate, and disclosed as a
#   residual finding rather than dropped.
import json, subprocess
from pathlib import Path

SEP = chr(10)
HERE = Path(__file__).resolve().parent
CITED = HERE / 'cited'
RES = json.loads((HERE / 'result.json').read_text(encoding='utf-8'))
A0102 = json.loads((CITED / 'ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json').read_text(encoding='utf-8-sig'))
A06 = json.loads((CITED / 'ENG-INV-06-09_43731b4.json').read_text(encoding='utf-8-sig'))
HARNESS = CITED / 'ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py'
CENSUS = CITED / 'census_inv_06_09.py'
TEST = '43731b4f1f19a56e835032dabf608a550f925717'
D = 'certification/eng_inv_01_02_06_reearn/'
CIT_A0102 = D + 'cited/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_corrected_43731b4f.json'
CIT_A06 = D + 'cited/ENG-INV-06-09_43731b4.json'
CIT_HARNESS = D + 'cited/ENG-INV-01-02_ENG-010-014_SEM-B1-B4_harness_corrected_43731b4f.py'
CIT_CENSUS = D + 'cited/census_inv_06_09.py'
CIT_SUMS = D + 'cited/SHA256SUMS.txt'
CIT_PROBE = D + 'probe.py'
CIT_RESULT = D + 'result.json'
CIT_VERIFY = D + 'verify_citations.py'
CIT_RESOLUTION = D + 'CITATION_RESOLUTION.json'


def lines(p, a, b):
    return SEP.join(p.read_text(encoding='utf-8-sig').splitlines()[a - 1:b])


def svc(a, b):
    out = subprocess.run(['git', 'show', TEST + ':_archive/hl_stage2/HL_Live_Copy_Service.py'],
                         capture_output=True).stdout.decode('utf-8-sig', 'replace')
    return SEP.join(out.splitlines()[a - 1:b])


def ctl(row, prefix):
    return [c for c in RES['mutation_controls'] if c['row'] == row and c['mutation'].startswith(prefix)]


def rr(row):
    return [r for r in RES['rows'] if r['row'] == row][0]


r01, r02, r06 = rr('ENG-INV-01'), rr('ENG-INV-02'), rr('ENG-INV-06')

# the actual source lines around the legacy send site, quoted from the commit
legacy_quote = svc(1028, 1046)

rows = []

rows.append({
    'row_id': 'ENG-INV-01',
    'verdict': 'PASS',
    'evidence_ref': [
        CIT_A0102 + '#checks/ENG-INV-01',
        CIT_SUMS,
        CIT_PROBE,
        CIT_RESULT + '#rows/ENG-INV-01',
    ],
    'quoted_evidence': {
        'artifact': CIT_A0102,
        'artifact_provenance': 'sha256-pinned copy of origin/cert/local-main-b142cf8 (cited/SHA256SUMS.txt)',
        'artifact_key': 'checks/ENG-INV-01',
        'quote': json.dumps(A0102['checks']['ENG-INV-01'], ensure_ascii=False),
        'why_row_specific': 'The artifact keys results by row id. ENG-INV-01 owns exactly one entry, NO_PROCESS_SPAWNS; no sibling row in the same file declares that check, so a sibling cannot ride on this record.',
        'independent_recheck': json.dumps(r01, ensure_ascii=False),
        'recheck_scope_widened': 'the cited harness parsed Core + Service only; this re-run parsed all five production sources at the same commit and still found zero spawn sites',
    },
    'mutation_control': (ctl('ENG-INV-01', 'inv01') or [None])[0],
    'extra_mutations': ctl('ENG-INV-01', 'inv01')[1:],
    'why': 'UNCHANGED FROM t_20e1cb6d (accepted by the reviewer). SPECIFICITY: a one-element check list owned by ENG-INV-01 alone. NON-VACUITY: appending subprocess.Popen, and separately multiprocessing.Process, both flip NO_PROCESS_SPAWNS to FAIL and were re-executed here. LIMIT: the runtime-process-count half of execution_proof is NOT claimed; the probe is a static census and host process lists cannot be bound to the cited commit.',
})

rows.append({
    'row_id': 'ENG-INV-02',
    'verdict': 'PASS',
    'evidence_ref': [
        CIT_A0102 + '#checks/ENG-INV-02',
        CIT_HARNESS + '#L220-L235',
        CIT_PROBE + '#production_order_sites',
        CIT_RESULT + '#rows/ENG-INV-02',
        CIT_SUMS,
    ],
    'predicate_change': {
        'before': 'len(order_nodes(ALL_PRODUCTION_FILES)) == 1  -> counted 2 -> FAIL',
        'after': 'len(order_nodes(CERTIFIED_ENGINE_SCOPE)) == 1 -> counts 1 -> PASS',
        'certified_scope': r02['certified_scope'],
        'scope_authority': r02['scope_authority'],
        'count_certified_scope': r02['detail']['count_certified_scope'],
        'count_all': r02['detail']['count_all'],
        'justification': 'The row asks for one physical PRODUCTION .order() call site, and the project fixes what production means. OD-26 / section 5 of MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md (Boss, 2026-10-09T12:30Z) rules that certification targets the real Core engine HL_Live_Copy_Service_Core.py, NOT the legacy HL_Live_Copy_Service.py that G1-G4 were built on. Core says so in its own header: it is intentionally independent of the legacy flow. ARCHITECTURE.md scope budget states the budget as production files <=2 and physical production order sites 1. The previous predicate counted .order() nodes in every .py shipped under _archive/, which is a file set, not the certified engine. It is narrowed on that recorded authority, not because the row needed to pass - which is why both counts are published and the excluded site is named.',
        'what_was_excluded_and_why': [
            {
                'file': 'HL_Live_Copy_Service.py',
                'line': 1036,
                'receiver': 'exchange',
                'enclosing_function': 'send_hyperliquid_order (defined at L936)',
                'classification': 'LEGACY MODULE - outside the certified engine scope',
                'why_not_a_production_sender_for_this_row': 'OD-26 fixes the certified Build 3 engine to HL_Live_Copy_Service_Core.py and keeps the legacy module as history. The legacy module is not what the repair targets and not what certification runs.',
                'disclosed_residual': 'NOT dead code and NOT a test shim - see residual_finding. Excluded on SCOPE, and that exclusion is disclosed rather than buried.',
            },
        ],
    },
    'identification_of_legacy_site': {
        'site': 'HL_Live_Copy_Service.py:1036',
        'enclosing_function': 'send_hyperliquid_order(payload, marketable_bps=0.0, use_current_quote=False, max_notional=None)  [defined L936]',
        'what_it_is': 'a real, complete Hyperliquid order sender - not dead code, not a helper stub, not a test shim',
        'evidence_it_is_real': [
            'L971 reads HL_LIVE_HL_PRIVATE_KEY; absent -> CREDENTIALS_MISSING.',
            'L1030 Account.from_key(private_key); L1035 Exchange(account, base_url=..., account_address=...).',
            'L1036 response = exchange.order(...) with wire size/price and an IOC limit tif.',
            'L1041 parse_hl_order_status(response) consumes and reports a real exchange ack.',
        ],
        'quoted_context': legacy_quote,
        'callers': [
            {
                'caller': 'manual_send_one_intent (L1124) -> send_hyperliquid_order at L1387',
                'kind': 'manual one-shot path',
                'reachable_via': 'HL_Live_Copy_Service.py --send-one-intent <id> --confirm-send',
            },
            {
                'caller': 'maybe_auto_send_would_send (L2825) -> manual_send_one_intent at L2860',
                'kind': 'AUTOMATED path',
                'reachable_via': 'run_once -> process_fill -> append_order_intent -> (L2781) maybe_auto_send_would_send',
                'runtime_gate': 'HL_LIVE_AUTO_SEND_ENABLED must be 1 (L141, default 0)',
                'note': 'With auto-send enabled this loop calls manual_send_one_intent(..., True), i.e. confirm_send=True, so the legacy sender can place a real order without a per-order human confirm.',
            },
        ],
        'reachability_verdict': 'REACHABLE. It is not dead code and not a test shim. It is a second, environment-gated order-send path in the legacy module.',
        'why_it_does_not_sink_this_row': 'The row is scoped to the certified engine by OD-26. The caller chain and the gating env var are recorded here so a reviewer can disagree with the scope call on the evidence rather than on trust.',
    },
    'quoted_evidence': {
        'artifact': CIT_A0102,
        'artifact_provenance': 'sha256-pinned copy of origin/cert/local-main-b142cf8 (cited/SHA256SUMS.txt)',
        'artifact_key': 'checks/ENG-INV-02',
        'quote': json.dumps(A0102['checks']['ENG-INV-02'], ensure_ascii=False),
        'predicate_that_produced_it': lines(HARNESS, 220, 235),
        'why_the_original_predicate_was_rejected': 'It is line-window bound (2700<line<2800) AND file bound (Core only). A second real send path appended to the legacy module leaves it PASSING, so it cannot speak for the row.',
    },
    'independent_recheck': json.dumps(r02, ensure_ascii=False),
    'mutation_control': (ctl('ENG-INV-02', 'inv02_add_site_core_far') or [None])[0],
    'extra_mutations': ctl('ENG-INV-02', 'inv02'),
    'residual_finding': {
        'title': 'A second, environment-gated real order-send path exists in the legacy module',
        'site': 'HL_Live_Copy_Service.py:1036 (send_hyperliquid_order)',
        'severity': 'product finding - NOT fixed here, NOT covered by this row',
        'detail': 'At the cited commit the legacy HL_Live_Copy_Service.py still contains a complete live Hyperliquid sender reachable from an automated loop when HL_LIVE_AUTO_SEND_ENABLED=1. OD-26 scopes certification to Core, so ENG-INV-02 does not measure it; but any operator running the legacy service with auto-send on would have two distinct sender implementations in one repo. Reported for the Controller/Architect to rule on. Deliberately not repaired under t_43fbb222.',
    },
    'why': 'PASS under a narrowed, authority-backed predicate. The narrowing is neither silent nor free: both counts are published (certified_scope=1, all=2), the excluded site is named with its enclosing function, its caller chain and its runtime gate, and a scope-demonstration control shows a synthetic send path added to the legacy module is invisible to the narrowed predicate while the unnarrowed one sees it. NON-VACUITY IS PROVEN: two independent mutations inside the certified engine - a send appended far from _place_order, and a second send stacked inside _place_order itself - both flip the narrowed check to FAIL, so the check can fail. HONEST RESIDUAL: the legacy sender is real and reachable, not dead code; it is excluded on the OD-26 scope ruling and recorded as residual_finding for a ruling rather than quietly dropped.',
})

c06 = A06['invariants']['ENG-INV-06']
rows.append({
    'row_id': 'ENG-INV-06',
    'verdict': 'PASS',
    'evidence_ref': [
        CIT_A06 + '#invariants/ENG-INV-06',
        CIT_A06 + '#mutation_tests/INV-06_second_order_site',
        CIT_CENSUS + '#L84-L88',
        CIT_PROBE,
        CIT_RESULT + '#rows/ENG-INV-06',
        CIT_SUMS,
    ],
    'quoted_evidence': {
        'artifact': CIT_A06,
        'artifact_provenance': 'sha256-pinned copy of origin/cert/local-main-b142cf8 (cited/SHA256SUMS.txt)',
        'artifact_key': 'invariants/ENG-INV-06',
        'quote': json.dumps({'id': c06['id'], 'result': c06['result'], 'checks': c06['checks'], 'order_call_sites': c06['order_call_sites'], 'process_spawns': c06['process_spawns'], 'persistent_stores': c06['persistent_stores'], 'total_py_files_scanned': c06['total_py_files_scanned']}, ensure_ascii=False),
        'artifact_negative_test': json.dumps(A06['mutation_tests']['INV-06_second_order_site'], ensure_ascii=False),
        'why_row_specific': 'ENG-INV-06 owns a four-check record plus its own order_call_sites list. ENG-INV-01 and ENG-INV-02 carry neither no_persistent_store nor no_new_third_party_imports, so the rows cannot be standing on one result.',
        'known_limitation_of_the_cited_run': 'total_py_files_scanned=1. The shipped census sets py_files = [core_file] (census_inv_06_09.py L86), so it never enumerated the other production files.',
        'limitation_quote': lines(CENSUS, 84, 88),
        'independent_recheck': json.dumps(r06, ensure_ascii=False),
    },
    'mutation_control': (ctl('ENG-INV-06', 'inv06_add_runtime_file') or [None])[0],
    'extra_mutations': ctl('ENG-INV-06', 'inv06'),
    'why': 'UNCHANGED FROM t_20e1cb6d (accepted by the reviewer). PASS on what the row asserts: No NEW engine/runtime around Build 3. Against branch point 89b3bc7 the production .py set gains ZERO files (five removed, none added), no new whole-tree .order() site appears, and no new authoritative store constructor is introduced. The cited artifact is row-specific and its INV-06_second_order_site negative test is non-vacuous (expected FAIL / actual FAIL). Independent mutations add a runtime file and add sqlite3.connect; the row flips to FAIL in both. LIMITS: (1) the cited run scanned only Core, so the whole-file-set comparison closes that gap; (2) the row asserts no NEW runtime, and the legacy sender at HL_Live_Copy_Service.py:1036 predates the baseline, so it is not a violation of this row.',
})

out = {
    'schema': 'eng_inv_01_02_06_verdicts/v2',
    'card': 't_43fbb222',
    'supersedes_card': 't_20e1cb6d',
    'repo': 'binancebotty-bot/hyperliquid-build3-repair',
    'branch': 'hermes/eng-inv-citation-fix-narrow-inv02-t_43fbb222',
    'branch_base': RES['branch_base'],
    'tested_commit': RES['tested_commit'],
    'probe': CIT_PROBE,
    'raw_result': CIT_RESULT,
    'citation_resolver': CIT_VERIFY,
    'citation_table': CIT_RESOLUTION,
    'summary': {r['row_id']: r['verdict'] for r in rows},
    'defects_repaired': {
        'defect_1_citation_resolution': 'every evidence_ref names a path that exists on this branch; the two previously cited certification/results/ paths are replaced by their pinned copies under cited/. CITATION_RESOLUTION.json holds the per-path EXISTS table resolved against the branch object.',
        'defect_2_inv02_scope': 'ENG-INV-02 is measured on the certified engine scope with the scope authority quoted; both counts (certified_scope=1, all=2) are published and the excluded legacy site is disclosed as residual_finding.',
    },
    'rows': rows,
}
(HERE / 'verdicts.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(out['summary'], indent=1))
