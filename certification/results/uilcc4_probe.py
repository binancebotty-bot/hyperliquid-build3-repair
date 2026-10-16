#!/usr/bin/env python3
"""Read-only fresh probes for the bounded UILCC4 evidence package."""
import json
import re
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8031'

def get(path, timeout=12):
    req = urllib.request.Request(BASE + path, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.status, response.headers.get('Content-Type'), response.read()

def main():
    page_status, page_type, page = get('/live-copy', timeout=10)
    config_status, config_type, config = get('/api/live-config', timeout=10)
    config_obj = json.loads(config)
    html = page.decode('utf-8', 'replace')
    form_match = re.search(r'<form class="lc-modal" id="lcAddForm">(.*?)</form>', html, re.S)
    form = form_match.group(1) if form_match else ''
    summary = {
        'surface': BASE + '/live-copy',
        'live_copy': {'status': page_status, 'content_type': page_type, 'bytes': len(page)},
        'live_config': {'status': config_status, 'content_type': config_type,
                        'bytes': len(config), 'keys': sorted(config_obj)},
        'add_wallet_form_found_in_response_source': bool(form_match),
        'leader_equity_base_field_in_form': bool(re.search(r'name=["\']leader_equity_base["\']', form)),
        'max_diff_pct_field_in_form': bool(re.search(r'name=["\']max_diff_pct["\']', form)),
        'add_wallet_submit_handler_in_response_source': "jpost('/api/live-config/add-wallet'" in html,
        'read_only': True,
        'caveat': 'HTTP response source inspection, not rendered DOM or behavioral/persistence proof.'
    }
    try:
        status, content_type, data = get('/api/live-audit-summary', timeout=12)
        summary['audit_summary'] = {'status': status, 'content_type': content_type, 'bytes': len(data)}
    except Exception as exc:
        summary['audit_summary'] = {'error': type(exc).__name__, 'detail': str(exc)}
    try:
        status, content_type, data = get('/api/live-config/add-wallet', timeout=5)
        summary['add_wallet_get'] = {'status': status, 'content_type': content_type, 'bytes': len(data)}
    except urllib.error.HTTPError as exc:
        summary['add_wallet_get'] = {'status': exc.code, 'error': exc.reason}
    print(json.dumps(summary, indent=2))
    return 0 if page_status == 200 and config_status == 200 else 1

if __name__ == '__main__':
    sys.exit(main())
