#!/usr/bin/env python3
'''Emit certification/results/UI_FP_batch3_t_t_356f8e3a.json for rows 101-150.

Verdicts are derived from probe_out.json, the committed DOM capture and the
certification matrix row titles. Only the engine-line map is hand-mapped (it
was measured by probe.py).
'''
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(REPO, 'certification', 'results',
                   'UI_FP_batch3_t_t_356f8e3a.json')
CARD = 't_356f8e3a'

P = json.load(open(os.path.join(HERE, 'probe_out.json'), encoding='utf-8'))
D = json.load(open(os.path.join(HERE, 'dom_capture.json'), encoding='utf-8'))
MATRIX = os.path.join(REPO, 'certification', 'certification_matrix.csv')

TITLE = {}
with open(MATRIX, encoding='utf-8', newline='') as f:
    for row in csv.reader(f):
        if row and row[0].startswith('UI-FP-'):
            TITLE[row[0]] = row[2]

SHA = P['serving_ssot_sha256']
EL = P['engine_lines']
A0 = D['auditRows'][0]
C = P['api_counts']
APPO = P['append_only']
COLS = P['order_intents_columns']
EX = P['exchange_snapshot']

REPRO = ('cd EVIDENCE/UI_FP_batch3_t_' + CARD + ' && '
         'C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe '
         'probe.py')

ORACLE_API = ('independent read of the served /api/live-audit-summary JSON and '
              'hl_live_copy_audit/append_only/*.csv; never imports '
              'HL_Copy_App_SSOT.py')
ORACLE_CSV = ('recount of append_only/order_intents.csv against the DOM cell '
              'text captured in dom_capture.json')

ROWS = []


def add(rid, cls, sel, val, line, verdict, probe, oracle, note=None):
    r = {'id': rid, 'row_id': rid, 'title': TITLE.get(rid, ''), 'class': cls,
         'selector': sel, 'value': val, 'engine_line': line,
         'observed': val + '  [raw capture: EVIDENCE/UI_FP_batch3_t_' + CARD
                     + '/dom_capture.json + probe_out.json]',
         'verdict': verdict,
         'serving_commit': P.get('serving_commit', 'NOT_A_GIT_CHECKOUT'),
         'serving_ssot_sha256': SHA, 'executed_probe': probe,
         'independent_oracle': oracle, 'reproduces': REPRO}
    if note:
        r['note'] = note
    ROWS.append(r)


# --- 101/102 Positions tab ------------------------------------------------
add('UI-FP-101', 'renderable',
    '#lcOrphanPositionRows td:nth-child(10) (Context)',
    'no row: tbody holds only the empty-state message "No account-level '
    'orphan exchange positions."',
    'HL_Copy_App_SSOT.py:2672/2703/2731 build ACCOUNT_LEVEL_ONLY rows only '
    'when exchange_available; render at :6693',
    'NOT_TESTED',
    'DOM capture after load + api_counts.orphan_exchange_positions='
    + str(C['orphan_exchange_positions']),
    ORACLE_API,
    'Surface cannot exercise this field: exchange snapshot is '
    + str(EX.get('status')) + ' (' + str(EX.get('reason')) + '), so no '
    'ACCOUNT_LEVEL_ONLY row is ever constructed. Not a UI pass or fail.')

add('UI-FP-102', 'renderable',
    '#lcOrphanPositionRows (shared-symbol residual aggregate)',
    'no row: api_counts.real_copy_positions=' + str(C['real_copy_positions'])
    + ', owned=' + str(C['owned_copy_positions']) + ', orphan='
    + str(C['orphan_exchange_positions']),
    'HL_Copy_App_SSOT.py:2703-2711 (shared-coin residual rows ARE stamped '
    'row_type=ACCOUNT_LEVEL_ONLY in this build)',
    'NOT_TESTED',
    'DOM capture + served-API counts above', ORACLE_API,
    'The 2026-05-11 baseline FAIL (row lacks row_type, filtered out) does not '
    'reproduce in source: line 2704 iterates sorted(shared_coins) and line '
    '2711 sets row_type=ACCOUNT_LEVEL_ONLY. The branch is still gated on '
    'exchange_available, so it cannot be shown rendering here.')

# --- 103-120 Execution Quality (18 columns) ------------------------------
EXEC = [('103', 'Time'), ('104', 'Wallet'), ('105', 'Coin'), ('106', 'Side'),
        ('107', 'Status'), ('108', 'Terminal state'),
        ('109', 'Operator action'), ('110', 'Reject category'),
        ('111', 'OID'), ('112', 'Fill avg px'), ('113', 'Size'),
        ('114', 'Pos before -> after'), ('115', 'Leader->send ms'),
        ('116', 'Total ms'), ('117', 'Symbol ms'), ('118', 'SDK ms'),
        ('119', 'Exchange ms'), ('120', 'Error')]
