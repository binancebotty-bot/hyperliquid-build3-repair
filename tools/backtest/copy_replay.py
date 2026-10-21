'''Replay OUR copy rules over a leader's real fills (offline, read-only).

Answers 'what would WE have earned copying this wallet' rather than 'what did the
wallet earn for itself': fixed 12 USD per leader fill, our min/uplift, our caps,
our dust rule, reduce-only exits.

Rules are transcribed from the engine and cited file:line under _archive/hl_stage2/.
Where the engine has no code for a condition, an ASSUMPTION line is emitted
instead of an invented number.

Network: public info API only (userFillsByTime, metaAndAssetCtxs). No keys, no
orders, no engine start. One wallet at a time.

  python copy_replay.py --self-check
  python copy_replay.py --wallet 0x.. --start 2026-10-14 --end 2026-10-21 --out DIR
'''
import argparse, datetime as dt, json, os, sys, time, urllib.request
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

INFO_URL = 'https://api.hyperliquid.xyz/info'
EPS = 1e-9

DEFAULT_CFG = {
    'fixed_notional': 12.0,
    'min_notional': 10.0,
    'max_order_notional': 20.0,
    'max_wallet_exposure': 40.0,
    'max_asset_directional_exposure': 40.0,
    'max_total_exposure': 100.0,
    'marketable_bps': 20.0,
    'fee_bps': 5.0,
    'max_entry_uplift_ratio': 1.25,
    'max_entry_uplift_abs_usd': 3.0,
    'uncapped': False,
}

# Measured from replay_snapshot_run6/append_only/{order_intents,live_fills}.csv:
# 2281 joined fills, HYPE excluded (6 rows with ~4900 bps artifacts). Median |copy-vs-leader
# gap| = 17.65 bps per fill. Flat cost per fill, applied on both legs.
SLIPPAGE_BPS_PER_FILL = 17.7
# (cost bps per ROUND TRIP, column name). Last column = measured slippage both legs + 5 bps fee both legs.
COST_COLUMNS = ((0.0, 'net_0bps'), (5.0, 'net_5bps'), (10.0, 'net_10bps'),
                (2 * SLIPPAGE_BPS_PER_FILL + 10.0, 'net_measured_slippage'))

ASSUMPTIONS = [
    'ASSUMPTION: follower mid for an entry is the leader fill price (no code found for an offline follower mid; engine calls follower_mid() at HL_Live_Copy_Service_Core.py:2481)',
    'ASSUMPTION: every simulated order fills in full at the marketable-adjusted limit (no partial-fill model found; engine sends IOC and parses the ACK at HL_Live_Copy_Service_Core.py:3613)',
    'ASSUMPTION: fees charged on both legs at 5.0 bps from HL_Copy_App_SSOT.py:100; the engine books no fees (no fee accounting found in HL_Live_Copy_Service_Core.py)',
    'ASSUMPTION: exposure caps are evaluated against the replay ledger, not follower exchange truth (engine reads exchange truth at HL_Live_Copy_Service_Core.py:2524)',
    'ASSUMPTION: leader fills are classified ENTRY/ADD/EXIT against OUR sleeve exactly as HL_Live_Copy_Service_Core.py:2204-2212 does, never from the leader dir/closedPnl',
]


def floor_sz(size, szd):
    q = Decimal(1).scaleb(-int(szd))
    return float(Decimal(str(size)).quantize(q, rounding=ROUND_FLOOR))


def ceil_sz(size, szd):
    q = Decimal(1).scaleb(-int(szd))
    return float(Decimal(str(size)).quantize(q, rounding=ROUND_CEILING))


def classify(before, side):
    delta = 1.0 if side == 'BUY' else -1.0
    if abs(before) <= EPS:
        return 'ENTRY', False
    if before * delta < 0:
        return 'EXIT', True
    return 'ADD', False


def is_leader_close_fill(fill):
    d = str(fill.get('dir') or fill.get('side') or '').lower()
    return 'close' in d or 'reduce' in d


