#!/usr/bin/env python3
'''B3-CERT t_9dee8e17 oracle for UI-FP-119/120/133/137/139/140. READ-ONLY.'''
import json, os, io, csv, sys, urllib.request
BASE = 'http://127.0.0.1:8031'
AP = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet/append_only'

def jget(p, t=40):
    with urllib.request.urlopen(BASE + p, timeout=t) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))

def rows(name, limit=60000):
    out = []
    with io.open(os.path.join(AP, name), 'r', encoding='utf-8-sig', errors='replace', newline='') as f:
        for i, r in enumerate(csv.DictReader(f)):
            if i >= limit: break
            out.append(r)
    return out

def ne(v):
    return v is not None and str(v).strip() not in ('', 'None', '\u2014', 'n/a')

def main():
    r = {'register_commit': 'b142cf88d389e791160f691aac3d936852b99975', 'surface': BASE + '/live-copy'}
    s = jget('/api/live-audit-summary')
    eq = s.get('execution_quality_rows') or []
    audit = s.get('audit_rows') or []
    recon = s.get('reconciliation_rows') or []
    send = rows('send_attempts.csv')
    intents = rows('order_intents.csv')
    recsv = rows('reconciliation.csv')
    eqx = [x for x in eq if ne(x.get('exchange_call_ms'))]
    eqe = [x for x in eq if ne(x.get('error'))]
    sx = [x for x in send if ne(x.get('exchange_call_ms'))]
    se = [x for x in send if ne(x.get('error'))]
    r['ui_fp_119'] = {'dom_header': 'EXCHANGE MS', 'api_field': 'execution_quality_rows[].exchange_call_ms',
        'api_rows_nonempty': len(eqx), 'api_sample': [{'oid': x.get('oid'), 'exchange_call_ms': x.get('exchange_call_ms'), 'status': x.get('status'), 'coin': x.get('coin')} for x in eqx[:3]],
        'oracle_csv': 'send_attempts.csv:exchange_call_ms', 'oracle_rows_nonempty': len(sx),
        'oracle_sample': [{'attempt_id': x.get('attempt_id'), 'exchange_call_ms': x.get('exchange_call_ms'), 'status': x.get('status')} for x in sx[:3]]}
    r['ui_fp_120'] = {'dom_header': 'ERROR', 'api_field': 'execution_quality_rows[].error',
        'api_rows_nonempty': len(eqe), 'api_sample': [{'coin': x.get('coin'), 'error': x.get('error'), 'reject_category': x.get('reject_category'), 'status': x.get('status')} for x in eqe[:3]],
        'oracle_csv': 'send_attempts.csv:error', 'oracle_rows_nonempty': len(se),
        'oracle_sample': [{'attempt_id': x.get('attempt_id'), 'error': str(x.get('error'))[:80], 'reject_category': x.get('reject_category')} for x in se[:3]]}
    def rr(a):
        iid = str(a.get('intent_id') or '')
        m = [x for x in send if str(x.get('intent_id')) == iid]
        if not m: return 'NO_SEND_ATTEMPT'
        st = str(m[-1].get('status') or '')
        return {'ORDER_FILLED': 'REAL_ORDER_FILLED', 'ORDER_REJECTED': 'EXCHANGE_REJECTED'}.get(st, st or 'NO_SEND_ATTEMPT')
    comp = [{'intent_id': a.get('intent_id'), 'computed_real_result': rr(a), 'coin': a.get('coin')} for a in audit[:6]]
    r['ui_fp_133'] = {'dom_header': 'REAL ORDER RESULT', 'api_field': 'audit_rows[].intent_id join send_attempts.status',
        'oracle_computed_sample': comp, 'oracle_distinct': sorted(set(c['computed_real_result'] for c in comp))}
    rca = [x for x in recon if ne(x.get('reject_category'))]
    rcc = [x for x in recsv if ne(x.get('reject_category'))]
    r['ui_fp_137'] = {'dom_header': 'REJECT CATEGORY', 'panel': 'recon -> Actionable Critical Items/Warnings',
        'api_rows_nonempty': len(rca), 'api_sample': [{'coin': x.get('coin'), 'reject_category': x.get('reject_category'), 'event': x.get('event')} for x in rca[:3]],
        'oracle_csv': 'reconciliation.csv:reject_category', 'oracle_rows_nonempty': len(rcc)}
    r['ui_fp_139'] = {'dom_header': 'COIN', 'api_rows_nonempty': len([x for x in recon if ne(x.get('coin'))]),
        'api_sample': [x.get('coin') for x in recon[:5]], 'oracle_rows_nonempty': len([x for x in recsv if ne(x.get('coin'))])}
    r['ui_fp_140'] = {'dom_header': 'WALLET', 'api_rows_nonempty': len([x for x in recon if ne(x.get('wallet')) or ne(x.get('leader_wallet'))]),
        'api_sample': [(x.get('wallet') or x.get('leader_wallet')) for x in recon[:5]], 'oracle_rows_nonempty': len([x for x in recsv if ne(x.get('leader_wallet'))])}
    out = sys.argv[1] if len(sys.argv) > 1 else 'oracle_119_140.json'
    with io.open(out, 'w', encoding='utf-8') as f:
        json.dump(r, f, indent=1, ensure_ascii=False)
    print(json.dumps(r, indent=1, ensure_ascii=False))

if __name__ == '__main__':
    main()
