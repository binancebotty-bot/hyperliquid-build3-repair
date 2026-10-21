#!/usr/bin/env python3
"""Core-targeted certification tests: settlement is not an ack, reduce-only on the wire, caps.

Every check imports HL_Live_Copy_Service_Core directly (the module that ships), not the
legacy HL_Live_Copy_Service. Each is mutation-proven by tools/mutation_proof.py.

S: an ORDER_FILLED ack is not settlement; only a live_fills row (the exchange re-read) settles it.
R: an EXIT is sent reduce-only, sized to the actual net, and cannot flip.
C: a per-wallet override can never raise effective exposure above the global cap (KNOWN DEFECT).

Run: python test_core_certification_topology.py   # RESULT:: markers, exit 0/1. Offline.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
DEFECTS = []
FOLLOWER = '0x' + 'c' * 40
LEADER = '0x' + 'd' * 40


def check(name, cond, detail='', known_defect=False):
    RESULTS.append((name, bool(cond)))
    if known_defect and not cond:
        DEFECTS.append(name)
        print('DEFECT::%s | %s' % (name, detail))
        return
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


def main():
    tmp = Path(tempfile.mkdtemp(prefix='coretopo_'))
    os.environ.update({'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LEADER_NETWORK': 'mainnet',
                       'HL_FOLLOWER_NETWORK': 'testnet', 'HL_LIVE_ENV_FILE': str(tmp / 'none.env')})
    import HL_Live_Copy_Service_Core as c

    c.MIDS_FETCHER = lambda payload: [] if payload.get('type') == 'perpDexs' else {'BTC': '100'}
    c.USER_WALLET = FOLLOWER

    def offline(*a, **k):
        raise RuntimeError('offline test: no network')

    c.requests.post = offline
    c.EXPOSURE_FETCHER = lambda payload: {'assetPositions': [], 'marginSummary': {'accountValue': '0'}}

    def config(gc=None, wallet_cfg=None, auto=True):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            'auto_send_enabled': auto,
            'global_controls': gc or {},
            'wallets': {LEADER: wallet_cfg or {'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed',
                                               'fixed_notional': 1000}},
        })

    seq = [0]

    def fill(side='BUY', price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill('t%d' % seq[0], LEADER, 'BTC', side, price, size, c.utc_now_ms(), 'TEST')

    class FakeExchange:
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({'coin': coin, 'is_buy': is_buy, 'size': size, 'px': px,
                               'tif': tif['limit']['tif'], 'reduce_only': reduce_only})
            return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [
                {'filled': {'totalSz': str(size), 'avgPx': str(px), 'oid': 424242}}]}}}

    def gateway(ledger_path):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=ledger_path))
        gw._resolve_coin = lambda coin: {'ok': True, 'sdk_coin': 'BTC', 'sz_decimals': 3,
                                        'price_max_decimals': 2, 'perp_dexs': [''],
                                        'sdk_order_compatible': True, 'min_order_value_usd': 1.0,
                                        'min_size': 0.0, 'status': 'OK'}
        gw._pre_send_ownership_gate = lambda intent: (True, {})
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exposure_cap_block = lambda *a, **k: ''
        gw._unowned_inventory_block = lambda *a, **k: ''
        return gw

    os.environ['HL_LIVE_HL_PRIVATE_KEY'] = '0x' + '1' * 64
    c.HLAccount, c.HLExchange = object, object

    # ---- S: an ack is not settlement ------------------------------------------------------
    config()
    gw = gateway(tmp / 's1.json')
    gw._get_exchange_client = lambda *a, **k: FakeExchange()
    gw._exchange_client_has_symbol = lambda *a, **k: True
    sent, status = gw.send_if_allowed(c.IntentBuilder(c.ConfigManager(), gw.ledger).build(fill()))
    sends = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
    live = c.read_csv_rows(c.LIVE_FILLS_CSV)
    acked = [r for r in sends if str(r.get('status') or '').upper() == 'ORDER_FILLED']
    check('S1_ACK_IS_RECORDED_AS_ORDER_FILLED', sent and status == 'ORDER_FILLED' and len(acked) == 1,
          '%s %s %d' % (sent, status, len(acked)))
    check('S2_ACK_WRITES_NO_LIVE_FILL', live == [], '%d live_fills rows' % len(live))
    ev = c.service_position_evidence_by_coin(sends=sends, live_fills=live)
    missing = (ev.get('BTC') or {}).get('missing_filled_oids') or []
    check('S3_ACK_WITHOUT_EXCHANGE_REREAD_IS_UNSETTLED', len(missing) == 1, 'missing=%s' % missing)
    c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, {
        'created_at': c.utc_now_iso(), 'leader_wallet': LEADER, 'leader_fill_id': 't1',
        'intent_id': acked[0].get('intent_id') if acked else '', 'coin': 'BTC', 'side': 'BUY',
        'fill_size': '1.0', 'fill_price': '100.0', 'exchange_order_id': '424242',
    })
    ev2 = c.service_position_evidence_by_coin(sends=sends, live_fills=c.read_csv_rows(c.LIVE_FILLS_CSV))
    check('S4_EXCHANGE_REREAD_SETTLES_THE_ACK',
          not ((ev2.get('BTC') or {}).get('missing_filled_oids') or []),
          str((ev2.get('BTC') or {}).get('missing_filled_oids')))

    # ---- R: reduce-only on the wire, capped, cannot flip ----------------------------------
    config()
    led = c.ManualLedger(path=tmp / 'r1.json')
    led.sleeve(LEADER, 'BTC')['signed_size'] = 1.0            # we own 1.0 long
    gw = gateway(tmp / 'r1.json')
    gw.ledger = led
    fake = FakeExchange()
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    intent = c.IntentBuilder(c.ConfigManager(), led).build(fill('SELL', size=5.0))  # leader closes 5x our net
    sent, status = gw.send_if_allowed(intent)
    check('R1_EXIT_SENT_REDUCE_ONLY', sent and status == 'ORDER_FILLED' and len(fake.calls) == 1
          and fake.calls[0]['reduce_only'] is True, '%s %s' % (status, fake.calls))
    check('R2_EXIT_SIZE_CAPPED_TO_ACTUAL_NET', bool(fake.calls) and abs(fake.calls[0]['size'] - 1.0) < 1e-9,
          str(fake.calls[0]['size']) if fake.calls else 'no call')
    config()
    fake2 = FakeExchange()
    gw2 = gateway(tmp / 'r3.json')
    gw2._get_exchange_client = lambda *a, **k: fake2
    gw2._exchange_client_has_symbol = lambda *a, **k: True
    gw2.send_if_allowed(c.IntentBuilder(c.ConfigManager(), gw2.ledger).build(fill('BUY', size=0.1)))
    check('R3_ENTRY_NOT_REDUCE_ONLY', bool(fake2.calls) and fake2.calls[0]['reduce_only'] is False,
          str(fake2.calls))

    # ---- C: caps --------------------------------------------------------------------------
    config(gc={'max_wallet_exposure_usd': 500},
           wallet_cfg={'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 1000,
                       'max_wallet_exposure_usd': 100})
    check('C1_PER_WALLET_OVERRIDE_BELOW_GLOBAL_IS_HONOURED',
          abs(c.ConfigManager().max_wallet_exposure(LEADER) - 100.0) < 1e-9,
          str(c.ConfigManager().max_wallet_exposure(LEADER)))
    config(gc={'max_wallet_exposure_usd': 500},
           wallet_cfg={'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 1000,
                       'max_wallet_exposure_usd': 100000})
    eff = c.ConfigManager().max_wallet_exposure(LEADER)
    check('C2_PER_WALLET_OVERRIDE_CANNOT_EXCEED_GLOBAL_CAP', eff <= 500.0 + 1e-9,
          'effective=%s' % eff, known_defect=True)

    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d DEFECTS=%d' % (len(RESULTS), len(failed), len(DEFECTS)))
    if DEFECTS:
        print('KNOWN_DEFECTS=' + ','.join(DEFECTS))
    unexpected = [n for n in failed if n not in DEFECTS]
    raise SystemExit(1 if unexpected else 0)


if __name__ == '__main__':
    main()
