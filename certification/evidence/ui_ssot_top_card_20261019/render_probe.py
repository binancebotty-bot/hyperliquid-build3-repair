import datetime
import hashlib
import json
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
TARGETS = {
    'top': 'http://127.0.0.1:8023/live-copy',
    'archive': 'http://127.0.0.1:8031/',
}

captures = {}
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    for name, url in TARGETS.items():
        page = browser.new_page()
        response = page.goto(url, wait_until='networkidle', timeout=30000)
        captures[name] = {
            'url': url,
            'http_status': response.status,
            'title': page.title(),
            'capture_time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'rendered_body_text': page.locator('body').inner_text(),
            'rendered_dom_html': page.content(),
        }
        page.close()
    browser.close()
captures['capture_time_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
path = ROOT / 'rendered_dom_capture.json'
path.write_text(json.dumps(captures, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({name: {'url': item['url'], 'status': item['http_status'], 'title': item['title'], 'text_sha256': hashlib.sha256(item['rendered_body_text'].encode()).hexdigest()} for name, item in captures.items() if isinstance(item, dict)}, indent=2))
