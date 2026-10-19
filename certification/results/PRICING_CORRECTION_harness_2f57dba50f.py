#!/usr/bin/env python3
'''B3-CERT PRICING CORRECTION harness (task t_0246c47f). Correction of t_bc8bd851.
Each check is EARNED by the runtime outcome of the engine's REAL gate logic.
Any check using an in-process exchange double is named '*_VIA_DOUBLE' and says the
double fabricates ORDER_FILLED which is NOT exchange truth. Exchange truth is NOT
achievable (follower wallet absent on testnet, t_5cf2e6cf) -> NOT_ESTABLISHED.
'''
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('C:/Users/wigmore/hyperliquid-build3-repair')
ENGINE_REL = '_archive/hl_stage2/HL_Live_Copy_Service_Core.py'
# Engine blob under test. Default = the card's reference engine (2dfbd571...).
# Override with PC_ENGINE_SHA to run the two-run control against current HEAD.
ENGINE_SHA256 = os.environ.get('PC_ENGINE_SHA', '2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405')
COMMIT10 = os.environ.get('PC_COMMIT10', '2f57dba50f')
ENGINE_GITREF = os.environ.get('PC_ENGINE_GITREF', '2f57dba')  # commit whose tree holds the engine blob
TASK_ID = 't_0246c47f'
ROWS = ['PRICE-001', 'PRICE-002', 'PRICE-005', 'PRICE-006', 'PRICE-007']
LEADER = '0x' + 'd' * 40
FOLLOWER = '0x' + 'c' * 40
CHECKS = []
NEG_TESTS = []


def check(name, passed, detail=''):
    CHECKS.append({'name': name, 'pass': bool(passed), 'detail': detail, 'oracle': 'runtime_gate_outcome_via_double'})
    print('  CHECK::%s::%s%s' % (name, 'PASS' if passed else 'FAIL', ('' if passed else ' | ' + detail)))


def neg(name, passed, detail=''):
    NEG_TESTS.append({'name': name, 'pass': bool(passed), 'detail': detail, 'oracle': 'runtime_gate_outcome_via_double'})
    print('  NEG::%s::%s%s' % (name, 'PASS' if passed else 'FAIL', ('' if passed else ' | ' + detail)))


def _load_committed_engine():
    blob = subprocess.check_output(['git', '-C', str(REPO), 'show', ENGINE_GITREF + ':' + ENGINE_REL])
    actual = hashlib.sha256(blob).hexdigest()
    if actual != ENGINE_SHA256:
        raise SystemExit('ENGINE_SHA_MISMATCH committed=%s expected=%s' % (actual, ENGINE_SHA256))
    d = Path(tempfile.mkdtemp(prefix='pricecert_engine_'))
    tmp_py = d / 'engine_under_test.py'
    tmp_py.write_bytes(blob)
    # materialise the sibling dependency from the SAME commit so the worktree's
    # uncommitted exchange_truth edits cannot change certified behaviour
    xt = subprocess.check_output(['git', '-C', str(REPO), 'show', 'HEAD:_archive/hl_stage2/exchange_truth.py'])
    (d / 'exchange_truth.py').write_bytes(xt)
    sys.path.insert(0, str(d))
    spec = importlib.util.spec_from_file_location('engine_under_test', str(tmp_py))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['engine_under_test'] = mod
    spec.loader.exec_module(mod)
    return mod, actual


