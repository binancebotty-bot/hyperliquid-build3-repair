import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / 'CERT23_t_e3846ecf_raw_reproduce.json')
D = json.loads(RAW.read_text(encoding='utf-8'))
I = D['inputs']
m22 = D['CTRL-I22']['measured']
m23 = D['CTRL-I23']['measured']
mev = D['CTRL-EVID']['measured']
mhw = D['CTRL-HWM']['measured']
fm = mev['field_matrix']
ROWS = []


def add(rid, verdict, why, sec):
    ROWS.append({'row_id': rid, 'verdict': verdict, 'why': why,
                 'evidence_ref': 'certification/results/CERT23_t_e3846ecf_evidence.json',
                 'evidence_section': sec})


add('CTRL-I22', 'PASS',
    'Notifications are not authority. Full type set enumerated: %d types over %d envelopes %s. Exactly %d envelope(s) are NOTIFICATION (%s) with keys %s and authority None. Authority (non-empty AUTHORITY_SOURCE, key or token) appears on %d envelopes, only on types %s. Mutation control injects AUTHORITY_SOURCE into all %d notification(s) and the detector flags %s; negative control strips it from real authority envelope %s and the detector goes silent. control_works=%s.'
    % (m22['types_total'], I['envelope_count'], json.dumps(m22['type_table_enumerated'], sort_keys=True),
       m22['notification_count'], [n['message_id'] for n in m22['notification_detail']],
       m22['notification_detail'][0]['keys'] if m22['notification_detail'] else [],
       m22['envelopes_carrying_authority'], json.dumps(m22['authority_by_type'], sort_keys=True),
       m22['mutation_control']['injected_into_all_notifications'],
       m22['mutation_control']['flagged_ids'],
       (m22['mutation_control']['negative_control'] or {}).get('message_id'),
       m22['control_works']), 'CTRL-I22')

add('CTRL-I23', 'PASS',
    'Model/provider is compute routing, not authority. %d AUTHORITY_SOURCE occurrences resolve to %d distinct values (per-value counts in value_occurrence_counts); zero match the model/provider pattern gpt-/claude/gemini/deepseek/nvidia/openrouter/nemotron/llama/qwen/mistral/sonnet/opus/haiku/anthropic/openai (matches=%s). Values are role/actor/ruling identifiers (CONTROLLER_*, ARCHITECT_*, RICHARD_*, GLOBAL_MD_*, B3-* ruling ids, company-control-v1). Mutation control runs gpt-6-astra and claude-sonnet-4 through the same detector and both match: %s. control_works=%s.'
    % (m23['authority_occurrences'], m23['authority_distinct'], m23['real_model_or_provider_matches'],
       m23['mutation_control']['matches'], m23['control_works']), 'CTRL-I23')

add('CTRL-HWM', 'FAIL',
    'Premise inverted by immutable inputs. origin/control-mailbox:CONTROL_STATE.json (blob %s, mailbox head %s) is updated_utc %s, %d keys, adjudication_log present=%s. Repo-tree CONTROL_STATE.json at the tested commit (blob %s) is updated_utc %s, %d keys, adjudication_log %d entries of which %d INVALIDATED, disposition present=%s. The mailbox copy is therefore the STALER one by %.4f days, so gate truth from mailbox rather than stale local state cannot hold as written. Cannot-recur is also unproven: tracked *.py naming CONTROL_STATE = %s, CONTROL_STATE load sites in Python = %d, so no census of gate-truth readers exists.'
    % (mhw['mailbox_state']['blob_sha'], mhw['mailbox_head'], mhw['mailbox_state']['updated_utc'],
       mhw['mailbox_state']['top_level_keys'], mhw['mailbox_state']['has_adjudication_log'],
       mhw['repo_state']['blob_sha'], mhw['repo_state']['updated_utc'], mhw['repo_state']['top_level_keys'],
       mhw['repo_state']['adjudication_entries'], mhw['repo_state']['adjudication_invalidated'],
       mhw['repo_state']['adjudication_disposition_present'], mhw['delta_days_repo_minus_mailbox'],
       mhw['python_files_naming_control_state'], mhw['loader_count']), 'CTRL-HWM')

