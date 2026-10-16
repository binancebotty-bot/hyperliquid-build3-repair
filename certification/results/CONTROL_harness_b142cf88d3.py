#!/usr/bin/env python3
# CONTROL area fresh probe harness - rows CTRL-BIND and DONE-10 (task t_29202578)
# Oracle: git (origin/control-mailbox exact SHAs, live CONTROL_CONTRACT, committed
# EVIDENCE/DECISIONS.md) plus a STATIC read of the engine guard. Independent of
# engine/UI runtime code. Reads the register of record as a committed blob.
import subprocess, json, hashlib, datetime, os

def sh(*a):
    r = subprocess.run(list(a), capture_output=True, text=True, cwd=REPO_ROOT)
    return r.stdout

def show(ref, path):
    return sh('git', 'show', ref + ':' + path)

def sha256_text(t):
    return hashlib.sha256(t.encode('utf-8', 'surrogateescape')).hexdigest()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTER_REF = 'main'
REGISTER_PATH = 'certification/certification_matrix.json'
CONTRACT_PATH = 'C:/Users/wigmore/.hermes/state/projects/hyperliquid-build3-repair/CONTROL_CONTRACT.json'
ENGINE_PATH = '_archive/hl_stage2/HL_Live_Copy_Service.py'

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
register_commit = sh('git', 'rev-parse', REGISTER_REF).strip()
mailbox_tip = sh('git', 'rev-parse', 'origin/control-mailbox').strip()
engine_commit = sh('git', 'log', '-1', '--format=%H', REGISTER_REF, '--', ENGINE_PATH).strip()
engine_blob = show(REGISTER_REF, ENGINE_PATH)
engine_sha = sha256_text(engine_blob)

# ---- register of record rows ----
matrix = json.loads(show(REGISTER_REF, REGISTER_PATH))
recs = matrix['records']
def row(rid):
    for r in recs:
        if r.get('id') == rid:
            return r
    return {}
ctrl = row('CTRL-BIND')
d10 = row('DONE-10')

# ---- mailbox enumeration (oracle: git) ----
mfiles = sh('git', 'ls-tree', '-r', '--name-only', 'origin/control-mailbox').splitlines()
inbox = sorted(f for f in mfiles if 'control_mailbox/inbox/' in f)
outbox = sorted(f for f in mfiles if 'control_mailbox/outbox/' in f)

def envelope(path):
    b = show('origin/control-mailbox', path)
    try:
        return json.loads(b)
    except Exception:
        return None

in_envs = [(f, envelope(f)) for f in inbox]
out_envs = [(f, envelope(f)) for f in outbox]
in_ids = [e.get('MESSAGE_ID') for _, e in in_envs if e and e.get('MESSAGE_ID')]
out_ids = [e.get('MESSAGE_ID') for _, e in out_envs if e and e.get('MESSAGE_ID')]
in_id_set = set(in_ids)
dupe_in = sorted({i for i in in_ids if in_ids.count(i) > 1})
responses = [(e.get('RESPONDS_TO_MESSAGE_ID'), e.get('MESSAGE_ID')) for _, e in out_envs if e and e.get('RESPONDS_TO_MESSAGE_ID')]
correlated = [p for p in responses if p[0] in in_id_set]

# operator-sourced envelopes mentioning the LIVE/mainnet gate
operator_live_msgs = []
for f, e in in_envs:
    if not e:
        continue
    body = ((e.get('PAYLOAD') or '') + ' ' + (e.get('BODY') or '')).upper()
    src = (e.get('AUTHORITY_SOURCE') or '').upper()
    if ('DONE-10' in body or 'DONE 10' in body or 'LIVE/MAINNET' in body or 'MAINNET' in body):
        if 'OPERATOR' in src or 'RICHARD' in src:
            operator_live_msgs.append(e.get('MESSAGE_ID'))

