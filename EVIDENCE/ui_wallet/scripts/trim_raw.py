#!/usr/bin/env python3
'''Trim the huge served-API bodies out of the raw probe captures so the evidence
package stays committable, while preserving a sha256 of the full untrimmed body
plus every field the verdicts actually rest on. READ-ONLY wrt the live system.'''
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.abspath(os.path.join(HERE, '..', 'raw'))

KEEP = ['available', 'status', 'account_address', 'updated_at', 'fetched_at_ms', 'account_value',
        'unified_portfolio_value', 'unified_portfolio_value_source', 'unrealized_pnl',
        'unrealized_pnl_source', 'realized_pnl_total', 'realized_pnl_selected',
        'realized_pnl_selected_label']
MAN = ['open_manual_position_count', 'manual_live_exposure_estimate', 'last_filled_manual_order',
       'last_rejected_manual_order']


def digest(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def trim(path, out_path, note):
    full_sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    info = {'__trimmed__': True, 'note': note, 'untrimmed_file_sha256': full_sha}
    for key in ('api_live_audit_summary',):
        b = (d.get(key) or {}).get('body')
        if isinstance(b, dict):
            info[key + '_body_sha256'] = digest(b)
            info[key + '_keys'] = sorted(b.keys())
            info[key + '_kept'] = {
                'exchange_account_snapshot': {k: (b.get('exchange_account_snapshot') or {}).get(k) for k in KEEP},
                'exchange_account_snapshot_open_positions_len': len((b.get('exchange_account_snapshot') or {}).get('open_positions') or []),
                'manual_live_summary': {k: (b.get('manual_live_summary') or {}).get(k) for k in MAN},
                'status_banner': b.get('status_banner'),
                'effective_real_orders_enabled': b.get('effective_real_orders_enabled'),
                'master_real_orders_enabled': b.get('master_real_orders_enabled'),
            }
            d[key] = {'http': (d.get(key) or {}).get('http'), 'body_trimmed': True,
                      'body_sha256': info[key + '_body_sha256'], 'body_keys': info[key + '_keys']}
    for key in ('api_state', 'api_ui_state', 'api_live_config'):
        b = (d.get(key) or {}).get('body')
        if isinstance(b, dict) and key == 'api_state':
            d[key]['body'] = {k: b.get(k) for k in ('ok', 'updated_at', 'auto_send_enabled', 'send_mode',
                                                    'wallet_gate_on_count', 'wallet_gate_on')}
        elif isinstance(b, dict) and key == 'api_live_config':
            d[key]['body'] = {'ok': b.get('ok'), 'wallet_count': b.get('wallet_count'),
                              'active_wallets': b.get('active_wallets'),
                              'wallets_trimmed': True,
                              'wallets_mode_counts': _counts((b.get('config') or {}).get('wallets') or {}, 'mode'),
                              'wallets_copy_mode_counts': _counts((b.get('config') or {}).get('wallets') or {}, 'copy_mode'),
                              'wallets_fixed_notional_values': sorted({v.get('fixed_notional') for v in ((b.get('config') or {}).get('wallets') or {}).values() if isinstance(v, dict)}),
                              'archived_wallets_len': len((b.get('config') or {}).get('archived_wallets') or {})}
    d['_raw_trim'] = info
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print('wrote %s (trimmed sha256 %s)' % (out_path, hashlib.sha256(open(out_path, 'rb').read()).hexdigest()))


def _counts(wallets, key):
    out = {}
    for v in wallets.values():
        if isinstance(v, dict):
            out[str(v.get(key))] = out.get(str(v.get(key)), 0) + 1
    return out


FULL = os.environ.get('FULL_RAW_DIR') or RAW
trim(os.path.join(FULL, 'ui_wallet_probe.full.json'), os.path.join(RAW, 'ui_wallet_probe.json'),
     'Full 14.1 MB capture archived off-repo; served-API bodies replaced by sha256 + the fields the verdicts rest on.')
trim(os.path.join(FULL, 'ui_lcc_card02_probe.full.json'), os.path.join(RAW, 'ui_lcc_card02_probe.json'),
     'Full 14.2 MB capture archived off-repo; served-API bodies replaced by sha256 + the fields the verdicts rest on.')
