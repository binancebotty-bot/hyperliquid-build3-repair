import json
from pathlib import Path

REG = 'origin/cert/local-main-b142cf8'
TESTED = 'b142cf88d389e791160f691aac3d936852b99975'
EVID = 'certification/results/CERT23_t_e3846ecf_evidence.json'

rows = [
 ('CTRL-I22', 'PASS',
  'Notification envelope carries no authority. Of 102 committed envelopes on origin/control-mailbox exactly 1 is TYPE=NOTIFICATION (B3-C2H-INGRESS-RESULT-1) and its AUTHORITY_SOURCE is null; AUTHORITY_SOURCE appears only on DIRECTIVE (37), ESCALATION (1) and RESULT (1). A notification carrying an authority source would flip this row and no other.'),
 ('CTRL-I23', 'PASS',
  'Authority provenance is never a model or provider name. All 31 distinct AUTHORITY_SOURCE values are role/actor/ruling identifiers (CONTROLLER_*, ARCHITECT_*, RICHARD_*, company-control-v1); zero match gpt-/claude/gemini/deepseek/nvidia/openrouter/nemotron/llama/qwen. The 16 envelopes that mention model/provider refer to account_net_provider (data provider) or model_copy_notional (sizing), none is an AUTHORITY_SOURCE.'),
 ('CTRL-GATE0', 'PASS',
  'Gate 0 four-leg acceptance is committed on origin/control-mailbox as B3-C2A-GATE0-PASS-1 (TYPE=GATE_STATUS_TRANSITION) naming CONTROLLER_TO_HERMES=PASS, HERMES_TO_CONTROLLER=PASS, CONTROLLER_TO_ARCHITECT=PASS, ARCHITECT_TO_CONTROLLER=PASS, BINDING_AUTHORITY=PASS, RESTART_REPLAY and an INSPECTED_MAIN_COMMIT; CONTROL_STATE.transport_certification.current_status=PASS with REST_API_CALLS_FOR_TRANSPORT=0. Dropping any one leg fails this row specifically.'),
 ('CTRL-BIND', 'FAIL',
  'CONTROL_STATE.json and CONTROL_CONTRACT.json do NOT agree, for either role. target_role_bindings controller=6ac8e179-932c-83ed-b9ca-1bdc5c976d5d (ACTIVE v2) vs CONTROL_STATE.bindings controller=6ac6427b-8df0-83eb-beb8-3b6e8796d1e1 (ACTIVE); architect contract=6ac8e151-e9f4-83eb-86d0-ba5b917ba09a vs state=6ac680c7-6d84-83eb-8c7d-d3706cea33fc. bindings.controller_uuid_dispute.state=UNRESOLVED_REQUIRES_ADJUDICATION and the state-side architect UUID appears in CONTROL_CONTRACT.retired_binding_uuids. Exactly-one-canonical-binding is not met.'),
 ('CTRL-HWM', 'FAIL',
  'The premise is inverted: origin/control-mailbox:CONTROL_STATE.json is updated_utc 2026-10-07T18:55:00Z while the repo-tree CONTROL_STATE.json is 2026-10-14T14:12:00Z, so the mailbox copy is the STALER one by 7 days. CONTROL_STATE.adjudication_log contains 1 INVALIDATED entry whose root_cause is verbatim "Sourced from stale local CONTROL_STATE.json instead of origin/control-mailbox", and adjudication_log_disposition.residual_risk states any surviving component reading local CONTROL_STATE will reproduce it. recurring_cause_eliminated rests only on deleting one scheduled task, so "cannot recur" is asserted, not proven; no census of gate-truth readers exists.'),
 ('CTRL-EVID', 'FAIL',
  'Measured over the 12 handoff-type envelopes (RESPONSE/RESULT/STATUS/ACK): TASK_ID 11/12, COMMIT_SHA 0/12, FILES_CHANGED 0/12, LOC 12/12, TESTS 5/12, OUTPUT 0/12, UNCERTAINTY 0/12, STAND_DOWN_REQUEST 0/12. Over all 102 envelopes FILES_CHANGED appears 3 times and OUTPUT 0 times. Five of the eight required fields are effectively absent, so "every handoff carries" is false.'),
 ('CTRL-ESC', 'PASS',
  'Tripwires are defined (ARCHITECTURE.md 74-77: production LOC >260, second process, new runtime dependency) and were exercised on real scope: B3-C2A-G2-SCOPE-ESCALATION-2 emits ARCHITECT_REVIEW_REQUIRED citing "+274 / -18" against "authorised cap <=260 genuinely new production LOC", and B3-C2A-G3-AUTHORITY-SCOPE-ESCALATION-1 emits ARCHITECT_REVIEW_REQUIRED citing production files = 2 / 2. Each is bound to its own scope evidence; a missing tripwire would appear as a landed over-budget commit with no escalation.'),
 ('B4-I01', 'PASS',
  'Executed engine.py at the tested blob (sha256 e2f04fa8..., byte-identical at fa9d9f5 and b142cf8). Pre-baseline fill via process_ws_fill -> reason=BASELINE_CREATED_FROM_WS, processed=False, leader_event_positions={}, fixed_sleeves={}, processed_ids=[]. Mutation control (same fill, baseline moved EARLIER to 500ms) -> processed=True, processed_ids=[f1], proving the predicate is non-vacuous.'),
 ('B4-I02', 'PASS',
  'Restart probe: service re-instantiated from the persisted SERVICE_STATE_FILE with baseline_ts_ms=2000 yields leader_event_positions={} (startup creates no authority). A stale/replayed fill below the baseline yields reason=WS_BEFORE_BASELINE, processed=False, and the ledger stays {}. A restart or catch-up that seeded authority would show a non-empty ledger here.'),
 ('B4-I03', 'PASS',
  'One logical stream: the same genuine fill_id delivered first on the WS path (process_ws_fill -> processed=True, LIVE_WS_DETECTED) and then on the REST/poll path (process_fill) is accepted exactly once - processed_count for that fill_id is 1 and the second path short-circuits on the shared processed_ids guard. A second acceptance would make it 2.'),
 ('B4-I04', 'FAIL',
  'Recovery does not collapse to the latest NET state. Driving the event-authorised sleeve with three missed INCREASE events (signed +1,+1,+1) mints 3 slices; driving it with one NET event of the same total magnitude (signed +3) mints 1 slice, i.e. ~3x the attributed sleeve for the replayed case. apply_leader_event() mints one fixed-sleeve slice per event with no net-collapse step, so replaying several missed events reproduces stale missed trades one-by-one - exactly what I04 forbids.'),
 ('B4-I05', 'FAIL',
  'Genuine events are consumed on truth failure. With MASTER truth unconfigured (ACCOUNT_NET_TRUTH_UNAVAILABLE) process_fill marks the event processed (processed_ids=[g1]) and persists leader authority (leader_event_positions[wallet::BTC]=1.0) while the reconciliation row is written blocked - the event cannot be retried. The row also names 429 survival, and there are ZERO occurrences of "429" (and no Retry-After handling) in HL_Live_Copy_Service.py or exchange_truth.py, so the transient-rate-limit path named by test_live_fill_truth_429_fail_closed.py does not exist.'),
 ('B4-I06', 'FAIL',
  'No deterministic execution identity. "cloid" and "client_order_id" occur 0 times in HL_Live_Copy_Service.py (the single repo-wide cloid hit is HL_Copy_App_SSOT.py:2531, a read of a row field, not a mint site). exchange.order() is called with (coin, is_buy, size, price, tif, reduce_only) and no client order id, so the only identity is the logical fill_id dedupe. Exactly-once across an ambiguous submission therefore rests entirely on post-hoc MASTER reconciliation, not on an exchange-dedupable CLOID.'),
 ('B4-I07', 'FAIL',
  'No fresh follower truth immediately before send. In the 2500 characters preceding the single exchange.order() call site there is no clearinghouseState / user_state / sub_accounts call; the only pre-send read is master_net_snapshot() (MASTER account net, documented as "reconciliation evidence, never order authority") and position_before comes from the local manual_live_positions.json. The send path signs and submits without re-reading follower exchange truth.'),
 ('B4-I08', 'FAIL',
  'No sender lease or fence exists. Counts in HL_Live_Copy_Service.py: fence 0, msvcrt 0, fcntl 0, CreateMutex 0, lock_file 0, lockfile 0 (the 4 "lease" hits are prose about releasing an in-flight reservation, not a sender lease). There is exactly 1 exchange.order() call site, but nothing prevents two processes from each owning it, so "exactly one canonical sender lease/fence" is unenforced.'),
]

out = {
 'batch': 'CERT 23/53',
 'task_id': 't_e3846ecf',
 'register_of_record': REG + ':certification/certification_matrix.json',
 'register_commit': TESTED,
 'tested_commit': TESTED,
 'engine_blob_sha256': 'e2f04fa826958c73169bae2490a6ebb3ebfd09d9aecda513ef0d7bd8a10ec2c6',
 'evidence_file': EVID,
 'standard': 'PASS only where evidence is ROW-BOUND and non-vacuous; shared sweeps and auto-named single checks with empty detail are not passes.',
 'counts': {'PASS': 0, 'FAIL': 0, 'NOT_TESTED': 0},
 'rows': [],
}
for rid, verdict, why in rows:
    out['rows'].append({'row_id': rid, 'verdict': verdict, 'evidence_ref': EVID, 'tested_commit': TESTED, 'why': why})
    out['counts'][verdict] += 1

Path('CERT23_t_e3846ecf_verdicts.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
print(json.dumps(out['counts']))
print('rows', len(out['rows']))
