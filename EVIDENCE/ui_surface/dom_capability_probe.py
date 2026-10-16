#!/usr/bin/env python3
'''Read-only DOM capability probe.
Loads http://127.0.0.1:8031/live-copy in a NEW headless Chromium (playwright),
reads RENDERED element text (textContent after JS execution), prints it.
NEVER touches operator's Edge/Chrome, CDP 9223, or the :8031 process.
Run with Python 3.11 (playwright installed there).
'''
import json, sys, datetime

URL = 'http://127.0.0.1:8031/live-copy'

def main():
    out = {'url': URL, 'ts': datetime.datetime.now().isoformat()}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = 'import playwright: %r' % (e,)
        print(json.dumps(out, indent=2))
        return 1

    try:
        with sync_playwright() as p:
            out['playwright_version'] = getattr(p, '_impl_obj', None) and 'n/a' or 'n/a'
            browser = p.chromium.launch(headless=True)  # NEW headless instance
            try:
                page = browser.new_page()
                resp = page.goto(URL, wait_until='networkidle', timeout=20000)
                out['http_status'] = resp.status if resp else None
                out['title'] = page.title()
                # Read a RENDERED element's text (post-JS), not raw source.
                sel = '#liveCopyPanel .lc-title'
                el = page.query_selector(sel)
                out['selector'] = sel
                out['rendered_text'] = el.inner_text() if el else None
                # also grab the header pills block text as a second sample
                pills = page.query_selector('#liveCopyPanel .lc-header-pills')
                out['pills_text'] = ' '.join((pills.inner_text() if pills else '').split())
                # proof it is rendered (DOM is live) rather than static source:
                out['dom_element_count'] = page.evaluate('document.querySelectorAll("*").length')
                out['body_text_len'] = len(page.evaluate('document.body.innerText'))
                out['body_text_sample'] = page.evaluate('document.body.innerText')[:400]
                out['route'] = 'ROUTE_AVAILABLE'
                out['route_name'] = 'playwright.chromium headless (Python 3.11)'
            finally:
                browser.close()
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = '%s: %r' % (type(e).__name__, e)

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get('route') == 'ROUTE_AVAILABLE' else 1

if __name__ == '__main__':
    sys.exit(main())