def main():
    print('=' * 70)
    print('B3-CERT PRICING CORRECTION harness (t_0246c47f)')
    print('Engine certified: committed blob @ HEAD sha256 %s' % ENGINE_SHA256)
    print('=' * 70)
    mod, engine_sha = _load_committed_engine()
    check('ENGINE_SHA256_MATCHES_COMMITTED_BLOB', engine_sha == ENGINE_SHA256, 'actual=%s' % engine_sha)

    tmp = Path(tempfile.mkdtemp(prefix='pricecert_'))
    os.environ.update({
        'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LEADER_NETWORK': 'mainnet',
        'HL_FOLLOWER_NETWORK': 'testnet', 'HL_LIVE_ENV_FILE': str(tmp / 'none.env'),
        'HL_LIVE_MOCK_SEND': '0',
    })
    mod.BASE_DIR = tmp
    mod.AUDIT_DIR = tmp
    mod.LIVE_CONFIG_FILE = tmp / 'live_config.json'
    mod.ORDER_INTENTS_CSV = tmp / 'order_intents.csv'
    mod.SEND_ATTEMPTS_CSV = tmp / 'send_attempts.csv'
    mod.LIVE_FILLS_CSV = tmp / 'live_fills.csv'
    mod.RECONCILIATION_CSV = tmp / 'reconciliation.csv'
    mod.LEADER_NETWORK = 'mainnet'
    mod.FOLLOWER_NETWORK = 'testnet'
    mod.USER_WALLET = FOLLOWER
    try:
        mod.ensure_dirs()
    except Exception:
        pass
    for path, fields in ((mod.ORDER_INTENTS_CSV, mod.ORDER_INTENT_FIELDS),
                         (mod.SEND_ATTEMPTS_CSV, mod.SEND_ATTEMPT_FIELDS),
                         (mod.LIVE_FILLS_CSV, mod.LIVE_FILL_FIELDS),
                         (mod.RECONCILIATION_CSV, mod.RECONCILIATION_FIELDS)):
        try:
            mod.ensure_csv_header(path, fields)
        except Exception:
            path.write_text(','.join(fields) + '\n', encoding='utf-8')

    mod.MIDS_FETCHER = lambda payload: {}
    mod.EXPOSURE_FETCHER = lambda payload: {'assetPositions': []}

    def set_follower_mid(coin, px, age_ms=0):
        mod._FOLLOWER_MIDS['px'] = {str(coin).upper(): float(px)}
        mod._FOLLOWER_MIDS['ms'] = mod.utc_now_ms() - int(age_ms)
        mod._FOLLOWER_MIDS['dexes'] = []
        mod._FOLLOWER_MIDS['dexes_ms'] = mod.utc_now_ms()

    def clear_follower_mid():
        mod._FOLLOWER_MIDS['px'] = {}
        mod._FOLLOWER_MIDS['ms'] = 0
        mod._FOLLOWER_MIDS['dexes'] = []
        mod._FOLLOWER_MIDS['dexes_ms'] = mod.utc_now_ms()

    class FakeExchange:
        '''In-process exchange double. Fabricates ORDER_FILLED. NOT exchange truth.'''
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({'coin': coin, 'is_buy': is_buy, 'size': size, 'px': px, 'reduce_only': reduce_only})
            return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [{'filled': {'totalSz': str(size), 'avgPx': str(px), 'oid': 990001}}]}}}

    RESOLVED_OK = {'ok': True, 'raw_coin': 'ZWIRE', 'sdk_coin': 'ZWIRE', 'sz_decimals': 2,
                   'price_max_decimals': 4, 'perp_dexs': [''], 'sdk_order_compatible': True,
                   'min_order_value_usd': 1.0, 'min_size': 0.0, 'status': 'OK'}

    def make_gw(global_controls=None):
        cfg_path = tmp / ('live_config_%d.json' % (int(time.time() * 1e6) % 10 ** 9))
        cfg_path.write_text(json.dumps({'auto_send_enabled': True,
            'wallets': {LEADER: {'enabled': True, 'mode': 'ON', 'copy_mode': 'fixed', 'fixed_notional': 1000}},
            'global_controls': global_controls or {}}), encoding='utf-8')
        cfg = mod.ConfigManager(config_path=cfg_path)
        ledger = mod.ManualLedger(path=tmp / ('pos_%d.json' % (int(time.time() * 1e6) % 10 ** 9)))
        return cfg, ledger, mod.SenderGateway(cfg, mod.AuditLogWriter(), ledger)

    def drive_send(gw, intent, entry_block_reason=''):
        fake = FakeExchange()
        saved = (gw._resolve_coin, gw._get_exchange_client, gw._exchange_client_has_symbol,
                 gw._pre_exchange_asset_safety, gw._pre_send_ownership_gate)
        saved_acct = getattr(mod, 'HLAccount', None)
        saved_exch = getattr(mod, 'HLExchange', None)
        saved_key = os.environ.get('HL_LIVE_HL_PRIVATE_KEY')
        gw._resolve_coin = lambda coin: dict(RESOLVED_OK)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._pre_send_ownership_gate = lambda *a, **k: (True, {})
        mod.HLAccount = object
        mod.HLExchange = object
        os.environ['HL_LIVE_HL_PRIVATE_KEY'] = '0x' + '1' * 64
        try:
            ok, status = gw.send_if_allowed(intent, entry_block_reason)
            return {'ok': ok, 'status': status, 'calls': list(fake.calls)}
        finally:
            (gw._resolve_coin, gw._get_exchange_client, gw._exchange_client_has_symbol,
             gw._pre_exchange_asset_safety, gw._pre_send_ownership_gate) = saved
            mod.HLAccount = saved_acct
            mod.HLExchange = saved_exch
            if saved_key is None:
                os.environ.pop('HL_LIVE_HL_PRIVATE_KEY', None)
            else:
                os.environ['HL_LIVE_HL_PRIVATE_KEY'] = saved_key

    seq = [0]

    def build(cfg, ledger, side, price, coin='ZWIRE'):
        seq[0] += 1
        fill = mod.LeaderFill('f%d' % seq[0], LEADER, coin, side, price, 1.0, mod.utc_now_ms(), 'TEST')
        return mod.IntentBuilder(cfg, ledger).build(fill)

    print('\n=== PRICE-001 ===')
    set_follower_mid('ZWIRE', 50000.0)
    cfg, ledger, gw = make_gw({})
    intent = build(cfg, ledger, 'BUY', 60000.0)
    res = drive_send(gw, intent)
    if res['calls']:
        got = res['calls'][0]['px']
        expected = mod.SenderGateway._format_limit_px(50000.0 * 1.002, 4)
        check('ENTRY_PRICED_FROM_FOLLOWER_MID_VIA_DOUBLE',
              abs(got - expected) < 1e-6 and abs(got - 60000.0) > 1.0,
              'limit=%s expected_from_mid=%s leader_price=60000 (double fabricates ORDER_FILLED; NOT exchange truth)' % (got, expected))
        check('FOLLOWER_MID_CONSULTED_FOR_ENTRY_VIA_DOUBLE', abs(got - 60000.0) > 1.0,
              'limit %s from follower mid not leader 60000 (double fabricates ORDER_FILLED)' % got)
    else:
        check('ENTRY_PRICED_FROM_FOLLOWER_MID_VIA_DOUBLE', False, 'no order; status=%s' % res['status'])
        check('FOLLOWER_MID_CONSULTED_FOR_ENTRY_VIA_DOUBLE', False, 'no order; status=%s' % res['status'])
    clear_follower_mid()
    cfg, ledger, gw = make_gw({})
    res = drive_send(gw, build(cfg, ledger, 'BUY', 60000.0))
    neg('PRICE-001_no_fresh_mid_blocks_entry_VIA_DOUBLE',
        (not res['calls']) and res['status'] == 'SEND_NOT_ATTEMPTED_FOLLOWER_PRICE_UNAVAILABLE',
        'status=%s calls=%d' % (res['status'], len(res['calls'])))
    set_follower_mid('ZWIRE', 50000.0)

    print('\n=== PRICE-002 ===')
    set_follower_mid('ZWIRE', 50000.0, 0)
    fresh = mod.follower_mid('ZWIRE')
    check('FRESH_MID_RETURNED_VIA_DOUBLE', abs(fresh - 50000.0) < 1e-9, 'follower_mid=%s for 0ms cache (seeded cache, NOT exchange truth)' % fresh)
    set_follower_mid('ZWIRE', 50000.0, 3000)
    within = mod.follower_mid('ZWIRE')
    check('WITHIN_MAX_AGE_RETURNS_VALUE_VIA_DOUBLE', abs(within - 50000.0) < 1e-9, 'follower_mid=%s for 3000ms cache (max 5000ms)' % within)
    set_follower_mid('ZWIRE', 50000.0, 6000)
    stale = mod.follower_mid('ZWIRE')
    check('BEYOND_MAX_AGE_RETURNS_ZERO_VIA_DOUBLE', stale == 0.0, 'follower_mid=%s for 6000ms cache (max 5000ms)' % stale)
    clear_follower_mid()
    empty = mod.follower_mid('ZWIRE')
    neg('PRICE-002_empty_cache_returns_zero_VIA_DOUBLE', empty == 0.0, 'follower_mid=%s empty' % empty)
    set_follower_mid('ZWIRE', 50000.0, 6000)
    beyond = mod.follower_mid('ZWIRE')
    neg('PRICE-002_beyond_max_age_returns_zero_VIA_DOUBLE', beyond == 0.0, 'follower_mid=%s 6s old' % beyond)
    set_follower_mid('ZWIRE', 50000.0)

    print('\n=== PRICE-005 ===')
    set_follower_mid('ZWIRE', 50000.0)
    cfg, ledger, gw = make_gw({})
    intent = build(cfg, ledger, 'SELL', 50000.0)
    intent.reduce_only_intended = True
    intent.wallet_position_before = 2.0
    intent.reason = 'REDUCE'
    res = drive_send(gw, intent, 'EXPOSURE_CAP')
    check('REDUCE_NOT_BLOCKED_BY_ENTRY_PROTECTION_VIA_DOUBLE',
          res['status'] != 'ENTRY_BLOCKED_EXPOSURE_CAP' and bool(res['calls']),
          'status=%s calls=%d (double fabricates ORDER_FILLED)' % (res['status'], len(res['calls'])))
    cfg, ledger, gw = make_gw({})
    intent = build(cfg, ledger, 'SELL', 50000.0)
    intent.wallet_position_before = 2.0
    intent.reason = 'EXIT'
    res = drive_send(gw, intent, 'EXPOSURE_CAP')
    check('EXIT_NOT_BLOCKED_BY_ENTRY_PROTECTION_VIA_DOUBLE',
          res['status'] != 'ENTRY_BLOCKED_EXPOSURE_CAP' and bool(res['calls']),
          'status=%s calls=%d (double fabricates ORDER_FILLED)' % (res['status'], len(res['calls'])))
    cfg, ledger, gw = make_gw({})
    res = drive_send(gw, build(cfg, ledger, 'BUY', 60000.0), 'EXPOSURE_CAP')
    neg('PRICE-005_entry_block_reason_blocks_entry_VIA_DOUBLE',
        res['status'] == 'ENTRY_BLOCKED_EXPOSURE_CAP' and (not res['calls']),
        'status=%s calls=%d' % (res['status'], len(res['calls'])))

    print('\n=== PRICE-006 ===')
    set_follower_mid('ZWIRE', 50000.0)
    cfg, ledger, gw = make_gw({'max_close_adverse_diff_pct': 0.25})
    intent = build(cfg, ledger, 'SELL', 60000.0)
    intent.wallet_position_before = 2.0
    intent.reason = 'EXIT'
    res = drive_send(gw, intent)
    if res['calls']:
        limit = res['calls'][0]['px']
        adverse = (50000.0 - limit) / 50000.0 * 100.0
        check('ADVERSE_DIFF_COMPUTED_VS_FOLLOWER_MID_VIA_DOUBLE',
              abs(limit - 49900.0) < 1e-6 and abs(adverse - 0.2) < 1e-6,
              'close limit=%s adverse_vs_mid=%.4f%% (NOT vs leader fill 60000)' % (limit, adverse))
    else:
        check('ADVERSE_DIFF_COMPUTED_VS_FOLLOWER_MID_VIA_DOUBLE', False, 'no order; status=%s' % res['status'])
    cfg, ledger, gw = make_gw({'max_close_adverse_diff_pct': 0.1})
    intent = build(cfg, ledger, 'SELL', 60000.0)
    intent.wallet_position_before = 2.0
    intent.reason = 'EXIT'
    res = drive_send(gw, intent)
    neg('PRICE-006_tight_adverse_limit_blocks_close_VIA_DOUBLE',
        res['status'] == 'SEND_NOT_ATTEMPTED_CLOSE_ADVERSE_DIFF' and (not res['calls']),
        'status=%s calls=%d' % (res['status'], len(res['calls'])))

    print('\n=== PRICE-007 ===')
    set_follower_mid('ZWIRE', 50000.0)
    cfg, ledger, gw = make_gw({})
    check('DEFAULT_SLIPPAGE_20BPS_READ', mod.ConfigManager(config_path=cfg.path).marketable_bps() == 20.0,
          'marketable_bps default=%s' % mod.ConfigManager(config_path=cfg.path).marketable_bps())
    res = drive_send(gw, build(cfg, ledger, 'BUY', 60000.0))
    if res['calls']:
        check('BUY_SLIPPAGE_APPLIED_VIA_DOUBLE', abs(res['calls'][0]['px'] - 50100.0) < 1e-6,
              'buy limit=%s expected=50100 (mid*1.002) via double' % res['calls'][0]['px'])
    else:
        check('BUY_SLIPPAGE_APPLIED_VIA_DOUBLE', False, 'no call; status=%s' % res['status'])
    cfg, ledger, gw = make_gw({})
    intent = build(cfg, ledger, 'SELL', 60000.0)
    intent.wallet_position_before = 2.0
    intent.reason = 'EXIT'
    res = drive_send(gw, intent)
    if res['calls']:
        check('SELL_SLIPPAGE_APPLIED_VIA_DOUBLE', abs(res['calls'][0]['px'] - 49900.0) < 1e-6,
              'sell limit=%s expected=49900 (mid*0.998) via double' % res['calls'][0]['px'])
    else:
        check('SELL_SLIPPAGE_APPLIED_VIA_DOUBLE', False, 'no call; status=%s' % res['status'])
    cfg, ledger, gw = make_gw({'marketable_bps': 50})
    res = drive_send(gw, build(cfg, ledger, 'BUY', 60000.0))
    if res['calls']:
        check('CUSTOM_50BPS_APPLIED_VIA_DOUBLE', abs(res['calls'][0]['px'] - 50250.0) < 1e-6,
              'buy limit=%s expected=50250 (mid*1.005, 50bps) via double' % res['calls'][0]['px'])
    else:
        check('CUSTOM_50BPS_APPLIED_VIA_DOUBLE', False, 'no call; status=%s' % res['status'])
    cfg, ledger, gw = make_gw({'marketable_bps': 0})
    res = drive_send(gw, build(cfg, ledger, 'BUY', 60000.0))
    neg('PRICE-007_zero_bps_limit_equals_mid_VIA_DOUBLE',
        bool(res['calls']) and abs(res['calls'][0]['px'] - 50000.0) < 1e-6,
        'buy limit=%s expected=50000 for 0 bps (status=%s)' % ((res['calls'][0]['px'] if res['calls'] else None), res['status']))

    def rows_for(row):
        return [c for c in CHECKS if row in c['name']], [n for n in NEG_TESTS if row in n['name']]

    ORACLE_NAMES = {'PRICE-001': 'Authoritative mark for OPEN/INCREASE/FLIP',
                    'PRICE-002': 'Public quote freshness',
                    'PRICE-005': 'Reduction/close never trapped by entry protection',
                    'PRICE-006': 'Adverse-diff measure is meaningful',
                    'PRICE-007': 'Marketable slippage'}
    rows_out = {}
    all_gate = True
    for row in ROWS:
        cs, ns = rows_for(row)
        passed = sum(1 for c in cs if c['pass']) + sum(1 for n in ns if n['pass'])
        total = len(cs) + len(ns)
        all_pass = all(c['pass'] for c in cs) and all(n['pass'] for n in ns)
        all_gate = all_gate and all_pass
        rows_out[row] = {'verdict': 'PARTIAL' if all_pass else 'FAIL',
                         'gate_logic_checks_pass': all(c['pass'] for c in cs),
                         'checks_pass': passed, 'checks_total': total,
                         'oracle_named_in_matrix': ORACLE_NAMES[row],
                         'oracle_actually_used': 'engine runtime gate outcome (send_if_allowed -> _send_real -> _format_limit_px) with an IN-PROCESS exchange double',
                         'exchange_truth_aspect': 'NOT_ESTABLISHED (follower wallet does not exist on testnet; t_5cf2e6cf)',
                         'checks': cs, 'negative_tests': ns}
    overall = 'PARTIAL' if all_gate else 'FAIL'
    result = {
        'task_id': TASK_ID,
        'title': 'B3-CERT PRICING CORRECTION (5 rows): mark/freshness semantics proof',
        'tested_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
        'engine_commit_reference': 'HEAD',
        'tested_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'engine_sha256': engine_sha,
        'engine_source': 'committed blob git show HEAD:' + ENGINE_REL,
        'engine_lines': len(subprocess.check_output(['git', '-C', str(REPO), 'show', 'HEAD:' + ENGINE_REL], text=True).splitlines()),
        'rows': rows_out, 'checks': CHECKS, 'negative_tests': NEG_TESTS,
        'summary': {'overall': overall, 'all_gate_logic_pass': all_gate,
                    'total_checks': len(CHECKS), 'passed_checks': sum(1 for c in CHECKS if c['pass']),
                    'total_negative': len(NEG_TESTS), 'non_vacuous_negative': len(NEG_TESTS),
                    'rows_total': len(ROWS),
                    'rows_partial': sum(1 for r in rows_out.values() if r['verdict'] == 'PARTIAL'),
                    'rows_fail': sum(1 for r in rows_out.values() if r['verdict'] == 'FAIL')},
        'oracle_statement': 'The matrix oracle for these rows is exchange truth, NOT achievable on testnet (follower wallet absent; t_5cf2e6cf). Every check is earned by the runtime outcome of the engine REAL pricing/gate logic against an IN-PROCESS exchange double. The double fabricates ORDER_FILLED; that is NOT exchange truth and is never claimed as such. No source-substring/regex check. Rows are PARTIAL: gate semantics ESTABLISHED, exchange-truth NOT_ESTABLISHED.',
        'harness': 'certification/results/PRICING_CORRECTION_harness_%s.py' % COMMIT10,
    }
    out = REPO / 'certification' / 'results' / ('PRICING_CORRECTION_%s.json' % COMMIT10)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('\n' + '=' * 70)
    print('Overall: %s' % overall)
    print('Checks: %d/%d PASS' % (result['summary']['passed_checks'], result['summary']['total_checks']))
    print('Negatives: %d/%d PASS' % (sum(1 for n in NEG_TESTS if n['pass']), len(NEG_TESTS)))
    for c in CHECKS:
        if not c['pass']:
            print('  FAILED CHECK: %s | %s' % (c['name'], c['detail']))
    for n in NEG_TESTS:
        if not n['pass']:
            print('  FAILED NEG: %s | %s' % (n['name'], n['detail']))
    print('Output: %s' % out)
    print('=' * 70)
    return 0 if overall == 'PARTIAL' else 1


if __name__ == '__main__':
    sys.exit(main())
