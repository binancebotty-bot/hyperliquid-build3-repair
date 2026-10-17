import json, os, sys, time, datetime, urllib.request

BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'
AUDIT_DIR = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'

def http_json(path, timeout=8):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}

def read_json_file(p):
    try:
        with open(p, 'rb') as f:
            return {'path': p, 'ok': True, 'body': json.loads(f.read().decode('utf-8-sig', 'replace'))}
    except Exception as e:
        return {'path': p, 'ok': False, 'error': '%s: %r' % (type(e).__name__, e)}

def dom_capture():
    out = {'url': URL, 'ts': datetime.datetime.now().isoformat()}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = 'import playwright: %r' % (e,)
        return out
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page()
                resp = pg.goto(URL, wait_until='networkidle', timeout=25000)
                out['http_status'] = resp.status if resp else None
                out['title'] = pg.title()
                panel = pg.query_selector('#liveCopyPanel')
                out['panel_present'] = bool(panel)
                out['panel_text'] = ' '.join((panel.inner_text() if panel else '').split())[:20000]
                # Live Copy Status card region
                st = pg.query_selector('#lcStatus')
                out['lcStatus_present'] = bool(st)
                out['lcStatus_text'] = ' '.join((st.inner_text() if st else '').split())[:6000]
                # every key/value-like row inside lcStatus
                out['lcStatus_rows'] = pg.evaluate("() => {const t=document.querySelector('#lcStatus'); if(!t) return []; return Array.from(t.querySelectorAll('*')).filter(e=>e.children.length===0 && (e.innerText||'').trim()).map(e=>(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,140));}")
                # search for the specific card labels anywhere in the panel
                labels = ['MASTER REAL ORDERS','MASTER REAL','ACTIVE','SUBSCRIBED','LAST SEND','LAST FILL','LAST REJECT','LAST LATENCY','LATENCY WARNING']
                out['label_hits'] = {}
                for lb in labels:
                    out['label_hits'][lb] = pg.evaluate("(lb)=>{const t=document.querySelector('#liveCopyPanel');if(!t)return [];const re=new RegExp(lb,'i');return Array.from(t.querySelectorAll('*')).filter(e=>e.children.length===0&&re.test(e.innerText||'')).map(e=>{let p=e;const chain=[];for(let i=0;i<4&&p;i++){chain.push(p.tagName+(p.id?('#'+p.id):'')+(p.className?('.'+String(p.className).split(' ').join('.')):''));p=p.parentElement;}return {txt:(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,140), chain:chain};}).slice(0,10);}", lb)
                # graph region: svgs and their container text
                out['svg_info'] = pg.evaluate("() => Array.from(document.querySelectorAll('svg')).map(s=>{let p=s.parentElement;const chain=[];for(let i=0;i<4&&p;i++){chain.push(p.tagName+(p.id?('#'+p.id):'')+(p.className?('.'+String(p.className).split(' ').join('.')):''));p=p.parentElement;}return {outer_len:s.outerHTML.length, chain:chain, parent_text:((s.parentElement&&s.parentElement.innerText)||'').trim().replace(/\\s+/g,' ').slice(0,300)};})")
                # any element whose text mentions PnL / Exposure / graph
                out['graph_text_hits'] = pg.evaluate("() => {const re=/(pnl|exposure|graph|equity|portfolio)/i;return Array.from(document.querySelectorAll('#liveCopyPanel *')).filter(e=>e.children.length===0&&re.test(e.innerText||'')).map(e=>{let p=e;const chain=[];for(let i=0;i<3&&p;i++){chain.push(p.tagName+(p.id?('#'+p.id):'')+(p.className?('.'+String(p.className).split(' ').join('.')):''));p=p.parentElement;}return {txt:(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,160), chain:chain};}).slice(0,40);}")
                # buttons/tabs present (graph selectors?)
                out['buttons'] = pg.evaluate("() => Array.from(document.querySelectorAll('#liveCopyPanel button, #liveCopyPanel select, #liveCopyPanel option')).map(e=>({tag:e.tagName, id:e.id||null, txt:(e.innerText||'').trim().slice(0,60), val:e.value||null})).slice(0,60)")
                out['route'] = 'ROUTE_AVAILABLE'
            finally:
                b.close()
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = '%s: %r' % (type(e).__name__, e)
    return out

def main():
    r = {}
    r['register_commit'] = 'b142cf88d389e791160f691aac3d936852b99975'
    r['tested_at_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'
    r['tested_at_ms'] = int(time.time() * 1000)
    r['dom'] = dom_capture()
    r['api_summary'] = http_json('/api/live-copy-summary')
    r['api_ui_state'] = http_json('/api/ui-state')
    r['snap'] = read_json_file(os.path.join(AUDIT_DIR, 'exchange_account_snapshot_app.json'))
    # try a couple of likely exchange-history files
    for name in ['exchange_account_history.json','live_integrity_status.json','live_service_state.json']:
        fp = os.path.join(AUDIT_DIR, name)
        if os.path.exists(fp):
            r['file_' + name] = read_json_file(fp)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    sys.exit(main())