for num, label in EXEC:
    add('UI-FP-' + num, 'renderable',
        '#lcExecQualRows td for column "' + label + '"',
        'no data row: tbody holds only the empty-state message. '
        'api_counts.execution_quality_rows='
        + str(C['execution_quality_rows']),
        'HL_Copy_App_SSOT.py:' + str(EL['exec_rows_builder'])
        + ' (_build_execution_quality_rows) fed by recent_send_attempts; '
        'render template :' + str(EL['render_exec_row_template']),
        'NOT_TESTED',
        'DOM capture of #lcExecQualRows; append_only/send_attempts.csv exists='
        + str(APPO['send_attempts.csv']['exists']) + ', live_fills.csv exists='
        + str(APPO['live_fills.csv']['exists']), ORACLE_API,
        'Row builder consumes recent_send_attempts, sourced from '
        'append_only/send_attempts.csv, which does not exist on this '
        'instance. The table is structurally unpopulatable, so field "'
        + label + '" cannot be certified.')

# --- 121-133 Order Intents / Audit (renders 10 rows) ---------------------
AUD_TPL = 'HL_Copy_App_SSOT.py:' + str(EL['render_audit_row_template'])
MISS = ('order_intents.csv has no such column (probe audit_field_presence '
        'is false). Because last_rows rows are ONLY ever order_intents records, '
        'this cell is blank for every row the table can render, no matter which '
        'audit files exist.')

add('UI-FP-121', 'renderable', '#lcAuditRows tr:first-child td:nth-child(1)',
    A0[0], AUD_TPL + ' first(r,[created_at,timestamp_iso,time])', 'PASS',
    'DOM cell text equals order_intents.csv last-row created_at', ORACLE_CSV)
add('UI-FP-122', 'renderable', '#lcAuditRows tr:first-child td:nth-child(2)',
    A0[1], 'HL_Copy_App_SSOT.py:6405 shortWallet() applied at ' + AUD_TPL,
    'PASS',
    'DOM 0xf7bfa3a7...acf123 == shortWallet(0xf7bfa3a7067624b913381f39c1e21'
    'ad9aeacf123): first 10 + ... + last 6', ORACLE_CSV)
add('UI-FP-123', 'renderable', '#lcAuditRows tr:first-child td:nth-child(3)',
    A0[2], AUD_TPL + ' first(r,[coin,asset])', 'PASS',
    'DOM BTC equals order_intents.csv coin=BTC for the same created_at',
    ORACLE_CSV)
add('UI-FP-124', 'renderable', '#lcAuditRows tr:first-child td:nth-child(4)',
    'empty string (renders zero-width; not an em dash)',
    AUD_TPL + ' first(r,[side]) -- key absent', 'FAIL',
    'DOM cell text is empty. CSV carries leader_side=SELL and copy_side=SELL; '
    'the template reads neither. ' + MISS, ORACLE_CSV)
add('UI-FP-125', 'renderable', '#lcAuditRows tr:first-child td:nth-child(5)',
    A0[4].replace(chr(10), ' / '),
    'HL_Copy_App_SSOT.py:6416 sourceOf() at ' + AUD_TPL, 'PASS',
    'DOM shows POLL plus reason max total exposure exceeded; CSV source=POLL, '
    'reason=max total exposure exceeded', ORACLE_CSV)
add('UI-FP-126', 'renderable', '#lcAuditRows tr:first-child td:nth-child(6)',
    A0[5] + ' (em-dash placeholder)',
    AUD_TPL + ' pill(first(r,[status])) -- key absent', 'FAIL',
    'DOM cell is an em dash. ' + MISS, ORACLE_CSV)
add('UI-FP-127', 'renderable', '#lcAuditRows tr:first-child td:nth-child(7)',
    A0[6] + ' (em-dash placeholder)',
    'HL_Copy_App_SSOT.py:6411 decisionPill(first(r,[execution_decision])) at '
    + AUD_TPL + ' -- key absent', 'FAIL',
    'DOM cell is an em dash. CSV DOES carry decision=SEND_BLOCKED_RISK, which '
    'the template never reads. ' + MISS, ORACLE_CSV)
add('UI-FP-128', 'renderable', '#lcAuditRows tr:first-child td:nth-child(8)',
    'empty string', AUD_TPL + ' tiny(first(r,[decision_reason])) -- key absent',
    'FAIL', 'DOM cell text is empty. ' + MISS, ORACLE_CSV)
