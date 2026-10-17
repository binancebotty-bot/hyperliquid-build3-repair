import json

REG = 'b142cf88d389e791160f691aac3d936852b99975'
R = []

def add(rid, verdict, ref, why):
    R.append({'row_id': rid, 'verdict': verdict, 'evidence_ref': ref,
              'tested_commit': REG, 'why': why})

add('F25-X05', 'FAIL',
    '_cert33/x05.py (executed lease probe) + _cert33/svc.py grep census',
    'Row-bound and executed, but against the wrong engine. The Core engine HL_Live_Copy_Service_Core.py (sha256 b171ec8f) does satisfy the property: acquire_instance_lock() takes only an OS byte-range lock (msvcrt.locking LK_NBLCK), never reads a PID/holder file (fn_mentions_pid=false); a live holder refuses a second start (REFUSED INSTANCE_ALREADY_RUNNING); and a planted "PID=999999" stale lock file neither blocks nor misidentifies the holder (ACQUIRED; the file is not even readable while genuinely locked). But the register declares the runtime as source_of_truth.terminal_runtime_local_path = _archive/hl_stage2/HL_Live_Copy_Service.py (sha256 e2f04fa8, 5109 lines), and that file has no lease at all: msvcrt 0, fcntl 0, instance.lock 0, acquire_instance_lock 0, CreateMutex 0, lock_file 0, lockfile 0. The shipped/declared runtime has no authoritative lease holder, so the F25 condition is unprotected where the product actually runs.')

add('F25-X06', 'NOT_TESTED',
    'git ls-tree -r b142cf88 (registry file census)',
    'Genuinely absent route, not a tooling fault. The register commit has no builder, no launcher, no packaging/release script and no CI definition: no build/launch/deploy/release/start/package file, and no .ps1/.cmd/.bat/.sh/.yml/.yaml/.toml anywhere in a 156-file tree. With no deployment-candidate builder there is no place for a dirty-worktree guard to live and nothing that could build from a dirty tree. Absent component named: BUILD/RELEASE-LAUNCHER (candidate builder). Deployment today is a manual operator checkout, outside the product.')

add('F25-X07', 'NOT_TESTED',
    'git ls-tree -r b142cf88 (registry file census) + engine grep',
    'Same absent component as F25-X06. With no builder there is no build step that could carry or omit a resolvable source commit. Confirmed independently: neither HL_Live_Copy_Service.py nor HL_Live_Copy_Service_Core.py resolves or embeds a build/source commit (grep for manifest/BUILD_SHA/git describe/source_commit returns nothing). Absent component named: BUILD/RELEASE-LAUNCHER (source-commit binding).')

add('F25-X08', 'NOT_TESTED',
    'git ls-tree -r b142cf88 (registry file census)',
    'Row requires a builder and a launcher to validate the same manifest files/schemas. Neither a builder nor a launcher exists at the register commit, and no product manifest exists at all (the only manifest.json files are unrelated graphify-out artifacts). There are two separate components, not one shared contract. Absent components named: BUILD/RELEASE-LAUNCHER and the shared MANIFEST SCHEMA.')

CLAIM_ROWS = [
    ('F-CLAIM-01', 'GREEN because unit tests passed', 'unit-tests'),
    ('F-CLAIM-02', 'GREEN because local ledger reconciled', 'local-ledger'),
    ('F-CLAIM-03', 'GREEN because WS event was seen', 'ws-event'),
    ('F-CLAIM-04', 'GREEN because order/fill row exists', 'order-row'),
    ('F-CLAIM-05', 'GREEN because dashboard row is clean', 'dashboard-row'),
    ('F-CLAIM-06', 'GREEN because one copied example worked', 'one-example'),
    ('F-CLAIM-07', 'SAFE because auto_send is disabled', 'auto_send'),
    ('F-CLAIM-08', 'SAFE because recovery handles it', 'recovery'),
]
for rid, claim, tag in CLAIM_ROWS:
    why = (
        "Not row-bound, and the stated basis is itself the forbidden claim.")
    if tag in ('unit-tests', 'local-ledger', 'order-row', 'dashboard-row', 'one-example'):
        why += (' The check ' + rid + '_NOT_USED_AS_EVIDENCE passes with detail="" - a predicate that cannot fail, '
                'identical in form across all eight F-CLAIM rows - and its evidence_ref/notes are carried boilerplate '
                'shared by 138 rows ("Regression sweep: 131/138 rows PASS ... Engine sha256 2dfbd57 verified"). '
                'For this row that boilerplate is literally the forbidden claim: a sweep/test-count, not a proof that ' +
                "'" + claim + "' was refused as evidence.")
    else:
        why += (' The check ' + rid + '_NOT_USED_AS_EVIDENCE passes with detail="" (unfalsifiable, identical across '
                'all eight F-CLAIM rows) and cites the shared 131/138 regression sweep. Nothing asserts that ' +
                "'" + claim + "' was ever rejected as evidence.")
    why += (' A census of all 33 committed certification JSON artifacts at the register commit found the phrase only '
            'inside this row\'s own expected_behaviour text - no artifact records a candidate claim being rejected. '
            'None of the eight claim rows would fail for a different row, which is exactly the demotion standard.')
    add(rid, 'FAIL', 'certification/results/REGRESSION_fa9d9f55ff.json (row check ' + rid + '_NOT_USED_AS_EVIDENCE)', why)

