#!/usr/bin/env python3
'''MO#2 behaviours A, B, D on the final-cap path.

A  per-wallet AND global allowance caps count in-flight / pending IOC exposure, not only settled positions.
B  unreadable exposure is a HOLD with replay+alert, never "zero exposure".
D  reductions always pass.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_exposure_inflight_hold_reduce.py
'''
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix='mo2_caps_'))
os.environ.update({'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LIVE_ENV_FILE': '/nonexistent'})
os.environ.pop('HL_LIVE_CAP_SIZE_DOWN', None)
import HL_Live_Copy_Service_Core as c

R = []
A = '0x' + 'a' * 40
B = '0x' + 'b' * 40


def check(n, ok, d=''):
    R.append(bool(ok))
    print('RESULT::%s_%s%s' % (n, 'PASS' if ok else 'FAIL', (' | ' + str(d)) if d and not ok else ''))


class Ledger:
    def __init__(self, per_wallet=None):
        self.per_wallet = per_wallet or {}

    def wallet_abs_exposure_usd(self, wallet, mark_prices=None):
        return float(self.per_wallet.get(wallet, 0.0))

    def wallet_coin_position(self, wallet, coin):
        return 0.0

    def coin_net(self, coin):
        return 0.0


def builder(cap_total=0.0, cap_asset=0.0, cap_wallet=0.0, min_n=10.0, exp=None, per_wallet=None):
    b = c.IntentBuilder.__new__(c.IntentBuilder)
    b.cfg = SimpleNamespace(
        max_total_exposure=lambda: cap_total,
        max_asset_directional_exposure=lambda: cap_asset,
        max_wallet_exposure=lambda w: cap_wallet,
        max_order_notional=lambda: 0.0,
        min_notional=lambda: min_n,
        auto_send_enabled=False,
        wallet_enabled=lambda w: True,
        wallet_mode=lambda w: 'ON',
        is_symbol_allowed=lambda coin: (True, ''),
        marketable_bps=lambda: 0.0,
    )
    b.ledger = Ledger(per_wallet)
    b._exposure_pending = []
    b._sizing_block = {}
    b._coin_clean = {}
    b._coin_activity = {}
    b.follower_exposure = lambda: (exp if exp is not None else {'ok': True, 'total_usd': 0.0, 'by_coin': {}})
    b._resting = lambda: {'total_usd': 0.0, 'buy_units': {}, 'sell_units': {}, 'by_wallet_usd': {}}
    b._order_value_px = lambda fill: 100.0
    b._is_leader_close_fill = lambda fill: False
    return b


seq = [0]


def mkfill(side='BUY', price=100.0, size=1.0, wallet=A, coin='BTC'):
    seq[0] += 1
    return c.LeaderFill('f%d' % seq[0], wallet, coin, side, price, size, c.utc_now_ms() + seq[0], 'TEST', 0, {})


def decide(b, wallet=A, lifecycle='ENTRY', notional=200.0, coin='BTC', side='BUY'):
    f = mkfill(side=side, size=notional / 100.0, wallet=wallet, coin=coin)
    return b._decision(wallet, f, lifecycle, notional, 0.0)


# A: per-wallet allowance must count in-flight entries for THAT wallet
b = builder(cap_wallet=300.0)
d1, w1 = decide(b, notional=200.0)
d2, w2 = decide(b, notional=200.0)
check('A1_FIRST_WALLET_ENTRY_ALLOWED', d1 == 'ENTRY_ALLOWED', (d1, w1))
check('A2_SECOND_WALLET_ENTRY_BLOCKED_BY_INFLIGHT', d2 == 'SEND_BLOCKED_RISK' and 'wallet exposure' in w2, (d2, w2))

b = builder(cap_wallet=300.0)
d1, _ = decide(b, wallet=A, notional=200.0)
d2, _ = decide(b, wallet=B, notional=200.0)
check('A3_OTHER_WALLET_UNAFFECTED_BY_INFLIGHT', d1 == 'ENTRY_ALLOWED' and d2 == 'ENTRY_ALLOWED', (d1, d2))

