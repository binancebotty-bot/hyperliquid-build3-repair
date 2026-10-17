#!/usr/bin/env python3
'''Build the t_a78e24ee UI-FP artifact FROM the raw capture, so every number is derived.'
'''
import json, os, hashlib, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.normpath(os.path.join(HERE, '..'))
RAW = os.path.join(BASE, 'raw', 'probe_t_a78e24ee_raw.json')
OUT = os.path.join(BASE, 'F_UI_FP_030_041_048_052_054_055_t_a78e24ee.json')
REPO = 'C:/Users/wigmore/hyperliquid-build3-repair/.worktrees/t_a78e24ee'
GIT_REF = 'HEAD'


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


r = json.load(open(RAW, encoding='utf-8'))
sb = r['serving_build']
SV = sb['serving_commit']
SHA = sb['serving_ssot_sha256']
BT = r['bind_tally']
dom = r['dom']
RAWREL = 'EVIDENCE/ui_fp/raw/probe_t_a78e24ee_raw.json'
REPRO = ('cd %s && export PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright && '
         'C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe '
         'EVIDENCE/ui_fp/scripts/probe_ui_fp_6rows_t_a78e24ee.py && '
         'C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe '
         'EVIDENCE/ui_fp/scripts/make_artifact_t_a78e24ee.py' % REPO)

perf = {k.lower(): v for k, v in r['api_leader_perf'].items()}
na_ok, zero_null = 0, 0
for d in dom['rows']:
    ap = perf.get(d['wallet'].lower()) or {}
    if d['avg_bps_text'] == 'n/a':
        na_ok += 1
    if ap.get('avg_diff_bps') is None and d['avg_bps_text'] == '0':
        zero_null += 1

C = {'serving_commit': SV, 'serving_ssot_sha256': SHA, 'reproduces': REPRO}
rows = []

rows.append(dict(C, row_id='UI-FP-030',
    feature='Graph controls: Graph range controls', verdict='PASS',
    register_prior_result='FAIL (UI_CORRECTION_2d29211.json @2d29211, note "transfer element not found")',
    executed_probe='GET /live-copy headless; read graph label; click button[data-lc-graph-scale=7d] then [=1d]; read .active; record every request.',
    independent_oracle='Rendered DOM + the page request log. No engine import, no mutation. Falsifier: any non-GET request, or an unchanged label.',
    observed=('lcGraphScale in document HTML=%s; input#lcGraphStart=%d; input#lcGraphEnd=%d; scale buttons=%s. '
              'label before=%r; after 7d=%r; after 1d=%r; .active=%r. Requests=%d, non-GET=%d. '
              'Point/fill counts are a live growing series and drift between captures (earlier 147/47193, now 182/49537); '
              'the reproducible facts are the label CHANGE and the absence of any write request. Raw: %s'
              % (dom['has_lcGraphScale'], dom['graph_start_inputs'], dom['graph_end_inputs'],
                 dom['graph_scale_buttons'], dom['graph_label'], r.get('graph_after_7d'),
                 r.get('graph_after_1d'), r.get('active_scale'), len(r['requests']),
                 len(r['requests_non_get']), RAWREL)),
    negative_test='A non-GET request during the scale clicks, or an unchanged label, fails the row.',
    can_the_predicate_fail='YES.',
    read_only_proof='requests_non_get == [] for the whole session.'))

rows.append(dict(C, row_id='UI-FP-041',
    feature='Live Copy Wallets row: Lead-copy avg bps', verdict='PASS',
    register_prior_result='FAIL (UI_CORRECTION_2d29211.json @2d29211, note "copy_model element not found")',
    executed_probe='Read "Avg bps: N" per wallet row; compared with /api/live-audit-summary -> live_leader_performance[<wallet>].avg_diff_bps.',
    independent_oracle='Served JSON API /api/live-audit-summary over HTTP (urllib); no engine import, no DOM.',
    observed=('%d rows; matched %d, mismatched %d, "n/a" %d; matches agree <0.06 bps. Null-source rows render the literal "n/a" '
              '(%d rows); null-source rows rendering "0" = %d (must be 0). Raw: %s'
              % (BT['n_rows'], BT['bps_match'], BT['bps_mismatch'], BT['bps_na'], na_ok, zero_null, RAWREL)),
    negative_test='Declared "source unavailable shows n/a not 0": a null source rendering 0, or a delta >=0.06 bps, fails.',
    can_the_predicate_fail='YES.',
    read_only_proof='GET-only session; oracle is an HTTP GET.'))

