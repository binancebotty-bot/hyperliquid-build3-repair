"""ENG-INV-08 offline half: startup/recovery truth covers every perp DEX scope
(default + HIP-3/builder) and a missing required scope fails closed.

Offline only: one fake /info double, no orders, no keys, no live exchange call.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


class FakeInfo:
    def __init__(self, dexes=('',), states=None, fail_enum=False, fail_scopes=()):
        self.dexes, self.states = list(dexes), states or {}
        self.fail_enum, self.fail_scopes = fail_enum, set(fail_scopes)
        self.calls = []

    def __call__(self, payload):
        self.calls.append(dict(payload))
        kind = payload.get('type')
        if kind == 'perpDexs':
            if self.fail_enum:
                raise RuntimeError('dex enumeration unavailable')
            return [{'name': d} for d in self.dexes if d]
        if kind == 'clearinghouseState':
            dex = payload.get('dex', '')
            if dex in self.fail_scopes:
                raise RuntimeError('scope %s unavailable' % dex)
            return {'assetPositions': [{'position': {'coin': c, 'szi': str(s)}}
                                       for c, s in self.states.get(dex, {}).items()]}
        raise RuntimeError('unexpected payload %r' % (payload,))


def cases():
    tmp = Path(tempfile.mkdtemp(prefix='inv08_'))
    import HL_Live_Copy_Service_Core as core
    core.AUDIT_DIR = tmp
    core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = tmp / 'exchange_account_snapshot.json'
    core.USER_WALLET = '0x' + '1' * 40
    rec = lambda: core.ExchangeReconciler(core.ManualLedger(), core.AuditLogWriter())

    f = FakeInfo(dexes=('', 'builder-hip3'),
                 states={'': {'BTC': 1.0}, 'builder-hip3': {'KMBUILD': 2.0}})
    core.EXPOSURE_FETCHER = f
    snap, status = rec().fetch_snapshot()
    pos = (snap or {}).get('positions_by_coin') or {}
    check('INV08_ALL_SCOPES_IN_SNAPSHOT', status == 'SNAPSHOT_OK' and pos.get('BTC') == 1.0
          and pos.get('KMBUILD') == 2.0, '%s %s' % (status, pos))
    check('INV08_BUILDER_SCOPE_QUERIED',
          {'type': 'clearinghouseState', 'user': core.USER_WALLET, 'dex': 'builder-hip3'} in f.calls,
          str(f.calls))
    check('INV08_READ_PATH_PLACES_NO_ORDER',
          all(c.get('type') in ('perpDexs', 'clearinghouseState') for c in f.calls), str(f.calls))

    core.EXPOSURE_FETCHER = FakeInfo(dexes=('',), states={'': {'BTC': 3.0}})
    snap, status = rec().fetch_snapshot()
    check('INV08_SINGLE_SCOPE_UNCHANGED', status == 'SNAPSHOT_OK'
          and ((snap or {}).get('positions_by_coin') or {}).get('BTC') == 3.0, '%s %s' % (status, snap))

    f = FakeInfo(dexes=('', 'builder-hip3'), states={'': {'BTC': 1.0}}, fail_enum=True)
    core.EXPOSURE_FETCHER = f
    snap, status = rec().fetch_snapshot()
    check('INV08_ENUM_FAILURE_FAILS_CLOSED', snap == {} and status != 'SNAPSHOT_OK'
          and not [c for c in f.calls if c.get('type') == 'clearinghouseState'], '%s %s' % (status, f.calls))

    core.EXPOSURE_FETCHER = FakeInfo(dexes=('', 'builder-hip3'),
                                     states={'': {'BTC': 1.0}, 'builder-hip3': {'KMBUILD': 2.0}},
                                     fail_scopes=('builder-hip3',))
    snap, status = rec().fetch_snapshot()
    check('INV08_UNREADABLE_SCOPE_FAILS_CLOSED', snap == {}
          and status.startswith('SNAPSHOT_SCOPE_UNAVAILABLE'), '%s %s' % (status, snap))

    # Recovery read: reloading the persisted two-scope snapshot must still see the builder coin
    # (it lives only in positions_by_coin; raw carries the default scope).
    core.EXPOSURE_FETCHER = FakeInfo(dexes=('', 'builder-hip3'),
                                     states={'': {'BTC': 1.0}, 'builder-hip3': {'KMBUILD': 2.0}})
    rec().fetch_snapshot()
    persisted, err = core.SenderGateway._persisted_exchange_positions()
    check('INV08_PERSISTED_READ_ALL_SCOPES', not err and persisted.get('BTC') == 1.0
          and persisted.get('KMBUILD') == 2.0, '%s %s' % (err, persisted))
    return tmp


MUTATIONS = {
    'a': ('for dex in enum["dexes"]:', 'for dex in [""]:'),
    'b': ('            if not enum.get("ok"):\r\n'
          '                return {}, str(enum.get("status") or "DEX_ENUM_UNAVAILABLE")\r\n',
          '            if not enum.get("ok"):\r\n'
          '                enum = {"ok": True, "dexes": [""]}\r\n'),
    # Recovery read falls back to the default-scope `raw` body, dropping builder positions.
    'c': ('        positions = snapshot.get("positions_by_coin")\r\n',
          '        positions = None\r\n'),
}


def run_copy(mutate=None):
    work = Path(tempfile.mkdtemp(prefix='inv08_mut_'))
    for name in ('exchange_truth.py', 'HL_Live_Copy_Service_Core.py', 'convergence_shadow.py'):
        src = HERE / name
        if src.exists():
            shutil.copy2(src, work / name)
    if mutate:
        target = work / 'HL_Live_Copy_Service_Core.py'
        data = target.read_bytes()
        needle, repl = MUTATIONS[mutate]
        needle, repl = needle.encode(), repl.encode()
        if data.count(needle) != 1:
            return None, 'needle count=%d' % data.count(needle)
        target.write_bytes(data.replace(needle, repl))
    # Pop modules BEFORE importing so the mutated version is loaded
    for mod in ('HL_Live_Copy_Service_Core', 'exchange_truth'):
        sys.modules.pop(mod, None)
    before = len(RESULTS)
    sys.path.insert(0, str(work))
    try:
        cases()
    finally:
        sys.path.pop(0)
        for mod in ('HL_Live_Copy_Service_Core', 'exchange_truth'):
            sys.modules.pop(mod, None)
    subset = RESULTS[before:]
    del RESULTS[before:]  # a reddening mutant must not fail the suite itself
    return sum(1 for _, ok in subset if not ok), len(subset)


def main():
    cases()
    print('BASELINE_TOTAL=%d BASELINE_FAILED=%d'
          % (len(RESULTS), sum(1 for _, ok in RESULTS if not ok)))
    for tag, label in (('a', 'DEX_LIST_FILTERED_TO_DEFAULT'), ('b', 'ENUM_FAILURE_FALLS_BACK_TO_DEFAULT'),
                       ('c', 'PERSISTED_READ_PREFERS_DEFAULT_RAW')):
        failed, total = run_copy(tag)
        if failed is None:
            check('INV08_MUTANT_%s_REDDENS' % label, False, str(total))
        else:
            check('INV08_MUTANT_%s_REDDENS' % label, failed > 0, 'failed=%s/%s' % (failed, total))
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), sum(1 for _, ok in RESULTS if not ok)))
    raise SystemExit(1 if any(not ok for _, ok in RESULTS) else 0)


if __name__ == '__main__':
    main()
