#!/usr/bin/env python3
"""The health banner must not cry RED for rejections the engine expects.

Boss, 2026-10-26: the Command Centre said "Needs a look: copy rows are still active red". The rows behind it were
14 exchange rejections in the last hour, every one of them benign: 7 `MARKET_HALTED` ("Trading is halted.") and 7
IOC no-immediate-match ("Order could not immediately match against any resting orders"). The engine records each
one, moves on, and its own status line already names the last one.

A banner that names nothing and implies a fault on expected, handled outcomes trains an operator to ignore it - which
is worse than no banner, because the one time it means something they will not look.

So: an expected rejection is AMBER under its own state; anything outside the expected set keeps RED.
FAILING FIRST on the pre-fix UI: MARKET_HALTED rows were RED and is_active.
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Copy_App_SSOT as U  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


NOW = int(time.time() * 1000)


def attempt(cat, err, age_ms=60_000, aid='a1', coin='ZK'):
    # the built rows do not carry attempt_id, so each fixture gets its own coin to be addressable
    return {'attempt_id': aid, 'intent_id': 'i-' + aid, 'coin': coin, 'side': 'B', 'status': 'ORDER_REJECTED',
            'reject_category': cat, 'error': err, 'created_at_ms': str(NOW - age_ms),
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime()), 'terminal_state': 'ORDER_REJECTED'}


rows = U._build_execution_quality_rows(
    [attempt('MARKET_HALTED', 'Trading is halted.', 60_000, 'halted', 'HALTEDCOIN'),
     attempt('IOC_NO_IMMEDIATE_MATCH', 'Order could not immediately match against any resting orders', 60_000, 'ioc', 'IOCCOIN'),
     attempt('', 'Order could not immediately match against any resting orders', 60_000, 'ioc-nocat', 'NOCATCOIN'),
     attempt('SIGNATURE_INVALID', 'invalid signature', 60_000, 'bad', 'BADCOIN'),
     attempt('MARKET_HALTED', 'Trading is halted.', 6 * 3600 * 1000, 'old', 'OLDCOIN')],
    [])
by = {r.get('coin'): r for r in rows}

check('A_HALTED_MARKET_IS_NOT_RED', by.get('HALTEDCOIN', {}).get('truth_severity') != 'RED',
      'MARKET_HALTED came out %r' % (by.get('HALTEDCOIN', {}).get('truth_severity'),))
check('AN_IOC_NO_MATCH_IS_NOT_RED', by.get('IOCCOIN', {}).get('truth_severity') != 'RED',
      'IOC_NO_IMMEDIATE_MATCH came out %r' % (by.get('IOCCOIN', {}).get('truth_severity'),))
check('AN_EXPECTED_REJECT_IS_STILL_VISIBLE', by.get('HALTEDCOIN', {}).get('is_active') is True,
      'an expected rejection vanished from the active set instead of being downgraded')
check('AN_EXPECTED_REJECT_IS_NAMED', 'EXPECTED' in str(by.get('HALTEDCOIN', {}).get('truth_state')),
      'state = %r - the banner cannot say why' % (by.get('HALTEDCOIN', {}).get('truth_state'),))
check('AN_UNEXPECTED_REJECTION_KEEPS_RED', by.get('BADCOIN', {}).get('truth_severity') == 'RED',
      'SIGNATURE_INVALID came out %r - a real fault must stay red' % (by.get('BADCOIN', {}).get('truth_severity'),))
check('AN_UNEXPECTED_REJECTION_IS_ACTIVE', by.get('BADCOIN', {}).get('is_active') is True,
      'a real fault is no longer in the active set')
check('AN_OLD_REJECTION_IS_NOT_ACTIVE', by.get('OLDCOIN', {}).get('is_active') is False,
      'a six-hour-old rejection still counts as active')
check('THE_ERROR_TEXT_ALONE_ALSO_CLASSIFIES', by.get('NOCATCOIN', {}).get('truth_severity') != 'RED',
      'a rejection with no category but a known error text stayed RED')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