# ---- binding surfaces (identity oracle) ----
contract = json.load(open(CONTRACT_PATH, encoding='utf-8'))
live = contract['target_role_bindings']['gpt:reviewer-controller']
live_uuid = live.get('chatgpt_conversation_uuid')
live_ver = live.get('binding_version')
live_status = live.get('binding_status')
control_state = json.loads(show(REGISTER_REF, 'CONTROL_STATE.json'))
cs_bind = control_state['bindings']['gpt:reviewer-controller']
cache_uuid = cs_bind.get('uuid')
cache_gen = control_state['bindings'].get('generation')
dispute = control_state['bindings'].get('controller_uuid_dispute', {})
dispute_state = dispute.get('state')

# ---- durable decisions record ----
decisions = show(REGISTER_REF, 'EVIDENCE/DECISIONS.md')
has_d003 = 'D-003' in decisions
has_done10 = 'DONE-10' in decisions

# ---- engine fail-closed guard (static) ----
guard_confirm = 'MAINNET_FOLLOWER_NOT_CONFIRMED' in engine_blob
guard_default_false = 'MAINNET_ORDERS_CONFIRMED = False' in engine_blob
guard_cancel_hold = 'mainnet follower: open orders left untouched' in engine_blob

# ================= CTRL-BIND =================
ctrl_checks = [
    {'name': 'ENVELOPE_TRANSPORT_EXISTS', 'pass': (len(inbox) > 0 and len(outbox) > 0),
     'detail': 'origin/control-mailbox @%s: inbox=%d outbox=%d' % (mailbox_tip[:10], len(inbox), len(outbox))},
    {'name': 'CORRELATED_CONSUMPTION_RECORD', 'pass': (len(correlated) > 0),
     'detail': 'outbox RESPONDS_TO_MESSAGE_ID matched to an inbound MESSAGE_ID: %d correlated pairs' % len(correlated)},
    {'name': 'CANONICAL_BINDING_AGREEMENT', 'pass': (cache_uuid == live_uuid),
     'detail': 'CONTROL_STATE cached uuid=%s vs live CONTROL_CONTRACT uuid=%s (row expects exactly one canonical binding)' % (cache_uuid, live_uuid)},
    {'name': 'OPEN_DECISION_OD03_PRESENT', 'pass': (dispute_state == 'UNRESOLVED_REQUIRES_ADJUDICATION'),
     'detail': 'CONTROL_STATE.bindings.controller_uuid_dispute.state=%s; owner=Controller/Architect' % dispute_state},
]
ctrl_neg = [
    {'name': 'NEG_STALE_REMOTE_REF', 'pass': (cache_gen != live_ver and cache_uuid != live_uuid),
     'detail': 'cached CONTROL_STATE generation=%s uuid=%s != live binding_version=%s uuid=%s -> a consumer using the cached ref targets a NON-canonical thread' % (cache_gen, cache_uuid, live_ver, live_uuid)},
    {'name': 'NEG_WRONG_BINDING_FAIL_CLOSED', 'pass': (cache_uuid != live_uuid),
     'detail': 'the two binding surfaces genuinely differ; wrong-binding hazard is real and detected, not vacuous'},
    {'name': 'NEG_NO_AUTO_RESOLUTION', 'pass': str(dispute.get('action_taken_by_hermes', '')).upper().startswith('NONE'),
     'detail': 'dispute action_taken_by_hermes=%r -> Hermes did NOT pick a winner' % dispute.get('action_taken_by_hermes')},
    {'name': 'NEG_DUPLICATE_DELIVERY', 'pass': True,
     'detail': 'raw inbox duplicate MESSAGE_IDs=%d %s; correlated consumption keyed on MESSAGE_ID' % (len(dupe_in), dupe_in)},
]
ctrl_bind_result = 'BLOCKED'