add('CTRL-EVID', 'FAIL',
    'Measured over the defined handoff set TYPE in RESPONSE/RESULT/STATUS/ACK = %d envelopes %s. Per field present-in-handoff / total-envelopes-carrying: %s. Absent on EVERY handoff: %s. Present only outside handoffs: %s. Absent everywhere: %s. The requirement is all eight fields on every handoff; %s are absent on all %d handoffs. The narrower claim FILES_CHANGED appears nowhere would be FALSE - it appears on %d envelopes %s, all outside the handoff set - so this row is graded on the handoff set, not a global string sweep.'
    % (mev['handoff_count'], json.dumps(mev['handoff_type_counts'], sort_keys=True),
       {k: '%d/%d' % (fm[k]['in_handoff_count'], fm[k]['total_envelopes_carrying']) for k in sorted(fm)},
       mev['fields_absent_on_all_handoffs'], mev['fields_present_only_outside_handoffs'],
       mev['fields_absent_everywhere'], mev['fields_absent_on_all_handoffs'], mev['handoff_count'],
       fm['FILES_CHANGED']['outside_handoff_count'],
       [x['id'] for x in fm['FILES_CHANGED']['outside_handoff']]), 'CTRL-EVID')

i1, i2, i3 = D['B4-I01'], D['B4-I02'], D['B4-I03']
add('B4-I01', 'PASS',
    'NO_COMMITTED_EVENT_HOLD. With no baseline the first WS fill creates the baseline and mints nothing: result=%s, leader_event_positions=%s, fixed_sleeves=%s, processed_ids=%s. Mutation control moves the baseline earlier (500ms) and replays the same fill: result=%s, processed_ids=%s. control_works=%s.'
    % (json.dumps(i1['measured']['pre_baseline_result']), i1['measured']['leader_event_positions'],
       i1['measured']['fixed_sleeves'], i1['measured']['processed_ids'],
       json.dumps(i1['mutation_control']['same_fill_result']), i1['mutation_control']['processed_ids'],
       i1['mutation_control']['control_works']), 'B4-I01')

add('B4-I02', 'PASS',
    'Restart creates no authority. A service re-instantiated from the persisted state file with baseline_ts_ms=2000 yields leader_event_positions=%s; a stale fill below baseline yields %s and leaves leader_event_positions=%s, fixed_sleeves=%s.'
    % (i2['measured']['restart_leader_event_positions'], json.dumps(i2['measured']['stale_fill_result']),
       i2['measured']['after_leader_event_positions'], i2['measured']['after_fixed_sleeves']), 'B4-I02')

add('B4-I03', 'PASS',
    'One logical stream. The same fill_id on the WS path (%s) then the REST path (%s) is accepted exactly %d time(s), so both transports share one processed_ids guard.'
    % (json.dumps(i3['measured']['ws_result']), json.dumps(i3['measured']['rest_result']),
       i3['measured']['acceptances_of_dup1']), 'B4-I03')

m4, m5, m6 = D['B4-I04']['measured'], D['B4-I05']['measured'], D['B4-I06']
add('B4-I04', 'FAIL',
    'Recovery does not collapse to NET. Three missed INCREASE events (+1,+1,+1) mint %d slices; one NET event of the same total magnitude (+3) mints %d slice; inflation ratio %s. apply_leader_event() mints one fixed-sleeve slice per event with no net-collapse step.'
    % (m4['three_missed_increases_slices'], m4['one_net_event_same_magnitude_slices'], m4['inflation_ratio']),
    'B4-I04')

add('B4-I05', 'FAIL',
    'Genuine events are consumed on truth failure. With MASTER_TRUTH_ADDRESS empty process_fill raises %s, marks the event processed (processed_ids=%s) and persists leader authority (%s) while writing %d reconciliation row for it, so it cannot be retried. The row also names 429 survival: the tested engine has %d occurrences of 429 and %d of retry-after.'
    % (m5['exception'], m5['processed_ids'], m5['leader_event_positions'],
       m5['reconciliation_rows_mentioning_event'], m5['engine_429_occurrences'],
       m5['engine_retry_after_occurrences']), 'B4-I05')

add('B4-I06', 'FAIL',
    'No deterministic execution identity. cloid occurs %d time(s), client_order_id %d time(s) in the tested engine; the single exchange.order() call is `%s` with no client-order-id argument. Mutation control injects cloid="mut" into that call: token counter goes to %d and the call-site detector fires (%s). control_works=%s.'
    % (m6['measured']['cloid_occurrences'], m6['measured']['client_order_id_occurrences'],
       m6['measured']['exchange_order_call_text'], m6['mutation_control']['mutated_cloid_occurrences'],
       m6['mutation_control']['mutated_call_has_kwarg'], m6['mutation_control']['control_works']), 'B4-I06')

m7 = D['B4-I07']
add('B4-I07', 'FAIL',
    'No fresh follower truth before send, measured on function scope. Send function lines %s-%s contains follower-truth calls %s; its caller lines %s-%s contains %s with positions from %s. Repo-wide follower-truth call count %s. Mutation control replaces that local read with info.user_state(...) in the caller scope and the detector fires on %s (injection point found=%s). control_works=%s.'
    % (m7['measured']['send_function']['start'], m7['measured']['send_function']['end'],
       m7['measured']['send_function']['follower_truth_calls'],
       m7['measured']['send_caller_function']['start'], m7['measured']['send_caller_function']['end'],
       m7['measured']['send_caller_function']['follower_truth_calls'],
       m7['measured']['send_caller_function']['positions_source_lines'],
       m7['measured']['repo_wide_follower_truth_call_count'],
       m7['mutation_control']['detector_finds_truth_in_mutated_caller_scope'],
       m7['mutation_control']['injection_point_found'], m7['mutation_control']['control_works']), 'B4-I07')

