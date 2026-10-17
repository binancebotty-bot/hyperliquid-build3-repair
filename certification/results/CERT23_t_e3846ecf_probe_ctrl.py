import json, glob, re

B = ''
fs = sorted(glob.glob(B + 'env/control_mailbox/inbox/*.json'))
ds = [(f, json.load(open(f, encoding='utf-8-sig'))) for f in fs]

print('ENVELOPES', len(ds))
print('--- authority-bearing types')
for f, d in ds:
    if d.get('TYPE') in ('NOTIFICATION', 'ACK'):
        print(' ', d.get('MESSAGE_ID'), d.get('TYPE'),
              'AUTH_SRC=', d.get('AUTHORITY_SOURCE'),
              'ACTION=', d.get('ACTION_ID'), 'DIR=', d.get('DIRECTIVE_ID'))

seqs = [d.get('SEQUENCE') for f, d in ds if isinstance(d.get('SEQUENCE'), int)]
print('SEQ count', len(seqs), 'min', min(seqs), 'max', max(seqs), 'distinct', len(set(seqs)))
print('SEQ duplicates', sorted({s for s in seqs if seqs.count(s) > 1}))

print('--- model/provider mentions')
n = 0
for f, d in ds:
    s = json.dumps(d)
    if re.search(r'model|provider', s, re.I):
        n += 1
        print(' ', d.get('MESSAGE_ID'), d.get('TYPE'),
              re.findall(r'[A-Za-z0-9_./-]{0,18}(?:model|provider)[A-Za-z0-9_./-]{0,18}', s, re.I)[:3])
print('TOTAL model/provider envelopes', n)

print('--- HWM: file-change-only evidence in envelopes')
n = 0
for f, d in ds:
    s = json.dumps(d)
    if re.search(r'FILES_CHANGED|files changed', s, re.I):
        n += 1
        print(' ', d.get('MESSAGE_ID'), d.get('TYPE'))
print('TOTAL', n)

m = json.load(open(B + 'env/CONTROL_STATE.json', encoding='utf-8-sig'))
r = json.load(open(B + 'CONTROL_STATE.json', encoding='utf-8-sig'))
c = json.load(open(B + 'CONTROL_CONTRACT.json', encoding='utf-8-sig'))
print('--- BIND')
print('mailbox-branch CONTROL_STATE updated_utc', m.get('updated_utc'))
print('repo CONTROL_STATE updated_utc', r.get('updated_utc'))
tb = c['target_role_bindings']
cu = tb['gpt:reviewer-controller']['chatgpt_conversation_uuid']
au = tb['gpt:project-architect']['chatgpt_conversation_uuid']
ru = r['bindings']['gpt:reviewer-controller']['uuid']
ra = r['bindings']['gpt:project-architect']['uuid']
print('contract controller', cu, tb['gpt:reviewer-controller']['binding_status'], 'v', tb['gpt:reviewer-controller']['binding_version'])
print('contract architect', au, tb['gpt:project-architect']['binding_status'], 'v', tb['gpt:project-architect']['binding_version'])
print('state controller', ru, r['bindings']['gpt:reviewer-controller']['status'])
print('state architect', ra, r['bindings']['gpt:project-architect']['status'])
print('AGREE controller', cu == ru, 'AGREE architect', au == ra)
print('dispute', r['bindings']['controller_uuid_dispute']['state'])
print('retired', c.get('retired_binding_uuids'))
print('contract keys', list(c.keys()))
