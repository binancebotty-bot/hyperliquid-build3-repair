import datetime, hashlib, json, pathlib, urllib.request
import psutil

ROOT = pathlib.Path(__file__).resolve().parent
URLS = {'top': 'http://127.0.0.1:8023/live-copy', 'archive': 'http://127.0.0.1:8031/'}
SOURCES = {
    'top': pathlib.Path('C:/Users/wigmore/trading_stack/build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py'),
    'archive': pathlib.Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/HL_Copy_App_SSOT.py'),
}

def main():
    captures = {}
    for name, url in URLS.items():
        req = urllib.request.Request(url, headers={'Cache-Control': 'no-cache'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read()
                captures[name] = {'url': url, 'status': response.status, 'headers': dict(response.headers), 'body_utf8': body.decode('utf-8', 'replace'), 'body_sha256': hashlib.sha256(body).hexdigest()}
        except Exception as exc:
            captures[name] = {'url': url, 'error': repr(exc)}
        binds = []
        port = '8023' if name == 'top' else '8031'
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd', 'create_time']):
            try:
                if port in ' '.join(proc.info.get('cmdline') or []):
                    binds.append({'pid': proc.info['pid'], 'name': proc.info['name'], 'cmdline': proc.info['cmdline'], 'cwd': proc.info['cwd'], 'process_start_epoch': proc.info['create_time'], 'process_start_utc': datetime.datetime.fromtimestamp(proc.info['create_time'], datetime.timezone.utc).isoformat()})
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
        captures[name]['processes'] = binds
        source = SOURCES[name]
        captures[name]['source_path'] = str(source)
        captures[name]['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
        captures[name]['source_mtime'] = datetime.datetime.fromtimestamp(source.stat().st_mtime, datetime.timezone.utc).isoformat() if source.exists() else None
    captures['capture_time_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = ROOT / 'dom_capture.json'
    out.write_text(json.dumps(captures, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(out)
    print(json.dumps({k: {x: v.get(x) for x in ('url','status','error','body_sha256','source_sha256','source_mtime','processes')} for k,v in captures.items() if isinstance(v,dict)}, indent=2))

if __name__ == '__main__':
    main()