b = builder(cap_wallet=300.0)
d1, _ = decide(b, notional=200.0, coin='BTC')
d2, _ = decide(b, notional=200.0, coin='ETH')
check('A4_INFLIGHT_COUNTS_ACROSS_COINS', d1 == 'ENTRY_ALLOWED' and d2 == 'SEND_BLOCKED_RISK', (d1, d2))

b = builder(cap_total=300.0)
c._CAP_TLS.scale = 1.0
d1, _ = decide(b, notional=200.0)
s1 = c._CAP_TLS.scale
c._CAP_TLS.scale = 1.0
d2, _ = decide(b, notional=200.0)
s2 = c._CAP_TLS.scale
# Boss cap rule: the last order fills the remaining allowance, then increases are blocked
check('A5_GLOBAL_INFLIGHT_COUNTS_BURST', d1 == 'ENTRY_ALLOWED' and abs(s1 - 1.0) < 1e-9
      and d2 == 'ENTRY_ALLOWED' and abs(s2 - 0.5) < 1e-9, (d1, s1, d2, s2))
b2_ = builder(cap_total=300.0)
decide(b2_, notional=200.0)
decide(b2_, notional=200.0)
d3, w3 = decide(b2_, notional=200.0)
check('A6_GLOBAL_INFLIGHT_EXHAUSTED_BLOCKS', d3 == 'SEND_BLOCKED_RISK', (d3, w3))

# B: unreadable exposure is a hold, never zero
b = builder(cap_total=1000.0, exp={'ok': False, 'status': 'SNAPSHOT_UNAVAILABLE'})
d, w = decide(b, notional=200.0)
check('B1_UNREADABLE_EXPOSURE_BLOCKS', d == 'SEND_BLOCKED_RISK', (d, w))
check('B2_UNREADABLE_REASON_IS_DEFERRABLE', any(m in w.lower() for m in c.LiveCopyCore._TRUTH_UNREADABLE_MARKERS), w)
check('B3_UNREADABLE_RECORDS_NO_PENDING', b._exposure_pending == [], b._exposure_pending)

b = builder(cap_total=1000.0, exp={'ok': True, 'by_coin': {'BTC': {'net': 1.0}}})
d, w = decide(b, notional=200.0)
check('B4_SNAPSHOT_WITHOUT_TOTAL_IS_HELD_NOT_ZERO', d == 'SEND_BLOCKED_RISK'
      and any(m in w.lower() for m in c.LiveCopyCore._TRUTH_UNREADABLE_MARKERS), (d, w))

b = builder(cap_wallet=300.0, exp={'ok': False, 'status': 'THROTTLED'})
d, w = decide(b, notional=200.0)
check('B5_UNREADABLE_HOLDS_WALLET_CAP_TOO', d == 'SEND_BLOCKED_RISK', (d, w))

# D: reductions always pass
b = builder(cap_total=100.0, cap_asset=100.0, cap_wallet=100.0,
            exp={'ok': True, 'total_usd': 5000.0, 'by_coin': {'BTC': {'net': 50.0}}},
            per_wallet={A: 5000.0})
d, w = decide(b, lifecycle='EXIT', notional=5000.0, side='SELL')
check('D1_EXIT_PASSES_THROUGH_BREACHED_CAPS', d == 'EXIT_ALLOWED', (d, w))

b = builder(cap_total=100.0, cap_asset=100.0, cap_wallet=100.0,
            exp={'ok': True, 'total_usd': 5000.0, 'by_coin': {'BTC': {'net': 50.0}}},
            per_wallet={A: 5000.0})
d, w = decide(b, lifecycle='REDUCE', notional=5000.0, side='SELL')
check('D2_REDUCE_PASSES_THROUGH_BREACHED_CAPS', d in {'EXIT_ALLOWED', 'ENTRY_ALLOWED'} and 'exposure' not in w, (d, w))

b = builder(cap_total=300.0)
decide(b, lifecycle='EXIT', notional=250.0, side='SELL')
check('D3_REDUCTION_NOT_BOOKED_AS_PENDING_ENTRY', b._exposure_pending == [], b._exposure_pending)

print('TOTAL=%d FAILED=%d' % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
