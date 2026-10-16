"""Read-only live UI/API probe for UILCC3 rows; no writes or engine imports."""
import json
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8031'
PATHS = ['/live-copy', '/api/live-config', '/api/live-ws-health', '/api/live-audit-summary', '/api/global-controls']

def probe(path):
    started = time.monotonic()
    req = urllib.request.Request(BASE + path, headers={'x-requested-with': 'fetch'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read()
            result = {'http': response.status, 'bytes': len(body), 'elapsed_s': round(time.monotonic() - started, 3)}
            if path.endswith('live-copy'):
                text = body.decode('utf-8', 'replace')
                result['static_tokens'] = {token: token in text for token in ['Live Copy Wallets', 'OFF', 'Archive', 'A — Live Performance', 'B — Open Positions', 'C — Lead vs Copy / Friction']}
            elif path.startswith('/api/'):
                try:
                    data = json.loads(body)
                    result['json_ok'] = data.get('ok')
                    result['top_keys'] = sorted(data.keys())
                    if path.endswith('live-audit-summary'):
                        result['rows'] = data.get('rows')
                        result['audit_keys'] = sorted(data.keys())
                except (ValueError, AttributeError):
                    result['json_valid'] = False
            return result
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {'error': type(exc).__name__ + ': ' + str(exc), 'elapsed_s': round(time.monotonic() - started, 3)}

if __name__ == '__main__':
    print(json.dumps({path: probe(path) for path in PATHS}, indent=2, sort_keys=True))
