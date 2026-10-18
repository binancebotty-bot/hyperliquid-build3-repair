#!/usr/bin/env python3
"""Read-only live-surface probe for wallet certification rows.

This harness deliberately does not mutate wallet/config controls. It captures
availability of the declared UI and audit oracle; it is not a substitute for
the row's state-changing Testnet proof.
"""
import json
import time
import urllib.error
import urllib.request

UI_URL = 'http://127.0.0.1:8031/live-copy'
AUDIT_URL = 'http://127.0.0.1:8031/api/live-audit-summary'


def probe(url, timeout=10):
    started = time.monotonic()
    request = urllib.request.Request(url, headers={'User-Agent': 'wallet-cert-readonly-probe/1'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            return {'url': url, 'http_status': response.status, 'bytes': len(payload),
                    'elapsed_seconds': round(time.monotonic() - started, 6),
                    'error': None}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {'url': url, 'http_status': None, 'bytes': None,
                'elapsed_seconds': round(time.monotonic() - started, 6),
                'error': str(exc)}


def main():
    print(json.dumps({'ui': probe(UI_URL), 'audit_oracle': probe(AUDIT_URL)}, sort_keys=True))


if __name__ == '__main__':
    main()