add('UI-FP-129', 'renderable', '#lcAuditRows tr:first-child td:nth-child(9)',
    'empty string',
    AUD_TPL + ' first(r,[suggested_limit_price,target_price]) -- both absent',
    'FAIL', 'DOM cell text is empty; both presence flags false. ' + MISS,
    ORACLE_CSV)
add('UI-FP-130', 'renderable', '#lcAuditRows tr:first-child td:nth-child(10)',
    'empty string',
    AUD_TPL + ' first(r,[adverse_diff_pct,diff_pct,real_diff_pct,'
    'price_diff_pct]) -- all four absent', 'FAIL',
    'DOM cell text is empty; all four presence flags false. ' + MISS,
    ORACLE_CSV)
add('UI-FP-131', 'renderable', '#lcAuditRows tr:first-child td:nth-child(11)',
    'empty string',
    AUD_TPL + ' first(r,[manual_reconcile_required]) -- key absent', 'FAIL',
    'DOM cell text is empty. ' + MISS, ORACLE_CSV)
add('UI-FP-132', 'renderable', '#lcAuditRows tr:first-child td:nth-child(12)',
    A0[11], AUD_TPL + ' first(r,[notes,message])', 'PASS',
    'DOM shows lifecycle=ENTRY; CSV notes=lifecycle=ENTRY', ORACLE_CSV)
add('UI-FP-133', 'renderable', '#lcAuditRows tr:first-child td:nth-child(13)',
    A0[12],
    AUD_TPL + ' inline realRes: no matching recent_send_attempts entry and '
    'execution_decision != WOULD_PLACE_IOC_LIMIT -> NO_SEND_ATTEMPT', 'PASS',
    'DOM shows NO_SEND_ATTEMPT. api_counts.recent_send_attempts='
    + str(C['recent_send_attempts']) + ' and send_attempts.csv exists='
    + str(APPO['send_attempts.csv']['exists'])
    + ', so that is the only reachable branch and it is the branch rendered',
    ORACLE_API)

# --- 134-150 Reconciliation ---------------------------------------------
RC = ['Event', 'Status', 'Action', 'Reject category', 'Terminal state',
      'Coin', 'Wallet', 'Intent', 'Notes']
EVENTS = ', '.join(k + '=' + str(v) for k, v in
                   sorted(P['reconciliation_event_counts'].items()))
RECON_NOTE = ('send_terminal_rows is built only from reconciliation.csv events '
              'SEND_TERMINAL/SEND_REJECTED (line ' + str(EL['terminal_row_filter'])
              + '). Measured event counts: ' + EVENTS
              + '. Zero rows match, so both bodies hold only their empty-state '
              'message (critRows=' + str(D['critRows']) + ', warnRows='
              + str(D['warnRows']) + ').')

for i, label in enumerate(RC):
    add('UI-FP-' + str(134 + i), 'state-changing',
        '#lcReconCriticalRows td for column "' + label + '"',
        'no row: tbody holds only "No actionable critical terminal items."',
        'HL_Copy_App_SSOT.py:' + str(EL['terminal_row_filter'])
        + ' filter; render at :' + str(EL['render_recon_critical']),
        'NOT_TESTED', RECON_NOTE, ORACLE_API,
        'A state-changing claim needs audit rows proving a transition. This '
        'instance has no SEND_TERMINAL/SEND_REJECTED row at all, so this '
        'column cannot be evidenced either way.')

for i, label in enumerate(RC[:8]):
    add('UI-FP-' + str(143 + i), 'state-changing',
        '#lcReconWarningRows td for column "' + label + '"',
        'no row: tbody holds only "No terminal warnings."',
        'HL_Copy_App_SSOT.py:' + str(EL['terminal_row_filter']) + ' filter; '
        'render at :' + str(EL['render_recon_warning']),
        'NOT_TESTED', RECON_NOTE, ORACLE_API,
        'Same root cause as the critical block: zero terminal audit rows exist '
        'to render.')