DONE = [
    ('DONE-01', 'PASS',
     'certification/results/CONTROL_fa9d9f55ff.json check DONE_01_SOURCE_TRACKED_FROM_BASELINE + git ancestry/absence probe',
     'Row-bound check, independently re-verified here. CONTROL_fa9d9f55ff.json (tested_commit fa9d9f55, 52/53 rows) carries the row-specific check DONE_01_SOURCE_TRACKED_FROM_BASELINE with detail "Baseline cea4beb77... verified". I re-derived it rather than trusting the note: cea4beb77af17a387f6c5aea9ca0c4057a8eb750 exists, is titled BUILD3_SOURCE_BASELINE_IMPORT_1, is an ancestor of the register commit (merge-base --is-ancestor => ANCESTOR_OK), and adds only the untouched Build 3 sources (HL_Live_Copy_Service.py 4261 lines + convergence_shadow.py 250 lines, 4511 insertions, no other file). The baseline is genuinely tracked from an untouched import; the check is specific to this row (a different row\'s baseline would fail it). Caveat recorded, not enough to fail the row: the declared runtime file has since diverged (+887/-39 lines) and the Core engine was added later at 2abf84c, so \'tracked from\' is satisfied but \'unchanged\' is not.'),
    ('DONE-02', 'PASS',
     'git archive b142cf88 -> _archive/hl_stage2/test_g2_copy_correctness.py executed: 41 passed, 0 failed; RESULT::G2_DELTA_SIZED_NOT_FIXED_PER_FILL_PASS',
     'Row-bound and executed on the register commit, not a shared sweep. I extracted the tree at b142cf88 and ran the G2 harness with py3.11: 41/41 checks passed, including the row-specific results "three ADDs converge follower to desired 3.0 (delta, not fixed per-fill)", G2_DELTA_SIZED_NOT_FIXED_PER_FILL_PASS, t3 proportional sizing unit semantics, G2_FIXED_MODE_AUTHORITY_HOLD_PASS (fixed mode holds with zero orders rather than minting fixed notionals) and G2_SINGLE_ORDER_CALL_SITE_PASS. The harness is decisive for this row: it asserts the delta/target semantics that fixed-per-fill sizing would violate, so it fails for the defect this row names.'),
    ('DONE-03', 'PASS',
     'git archive b142cf88 -> _archive/hl_stage2/test_g3_exchange_truth.py executed: 48 passed, 0 failed; RESULT::G3_MULTIDEX_HIP3_AGGREGATE_PASS',
     'Row-bound and executed on the register commit. G3 harness (py3.11): 48/48 checks passed, including "multi-DEX / HIP-3 aggregation; missing scope fails closed" with a two-DEX fixture (default + builder-hip3, BTC 1.0 + 0.5), G3_MULTIDEX_HIP3_AGGREGATE_PASS, per-scope userFillsByTime attribution, deterministic cross-scope dedupe, G3_SCOPE_UNAVAILABLE_FAIL_CLOSED_PASS and G3_MASTER_TRUTH_ACTUAL_PASS. Independently corroborated in the engine source: follower mid uses allMids per HIP-3 DEX (_FOLLOWER_MIDS), leader equity sums accountValue across every enumerated DEX, and follower exposure uses master_exposure over all DEX scopes. The check is specific to this row (single-DEX code would fail it).'),
]
for rid, verdict, ref, why in DONE:
    add(rid, verdict, ref, why)

out = {'task': 't_cdba5d5b', 'batch': 'CERT 33/53 (15 rows)',
       'register_commit': REG,
       'register_source': 'origin/cert/local-main-b142cf8:certification/certification_matrix.json',
       'tested_commit': REG,
       'rows': R}
assert len(R) == 15, len(R)
assert len({r['row_id'] for r in R}) == 15
json.dump(out, open('C:/Users/wigmore/.hermes/cache/scratch/b3_clean/_cert33/CERT33_verdicts.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
from collections import Counter
print(Counter(r['verdict'] for r in R))
print([r['row_id'] for r in R])
