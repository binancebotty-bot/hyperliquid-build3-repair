#!/usr/bin/env python3
"""Read-only Hyperliquid /info access for the CC-1 M3 oracle.

Standard library only. No engine imports (GUT I26 / VERIFY-008). Every call here is a
POST to an /info endpoint: no signing, no private key, no writes to the exchange.
"""
import collections, json, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D

MAINNET = 'https://api.hyperliquid.xyz/info'
TESTNET = 'https://api.hyperliquid-testnet.xyz/info'
PAGE = 2000          # /info userFillsByTime hard page size
MAX_PAGES = 40


def post(url, payload, tries=5, timeout=30):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = 'HTTP %s %s' % (e.code, e.read().decode()[:100].replace('\n', ' '))
            time.sleep(1.5 * (i + 1) if e.code == 429 else 0.5 * (i + 1))
            continue
        except Exception as e:
            last = '%s: %s' % (type(e).__name__, str(e)[:120])
        time.sleep(0.5 * (i + 1))
    raise RuntimeError(last or 'transport error')


def dec(s, d=None):
    if s is None or str(s).strip() == '':
        return d
    try:
        return D(str(s).strip())
    except Exception:
        return d


def live_dexes(url):
    """[''] plus every named perp DEX that actually lists assets.

    perpDexs returns ~277 testnet entries, most empty shells that answer HTTP 429 to
    every query. A DEX that lists assets advertises them in assetToStreamingOiCap /
    assetToFundingMultiplier; filtering on that turns 277 noisy probes into the ~85 that
    can hold a position. Skipped names are counted and reported, never dropped silently.
    """
    try:
        raw = post(url, {'type': 'perpDexs'})
    except Exception as e:
        return [''], [], 'perpDexs failed: %s' % str(e)[:140]
    keep, skipped = [], []
    for x in raw:
        if not isinstance(x, dict) or not x.get('name'):
            continue
        if x.get('assetToStreamingOiCap') or x.get('assetToFundingMultiplier'):
            keep.append(x['name'])
        else:
            skipped.append(x['name'])
    return [''] + keep, skipped, None


def account(url, user, dex):
    """clearinghouseState + openOrders for one DEX. Raises only on clearinghouseState
    failure; an openOrders failure is returned so the caller can mark it unreadable."""
    p = {'type': 'clearinghouseState', 'user': user}
    if dex:
        p['dex'] = dex
    st = post(url, p) or {}
    q = {'type': 'openOrders', 'user': user}
    if dex:
        q['dex'] = dex
    try:
        oo, oerr = post(url, q) or [], None
    except Exception as e:
        oo, oerr = None, str(e)[:120]
    return st, oo, oerr


def read_positions(user, url, workers=6):
    """FRESH multi-DEX position read. Returns (coin->signed size, orders, report)."""
    dexs, skipped, enum_err = live_dexes(url)
    pos = collections.defaultdict(D)
    orders = []
    rep = {'dexes_enumerated': len(dexs), 'dexes_skipped_empty': len(skipped),
           'dexes_read': [], 'dexes_failed': [], 'dexes_with_positions': [],
           'dexes_with_orders': [], 'enum_error': enum_err}

    def one(dx):
        try:
            return dx, account(url, user, dx), None
        except Exception as e:
            return dx, None, str(e)[:140]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(one, dexs))
    for dx, val, err in res:
        lb = dx or '(default)'
        if err:
            rep['dexes_failed'].append({'dex': lb, 'error': err})
            continue
        rep['dexes_read'].append(lb)
        st, oo, oerr = val
        ap = st.get('assetPositions') or []
        if ap:
            rep['dexes_with_positions'].append(lb)
        for a in ap:
            p = a.get('position') or {}
            szi = dec(p.get('szi'), D(0))
            if p.get('coin') and szi:
                pos[p['coin']] += szi
        if oo is None:
            rep['dexes_failed'].append({'dex': lb, 'error': 'openOrders: %s' % oerr})
            continue
        if oo:
            rep['dexes_with_orders'].append(lb)
        for o in oo:
            orders.append({'dex': dx, 'oid': o.get('oid'), 'coin': o.get('coin'),
                           'side': o.get('side'), 'sz': dec(o.get('sz'), D(0)),
                           'cloid': o.get('cloid'),
                           'reduceOnly': bool(o.get('reduceOnly'))})
    return dict(pos), orders, rep


