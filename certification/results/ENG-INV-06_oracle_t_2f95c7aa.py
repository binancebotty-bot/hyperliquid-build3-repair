import ast, json, sys, shutil, tempfile, pathlib
ALLOWED = {'requests','websocket','eth_account','hyperliquid','fastapi','uvicorn','pydantic','starlette'}
def scan(root):
    hls = pathlib.Path(root)/'_archive'/'hl_stage2'
    if not hls.exists(): hls = pathlib.Path(root)
    prod = [p for p in sorted(hls.glob('*.py')) if not (p.name.startswith('test_') or p.name.endswith('_test.py'))]
    sites=[]; spawns=[]; imps={}; files=[]
    for p in prod:
        files.append(p.name)
        s = p.read_text(encoding='utf-8-sig', errors='replace')
        t = ast.parse(s, filename=str(p))
        gate = ('--send-one-intent' in s) or ('--confirm-send' in s)
        for n in ast.walk(t):
            if not isinstance(n, ast.Call): continue
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == 'order':
                if isinstance(f.value, ast.Name): r = f.value.id
                elif isinstance(f.value, ast.Attribute): r = f.value.attr
                else: r = '?'
                sites.append({'file': p.name, 'line': n.lineno, 'receiver': r, 'manual_cli_gate': gate})
            if isinstance(f, ast.Attribute) and f.attr in ('Popen','run','system','call') and isinstance(f.value, ast.Name) and f.value.id in ('subprocess','os','multiprocessing'):
                spawns.append({'file': p.name, 'line': n.lineno})
        for n in ast.walk(t):
            mods = []
            if isinstance(n, ast.Import): mods = [a.name.split('.')[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module: mods = [n.module.split('.')[0]]
            for m in mods: imps.setdefault(m, set()).add(p.name)
    local = {pathlib.Path(x).stem for x in files}
    unexp = {m: sorted(v) for m, v in imps.items() if m not in ALLOWED and m not in local and m not in sys.stdlib_module_names}
    auto = [x for x in sites if not x['manual_cli_gate']]
    man = [x for x in sites if x['manual_cli_gate']]
    checks = {'one_automated_send_site': len(auto) == 1, 'no_process_spawns': len(spawns) == 0, 'no_unexpected_imports': len(unexp) == 0, 'engine_wide_scope': len(files) > 1}
    return {'files': files, 'all_sites': sites, 'automated': auto, 'manual': man, 'spawns': spawns, 'unexpected': unexp, 'checks': checks, 'result': 'PASS' if all(checks.values()) else 'FAIL'}
def main():
    d = sys.argv[1]; mut = '--mutate' in sys.argv
    b = scan(d); out = {'baseline': b}; ok = b['result'] == 'PASS'
    if mut:
        td = tempfile.mkdtemp(); m = pathlib.Path(td)/'m'; shutil.copytree(d, m)
        hls = m/'_archive'/'hl_stage2'
        if not hls.exists(): hls = m
        c = hls/'HL_Live_Copy_Service_Core.py'
        if not c.exists(): c = sorted(hls.glob('*Core*.py'))[0]
        c.write_text(c.read_text(encoding='utf-8') + '\n\ndef _mutant():\n    return _EX.order(1,2,3,4,5)\n', encoding='utf-8')
        mu = scan(m)
        out['mutation'] = {'expected': 'FAIL', 'actual': mu['result'], 'base_sites': len(b['all_sites']), 'mut_sites': len(mu['all_sites']), 'non_vacuous': mu['result'] == 'FAIL'}
        ok = ok and out['mutation']['non_vacuous']
    out['verdict'] = 'PASS' if ok else 'FAIL'
    print(json.dumps(out, indent=2))
    sys.exit(0 if out['verdict'] == 'PASS' else 1)
main()
