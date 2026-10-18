import json, collections
RES = 'C:/Users/wigmore/.hermes/cache/scratch/b3_cert13/certification/results/'
d = json.load(open(RES + 'UI_LCC_AUD_REC_WS_capture_t_bb3dfa77.json', encoding='utf-8'))
src = d['manual_reconciliation_rows']
dom = d['rendered_recon_rows']
out = {}
out['serving_process'] = json.load(open(RES + '_serving_process.json', encoding='utf-8'))
for label in ('src', 'dom'):
    rows = src if label == 'src' else dom
    cex = collections.defaultdict(set)
    cman = collections.defaultdict(set)
    for s in rows:
        if label == 'src':
            c, e, m = str(s.get('coin')), s.get('exchange_signed_size'), s.get('manual_signed_size')
        else:
            c, e, m = s[1], s[5], s[4]
        cex[c].add(repr(e)); cman[c].add(repr(m))
    out[label + '_rows'] = len(rows)
    out[label + '_coins'] = len(cex)
    out[label + '_coins_with_1_distinct_exchange'] = sum(1 for v in cex.values() if len(v) == 1)
    out[label + '_coins_with_1_distinct_manual'] = sum(1 for v in cman.values() if len(v) == 1)
cnt = collections.Counter(str(s.get('coin')) for s in src)
out['coins_held_by_multiple_wallets'] = sum(1 for c, n in cnt.items() if n > 1)
out['rows_in_multi_wallet_coins'] = sum(n for c, n in cnt.items() if n > 1)
out['top_coin_counts'] = cnt.most_common(4)
print(json.dumps(out, indent=1)[:2500])