def prove_orders(orders, user, url, workers=4):
    """IN_FLIGHT leg. An order counts only if orderStatus resolves to status 'order'.

    Anything else - an unreadable oid, an HTTP failure, a missing cloid, a payload we
    do not recognise - is returned with status_error set and is NEVER treated as zero
    in flight. Order-status queries on this venue must not be given a dex parameter:
    the dex argument is silently ignored and the query is answered against the default
    DEX, so a HIP-3 order would come back 'unknownOid' regardless of its real state.
    """
    def one(o):
        r = dict(o); r['status'] = None; r['status_error'] = None
        if o.get('oid') is None:
            r['status_error'] = 'openOrders row has no oid'
            return r
        try:
            s = post(url, {'type': 'orderStatus', 'user': user, 'oid': o['oid']}) or {}
        except Exception as e:
            r['status_error'] = '%s: %s' % (type(e).__name__, str(e)[:90])
            return r
        r['status'] = s.get('status')
        if s.get('status') == 'order':
            inner = ((s.get('order') or {}).get('order') or {})
            r['status_coin'] = inner.get('coin')
            r['status_cloid'] = inner.get('cloid')
            r['status_dex_agnostic'] = True
        elif s.get('status') in ('filled', 'canceled', 'rejected', 'marginCanceled',
                                 'triggered', 'unknownOid', 'waitingForTrigger'):
            pass
        else:
            r['status_error'] = 'unrecognised orderStatus %s' % json.dumps(s)[:100]
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, orders))


def all_mids(url, dex=None):
    p = {'type': 'allMids'}
    if dex:
        p['dex'] = dex
    try:
        return post(url, p) or {}
    except Exception:
        return {}


def price_map(url, extra_dex='xyz'):
    out = {}
    for src in (all_mids(url), all_mids(url, extra_dex)):
        for k, v in src.items():
            d = dec(v)
            if d and k not in out:
                out[k] = d
    return out


def leader_fills(wallet, baseline_ms, url=MAINNET):
    """Forward pagination of mainnet fills strictly after the copy baseline.

    Serial with spacing on purpose: mainnet /info rate-limits parallel paging into
    HTTP 429 storms, and a 429 here would silently truncate a leader's history.
    Returns (fills, pages, capped).
    """
    cur, out, pages, capped = baseline_ms + 1, [], 0, False
    while pages < MAX_PAGES:
        pg = post(url, {'type': 'userFillsByTime', 'user': wallet,
                        'startTime': cur, 'aggregateByTime': False})
        pages += 1
        if not pg:
            break
        out.extend(pg)
        if len(pg) < PAGE:
            break
        nxt = pg[-1]['time'] + 1
        if nxt <= cur:
            capped = True
            break
        cur = nxt
        time.sleep(0.35)
    else:
        capped = True
    return out, pages, capped


def replay(fills):
    """Per coin: signed net of the given fills, fill count, last fill time."""
    by = collections.defaultdict(list)
    for f in fills:
        by[f['coin']].append(f)
    out = {}
    for coin, rows in by.items():
        rows.sort(key=lambda r: (r['time'], r.get('tid') or 0))
        net, ok = D(0), True
        for r in rows:
            sz = dec(r.get('sz'))
            if sz is None:
                ok = False
                continue
            net += sz if r.get('side') == 'B' else -sz
        out[coin] = {'net': net if ok else None, 'n': len(rows),
                     'last_ms': rows[-1]['time']}
    return out