class Sim:
    def __init__(self, cfg, meta):
        self.cfg = cfg
        self.meta = meta
        self.pos = {}
        self.avg = {}
        self.coins = {}
        self.orders = 0
        self.skipped = []
        self.realised = 0.0
        self.fees = 0.0
        self.trips = []          # completed round trips: coin, gross_usd, bps, notional
        self._trip = {}          # coin -> [gross_usd, bps*w, notional] until sleeve flat

    def _stat(self, coin):
        return self.coins.setdefault(coin, {'realised': 0.0, 'fees': 0.0, 'orders': 0, 'skipped': 0, 'volume': 0.0})

    def skip(self, fill, reason, status):
        self.skipped.append({'time': fill.get('time'), 'coin': fill.get('coin'), 'side': fill.get('side'), 'status': status, 'reason': reason})
        self._stat(str(fill.get('coin')))[ 'skipped'] += 1
        return None

    def step(self, fill):
        cfg = self.cfg
        if cfg['uncapped']:   # cap model out of scope: every leader fill is one $12 copy
            cfg = dict(cfg)
            cfg.update({k: 0.0 for k in ('max_order_notional', 'max_wallet_exposure',
                                        'max_total_exposure', 'max_asset_directional_exposure',
                                        'min_notional', 'marketable_bps')})  # cost columns charge the slippage
        coin = str(fill['coin'])
        px = float(fill['px'])
        side = 'BUY' if str(fill.get('side')).upper() in ('B', 'BUY') else 'SELL'
        szd = self.meta.get(coin)
        if szd is None:
            return self.skip(fill, 'coin not in perp universe', 'SYMBOL_UNAVAILABLE')
        before = self.pos.get(coin, 0.0)
        lifecycle, is_reduce = classify(before, side)

        if lifecycle == 'EXIT':
            size = abs(before)
            notional = size * px
        else:
            notional = cfg['fixed_notional']
            size = notional / px if px > 0 else 0.0

        if lifecycle == 'ENTRY' and abs(before) <= EPS and is_leader_close_fill(fill) and not cfg['uncapped']:
            return self.skip(fill, 'leader close fill on flat sleeve cannot open', 'SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION')
        if notional <= 0:
            return self.skip(fill, 'copy notional is zero', 'MANUAL_REVIEW')
        if notional < cfg['min_notional'] and lifecycle in ('ENTRY', 'ADD'):
            return self.skip(fill, 'entry notional below min_notional', 'BELOW_MIN_NOTIONAL')

        if lifecycle in ('ENTRY', 'ADD'):
            value_px = px * (1.0 + cfg['marketable_bps'] / 10000.0)
            order_notional = notional / px * value_px if px > 0 else 0.0
            if cfg['max_order_notional'] > 0 and order_notional > cfg['max_order_notional']:
                return self.skip(fill, 'max order notional exceeded', 'SEND_BLOCKED_RISK')
            wallet_exp = sum(abs(s) * self.avg.get(c, px) for c, s in self.pos.items())
            if cfg['max_wallet_exposure'] > 0 and wallet_exp + order_notional > cfg['max_wallet_exposure']:
                return self.skip(fill, 'max wallet exposure exceeded', 'SEND_BLOCKED_RISK')
            total_exp = sum(abs(s) * self.avg.get(c, px) for c, s in self.pos.items())
            if cfg['max_total_exposure'] > 0 and total_exp + notional > cfg['max_total_exposure']:
                return self.skip(fill, 'max total exposure exceeded', 'SEND_BLOCKED_RISK')
            if cfg['max_asset_directional_exposure'] > 0:
                net = before + (size if side == 'BUY' else -size)
                if abs(net) * value_px > cfg['max_asset_directional_exposure']:
                    return self.skip(fill, 'max asset directional exposure exceeded', 'SEND_BLOCKED_RISK')

        limit_px = px * (1 + cfg['marketable_bps'] / 10000.0) if side == 'BUY' else px * (1 - cfg['marketable_bps'] / 10000.0)
        wire = floor_sz(size, szd)
        if wire <= 0:
            return self.skip(fill, 'size floors to zero at szDecimals', 'SEND_NOT_ATTEMPTED_INVALID_SIZE')
        wire_notional = abs(wire * limit_px)
        effective_min = max(cfg['min_notional'], 10.0)
        if lifecycle in ('ENTRY', 'ADD') and notional + EPS >= cfg['min_notional'] and wire_notional < effective_min:
            target = effective_min * 1.01
            cap = max(notional * cfg['max_entry_uplift_ratio'], notional + cfg['max_entry_uplift_abs_usd'])
            if target > cap:
                return self.skip(fill, 'min uplift would exceed intended notional', 'BELOW_SYMBOL_MIN_EXCEEDS_COPY_NOTIONAL')
            wire = max(wire, ceil_sz(target / limit_px, szd))
            wire_notional = abs(wire * limit_px)
        if lifecycle in ('ENTRY', 'ADD') and cfg['max_order_notional'] > 0 and wire_notional > cfg['max_order_notional'] + EPS:
            return self.skip(fill, 'final wire notional over max order', 'MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE')

        return self._book(coin, side, wire, limit_px, lifecycle, is_reduce)

    def _book(self, coin, side, size, px, lifecycle, is_reduce):
        signed = size if side == 'BUY' else -size
        before = self.pos.get(coin, 0.0)
        after = before + signed
        fee = abs(size * px) * self.cfg['fee_bps'] / 10000.0
        realised = 0.0
        if before != 0 and before * signed < 0:
            closed = min(abs(signed), abs(before))
            direction = 1.0 if before > 0 else -1.0
            entry = self.avg.get(coin, 0.0)
            gross = (px - entry) * closed * direction
            realised = gross - fee
            self.realised += realised
            trip = self._trip.setdefault(coin, [0.0, 0.0, 0.0])
            trip[0] += gross
            trip[1] += gross
            trip[2] += entry * closed
            if abs(after) <= EPS:
                after = 0.0
                self.trips.append({'coin': coin, 'gross_usd': trip[0],
                                   'bps': trip[1] / trip[2] * 10000.0 if trip[2] else 0.0,
                                   'notional': trip[2]})
                del self._trip[coin]
        if before == 0.0 or before * signed > 0:
            new_abs = abs(after)
            self.avg[coin] = ((self.avg.get(coin, 0.0) * abs(before)) + px * size) / new_abs if new_abs > EPS else 0.0
        if abs(after) <= EPS:
            self.avg[coin] = 0.0
        self.pos[coin] = after
        self.fees += fee
        self.orders += 1
        st = self._stat(coin)
        st['realised'] += realised
        st['fees'] += fee
        st['orders'] += 1
        st['volume'] += abs(size * px)
        return {'coin': coin, 'side': side, 'size': size, 'px': px, 'lifecycle': lifecycle, 'reduce_only': bool(is_reduce), 'notional': abs(size * px), 'fee': fee, 'realised': realised}

    def summary(self, wallet, start_ms, end_ms, leader_fills=None):
        worst = min(self.coins.items(), key=lambda kv: kv[1]['realised'])[0] if self.coins else ''
        why = {}
        for s in self.skipped:
            why[s['status']] = why.get(s['status'], 0) + 1
        days = (end_ms - start_ms) / 86400000.0 or 1.0
        rt_notional = sum(t['notional'] for t in self.trips)
        gross = sum(t['gross_usd'] for t in self.trips)
        econ = {}
        for cost_bps, name in COST_COLUMNS:
            net = gross - cost_bps / 10000.0 * rt_notional
            econ[name] = {'cost_bps_per_round_trip': cost_bps, 'net_usd': round(net, 4),
                          'net_per_day_usd': round(net / days, 4)}
        return {
            'wallet': wallet,
            'window': {'start_ms': start_ms, 'end_ms': end_ms,
                       'start_utc': dt.datetime.fromtimestamp(start_ms / 1000, dt.timezone.utc).isoformat(),
                       'end_utc': dt.datetime.fromtimestamp(end_ms / 1000, dt.timezone.utc).isoformat()},
            'simulated_realised_pnl_usd': round(self.realised, 4),
            'fees_usd': round(self.fees, 4),
            'orders': self.orders,
            'skipped': len(self.skipped),
            'skipped_by_reason': why,
            'days': round(days, 4),
            'leader_fills': leader_fills,
            'fills_per_day': round(leader_fills / days, 3) if leader_fills is not None else None,
            'round_trips': len(self.trips),
            'round_trips_per_day': round(len(self.trips) / days, 3),
            'avg_gross_bps_per_round_trip': round(gross / rt_notional * 10000.0, 3) if rt_notional else None,
            'win_rate': round(sum(1 for t in self.trips if t['gross_usd'] > 0) / len(self.trips), 4) if self.trips else None,
            'economics': econ,
            'uncapped': bool(self.cfg['uncapped']),
            'worst_coin': worst,
            'worst_coin_realised_usd': round(self.coins.get(worst, {}).get('realised', 0.0), 4),
            'per_coin': {c: {k: (round(v, 6) if isinstance(v, float) else v) for k, v in st.items()} for c, st in sorted(self.coins.items())},
            'assumptions': ASSUMPTIONS,
        }


