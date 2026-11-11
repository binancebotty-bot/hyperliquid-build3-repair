#!/usr/bin/env python3
"""The UI must report the send mode the engine is actually honouring.

Defect (Boss looking at it, 2026-10-26 08:19Z): the Command Centre showed SENDING **OFF** on a pair that had filled
167 orders. The file said `global_controls.send_mode: "ON"`.

Root cause: `_GLOBAL_CONTROLS_DEFAULTS` models only the numeric controls, and `_normalise_global_controls` rebuilt
the dict from those defaults - so `send_mode` was DROPPED, `/api/global-controls` returned `send_mode: None`, and
`_send_mode` fell through to `auto_send_enabled` (absent) and then to the env default `OFF`.

This is the worst thing this page can say: an operator reading "SENDING OFF" while orders go out will draw the wrong
conclusion about their own exposure. The normaliser now passes through any control it does not model, verbatim.

FAILING FIRST on 2e44573: send_mode is absent from the normalised dict and _send_mode returns OFF.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Copy_App_SSOT as U  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


def mode(controls):
    return U._send_mode({'global_controls': U._normalise_global_controls(controls)})


# the live shape: the file has send_mode ON and no auto_send_enabled at all
live = {'send_mode': 'ON', 'max_total_live_exposure_usd': 900.0, 'max_wallet_exposure_usd': 400.0,
        'max_asset_directional_exposure_usd': 300.0, 'max_daily_loss_usd': 100.0}

check('SEND_MODE_SURVIVES_NORMALISATION', U._normalise_global_controls(live).get('send_mode') == 'ON',
      'normalised controls = %r' % (sorted(U._normalise_global_controls(live)),))
check('A_SENDING_PAIR_NEVER_DISPLAYS_OFF', mode(live) == 'ON',
      '_send_mode returned %r for send_mode=ON - the page would tell an operator sending is off' % (mode(live),))
check('OFF_IS_STILL_OFF', mode(dict(live, send_mode='OFF')) == 'OFF', 'got %r' % (mode(dict(live, send_mode='OFF')),))
check('CLOSE_ONLY_IS_STILL_CLOSE', mode(dict(live, send_mode='CLOSE')) == 'CLOSE',
      'got %r' % (mode(dict(live, send_mode='CLOSE')),))
check('THE_NUMERIC_CONTROLS_ARE_STILL_NUMBERS',
      all(isinstance(U._normalise_global_controls(live).get(k), float)
          for k in ('max_total_live_exposure_usd', 'max_wallet_exposure_usd', 'max_daily_loss_usd')),
      'a numeric control stopped being coerced to a number')
check('AN_UNKNOWN_CONTROL_IS_PASSED_THROUGH_UNTOUCHED',
      U._normalise_global_controls({'some_future_mode': 'X'}).get('some_future_mode') == 'X',
      'a control the defaults do not model was dropped again')
check('AN_EMPTY_CONFIG_STILL_LOADS_DEFAULTS',
      U._normalise_global_controls({}).get('marketable_bps') == 20.0,
      "Boss's 20 bps default was lost")

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
