"""Independent recompute of the orphan-table predicate (UI-FP-095..100).
Reviewer-runnable: python EVIDENCE/ui_fp_001_100/orphan_recompute.py
Reads only frozen snapshots; no app import, no HTTP.
"""
import json, os, sys
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OUT)
import oracle_lib

A = oracle_lib.compute(os.path.join(OUT, 'snap_A_min'))
B = oracle_lib.compute(os.path.join(OUT, 'snap_B_min'))


def ledger_coins(snap):
    mn = json.load(open(os.path.join(OUT, snap, 'manual_live_positions.json'), encoding='utf-8-sig'))
    s = set()
    for w, coins in (mn.get('by_wallet') or {}).items():
        for k, v in coins.items():
            if abs(oracle_lib.fnum(v.get('signed_size'))) > 1e-12:
                s.add(k.upper())
    return s


def exchange_coins(res):
    s = set()
    for k, v in res['positions_by_coin'].items():
        sz = v if isinstance(v, (int, float)) else oracle_lib.fnum((v or {}).get('signed_size'))
        if abs(sz) > 1e-12:
            s.add(k.upper())
    return s

for snap, res in (('snap_A', A), ('snap_B', B)):
    lc = ledger_coins(snap)
    ec = exchange_coins(res)
    orph = sorted(ec - lc)
    print(snap, 'ledger_coins=%d exchange_coins=%d unexplained=%d' % (len(lc), len(ec), len(orph)))
    print('  unexplained:', orph[:12], '...' if len(orph) > 12 else '')