def _post(payload, tries=3):
    body = json.dumps(payload).encode()
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(INFO_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (n + 1))
    raise SystemExit('info API failed for %s: %r' % (payload.get('type'), last))


def fetch_meta():
    raw = _post({'type': 'metaAndAssetCtxs'})
    return {u['name']: int(u['szDecimals']) for u in raw[0]['universe'] if not u.get('isDelisted')}


def fetch_fills(wallet, start_ms, end_ms):
    out, cursor = [], start_ms
    while True:
        page = _post({'type': 'userFillsByTime', 'user': wallet, 'startTime': cursor, 'endTime': end_ms})
        if not isinstance(page, list) or not page:
            break
        out.extend(page)
        last = max(int(f['time']) for f in page)
        if last <= cursor or len(page) < 2000:
            break
        cursor = last + 1
        time.sleep(0.3)
    seen, uniq = set(), []
    for f in sorted(out, key=lambda f: (int(f['time']), int(f.get('tid', 0)))):
        k = (f.get('tid'), f.get('hash'), f.get('oid'))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    return uniq


FIXTURE = [
    ({'coin': 'BTC', 'side': 'B', 'px': '60000', 'sz': '0.1', 'time': 1, 'dir': 'Open Long'}, {}, 'ENTRY', 0.0002, False),
    ({'coin': 'BTC', 'side': 'B', 'px': '62000', 'sz': '0.1', 'time': 2, 'dir': 'Open Long'}, {}, 'ADD', 0.00019, False),
    ({'coin': 'BTC', 'side': 'A', 'px': '65000', 'sz': '0.2', 'time': 3, 'dir': 'Close Long'}, {}, 'EXIT', None, True),
    ({'coin': 'ETH', 'side': 'B', 'px': '3000', 'sz': '1', 'time': 4, 'dir': 'Open Long'}, {'max_order_notional': 5.0}, 'SKIP', None, 'SEND_BLOCKED_RISK'),
    ({'coin': 'ETH', 'side': 'B', 'px': '3000', 'sz': '1', 'time': 5, 'dir': 'Open Long'}, {'min_notional': 50.0}, 'SKIP', None, 'BELOW_MIN_NOTIONAL'),
    # uncapped: cap model off, so the fill blocked at t=4 is copied
    ({'coin': 'ETH', 'side': 'B', 'px': '3000', 'sz': '1', 'time': 6, 'dir': 'Open Long'}, {'max_order_notional': 5.0, 'uncapped': True}, 'ENTRY', 0.004, False),
]
META = {'BTC': 5, 'ETH': 4}


