#!/usr/bin/env python3
'''B3-CERT t_d925c3dd probe 2 -- FULL-PAGE rendered scan + OS/process oracle.
READ-ONLY. No engine import. New headless Chromium (py3.11).
'''
import json, os, subprocess, sys, datetime, urllib.request

BASE = 'http://127.0.0.1:8031'
OUT = {}


def jget(path, timeout=8):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def dom_pages():
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            for name, url in (('live_copy', BASE + '/live-copy'), ('analytics_home', BASE + '/')):
                pg = b.new_page()
                try:
                    resp = pg.goto(url, wait_until='networkidle', timeout=25000)
                    body = pg.evaluate('document.body.innerText')
                    res[name] = {
                        'url': url, 'http_status': resp.status if resp else None,
                        'title': pg.title(), 'body_len': len(body),
                        'body_text': body[:6000],
                    }
                except Exception as e:
                    res[name] = {'url': url, 'error': '%s: %r' % (type(e).__name__, e)}
                finally:
                    pg.close()
        finally:
            b.close()
    return res


def ps_oracle():
    '''OS oracle: process table + port bindings. Read-only, no kills.'''
    o = {}
    try:
        o['netstat_8031_8014'] = subprocess.run(
            ['netstat', '-ano'], capture_output=True, text=True, timeout=30).stdout.splitlines()
        o['netstat_8031_8014'] = [l.strip() for l in o['netstat_8031_8014']
                                  if (':8031' in l or ':8014' in l) and 'LISTENING' in l]
    except Exception as e:
        o['netstat_err'] = repr(e)
    try:
        tl = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=40).stdout
        o['python_procs'] = [l.strip() for l in tl.splitlines()
                             if l.lower().startswith('"python') or 'uvicorn' in l.lower()]
    except Exception as e:
        o['tasklist_err'] = repr(e)
    return o


def main():
    r = {'register_ref': 'main:certification/certification_matrix.json',
         'register_commit': 'b142cf88d389e791160f691aac3d936852b99975',
         'tested_at_utc': datetime.datetime.utcnow().isoformat() + 'Z'}
    try:
        r['dom'] = dom_pages()
    except Exception as e:
        r['dom'] = {'error': '%s: %r' % (type(e).__name__, e)}
    TIERS = ['AUTHORITATIVE_EXCHANGE', 'LOCAL_LEDGER', 'LEADER_SIGNAL', 'DISPLAY_ONLY', 'STALE', 'BLOCKED', 'SKIPPED']
    r['tier_token_scan'] = {}
    for name, page in (r.get('dom') or {}).items():
        if not isinstance(page, dict):
            continue
        t = page.get('body_text', '')
        r['tier_token_scan'][name] = {k: (k in t) for k in TIERS}
    r['api_state'] = jget('/api/state')
    r['api_ui_state'] = jget('/api/ui-state')
    r['ps_oracle'] = ps_oracle()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
