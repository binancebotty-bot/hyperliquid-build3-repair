"""UI-ROUTE probe for card t_cfcad924.

Read-only against the live app on 127.0.0.1:8023. GET-only: no POST, no state mutation.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8023'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'UI_ROUTE_TRUTH_t_cfcad924.json')

# Sample ids taken from the live app payloads (never guessed).
SAMPLE_WALLET = '0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'

# (row_id, method, path_template, rendered_url, marker_expected)
ROUTES = [
    ('UI-ROUTE-01', 'GET', '/', '/', 'HL Copy'),
    ('UI-ROUTE-02', 'GET', '/model', '/model', 'HL Copy'),
    ('UI-ROUTE-03', 'GET', '/legacy-model', '/legacy-model', 'HL Copy'),
    ('UI-ROUTE-04', 'GET', '/api/model-cache-status', '/api/model-cache-status', 'refresh_status'),
    ('UI-ROUTE-05', 'GET', '/api/state', '/api/state', 'global_controls'),
    ('UI-ROUTE-06', 'GET', '/api/metrics', '/api/metrics', 'wallets'),
    ('UI-ROUTE-07', 'GET', '/api/trades/{wallet}', '/api/trades/' + SAMPLE_WALLET, 'JSON_LIST'),
    ('UI-ROUTE-08', 'GET', '/api/equity/{wallet}', '/api/equity/' + SAMPLE_WALLET, 'JSON_LIST'),
    ('UI-ROUTE-09', 'POST', '/api/wallet-include', None, 'DEFERRED'),
    ('UI-ROUTE-10', 'POST', '/api/wallet-config', None, 'DEFERRED'),
    ('UI-ROUTE-11', 'GET', '/wallet-meta/{wallet}', '/wallet-meta/' + SAMPLE_WALLET, 'Wallet meta'),
    ('UI-ROUTE-12', 'POST', '/api/wallet-meta', None, 'DEFERRED'),
    ('UI-ROUTE-13', 'POST', '/api/admin/purge-wallet', None, 'DEFERRED'),
    ('UI-ROUTE-14', 'GET', '/wallet/{wallet}', '/wallet/' + SAMPLE_WALLET, 'ledger'),
    ('UI-ROUTE-15', 'GET', '/api/ui-state', '/api/ui-state', 'wallet_include'),
    ('UI-ROUTE-16', 'POST', '/api/ui-state', None, 'DEFERRED'),
    ('UI-ROUTE-17', 'POST', '/api/norm', None, 'DEFERRED'),
    ('UI-ROUTE-18', 'POST', '/api/set-wallet-mode', None, 'DEFERRED'),
    ('UI-ROUTE-19', 'POST', '/api/set-all-modes', None, 'DEFERRED'),
    ('UI-ROUTE-20', 'POST', '/api/reset-app-history', None, 'DEFERRED'),
    ('UI-ROUTE-21', 'POST', '/api/snapshot', None, 'DEFERRED'),
    ('UI-ROUTE-22', 'GET', '/sort/{column}', '/sort/wallet', 'HL Copy'),
    ('UI-ROUTE-23', 'GET', '/api/live-config', '/api/live-config', 'global_controls'),
    ('UI-ROUTE-24', 'GET', '/live-copy', '/live-copy', 'live'),
    ('UI-ROUTE-25', 'GET', '/live-copy.json', '/live-copy.json', 'ok'),
    ('UI-ROUTE-26', 'GET', '/api/live-copy-summary', '/api/live-copy-summary', 'ok'),
    ('UI-ROUTE-27', 'GET', '/api/global-controls', '/api/global-controls', 'global_controls'),
    ('UI-ROUTE-28', 'POST', '/api/global-controls', None, 'DEFERRED'),
    ('UI-ROUTE-29', 'GET', '/api/live-ws-health', '/api/live-ws-health', 'health'),
    ('UI-ROUTE-30', 'GET', '/api/live-audit-summary', '/api/live-audit-summary', 'ok'),
    ('UI-ROUTE-31', 'POST', '/api/live-config/add-wallet', None, 'DEFERRED'),
    ('UI-ROUTE-32', 'POST', '/api/live-config/set-wallet', None, 'DEFERRED'),
    ('UI-ROUTE-33', 'POST', '/api/live-config/remove-wallet', None, 'DEFERRED'),
    ('UI-ROUTE-34', 'POST', '/api/live-config/set-mode', None, 'DEFERRED'),
    ('UI-ROUTE-35', 'POST', '/api/manual-reconciliation/archive-ledger-row', None, 'DEFERRED'),
]


def fetch(url, timeout=15):
    req = urllib.request.Request(url, method='GET', headers={'Accept': '*/*'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return {
                'http_status': r.status,
                'content_type': r.headers.get('content-type', ''),
                'bytes': len(body),
                'elapsed_ms': round((time.time() - t0) * 1000, 1),
                'body': body,
                'error': None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, 'read') else b''
        return {
            'http_status': exc.code,
            'content_type': exc.headers.get('content-type', '') if exc.headers else '',
            'bytes': len(body),
            'elapsed_ms': round((time.time() - t0) * 1000, 1),
            'body': body,
            'error': 'HTTPError',
        }
    except Exception as exc:  # noqa: BLE001 - transport failure must be recorded, not raised
        return {
            'http_status': None,
            'content_type': '',
            'bytes': 0,
            'elapsed_ms': round((time.time() - t0) * 1000, 1),
            'body': b'',
            'error': repr(exc),
        }


def markers(body_bytes, marker):
    text = body_bytes.decode('utf-8', 'replace')
    return marker in text, text


def main():
    server_probe = fetch(BASE + '/openapi.json')
    openapi = {}
    if server_probe['http_status'] == 200:
        try:
            openapi = json.loads(server_probe['body'])
        except Exception:  # noqa: BLE001
            openapi = {}
    declared = set(openapi.get('paths', {}).keys())

    rows = []
    for row_id, method, path_t, url_path, marker in ROUTES:
        entry = {
            'id': row_id,
            'declared_method': method,
            'declared_path': path_t,
            'probed_url': (BASE + url_path) if url_path else None,
            'declared_in_openapi': path_t in declared,
        }
        if url_path is None:
            entry.update({
                'http_status': None,
                'marker': None,
                'marker_found': None,
                'content_type': None,
                'bytes': None,
                'verdict': 'NOT_TESTED',
                'reason': 'POST/write route: not exercised - a successful write mutates live engine state, which this card forbids ("Do not edit the matrix, restart the engine or the UI"). Presence is asserted from openapi.json + source instead.',
            })
            rows.append(entry)
            continue

        res = fetch(entry['probed_url'])
        text = res['body'].decode('utf-8', 'replace')
        if marker == 'JSON_LIST':
            try:
                parsed = json.loads(text)
                found = isinstance(parsed, list)
                entry['json_shape'] = type(parsed).__name__
                entry['json_len'] = len(parsed) if isinstance(parsed, list) else None
            except Exception:  # noqa: BLE001
                found = False
                entry['json_shape'] = 'unparseable'
            marker = 'JSON array body (list)'
        else:
            found, text = markers(res['body'], marker)
        status = res['http_status']
        generic_error = any(tok in text[:2000].lower() for tok in ('internal server error', 'traceback (most recent call last)'))
        if status == 200 and found and not generic_error:
            verdict = 'PASS'
            reason = 'HTTP 200 and body carries the declared surface marker %r' % marker
        elif status == 200 and not found:
            verdict = 'FAIL'
            reason = 'HTTP 200 but body lacks the declared marker %r (wrong surface or generic page)' % marker
        elif status is None:
            verdict = 'FAIL'
            reason = 'transport error: %s' % res['error']
        else:
            verdict = 'FAIL'
            reason = 'HTTP %s (expected 200)' % status
        entry.update({
            'http_status': status,
            'content_type': res['content_type'],
            'bytes': res['bytes'],
            'elapsed_ms': res['elapsed_ms'],
            'marker': marker,
            'marker_found': found,
            'generic_error_page': generic_error,
            'verdict': verdict,
            'reason': reason,
        })
        rows.append(entry)

    out = {
        'card': 't_cfcad924',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'base_url': BASE,
        'serving_pid': 15760,
        'served_module_path': 'C:/Users/wigmore/trading_stack/build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py',
        'served_module_sha256': 'fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0',
        'openapi_path_count': len(declared),
        'openapi_paths': sorted(declared),
        'route_rows': rows,
    }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)

    passed = sum(1 for r in rows if r['verdict'] == 'PASS')
    failed = sum(1 for r in rows if r['verdict'] == 'FAIL')
    deferred = sum(1 for r in rows if r['verdict'] == 'NOT_TESTED')
    print(json.dumps({'rows': len(rows), 'PASS': passed, 'FAIL': failed, 'NOT_TESTED': deferred, 'out': OUT}, indent=2))
    for r in rows:
        if r['verdict'] != 'PASS':
            print(r['id'], r['verdict'], r.get('http_status'), r['reason'][:140])


if __name__ == '__main__':
    main()