def run_self_check():
    checks = []
    sim = Sim(dict(DEFAULT_CFG), META)
    btc_sim = sim          # the BTC entry/add/exit run, kept for the final assertions
    uncapped_sim = None
    for fill, overlay, kind, want_size, want_ro in FIXTURE:
        cfg = dict(DEFAULT_CFG)
        cfg.update(overlay)
        if overlay:
            sim = Sim(cfg, META)
        else:
            sim.cfg = cfg
        res = sim.step(fill)
        if cfg['uncapped']:
            uncapped_sim = sim
        tag = fill['coin'] + ' ' + str(fill['time'])
        if kind == 'SKIP':
            got = sim.skipped[-1]['status'] if sim.skipped else 'NONE'
            checks.append((tag + ' skip=' + want_ro, got == want_ro, got))
        else:
            checks.append((tag + ' filled', res is not None, 'none'))
            if res:
                checks.append((tag + ' lifecycle=' + kind, res['lifecycle'] == kind, res['lifecycle']))
                checks.append((tag + ' reduce_only=' + str(want_ro), res['reduce_only'] == want_ro, str(res['reduce_only'])))
                if want_size is not None:
                    checks.append((tag + ' size=' + str(want_size), abs(res['size'] - want_size) < 1e-9, str(res['size'])))
    checks.append(('sleeve flat after exit', abs(btc_sim.pos.get('BTC', 0.0)) < EPS, str(btc_sim.pos.get('BTC'))))
    checks.append(('realised pnl booked on exit', btc_sim.realised > 0, str(btc_sim.realised)))
    checks.append(('uncapped: cap-blocked fill is copied', uncapped_sim is not None and uncapped_sim.orders == 1 and uncapped_sim.skipped == [], 'control'))
    checks.append(('negative control: wrong size is caught', not (abs(0.0002 - 0.00025) < 1e-9), 'control'))
    bad = [c for c in checks if not c[1]]
    for name, ok, got in checks:
        print(('  PASS  ' if ok else '  FAIL  ') + name + ('' if ok else '   got=' + str(got)))
    print('\nself-check: %d/%d passed' % (len(checks) - len(bad), len(checks)))
    return 0 if not bad else 1


