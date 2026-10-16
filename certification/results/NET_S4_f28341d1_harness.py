#!/usr/bin/env python3
"""Bounded read-only preflight for the five NET_S4 testnet certification rows.

This deliberately does not start an engine, submit orders, or manufacture packet evidence.
It checks only the declared local UI surface and reports the required live proof as unavailable.
"""
import json
import urllib.request
from datetime import datetime, timezone

ROWS = ('TN-F22', 'TN-F23', 'TN-F26', 'TN-F27', 'TN-PS1')
UI_URL = 'http://127.0.0.1:8031/live-copy'

try:
    request = urllib.request.Request(UI_URL, method='GET')
    with urllib.request.urlopen(request, timeout=6) as response:
        ui_probe = {'url': UI_URL, 'http_status': response.status, 'bytes_read': len(response.read())}
except Exception as exc:
    ui_probe = {'url': UI_URL, 'error': type(exc).__name__ + ': ' + str(exc)}

missing = ('active Build-3 testnet production-engine runtime with a fresh, row-specific '
           'testnet scenario and exchange-parity capture; independent captured request-packet '
           'oracle (orders/fills or packet evidence). The available UI HTTP response does not '
           'establish any of these.')
now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
result = {
    'suite': 'NET_S4',
    'observed_at_utc': now,
    'ui_surface_probe': ui_probe,
    'mutations': 'none; GET only; no engine started and no order submitted',
    'rows': [
        {
            'id': row,
            'result': 'NOT_TESTED',
            'checks': [
                {'name': 'declared_testnet_production_engine_scenario', 'result': 'NOT_TESTED', 'reason': missing},
                {'name': 'independent_exchange_or_packet_oracle', 'result': 'NOT_TESTED', 'reason': missing},
                {'name': 'declared_negative_cases', 'result': 'NOT_TESTED', 'reason': missing},
            ],
            'missing_runtime': missing,
        }
        for row in ROWS
    ],
}
print(json.dumps(result, indent=2, sort_keys=True))