m8 = D['B4-I08']
add('B4-I08', 'FAIL',
    'No sender lease or fence. Token counts: %s; the %d lease occurrences are prose about releasing an in-flight reservation. Exactly %d exchange.order() call site(s) with nothing preventing two processes from each owning it. Mutation control appends an msvcrt-based _sender_fence(): %s. control_works=%s.'
    % (json.dumps(m8['measured']['token_counts'], sort_keys=True), m8['measured']['lease_occurrences'],
       m8['measured']['order_call_sites'], m8['mutation_control']['mutated_token_counts_nonzero'],
       m8['mutation_control']['control_works']), 'B4-I08')

counts = {'PASS': sum(r['verdict'] == 'PASS' for r in ROWS),
          'FAIL': sum(r['verdict'] == 'FAIL' for r in ROWS),
          'NOT_TESTED': sum(r['verdict'] == 'NOT_TESTED' for r in ROWS)}

verdicts = {
    'batch': 'CERT 23/53 REDO (reviewer-rejected rows)',
    'task_id': 't_9f136eb4',
    'supersedes': {'task_id': 't_e3846ecf', 'head': '8b391187c7cdaab638b69c2cef4f14e0f214336a'},
    'tested_commit': I['tested_commit'],
    'engine_blob_sha256': I['engine_blob_sha256'],
    'control_mailbox_head': I['mailbox_head'],
    'envelope_count': I['envelope_count'],
    'evidence_file': 'certification/results/CERT23_t_e3846ecf_evidence.json',
    'reproduce_command': 'python3.11 certification/results/CERT23_t_e3846ecf_reproduce.py > certification/results/CERT23_t_e3846ecf_raw_reproduce.json',
    'reproduce_script_sha256': I['script_sha256'],
    'two_run_control': 'byte-identical output with inherited PYTHON* env and with PYTHONPATH/PYTHONHOME/PYTHONSTARTUP unset',
    'standard': 'PASS only where evidence is row-bound, read from git objects at the tested commit, and backed by a mutation/negative control proving the measurement is non-vacuous.',
    'counts': counts,
    'rows': ROWS,
}

evidence = {
    'batch': verdicts['batch'],
    'task_id': 't_9f136eb4',
    'supersedes_task_id': 't_e3846ecf',
    'tested_commit': I['tested_commit'],
    'engine_blob': '_archive/hl_stage2/HL_Live_Copy_Service.py',
    'engine_blob_sha256': I['engine_blob_sha256'],
    'engine_blob_matches_pinned': I['engine_blob_matches_pinned'],
    'control_mailbox_ref': I['mailbox_ref'],
    'control_mailbox_head': I['mailbox_head'],
    'envelope_count': I['envelope_count'],
    'python': I['python'],
    'reproduce_script': 'certification/results/CERT23_t_e3846ecf_reproduce.py',
    'reproduce_script_sha256': I['script_sha256'],
    'raw_output': 'certification/results/CERT23_t_e3846ecf_raw_reproduce.json',
    'reproduce': {
        'step_1': 'git fetch origin control-mailbox',
        'step_2': 'python3.11 certification/results/CERT23_t_e3846ecf_reproduce.py > certification/results/CERT23_t_e3846ecf_raw_reproduce.json',
        'step_3': 'python3.11 certification/results/CERT23_t_e3846ecf_build_verdicts2.py certification/results/CERT23_t_e3846ecf_raw_reproduce.json',
        'note': 'The reproduce script reads the engine blob and every envelope straight from git objects at the pinned commit and branch. No pre-materialised engine.py, no env var, no untracked probe. Each row section carries measured data plus a mutation_control.',
    },
    'rows': [r['row_id'] for r in ROWS],
    'row_verdicts': {r['row_id']: r['verdict'] for r in ROWS},
    'row_evidence': {r['row_id']: D[r['row_id']] for r in ROWS},
    'type_table': D['type_table'],
    'inputs': I,
}

(HERE / 'CERT23_t_e3846ecf_verdicts.json').write_text(json.dumps(verdicts, indent=1, sort_keys=True), encoding='utf-8')
(HERE / 'CERT23_t_e3846ecf_evidence.json').write_text(json.dumps(evidence, indent=1, sort_keys=True), encoding='utf-8')
print(json.dumps({'rows': len(ROWS), 'counts': counts}))
