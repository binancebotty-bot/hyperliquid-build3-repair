#!/usr/bin/env python3
"""No-trade fixture must not publish a 'reconciliation_gap' between two different scopes.

Defect (#81 6323126438): reconciliation_gap = net_account_change - attributed_open_pnl
subtracted a UNIFIED spot-USDC delta (14.55) from a sum of per-wallet copy live_net_pnl
(-44.11) and published 58.66 as if it were an unexplained loss.

  - both published terms are same-scope: residual 0 on a no-trade fixture
  - no 'reconciliation_gap' key is published (scopes differ; their difference is not a gap)
  - REVERT CONTROL: the same #81 pair on base 91bd8ef9 still publishes 58.66 (RED on base)

Run: python test_g4_reconciliation_scope.py     # RESULT:: markers, exit 0/1
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_REF = '91bd8ef9'
RESULTS = []


def check(name: str, cond: bool, detail: str = '') -> None:
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


def snapshot(unified: float) -> dict:
    return {'account_address': '0xfixture', 'unified_portfolio_value': unified,
            'unified_portfolio_value_source': 'spotClearinghouseState.balances[coin=USDC].total',
            'updated_at': '2026-01-01T00:00:00Z', 'available': True}


def seed_baseline(module, audit_dir: Path) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / 'exchange_baselines.json'
    path.write_text(json.dumps({'account_reconciliation': {'0xfixture': {
        'account_address': '0xfixture', 'baseline_unified_portfolio_value': 1000.0,
        'baseline_timestamp': '2026-01-01T00:00:00Z'}}}), encoding='utf-8')
    module.EXCHANGE_BASELINES_JSON = path


def load_base_module(tmp: Path):
    """Base 91bd8ef9 UI module imported from a scratch dir, so its DATA_DIR is scratch too."""
    src = subprocess.run(['git', '-C', str(HERE), 'show', f'{BASE_REF}:_archive/hl_stage2/HL_Copy_App_SSOT.py'],
                         capture_output=True, text=True, check=True).stdout
    base_dir = tmp / 'base'
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / 'HL_Copy_App_SSOT_base.py').write_text(src, encoding='utf-8')
    (base_dir / 'exchange_truth.py').write_text((HERE / 'exchange_truth.py').read_text(encoding='utf-8'), encoding='utf-8')
    sys.path.insert(0, str(base_dir))
    import HL_Copy_App_SSOT_base as base
    return base


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix='g4recon_'))
    os.environ['HL_LIVE_AUDIT_DIR'] = str(tmp)
    os.environ['HL_LIVE_AUTO_SEND_ENABLED'] = '0'
    os.environ['HL_LIVE_POLL_ENABLED'] = '0'
    sys.path.insert(0, str(HERE))

    import HL_Copy_App_SSOT as ui
    seed_baseline(ui, tmp / 'fixed')

    out = ui._build_account_reconciliation(snapshot(1000.0), {})  # no trade, nothing attributed
    residual = round(out['net_account_value_change_unadjusted'] - out['attributed_open_pnl'], 6)
    check('FIXED_NO_TRADE_SAME_SCOPE_RESIDUAL_IS_ZERO', residual == 0.0, f'residual={residual}')
    check('FIXED_PUBLISHES_NO_RECONCILIATION_GAP', 'reconciliation_gap' not in out, f'keys={sorted(out)}')
    check('FIXED_STILL_PUBLISHES_BOTH_TERMS',
          'net_account_value_change_unadjusted' in out and 'attributed_open_pnl' in out)
    check('FIXED_NO_TRADE_ATTRIBUTION_ZERO', out['attributed_open_pnl'] == 0.0, f"attributed={out.get('attributed_open_pnl')}")

    # REVERT CONTROL: base still turns the #81 pair into a published 58.66 "gap".
    base = load_base_module(tmp)
    seed_baseline(base, tmp / 'base')
    base_out = base._build_account_reconciliation(snapshot(1014.55), {'0xleader': {'live_net_pnl': -44.11}})
    base_gap = base_out.get('reconciliation_gap')
    check('BASE_91BD8EF9_PUBLISHES_THE_NONZERO_GAP', base_gap is not None and abs(base_gap) > 1e-9, f'gap={base_gap!r}')
    check('BASE_91BD8EF9_GAP_IS_58_66', base_gap == 58.66, f'gap={base_gap!r}')

    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
