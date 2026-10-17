'''Build a compact, committed replay bundle whose oracle aggregates are IDENTICAL to snap_A/snap_B.

Why: the full append_only CSVs are ~400MB per snapshot, so a reviewer cannot fetch them from the repo.
oracle_lib only ever consumes (a) the last 20000 send_attempts rows, (b) the order_intents rows for the
intent_ids referenced by those attempts, (c) the last 500 live_fills rows, plus the small JSONs. This
script writes exactly that slice and then PROVES equality by recomputing the oracle on both and diffing.
'''
import csv, json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, '.')
import oracle_lib

ATTEMPTS_WINDOW = 20000
FILLS_WINDOW = 500

def tail_rows(path, n):
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        rd = csv.DictReader(f)
        fields = rd.fieldnames
        dq = collections.deque(rd, maxlen=n)
    return fields, list(dq)

def build(src, dst):
    os.makedirs(os.path.join(dst, 'append_only'), exist_ok=True)
    for n in ('live_config.json','live_ws_health.json','manual_live_positions.json',
              'exchange_account_snapshot.json','exchange_account_history.json',
              'live_integrity_status.json','live_service_state.json'):
        with open(os.path.join(src, n), 'rb') as a, open(os.path.join(dst, n), 'wb') as b:
            b.write(a.read())
    fields, rows = tail_rows(os.path.join(src, 'append_only', 'send_attempts.csv'), ATTEMPTS_WINDOW)
    with open(os.path.join(dst, 'append_only', 'send_attempts.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    ids = set(str(r.get('intent_id') or '') for r in rows)
    with open(os.path.join(src, 'append_only', 'order_intents.csv'), newline='', encoding='utf-8', errors='replace') as f:
        rd = csv.DictReader(f); ifields = rd.fieldnames
        keep = [r for r in rd if str(r.get('intent_id') or '') in ids]
    with open(os.path.join(dst, 'append_only', 'order_intents.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=ifields)
        w.writeheader(); w.writerows(keep)
    ff, frows = tail_rows(os.path.join(src, 'append_only', 'live_fills.csv'), FILLS_WINDOW)
    with open(os.path.join(dst, 'append_only', 'live_fills.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=ff)
        w.writeheader(); w.writerows(frows)
    return {'attempts': len(rows), 'intents': len(keep), 'fills': len(frows)}

def size(p):
    t = 0
    for root, _, files in os.walk(p):
        for x in files:
            t += os.path.getsize(os.path.join(root, x))
    return t

rep = {}
for s in ('snap_A', 'snap_B'):
    d = s + '_min'
    rep[s] = build(s, d)
    a = oracle_lib.compute(s)
    b = oracle_lib.compute(d)
    same = json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    rep[s]['oracle_identical'] = same
    rep[s]['bytes'] = size(d)
    if not same:
        ja = json.dumps(a, sort_keys=True, default=str)
        jb = json.dumps(b, sort_keys=True, default=str)
        for i in range(min(len(ja), len(jb))):
            if ja[i] != jb[i]:
                print('FIRST_DIFF', s, i, ja[max(0,i-200):i+200], '|||', jb[max(0,i-200):i+200])
                break
json.dump(rep, open('replay_build.json','w'), indent=1)
print(json.dumps(rep, indent=1))