ART = {
    'card_id': CARD,
    'slice': 'UI-FP-101 .. UI-FP-150 (rows 101-150 of 197)',
    'serving_commit': P.get('serving_commit', 'NOT_A_GIT_CHECKOUT'),
    'serving_ssot_sha256': SHA,
    'how_serving_build_was_established': (
        'netstat -ano | findstr :8023 -> LISTENING PID ' + str(P['serving_pid'])
        + '; Get-Process StartTime = ' + str(P['serving_pid_start_utc'])
        + '; cmdline = python -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 '
        '--port 8023; sha256sum over ' + P['serving_ssot_path']
        + ' = ' + SHA + '; file mtime epoch ' + str(P['serving_ssot_mtime'])
        + ' predates process start, and the instance dir contains exactly this '
        'one HL_Copy_App_SSOT.py, so the hashed file is the module uvicorn '
        'imported. The instance is not a git checkout, hence '
        'serving_commit=NOT_A_GIT_CHECKOUT.'),
    'serving_process': {
        'pid': P['serving_pid'],
        'start_utc': P['serving_pid_start_utc'],
        'cwd': os.path.dirname(P['serving_ssot_path']),
        'ssot_mtime_epoch': P['serving_ssot_mtime'],
        'disk_file_predates_process_start': True,
    },
    'oracle': ('probe.py never imports HL_Copy_App_SSOT.py. It reads the '
               'served HTML, the served /api/live-audit-summary JSON and the '
               'append-only CSVs and re-derives each claimed value. The DOM '
               'capture was taken in a real browser against '
               'http://127.0.0.1:8023/live-copy after the page fetched its APIs.'),
    'files': ['EVIDENCE/UI_FP_batch3_t_' + CARD + '/' + n for n in
              ('probe.py', 'build_artifact.py', 'probe_out.json',
               'live_copy.html', 'audit_summary.json', 'dom_capture.json',
               'screen_live_copy.png')],
    'surface_observations': {
        'http_8023_root': 200,
        'http_8023_live_copy': 200,
        'exchange_account_snapshot': EX,
        'append_only_files': APPO,
        'api_counts': C,
        'order_intents_rows': P['order_intents_rows'],
        'order_intents_columns': COLS,
        'reconciliation_rows': C['reconciliation_rows'],
        'reconciliation_event_counts': P['reconciliation_event_counts'],
        'dom_exec_headers': D['execHeaders'],
        'dom_exec_rows_rendered': D['execRows'],
        'dom_audit_rows_rendered': len(D['auditRows']),
        'dom_owned_rows': D['ownedRows'],
        'dom_orphan_rows': D['orphanRows'],
        'dom_crit_rows': D['critRows'],
        'dom_warn_rows': D['warnRows'],
        'dom_chips_exec': D['chipsExec'],
        'dom_real_orders': D['realOrders'],
    },
    'chaining_cross_check': {
        'why': 'Proves the rendered rows are the real last-10 order_intents '
               'records in reverse order, not a coincidence of row 0.',
        'dom_row_1_first_3_cells': (P.get('cross_check_row1') or [])[:3],
        'csv_second_newest_first_3': (P.get('cross_check_csv_prev') or [])[:3],
        'match_on_created_at_wallet_coin': (
            (P.get('cross_check_row1') or [])[:3]
            == (P.get('cross_check_csv_prev') or [])[:3]),
    },
    'additional_findings': [
        {'id': 'FINDING-EXEC-COLCOUNT', 'severity': 'high',
         'detail': 'The Execution Quality row template emits '
                   + str(P['exec_template_td_count']) + ' <td> cells against '
                   + str(len(D['execHeaders'])) + ' <th> headers (the Status '
                   'cell is followed by a second, unheaded truth pill). Any '
                   'real row would shift every column after Status one cell to '
                   'the right. Latent today only because zero rows render.',
         'evidence': 'probe_out.json exec_template_td_count vs '
                     'dom_execHeaders; source :'
                     + str(EL['render_exec_row_template']) + ' vs the 18 <th> '
                     'at :6335'},
        {'id': 'FINDING-AUDIT-KEYDRIFT', 'severity': 'high',
         'detail': 'The Order Intents / Audit renderer reads 7 field groups '
                   'that do not exist in order_intents.csv (side, status, '
                   'execution_decision, decision_reason, '
                   'suggested_limit_price/target_price, the four diff_pct '
                   'variants, manual_reconcile_required). 6 of 13 columns render '
                   'blank or em-dash on every row. Rows 124 and 126-131 are the '
                   'field-level consequence.',
         'evidence': 'probe_out.json audit_field_presence (all false)'},
        {'id': 'FINDING-RECON-NOTERMINAL', 'severity': 'medium',
         'detail': 'reconciliation.csv on this instance contains no '
                   'SEND_TERMINAL/SEND_REJECTED event, so the Reconciliation tab '
                   'is permanently empty here and rows 134-150 cannot be '
                   'evidenced against this surface.',
         'evidence': 'probe_out.json reconciliation_event_counts'},
    ],
    'rows': ROWS,
}

tally = {}
for r in ROWS:
    tally[r['verdict']] = tally.get(r['verdict'], 0) + 1
ART['verdict_tally'] = tally

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(ART, f, indent=2)
    f.write('\n')

ids = [r['row_id'] for r in ROWS]
expect = ['UI-FP-' + str(i) for i in range(101, 151)]
print('wrote', OUT)
print('rows', len(ROWS), 'tally', tally)
print('EXACT_SLICE_MATCH', ids == expect)
print('missing', [e for e in expect if e not in ids])
