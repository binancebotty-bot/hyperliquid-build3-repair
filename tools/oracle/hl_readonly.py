#!/usr/bin/env python3
"""Read-only Hyperliquid /info access for the CC-1 M3 oracle.

Standard library only. No engine imports (GUT I26 / VERIFY-008). Every call here is a
POST to an /info endpoint: no signing, no private key, no writes to the exchange.
"""
import collections, json, os, random, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D

MAINNET = 'https://api.hyperliquid.xyz/info'
TESTNET = 'https://api.hyperliquid-testnet.xyz/info'
PAGE = 2000          # /info userFillsByTime hard page size
MAX_PAGES = 40

# Paced retry: honour Retry-After on 429, else exponential backoff with jitter.
BACKOFF_START_S = 0.5
BACKOFF_CAP_S = 30.0
POST_TRIES = 8
RETRY_AFTER_CAP_S = 120.0
FILL_CACHE_VERSION = 1


def _jitter(x):
    """+/-20% so a retry storm from several wallets does not stay in lockstep."""
    return max(0.05, x * (0.8 + 0.4 * random.random()))


def post(url, payload, tries=POST_TRIES, timeout=30, stats=None):
    """POST /info with paced retry. Never signs, never writes.

    HTTP 429 waits for `Retry-After` when the header is present, otherwise
    exponential backoff from 0.5 s to a 30 s cap with jitter. Other transport
    and 5xx failures take the same exponential path. `stats`, when supplied, is
    filled in place with attempts / last_status / rate_limited / retry_after so
    a caller can tell "rate limited hard" from "gone" instead of one opaque
    string.
    """
    st = {'attempts': 0, 'last_status': None, 'rate_limited': False,
          'retry_after': None, 'errors': []}
    last = None
    delay = BACKOFF_START_S
    for i in range(max(1, tries)):
        st['attempts'] += 1
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode())
                st['last_status'] = 200
                if stats is not None:
                    stats.update(st)
                return body
        except urllib.error.HTTPError as e:
            st['last_status'] = e.code
            detail = ''
            try:
                detail = e.read().decode()[:100].replace('\n', ' ')
            except Exception:
                pass
            last = 'HTTP %s %s' % (e.code, detail)
            st['errors'].append(last)
            wait = None
            if e.code == 429:
                st['rate_limited'] = True
                ra = None
                try:
                    ra = (e.headers or {}).get('Retry-After')
                except Exception:
                    ra = None
                if ra:
                    st['retry_after'] = ra
                    try:
                        wait = min(max(float(str(ra).strip()), 0.5), RETRY_AFTER_CAP_S)
                    except ValueError:
                        wait = None
            if wait is None:
                wait = _jitter(min(delay, BACKOFF_CAP_S))
            delay = min(delay * 2.0, BACKOFF_CAP_S)
            time.sleep(wait)
            continue
        except Exception as e:
            last = '%s: %s' % (type(e).__name__, str(e)[:120])
            st['errors'].append(last)
            time.sleep(_jitter(min(delay, BACKOFF_CAP_S)))
            delay = min(delay * 2.0, BACKOFF_CAP_S)
    if stats is not None:
        stats.update(st)
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


def _cache_path(wallet, since_ms, cache_dir):
    return os.path.join(cache_dir, '%s_%d.json' % (wallet.lower(), int(since_ms)))


def load_fill_cache(wallet, since_ms, cache_dir):
    """Return (cache_dict|None, path). None when the key does not match exactly."""
    p = _cache_path(wallet, since_ms, cache_dir)
    try:
        with open(p, encoding='utf-8') as fh:
            d = json.load(fh)
    except Exception:
        return None, p
    if (d.get('version') != FILL_CACHE_VERSION
            or str(d.get('wallet', '')).lower() != wallet.lower()
            or int(d.get('since_ms', -1)) != int(since_ms)):
        return None, p
    return d, p


def save_fill_cache(path, d):
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(d, fh)
    os.replace(tmp, path)


def leader_fills(wallet, baseline_ms, url=MAINNET, stats=None, cache_dir=None,
                 page_gap=0.35):
    """Forward pagination of mainnet fills strictly after the copy baseline.

    Serial with spacing on purpose: mainnet /info rate-limits parallel paging into
    HTTP 429 storms, and a 429 here would silently truncate a leader's history.
    Each page is retried by `post` (Retry-After, else exponential backoff+jitter).

    When `cache_dir` is given, every completed page is persisted keyed by
    (wallet, since_ms, cursor) and a re-run resumes from the stored tail instead of
    re-fetching the whole window.

    Returns (fills, pages_fetched, capped). `pages_fetched` counts live requests only;
    `stats` receives cache/pacing detail.
    """
    st = {'pages_fetched': 0, 'pages_reused': 0, 'attempts': 0, 'last_status': None,
          'rate_limited': False, 'cache': None}
    cur, out, fetched, capped = int(baseline_ms) + 1, [], 0, False
    cache = None
    cpath = None
    if cache_dir:
        cache, cpath = load_fill_cache(wallet, baseline_ms, cache_dir)
    if cache:
        for pg in cache.get('pages') or []:
            out.extend(pg.get('fills') or [])
            st['pages_reused'] += 1
        if (cache.get('pages') or []):
            cur = int(cache['pages'][-1]['next_cursor'])
        st['cache'] = cpath
    if cache is not None and cache.get('complete'):
        # stored window was fully walked; still poll once for the new tail below
        pass
    if cache is None:
        cache = {'version': FILL_CACHE_VERSION, 'wallet': wallet, 'since_ms': int(baseline_ms),
                 'pages': [], 'complete': False,
                 'fetched_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}

    while fetched < MAX_PAGES:
        pst = {}
        pg = post(url, {'type': 'userFillsByTime', 'user': wallet,
                        'startTime': cur, 'aggregateByTime': False}, stats=pst)
        fetched += 1
        st['pages_fetched'] += 1
        st['attempts'] += pst.get('attempts') or 0
        st['last_status'] = pst.get('last_status')
        if pst.get('rate_limited'):
            st['rate_limited'] = True
        if not pg:
            cache['complete'] = True
            break
        out.extend(pg)
        if len(pg) < PAGE:
            cache['pages'].append({'cursor': cur, 'next_cursor': int(pg[-1]['time']) + 1,
                                   'fills': pg})
            cache['complete'] = True
            break
        nxt = pg[-1]['time'] + 1
        if nxt <= cur:
            capped = True
            break
        cache['pages'].append({'cursor': cur, 'next_cursor': nxt, 'fills': pg})
        cur = nxt
        if cpath:
            save_fill_cache(cpath, cache)
        time.sleep(page_gap)
    else:
        capped = True
    if capped:
        cache['complete'] = False
    cache['fetched_at_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if cpath:
        try:
            save_fill_cache(cpath, cache)
        except Exception:
            pass
    if stats is not None:
        stats.update(st)
    return out, fetched, capped


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
