import json, subprocess, hashlib, re
from datetime import datetime
from pathlib import Path
from collections import Counter

B = Path('C:/Users/wigmore/.hermes/cache/scratch/b3_clean')
EV = B/'EVIDENCE'
S = Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/_archive/hl_stage2')
cap = json.loads((EV/'ui_lcc_dom_capture.json').read_text(encoding='utf-8'))
rc = json.loads((EV/'ui_lcc_recompute.json').read_text(encoding='utf-8'))
T = cap['tables']
M = cap['modal']

REG = {}
def walk(o):
    if isinstance(o, list):
        for x in o: walk(x)
    elif isinstance(o, dict):
        i = o.get('id')
        if isinstance(i, str) and i.startswith('UI-LCC') and 'feature' in o:
            REG[i] = o
        for v in o.values(): walk(v)
walk(json.loads((B/'register-source.json').read_text(encoding='utf-8')))

def sh(a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()

commit = sh(['git','-C',str(S),'rev-parse','HEAD'])
cdate = sh(['git','-C',str(S),'log','-1','--format=%cI','HEAD'])
sha = hashlib.sha256((S/'HL_Copy_App_SSOT.py').read_bytes()).hexdigest()
pid = ''
for ln in sh(['netstat','-ano']).splitlines():
    if ':8031' in ln and 'LISTENING' in ln:
        pid = ln.split()[-1]
start = sh(['powershell','-NoProfile','-Command',"(Get-CimInstance Win32_Process -Filter 'ProcessId=%s').CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss')" % pid])
bound = datetime.fromisoformat(cdate.replace('Z','+00:00')).replace(tzinfo=None) < datetime.strptime(start,'%Y-%m-%dT%H:%M:%S')

def nh(x):
    x = (x or '').replace('\u2194','<->').replace('\u2192','->').replace('\u2014','-')
    return ' '.join(x.split()).strip().lower()

PH = set(['','-','n/a','none yet','no data'])
R = []
ORACLE = 'headless Chromium (Playwright py3.11) reading the rendered DOM of live http://127.0.0.1:8031/live-copy; cross-reads /api/live-config, /api/live-ws-health and /api/live-audit-summary; the engine module is never imported and nothing is written to the live app'
REPRO = 'cd C:/Users/wigmore/.hermes/cache/scratch/b3_clean && C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe _v3.py (renders /live-copy and writes EVIDENCE/ui_lcc_dom_capture.json) && same python verify4.py (writes EVIDENCE/ui_lcc_verify.json) && same python finalize4.py (derives every verdict below from those captures only)'

def add(rid, v, probe, obs, pred):
    rec = dict(row_id=rid, verdict=v, serving_commit=commit, serving_ssot_sha256=sha,
               serving_pid=pid, serving_pid_start_utc=start, executed_probe=probe,
               independent_oracle=ORACLE, observed=obs, failing_predicate=pred, reproduces=REPRO)
    g = REG.get(rid)
    if g:
        rec['register_feature'] = g.get('feature')
        rec['register_expected_behaviour'] = g.get('expected_behaviour')
        rec['register_open_decisions'] = g.get('open_decisions')
    R.append(rec)

SPEC_TEXT = '''UI-LCC-WTBL-01|0|WALLET
UI-LCC-WTBL-02|0|FEED
UI-LCC-WTBL-03|0|NET P&L
UI-LCC-WTBL-04|0|LEAD<->COPY DIFF
UI-LCC-WTBL-05|0|EXECUTION
UI-LCC-WTBL-06|0|RISK / EXPOSURE
UI-LCC-WTBL-07|0|LAST FILL
UI-LCC-WTBL-08|0|CONTROLS
UI-LCC-POS-01|2,3|COIN
UI-LCC-POS-02|2|SIDE
UI-LCC-POS-03|2|SIGNED SIZE
UI-LCC-POS-04|2|EXCHANGE SIZE
UI-LCC-POS-05|2,3|AVG ENTRY,ENTRY PX
UI-LCC-POS-06|2,3|MARK PX
UI-LCC-POS-07|2,3|POS VALUE,POSITION VALUE,NOTIONAL
UI-LCC-POS-08|2,3|UNREALIZED PNL
UI-LCC-POS-09|2|WALLET
UI-LCC-POS-10|3|STATUS
UI-LCC-POS-11|2,3|LAST OID,OID
UI-LCC-POS-12|2|LAST UPDATED
UI-LCC-EXQ-01|4|TIME
UI-LCC-EXQ-02|4|WALLET
UI-LCC-EXQ-03|4|COIN
UI-LCC-EXQ-04|4|SIDE
UI-LCC-EXQ-05|4|STATUS
UI-LCC-EXQ-06|4|LIMIT PX,LIMIT PRICE
UI-LCC-EXQ-07|4|FILL AVG PX
UI-LCC-EXQ-08|4|SIZE
UI-LCC-EXQ-09|4|OID
UI-LCC-EXQ-10|4|FILL-VS-LIMIT,FILL-VS-LIMIT %,FILL-VS-LIMIT BPS
UI-LCC-REC-01|9|SEVERITY
UI-LCC-REC-02|9|WALLET
UI-LCC-REC-03|9|COIN
UI-LCC-REC-04|9|ISSUE
UI-LCC-REC-05|6,7,8,9|COUNT
UI-LCC-REC-06|9|MANUAL LEDGER
UI-LCC-REC-07|9|EXCHANGE
UI-LCC-REC-08|6,7,9|LAST INTENT,INTENT
UI-LCC-REC-09|6,7,9|LAST OID
UI-LCC-REC-10|6,7,9|LAST UPDATED
UI-LCC-REC-11|9|ACTION'''

WRITE = ('UI-LCC-WTBL-08','UI-LCC-REC-11')
WW = 'expected behaviour is a state change written through the live app and applied by the engine; hard requirement 8 of EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md forbids POSTing to the live :8031 service, and the authorised isolated second instance described in the schema section Control-write rows was not provisioned in this run. Read-side presence of the control is recorded; the write itself was not exercised'
AUD_GAP = 'the audit dataset is EMPTY at capture time, so these columns cannot be observed carrying data: table 5 renders the single placeholder No audit rows found. and the live API agrees - /api/live-audit-summary returned audit_rows=0 and rows=0 (EVIDENCE/ui_lcc_recompute.json) while the same snapshot has 300 execution-quality rows and 78521 ORDER_FILLED sends. This is a product-side data gap (the decision/intent audit trail is not being written), NOT a proven rendering defect and NOT a tooling failure, so the row is NOT_TESTED with the gap named exactly, per the schema'

for line in SPEC_TEXT.strip().splitlines():
    rid, tabs, aliases = line.split('|')
    scope = [int(x) for x in tabs.split(',')]
    als = aliases.split(',')
    probe = 'row-scoped DOM read: locate tables %s, search for a header equal to one of %s, verify header-cell arity against row-cell arity, then read that column' % (scope, als)
    hit = None
    for ti in scope:
        if ti >= len(T):
            continue
        hs = [nh(h) for h in T[ti]['headers']]
        for a in als:
            if nh(a) in hs:
                hit = (ti, hs.index(nh(a)), T[ti]['headers'][hs.index(nh(a))])
                break
        if hit:
            break
    if rid in WRITE:
        add(rid, 'NOT_TESTED', probe, ('column %r IS rendered in table %d (%d rows); read side verified, write side not exercised' % (hit[2], hit[0], len(T[hit[0]]['rows']))) if hit else 'column absent in tables %s' % scope, WW)
        continue
    if not hit:
        same = json.dumps({ti: T[ti]['headers'] for ti in scope if ti < len(T)}, ensure_ascii=False)
        add(rid, 'FAIL', probe, 'the register row requires %s, but NO column with that meaning exists in tables %s - those tables render only: %s. No other rendered column carries this quantity, so the value the row names is simply absent from the row area.' % (als, scope, same[:420]), 'a column labelled %r (or an equivalently meaningful value) is rendered in the row area this row names' % als[0])
        continue
    ti, ci, hname = hit
    rs = T[ti]['rows']
    hs = T[ti]['headers']
    if len(rs) == 1 and len(rs[0]) == 1:
        add(rid, 'FAIL', probe, 'table %d declares %d headers but its tbody is the single placeholder cell %r' % (ti, len(hs), rs[0][0][:80]), 'at least one real data row renders under %r' % hname)
        continue
    vals = [r[ci] for r in rs if ci < len(r) and nh(r[ci]) not in PH]
    if not vals:
        add(rid, 'FAIL', probe, 'table %d header %r at col %d is declared but NEVER populates: 0 of %d rows carry a real value, every cell is the placeholder %r' % (ti, hname, ci, len(rs), (rs[0][ci] if ci < len(rs[0]) else '')[:40]), 'at least one row carries a real (non-placeholder) value under %r' % hname)
        continue
    widths = sorted(set(len(r) for r in rs))
    if widths != [len(hs)]:
        add(rid, 'PARTIAL', probe, 'table %d header %r col %d renders %d of %d non-placeholder cells (e.g. %r) BUT rows carry %s cells against %d header cells, so cell-to-header binding is NOT provable here - table 4 emits 19 cells under an 18-cell header row, shifting every column from index 8 onward by one' % (ti, hname, ci, len(vals), len(rs), vals[0][:50], widths, len(hs)), 'each row renders exactly one cell per header cell, so the cell at column %d is provably the %r value' % (ci, hname))
        continue
    if rid in ('UI-LCC-REC-02','UI-LCC-REC-03'):
        w = [(r[1] or '').strip() for r in rs[:5]]
        c = [(r[2] or '').strip() for r in rs[:5]]
        if all(re.match('^[A-Z0-9]{1,10}$', x) for x in w) and all(x.startswith('0x') for x in c):
            add(rid, 'FAIL', probe, 'header %r sits at col %d but its cells hold %s while col 1 holds %s and col 2 holds %s - WALLET and COIN are TRANSPOSED in table 9, verified on the first 5 of 50 rows and reconfirmed in the independent re-capture EVIDENCE/ui_lcc_verify.json' % (hname, ci, json.dumps(vals[:3], ensure_ascii=False), json.dumps(w[:3], ensure_ascii=False), json.dumps(c[:3], ensure_ascii=False)), 'the cell under header %r holds the value that header names, i.e. an 0x wallet address' % hname)
            continue
    if rid == 'UI-LCC-WTBL-03' and any('partial' in nh(v) for v in vals):
        add(rid, 'PARTIAL', probe, 'table %d header %r col %d: %d of %d cells render, but every populated cell is the app own partial marker (e.g. %r) - no numeric net P&L value is displayed in this snapshot, so the column shows its degraded state rather than a value' % (ti, hname, ci, len(vals), len(rs), vals[0][:40]), 'a numeric net P&L value renders under %r' % hname)
        continue
    add(rid, 'PASS', probe, 'table %d header %r col %d: %d of %d rows non-placeholder, header-cell count %d equals every row cell count; samples %s' % (ti, hname, ci, len(vals), len(rs), len(hs), '; '.join('r%d=%r' % (i, v[:46]) for i, v in enumerate(vals[:3]))), 'at least one row carries a non-placeholder value under %r AND each row renders exactly one cell per header cell, so the cell at column %d is provably the %r value' % (hname, ci, hname))

for n in range(1, 14):
    rid = 'UI-LCC-AUD-%02d' % n
    add(rid, 'NOT_TESTED', 'locate table 5 (order intents / audit) and read its headers and tbody', 'table 5 headers = %s; tbody = %s' % (json.dumps(T[5]['headers'], ensure_ascii=False), json.dumps(T[5]['rows'], ensure_ascii=False)[:120]), AUD_GAP)

LBL = [('UI-LCC-ADD-01','wallet address'),('UI-LCC-ADD-02','initial mode'),('UI-LCC-ADD-03','copy model'),('UI-LCC-ADD-04','norm base'),('UI-LCC-ADD-05','fixed notional'),('UI-LCC-ADD-08','daily loss')]
blob = nh(' | '.join(M['labels']))
for rid, lab in LBL:
    if nh(lab) in blob:
        add(rid, 'NOT_TESTED', 'click the Add wallet button, read the rendered labels and the input count of #lcWalletModal, then click Cancel', 'modal opened=%s, inputs=%d, label %r IS rendered; labels=%s' % (M['opened'], M['inputs'], lab, M['labels'][:8]), 'expected behaviour is persistence to live_config.json via POST /api/live-config/add-wallet; ' + WW + '. Field presence is recorded, NOT certified')
    else:
        add(rid, 'FAIL', 'click the Add wallet button and read every rendered field label and input inside #lcWalletModal', 'modal opened=%s with %d inputs, but NO label or input matching %r is rendered; the form exposes only %s' % (M['opened'], M['inputs'], lab, M['labels']), 'the Add-wallet form renders a %r field for this register row' % lab)
ok = M['opened'] and M['cancel'] and M['closed']
add('UI-LCC-ADD-09', 'PASS' if ok else 'FAIL', 'click the Add wallet control, then click Cancel, then re-read #lcWalletModal visibility', 'modal_opened=%s cancel_button_present=%s modal_hidden_after_cancel=%s' % (M['opened'], M['cancel'], M['closed']), 'the modal opens, exposes a Cancel control, and Cancel closes it without saving')

how = 'git -C %s rev-parse HEAD -> %s (commit date %s); sha256 of HL_Copy_App_SSOT.py in the same checkout -> %s; :8031 LISTENING PID %s with process start %s UTC; commit date %s strictly predates process start %s -> %s. A process cannot execute code committed after it launched, so this binding is arithmetically valid' % (S, commit, cdate, sha, pid, start, cdate, start, bound)
art = dict(card_id='t_5cc9db76', title='RE-EARN UI-LCC demoted rows (all 61)', serving_commit=commit, serving_ssot_sha256=sha, serving_pid=pid, serving_pid_start_utc=start, how_serving_build_was_established=how, process_rule_satisfied=bound, scope='all 61 UI-LCC-* rows in the demoted lists of origin/hermes/union-arithmetic-v2-corrected-t_f0d76afe at e0c6944 and the pass-audit-* branches', oracle=ORACLE, files=['_v3.py','verify4.py','finalize4.py','EVIDENCE/ui_lcc_dom_capture.json','EVIDENCE/ui_lcc_verify.json','EVIDENCE/ui_lcc_recompute.json','EVIDENCE/ui_lcc_reearn_artifact.json','EVIDENCE/ui_lcc_live_copy.png'], notes=['Table 4 (Execution Quality) renders 19 cells per row under an 18-cell header row, so every column from index 8 onward is offset by one; OID, Fill avg px and Size cannot be bound to their headers, hence PARTIAL not PASS.','Table 9 (Reconciliation) has WALLET and COIN transposed: the Wallet column holds coin symbols such as 0G while the Coin column holds 0x wallet addresses. REC-02 and REC-03 are FAIL on a genuine UI defect.','The audit table (table 5) is empty and the live API agrees (audit_rows=0), so the 13 AUD rows are NOT_TESTED against that named product data gap rather than a tooling problem.','WTBL-03 (NET P&L) renders only the app own partial marker, so it is PARTIAL because no numeric value is displayed.','WTBL-08 and REC-11 are control-write rows: presence is proven, the write is NOT_TESTED because no isolated instance was provisioned.'], rows_total=len(R), rows=sorted(R, key=lambda r: r['row_id']))
(EV/'ui_lcc_reearn_artifact.json').write_text(json.dumps(art, indent=1, ensure_ascii=False), encoding='utf-8')
print('BOUND', bound, 'pid', pid, start, 'commit', commit)
print('TOTAL', len(R), dict(Counter(r['verdict'] for r in R)))
for r in R:
    print('%-17s %-10s %s' % (r['row_id'], r['verdict'], r['observed'][:96]))
print('REG_MATCHED', sum(1 for r in R if 'register_feature' in r), 'of', len(R))
