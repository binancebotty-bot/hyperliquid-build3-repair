import json

for v in ('A', 'B'):
    d = json.load(open('probe_%s.json' % v, encoding='utf-8'))
    a = d['api']
    print('=' * 20, v)
    print('DOM truth_status  :', json.dumps(d['dom']['truth_status'], ensure_ascii=False))
    print('DOM real_cards    :', json.dumps(d['dom']['real_cards'], ensure_ascii=False))
    for k in ('restart_note', 'banner_sending', 'banner_acct', 'banner_health', 'banner_open', 'ws_overall', 'wallet_count'):
        print('DOM %-14s:' % k, json.dumps(d['dom'][k], ensure_ascii=False))
    print('TS  :', json.dumps(a['live_top_status'], ensure_ascii=False))
    print('SNAP:', json.dumps(a['snapshot'], ensure_ascii=False))
    print('FA  :', json.dumps(a['follower_account'], ensure_ascii=False))
    print('EXPO:', a['manual_live_exposure_estimate'])
    print('last_send coin/status:', (a['last_send'] or {}).get('coin'), (a['last_send'] or {}).get('status'))
    print('last_fill coin/side:', (a['last_fill'] or {}).get('coin'), (a['last_fill'] or {}).get('side'), (a['last_fill'] or {}).get('created_at'))
    print('last_reject coin/cat:', (a['last_reject'] or {}).get('coin'), (a['last_reject'] or {}).get('reject_category'))
    print('last_lat notes:', (a['last_latency_warning'] or {}).get('notes'))