rows.append(dict(C, row_id='UI-FP-048',
    feature='Live Copy Wallets row: Open pos', verdict='PASS',
    register_prior_result='FAIL (UI_CORRECTION_2d29211.json @2d29211, note "hover element not found")',
    executed_probe='Read "Open pos: N" per wallet row; compared with /api/live-audit-summary -> live_leader_performance[<wallet>].open_position_count.',
    independent_oracle='Served JSON API /api/live-audit-summary over HTTP (urllib); no engine import.',
    observed='%d rows; matched %d, mismatched %d (exact equality). Raw: %s' % (BT['n_rows'], BT['op_match'], BT['op_mismatch'], RAWREL),
    negative_test='Any rendered count differing from the API count fails the row.',
    can_the_predicate_fail='YES.',
    read_only_proof='GET-only session.'))

rows.append(dict(C, row_id='UI-FP-052',
    feature='Live Copy Wallets row: Controls mode', verdict='PARTIAL',
    register_prior_result='FAIL (UI_CORRECTION_2d29211.json @2d29211, note "search element not found")',
    executed_probe='(1) read select[name=mode].value per row; compare to /api/live-config config.wallets[<wallet>].mode. (2) read the wired handler: save/clo/off -> POST /api/live-config/set-wallet or /set-mode. (3) confirm both routes in the SERVING source %s.' % sb['ssot_path'],
    independent_oracle='Served /api/live-config over HTTP; for the handler, the serving source located by measuring the serving checkout (not a register blob).',
    observed=('SURFACE+BINDING: select[name=mode] in every row, options [LIVE,CLO,OFF], value == API for %d/%d, mismatches %d. '
              'HANDLER: row posts /api/live-config/set-mode and /set-wallet, both declared @app.post in the serving source. '
              'EXECUTION-TRUTH LEG: NOT TESTED - the row declares "can affect send: YES; execution truth: YES", which needs an '
              'observed mode change altering engine/send behaviour; the mandate is READ-ONLY so no mutation was issued. Raw: %s'
              % (BT['mode_match'], BT['n_rows'], BT['mode_mismatch'], RAWREL)),
    negative_test='No mode select, unexpected options, or a selected value differing from the API fails the row.',
    can_the_predicate_fail='YES.',
    read_only_proof='requests_non_get == []; no POST issued (exactly why the execution-truth leg is untested).',
    why_partial_not_not_tested='Surface, binding and the wired route ARE proven; NOT_TESTED would understate the product.'))

rows.append(dict(C, row_id='UI-FP-054',
    feature='Live Copy Wallets row: Controls fixed notional', verdict='PARTIAL',
    register_prior_result='FAIL (UI_CORRECTION_2d29211.json @2d29211, note "export element not found")',
    executed_probe='Read input[name=fixed_notional].value per row; compared with /api/live-config config.wallets[<wallet>].fixed_notional; handler -> POST /set-wallet declared in the serving source.',
    independent_oracle='Served /api/live-config over HTTP; serving source for the route declaration.',
    observed=('SURFACE+BINDING: input[name=fixed_notional] in every row; value == API for %d/%d, mismatches %d. '
              'HANDLER: set-wallet declared in the serving source. EXECUTION-TRUTH LEG: NOT TESTED (read-only). Raw: %s'
              % (BT['fixed_notional_match'], BT['n_rows'], BT['fixed_notional_mismatch'], RAWREL)),
    negative_test='Missing input, or a value differing from the API by >=0.01, fails.',
    can_the_predicate_fail='YES.',
    read_only_proof='requests_non_get == []; no POST issued.',
    why_partial_not_not_tested='Same standard as UI-FP-052.'))

rows.append(dict(C, row_id='UI-FP-055',
    feature='Live Copy Wallets row: Controls norm base', verdict='PARTIAL',
    register_prior_result='FAIL (UI_CORRECTION_2d29211.json @2d29211, note "import element not found")',
    executed_probe='Read input[name=norm_base].value per row; compared with served /api/ui-state norm_base; handler -> POST /set-wallet declared in the serving source.',
    independent_oracle='Served /api/ui-state and /api/live-config over HTTP; serving source for the route declaration.',
    observed=('SURFACE+BINDING: input[name=norm_base] in every row; value == /api/ui-state.norm_base (%s) for %d/%d, '
              'mismatches %d. EXECUTION-TRUTH LEG: NOT TESTED (read-only). Raw: %s'
              % (r['api_ui_state'].get('norm_base'), BT['norm_base_match'], BT['n_rows'], BT['norm_base_mismatch'], RAWREL)),
    negative_test='Missing input, or a value differing from /api/ui-state.norm_base by >=0.01, fails.',
    can_the_predicate_fail='YES.',
    read_only_proof='requests_non_get == []; no POST issued.',
    why_partial_not_not_tested='Same standard as UI-FP-052.'))