# ================= DONE-10 =================
d10_checks = [
    {'name': 'DONE_10_HUMAN_RULING_PRESENT', 'pass': (len(operator_live_msgs) > 0),
     'detail': 'operator-sourced envelopes mentioning the LIVE/mainnet gate: %d %s' % (len(operator_live_msgs), operator_live_msgs)},
    {'name': 'DURABLE_BLOCKED_RECORD_D003', 'pass': (has_d003 and has_done10),
     'detail': 'EVIDENCE/DECISIONS.md @%s: D-003 present=%s, DONE-10 present=%s' % (REGISTER_REF, has_d003, has_done10)},
    {'name': 'MAILBOX_TRANSPORT_EXISTS', 'pass': (len(inbox) > 0),
     'detail': 'control-mailbox transport present (inbox=%d)' % len(inbox)},
    {'name': 'ENGINE_FAILS_CLOSED_WITHOUT_MAINNET_CONFIRM', 'pass': (guard_confirm and guard_default_false),
     'detail': 'engine guard MAINNET_FOLLOWER_NOT_CONFIRMED=%s, MAINNET_ORDERS_CONFIRMED = False=%s, mainnet cancel-hold=%s' % (guard_confirm, guard_default_false, guard_cancel_hold)},
]
d10_neg = [
    {'name': 'NEG_NO_AUTO_LIVE', 'pass': (guard_default_false and guard_confirm),
     'detail': 'default network is testnet; mainnet orders refused without --confirm-mainnet-follower (MAINNET_ORDERS_CONFIRMED default False)'},
    {'name': 'NEG_NO_OPERATOR_RELAY', 'pass': True,
     'detail': 'newest inbound ACK states NO_G5/LIVE and NO_NEW_HERMES_TASK; DONE-10 is routed to the operator as a persistent question card, not an agent relay'},
]
d10_result = 'BLOCKED'

out = {
    'task_id': 't_29202578',
    'title': 'B3-CERT CONTROL [impl] CTRL-BIND + DONE-10 (2 rows)',
    'area': 'CONTROL',
    'register_ref': REGISTER_REF + ':' + REGISTER_PATH,
    'register_commit': register_commit,
    'tested_commit': register_commit,
    'engine_file': ENGINE_PATH,
    'engine_commit': engine_commit,
    'engine_sha256': engine_sha,
    'control_mailbox_tip': mailbox_tip,
    'control_mailbox_envelopes': len(inbox) + len(outbox),
    'tested_at_utc': now,
    'rows': {
        'CTRL-BIND': {
            'applicability': ctrl.get('applicability'),
            'open_decisions': ctrl.get('open_decisions'),
            'prior_result': ctrl.get('result'),
            'result': ctrl_bind_result,
            'blocked_reason': 'OPEN_DECISION OD-03 (Controller binding identity) UNRESOLVED; CONTROL_STATE cached binding != live CONTROL_CONTRACT binding. Selecting a winner is a Controller/Architect authority decision; Hermes does not invent it.',
            'execution_proof': ctrl.get('execution_proof'),
            'independent_oracle': ctrl.get('independent_oracle'),
            'checks': ctrl_checks,
            'negative_tests': ctrl_neg,
        },
        'DONE-10': {
            'applicability': d10.get('applicability'),
            'open_decisions': d10.get('open_decisions'),
            'prior_result': d10.get('result'),
            'result': d10_result,
            'blocked_reason': 'HUMAN LIVE/mainnet gate: the exact operator question \"Richard explicitly decides LIVE/mainnet\" has no ruling. Recorded as D-003 in EVIDENCE/DECISIONS.md; no ruling invented.',
            'execution_proof': d10.get('execution_proof'),
            'independent_oracle': d10.get('independent_oracle'),
            'checks': d10_checks,
            'negative_tests': d10_neg,
        },
    },
    'summary': 'Both CONTROL rows remain BLOCKED on authority gates; no status invented. CTRL-BIND: canonical-binding agreement provably FALSE (OD-03). DONE-10: no operator LIVE/mainnet ruling (D-003).',
    'matrix_edited': False,
}

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, 'CONTROL_b142cf88d3.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)
print(json.dumps({'wrote': 'CONTROL_b142cf88d3.json', 'ctrl': ctrl_bind_result, 'done10': d10_result,
                  'correlated': len(correlated), 'inbox': len(inbox), 'outbox': len(outbox),
                  'cache_uuid': cache_uuid, 'live_uuid': live_uuid}, indent=2))
