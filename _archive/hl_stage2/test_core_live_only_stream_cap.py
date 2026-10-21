#!/usr/bin/env python3
"""The 10-slot leader stream counts LIVE only; CLO rides REST polling, never a websocket slot.

Controller ruling 6313307039: a swapped-out wallet goes CLO (close-only) and is followed by polling
only, so all 10 WS slots stay free for the 10 fully-copied wallets. Before this, active_wallets()
counted CLO, stream_wallets() gave CLO the scarce WS slots, and the startup gate refused
10 LIVE + 8 CLO with TOO_MANY_ACTIVE_WALLETS.

L: 10 LIVE + 8 CLO starts; 11 LIVE is still refused; stream_wallets() is exactly the LIVE wallets;
   poll_wallets() still covers every CLO and every LIVE; a 429 on the poll path leaves the wallet
   modes byte-identical (a rate limit never flips a mode).

Run: python test_core_live_only_stream_cap.py   # RESULT:: markers, exit 0/1. Offline, no orders.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


def wallets(n_live, n_clo=0):
    out = {}
    for i in range(n_live):
        out['0x%040x' % (0xB000 + i)] = {'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed'}
    for i in range(n_clo):
        out['0x%040x' % (0xC000 + i)] = {'enabled': True, 'mode': 'CLO'}
    return out


def main():
    tmp = Path(tempfile.mkdtemp(prefix='livecap_'))
    base_env = {k: v for k, v in os.environ.items() if not k.startswith('HL_')}
    base_env.update({'HL_LIVE_ENV_FILE': str(tmp / 'none.env')})

    import HL_Live_Copy_Service_Core as c

    def write_cfg(run_dir, ws):
        run_dir.mkdir(parents=True, exist_ok=True)
        p = run_dir / 'live_config.json'
        p.write_text(json.dumps({'auto_send_enabled': False, 'wallets': ws, 'global_controls': {}}), encoding='utf-8')
        return p

    def run_once(run_dir):
        e = dict(base_env)
        e['HL_LIVE_AUDIT_DIR'] = str(run_dir)
        return subprocess.run([sys.executable, 'HL_Live_Copy_Service_Core.py', '--once'], cwd=str(HERE),
                              env=e, capture_output=True, text=True, timeout=300)

    # ---- L1: 10 LIVE + 8 CLO is under the cap (this config was refused at 09:52Z) ---------------
    # In-process: the running engine holds the machine-wide instance lock, so a spawned second
    # engine would die on that lock, not on the wallet cap, and pass for the wrong reason.
    d10 = tmp / 'run10'
    cfg10 = write_cfg(d10, wallets(10, 8))
    cm = c.ConfigManager(cfg10)
    check('L1_TEN_LIVE_EIGHT_CLO_NOT_OVER_CAP', cm.live_over_stream_cap() is False,
          'live=%d max=%d' % (len(cm.live_wallets()), c.MAX_WALLETS))
    check('L1_CLO_STILL_ACTIVE_FOR_POLLING', len(cm.active_wallets()) == 18,
          'active=%d' % (len(cm.active_wallets()),))

    # ---- L2: 11 LIVE is still over the cap ------------------------------------------------------
    cm11 = c.ConfigManager(write_cfg(tmp / 'run11', wallets(11)))
    check('L2_ELEVEN_LIVE_OVER_CAP', cm11.live_over_stream_cap() is True, 'live=%d' % (len(cm11.live_wallets()),))
    check('L2_ELEVEN_LIVE_STREAM_STILL_CAPPED', len(cm11.stream_wallets()) == c.MAX_WALLETS,
          str(len(cm11.stream_wallets())))

    # ---- L3: stream_wallets() is exactly the LIVE wallets; no CLO -------------------------------
    stream = cm.stream_wallets()
    live = cm.live_wallets()
    clo = [w for w in cm.wallets() if cm.wallet_mode(w) == 'CLO']
    check('L3_STREAM_IS_THE_TEN_LIVE', len(stream) == 10 and stream == live,
          'stream=%d live=%d' % (len(stream), len(live)))
    check('L3_NO_CLO_IN_STREAM', not (set(clo) & set(stream)),
          'CLO in stream: %s' % (sorted(set(clo) & set(stream)),))
    check('L3_MAX_WALLETS_RESPECTED', len(stream) <= c.MAX_WALLETS, str(len(stream)))

    # ---- L4: poll_wallets() still covers all 8 CLO and every LIVE -------------------------------
    class _Core:
        def __init__(self, cfg):
            self.cfg = cfg
            self.wallets = cfg.stream_wallets()
    polled = c.LiveCopyCore.poll_wallets(_Core(cm))
    check('L4_POLL_COVERS_ALL_CLO', set(clo) <= set(polled), 'missing CLO: %s' % (sorted(set(clo) - set(polled)),))
    check('L4_POLL_COVERS_ALL_LIVE', set(live) <= set(polled), 'missing LIVE: %s' % (sorted(set(live) - set(polled)),))

    # ---- L5: both gates use the one shared rule; the startup message offers CLO -----------------
    src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8-sig')
    check('L5_GATE4_USES_SHARED_RULE', 'self.cfg.live_over_stream_cap()' in src, 'gate 4 not switched')
    check('L5_NO_GATE_COMPARES_ACTIVE_TO_STREAM',
          'set(self.cfg.active_wallets()) <= set(self.cfg.stream_wallets())' not in src,
          'a gate still treats LIVE+CLO as the capped set')
    tail = src.rsplit('TOO_MANY_ACTIVE_WALLETS', 1)   # the STARTUP gate is the last one
    check('L5_STARTUP_GATE_USES_SHARED_RULE', '_cfg.live_over_stream_cap()' in tail[0][-400:],
          tail[0][-200:].strip())
    check('L5_STARTUP_MESSAGE_NAMES_CLO', 'CLO' in tail[1], tail[1][:120])

    # ---- L6: a 429 on the poll path leaves the wallet modes byte-identical ----------------------
    before = cfg10.read_bytes()
    os.environ['HL_LIVE_AUDIT_DIR'] = str(d10)
    core = c.LiveCopyCore(source_csv=tmp / 'none.csv')

    def _limit(*_a, **_k):
        raise RuntimeError('429 Too Many Requests')
    _saved = core.ingestor.poll_hyperliquid_fills
    core.ingestor.poll_hyperliquid_fills = _limit
    try:
        core.run_cycle(use_source_csv=False, poll_live=True)
    except Exception:
        pass
    finally:
        core.ingestor.poll_hyperliquid_fills = _saved
    after = cfg10.read_bytes()
    cm_after = c.ConfigManager(cfg10)
    check('L5_429_LEAVES_CONFIG_BYTES_IDENTICAL', before == after, 'config file rewritten by a 429')
    check('L5_429_NEVER_FLIPS_A_MODE',
          {w: cm_after.wallet_mode(w) for w in cm_after.wallets()} == {w: cm.wallet_mode(w) for w in cm.wallets()},
          'mode changed after 429')

    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