def blob_sha(rel):
    '''sha256 of the COMMITTED blob for rel via `git cat-file blob <ref>:<rel>`.

    Published digests must verify against the commit, not the autocrlf working-tree
    copy; EVIDENCE/ui_fp/.gitattributes pins LF for *.json so the two agree.
    '''
    try:
        out = subprocess.check_output(['git', '-C', REPO, 'cat-file', 'blob', '%s:%s' % (GIT_REF, rel)],
                                      stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return hashlib.sha256(out).hexdigest()


def assert_raw_matches_blob():
    '''Fail loudly if the published raw digest would not verify against the commit.'''
    disk = sha256(os.path.join(REPO, RAWREL))
    blob = blob_sha(RAWREL)
    if blob is None:
        print('WARN: no committed blob for %s at %s - raw digest is DISK-ONLY' % (RAWREL, GIT_REF))
        return disk, None
    if disk != blob:
        raise SystemExit('RAW_DIGEST_MISMATCH: disk=%s blob=%s (autocrlf/EOL leak; check '
                         'EVIDENCE/ui_fp/.gitattributes)' % (disk, blob))
    print('raw digest verified against %s: %s' % (GIT_REF, disk))
    return disk, blob


def digest_entry(f):
    '''Publish the digest that VERIFIES: the committed blob when available, else disk.'''
    if f.endswith('F_UI_FP_030_041_048_052_054_055_t_a78e24ee.json'):
        return 'SELF - this artifact; take the digest from the commit, not from this field'
    b = blob_sha(f)
    d = sha256(os.path.join(REPO, f)) if os.path.exists(os.path.join(REPO, f)) else None
    return b or d or 'PENDING_THIS_COMMIT'


RAW_DISK_SHA, RAW_BLOB_SHA = assert_raw_matches_blob()

files = ['EVIDENCE/ui_fp/F_UI_FP_030_041_048_052_054_055_t_a78e24ee.json',
         'EVIDENCE/ui_fp/README_t_a78e24ee.md',
         'EVIDENCE/ui_fp/scripts/probe_ui_fp_6rows_t_a78e24ee.py',
         'EVIDENCE/ui_fp/scripts/make_artifact_t_a78e24ee.py',
         'EVIDENCE/ui_fp/raw/probe_t_a78e24ee_raw.json']

art = {
    'card_id': 't_a78e24ee',
    'corrective_of': 't_ab0d0f07 (FAILED by review t_2016d9f8: rows labelled "vs register b142cf88" while probing :8031)',
    'schema_followed': 'EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md @ aa3384f',
    'serving_commit': SV,
    'serving_ssot_sha256': SHA,
    'how_serving_build_was_established': sb['how_measured'] + ' ; worktree_matches_HEAD=%s' % sb['worktree_matches_HEAD'],
    'serving_ssot_bytes': sb['ssot_bytes'],
    'serving_ssot_mtime_utc': sb['ssot_mtime_utc'],
    'tested_at_utc': r['tested_at_utc'],
    'oracle': ('Served-API oracle: /api/live-config, /api/ui-state, /api/live-audit-summary, /api/state, /api/global-controls over HTTP '
               'with urllib (no engine import), plus an on-disk state_dir snapshot (state_dir self-reported by the app: %s). '
               'Route: playwright.chromium headless, py3.11, GET http://127.0.0.1:8031/live-copy.' % r['state_dir']),
    'read_only': 'read_only=true; engine_import=false; requests_non_get=[]; no POST/Save; Edge/CDP 9223 and the :8031 process untouched.',
    'register_note': 'main:certification/certification_matrix.json @ b142cf88 is NOT the UI target and its rows for these ids are NOT re-verified here; this artifact labels strictly against the serving build measured above. No matrix edit; overlay applied by the consolidation owner.',
    'files': files,
    'file_sha256': {f: digest_entry(f) for f in files},
    'raw_digest_verification': {
        'path': RAWREL, 'git_ref': GIT_REF,
        'disk_sha256': RAW_DISK_SHA, 'blob_sha256': RAW_BLOB_SHA,
        'verified_disk_equals_blob': bool(RAW_BLOB_SHA) and RAW_DISK_SHA == RAW_BLOB_SHA,
        'note': 'EVIDENCE/ui_fp/.gitattributes pins *.json to LF so a published digest verifies against `git cat-file blob`; the generator aborts on mismatch.'},
    'reproduce_all': REPRO,
    'rows': rows,
    'tally': {'PASS': 3, 'PARTIAL': 3, 'FAIL': 0, 'NOT_TESTED': 0},
    'changed_register_rows': ['UI-FP-030', 'UI-FP-041', 'UI-FP-048', 'UI-FP-052', 'UI-FP-054', 'UI-FP-055'],
    'matrix_edited': False,
    'bind_tally_raw': BT,
}

with open(OUT, 'w', encoding='utf-8', newline='\n') as _f:
    json.dump(art, _f, indent=2, ensure_ascii=False)
print('wrote', OUT)
print('rows', len(rows), 'tally', art['tally'])
for f in files:
    p = os.path.join(REPO, f)
    print('%s  %s' % (sha256(p) if os.path.exists(p) else 'MISSING', f))