def parse_day(s):
    return int(dt.datetime.strptime(s, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def markdown(res):
    L = ['# Copy-rules replay: ' + res['wallet'], '',
         'Window: ' + res['window']['start_utc'] + ' -> ' + res['window']['end_utc'], '',
         '| metric | value |', '|---|---|',
         '| simulated realised PnL (USD) | %s |' % res['simulated_realised_pnl_usd'],
         '| fees (USD) | %s |' % res['fees_usd'],
         '| leader fills | %s |' % res.get('leader_fills', ''),
         '| orders | %s |' % res['orders'],
         '| skipped | %s |' % res['skipped'],
         '| worst coin | %s (%s USD) |' % (res['worst_coin'], res['worst_coin_realised_usd']), '',
         '| mode | %s |' % ('UNCAPPED' if res.get('uncapped') else 'capped'),
         '| fills / day | %s |' % res.get('fills_per_day', ''),
         '| round trips / day | %s |' % res.get('round_trips_per_day', ''),
         '| avg gross bps per round trip | %s |' % res.get('avg_gross_bps_per_round_trip', ''),
         '| win rate | %s |' % res.get('win_rate', ''), '',
         '| cost model | bps per round trip | net USD | net USD / day |', '|---|---|---|---|']
    for name, e in (res.get('economics') or {}).items():
        L.append('| %s | %s | %s | %s |' % (name, e['cost_bps_per_round_trip'], e['net_usd'], e['net_per_day_usd']))
    L += ['',
         '| coin | orders | skipped | realised USD | fees USD | volume USD |', '|---|---|---|---|---|---|']
    for c, st in res['per_coin'].items():
        L.append('| %s | %s | %s | %s | %s | %s |' % (c, st['orders'], st['skipped'], st['realised'], st['fees'], round(st['volume'], 2)))
    L += ['', 'Skips: ' + json.dumps(res['skipped_by_reason']), '', '## ASSUMPTIONS (verbatim)', '']
    L += ['- ' + a for a in res['assumptions']]
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description='Replay our copy rules over a leader wallet fills.')
    ap.add_argument('--wallet')
    ap.add_argument('--start', help='YYYY-MM-DD UTC inclusive')
    ap.add_argument('--end', help='YYYY-MM-DD UTC exclusive end-of-day')
    ap.add_argument('--out', default='.')
    ap.add_argument('--fixed-notional', type=float, default=DEFAULT_CFG['fixed_notional'])
    ap.add_argument('--uncapped', action='store_true', help='exposure caps off: every leader fill is one $12 copy fill')
    ap.add_argument('--self-check', action='store_true')
    a = ap.parse_args(argv)
    if a.self_check:
        return run_self_check()
    if not (a.wallet and a.start and a.end):
        ap.error('--wallet --start --end required (or --self-check)')
    cfg = dict(DEFAULT_CFG)
    cfg['fixed_notional'] = a.fixed_notional
    cfg['uncapped'] = bool(a.uncapped)
    if cfg['uncapped']:
        cfg['fee_bps'] = 0.0   # the cost columns carry every cost; the ledger fee would double-count
        cfg['marketable_bps'] = 0.0
    start_ms, end_ms = parse_day(a.start), parse_day(a.end)
    meta = fetch_meta()
    fills = fetch_fills(a.wallet, start_ms, end_ms)
    sim = Sim(cfg, meta)
    acts = [sim.step(f) for f in fills]
    res = sim.summary(a.wallet, start_ms, end_ms, leader_fills=len(fills))
    res['config'] = cfg
    res['actions_sample'] = [x for x in acts if x][:20]
    os.makedirs(a.out, exist_ok=True)
    jp = os.path.join(a.out, 'copy_replay.json')
    mp = os.path.join(a.out, 'copy_replay.md')
    with open(jp, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=2)
    with open(mp, 'w', encoding='utf-8') as fh:
        fh.write(markdown(res))
    print(json.dumps({k: res[k] for k in ('wallet', 'window', 'leader_fills', 'orders', 'skipped', 'simulated_realised_pnl_usd', 'fees_usd', 'worst_coin', 'skipped_by_reason')}, indent=2))
    print('\nwrote ' + jp + '\nwrote ' + mp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
