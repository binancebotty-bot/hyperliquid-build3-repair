#!/usr/bin/env python3
"""Read-only timing harness for the live audit-summary endpoint.

Run: python evidence/ui_surface/AUDIT_SUMMARY_TIMEOUT_5223ce257f_harness.py
Makes three sequential GETs, fully reads each response, and reports status,
byte count, and wall time. It does not mutate the surface or project state.
"""
import json
import time
import urllib.error
import urllib.request

URL = 'http://127.0.0.1:8031/api/live-audit-summary'
TIMEOUT_SECONDS = 10
REQUESTS = 3

for index in range(1, REQUESTS + 1):
    started = time.perf_counter()
    request = urllib.request.Request(URL, method='GET')
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read()
            result = {
                'request': index,
                'http_status': response.status,
                'body_bytes': len(payload),
                'elapsed_seconds': round(time.perf_counter() - started, 3),
            }
            try:
                body = json.loads(payload)
                result['ok'] = body.get('ok')
                result['rows'] = body.get('rows')
            except (UnicodeDecodeError, json.JSONDecodeError):
                result['json'] = False
    except (urllib.error.URLError, TimeoutError) as exc:
        result = {
            'request': index,
            'error': type(exc).__name__,
            'detail': str(exc),
            'elapsed_seconds': round(time.perf_counter() - started, 3),
        }
    print(json.dumps(result, sort_keys=True))
