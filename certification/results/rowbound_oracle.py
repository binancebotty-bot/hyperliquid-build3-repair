import ast, json, pathlib, shutil, subprocess, sys, tempfile
ENTRY = ('HL_Live_Copy_Service_Core', 'HL_Live_Copy_Service', 'HL_Copy_App_SSOT')
DEFAULT_BASELINE = '43731b4f1f19a56e835032dabf608a550f925717'
STORES = {'sqlite3','psycopg','psycopg2','pymysql','MySQLdb','redis','shelve','dbm','sqlalchemy','peewee','pymongo','motor','lmdb','rocksdb','tinydb','zodb'}
B4 = {'build4','b4','mission_control','missioncontrol','control_plane','controlplane','gate_root','b4_gate','hl_prod_base','hyperliquid_build4'}
B4_PREFIX = ('build4_','b4_','mission_control_')
STORE_RECV = {'conn','cursor','cur','db','cxn','con','connection'}
ROWS = ('ENG-INV-03','ENG-INV-04','ENG-INV-05')

def git_show(root, rev, path):
    out = subprocess.run(['git','-C',str(root),'show','%s:%s' % (rev,path)], capture_output=True)
    return None if out.returncode else out.stdout.decode('utf-8-sig','replace')

def list_prod(root):
    hls = pathlib.Path(root)/'_archive'/'hl_stage2'
    if not hls.exists():
        hls = pathlib.Path(root)
    return sorted(p for p in hls.glob('*.py') if not (p.name.startswith('test_') or p.name.endswith('_test.py')))

def imports_of(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.append((n.lineno, a.name.split('.')[0], 'import'))
        elif isinstance(n, ast.ImportFrom):
            if n.level or not n.module:
                continue
            out.append((n.lineno, n.module.split('.')[0], 'from'))
    return out

def dyn_imports(tree):
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else '')
        if nm not in ('__import__','import_module'):
            continue
        a0 = n.args[0] if n.args else None
        if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
            out.append((n.lineno, a0.value.split('.')[0], 'dynamic'))
    return out

def store_sinks(tree):
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        at = n.func.attr
        rc = n.func.value
        rn = rc.id if isinstance(rc, ast.Name) else ''
        if at == 'to_sql':
            out.append((n.lineno, '<sink:to_sql>', 'sink'))
        elif at in ('execute','executemany','executescript') and rn in STORE_RECV:
            out.append((n.lineno, '<sink:%s.%s>' % (rn, at), 'sink'))
    return out

def is_b4(m):
    return m in B4 or any(m.startswith(p) for p in B4_PREFIX)

def parse_dir(root):
    files = list_prod(root)
    parsed, bad, trees = 0, [], {}
    for p in files:
        src = p.read_text(encoding='utf-8-sig', errors='replace')
        try:
            trees[p.name] = ast.parse(src, filename=str(p))
            parsed += 1
        except SyntaxError as e:
            bad.append({'file': p.name, 'error': str(e)})
    return files, trees, parsed, bad

def closure(stems, trees, seeds):
    seen, stack = set(), [s for s in seeds if s in stems]
    while stack:
        fn = stems.get(stack.pop())
        if fn is None or fn in seen:
            continue
        seen.add(fn)
        for _l, m, _k in imports_of(trees[fn]):
            if m in stems and stems[m] not in seen:
                stack.append(m)
    return seen

def row03(trees, names, stdlib, approved, base_deps, local=frozenset()):
    v, present = [], set()
    for fn in names:
        for ln, mod, kind in imports_of(trees[fn]):
            if mod in stdlib or is_b4(mod) or mod in STORES or mod in local:
                continue
            present.add(mod)
            if mod in approved or mod in base_deps:
                continue
            v.append({'file': fn, 'line': ln, 'module': mod, 'kind': kind})
    return v, {'present': sorted(present), 'approved': sorted(approved),
               'at_baseline': sorted(base_deps),
               'new_unapproved': sorted(present - base_deps - approved)}

def row04(trees, names):
    v = []
    for fn in names:
        for ln, mod, _k in imports_of(trees[fn]):
            if mod in STORES:
                v.append({'file': fn, 'line': ln, 'module': mod, 'kind': 'driver-import'})
        for ln, mod, _k in dyn_imports(trees[fn]):
            if mod in STORES:
                v.append({'file': fn, 'line': ln, 'module': mod, 'kind': 'dynamic-driver'})
        for ln, mod, _k in store_sinks(trees[fn]):
            v.append({'file': fn, 'line': ln, 'module': mod, 'kind': 'store-sink'})
    return v, {'drivers': sorted(STORES)}

def row05(trees, names):
    v = []
    for fn in names:
        for ln, mod, kind in imports_of(trees[fn]):
            if is_b4(mod):
                v.append({'file': fn, 'line': ln, 'module': mod, 'kind': kind})
        for ln, mod, _k in dyn_imports(trees[fn]):
            if is_b4(mod):
                v.append({'file': fn, 'line': ln, 'module': mod, 'kind': 'dynamic'})
    return v, {'namespaces': sorted(B4)}

def load_approved(root):
    p = pathlib.Path(root)/'certification'/'approved_dependencies.json'
    try:
        return set(json.loads(p.read_text(encoding='utf-8-sig')).get('approved') or [])
    except Exception:
        return set()

def baseline_deps(root, rev, stdlib):
    if not rev:
        return set()
    hls = '_archive/hl_stage2/'
    ls = subprocess.run(['git','-C',str(root),'ls-tree','--name-only',rev,hls], capture_output=True)
    if ls.returncode:
        return set()
    names = [n.split('/')[-1] for n in ls.stdout.decode().split() if n.endswith('.py')]
    stems = {n[:-3]: n for n in names if not (n.startswith('test_') or n.endswith('_test.py'))}
    trees = {}
    for fn in stems.values():
        src = git_show(root, rev, hls + fn)
        if src is None:
            continue
        try:
            trees[fn] = ast.parse(src)
        except SyntaxError:
            continue
    deps = set()
    for fn in closure(stems, trees, ENTRY):
        for _l, mod, _k in imports_of(trees[fn]):
            if mod in stdlib or mod in STORES or is_b4(mod) or mod in stems:
                continue
            deps.add(mod)
    return deps

def scan(root, rev):
    files, trees, parsed, bad = parse_dir(root)
    stems = {p.stem: p.name for p in files}
    reach = sorted(closure(stems, trees, ENTRY))
    allnames = [p.name for p in files]
    stdlib = set(sys.stdlib_module_names)
    approved = load_approved(root)
    base = baseline_deps(root, rev, stdlib)
    v3, x3 = row03(trees, reach, stdlib, approved, base, stems)
    v4, x4 = row04(trees, reach)
    v5, x5 = row05(trees, reach)
    w3, _ = row03(trees, allnames, stdlib, approved, base, stems)
    w4, _ = row04(trees, allnames)
    w5, _ = row05(trees, allnames)
    ck = {'ENG-INV-03': not v3, 'ENG-INV-04': not v4, 'ENG-INV-05': not v5}
    scope_ok = parsed == len(files) and len(reach) >= 2
    return {'repo_root': str(pathlib.Path(root).resolve()), 'baseline_rev': rev,
            'files_in_dir': allnames, 'engine_closure': reach, 'files_parsed': parsed,
            'parse_errors': bad, 'scope_ok': scope_ok,
            'ENG-INV-03': dict(x3, invariant='No NEW third-party runtime dependency without Architect approval.', violations=v3),
            'ENG-INV-04': dict(x4, invariant='No authoritative persistent trading-state store.', violations=v4),
            'ENG-INV-05': dict(x5, invariant='No Build-4 control-plane/platform import.', violations=v5),
            'wider_scope_violations': {'ENG-INV-03': w3, 'ENG-INV-04': w4, 'ENG-INV-05': w5},
            'checks': ck,
            'result': 'PASS' if all(ck.values()) and scope_ok else 'FAIL'}
MUT = dict()
MUT['ENG-INV-03'] = 'import totally_unapproved_new_package'
MUT['ENG-INV-04'] = """import sqlite3
_CONN = sqlite3.connect("authoritative_positions.db")"""
MUT['ENG-INV-05'] = 'import build4_control_plane'


def mutate(root, row, rev):
    tmp = tempfile.mkdtemp(prefix='rowbound_')
    dest = pathlib.Path(tmp) / 'm'
    try:
        shutil.copytree(str(root), str(dest))
        hls = dest / '_archive' / 'hl_stage2'
        if not hls.exists():
            hls = dest
        tgt = hls / 'HL_Live_Copy_Service_Core.py'
        if not tgt.exists():
            c = sorted(hls.glob('*Core*.py'))
            if not c:
                return {'row': row, 'non_vacuous': False, 'error': 'no core file'}
            tgt = c[0]
        tgt.write_text(tgt.read_text(encoding='utf-8') + '\n' + MUT[row], encoding='utf-8')
        got = scan(dest, rev)['checks']
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sib = [r for r in ROWS if r != row]
    return {'row': row, 'mutation': MUT[row], 'results_all_rows': got,
            'this_row_red': got[row] is False,
            'siblings_green': all(got[s] for s in sib),
            'sibling_detail': {s: got[s] for s in sib},
            'non_vacuous': got[row] is False and all(got[s] for s in sib)}

def main():
    if len(sys.argv) < 2:
        print('usage: oracle <repo_root> [--baseline REV] [--mutate]', file=sys.stderr)
        return 2
    root = sys.argv[1]
    rev = DEFAULT_BASELINE
    if '--baseline' in sys.argv:
        rev = sys.argv[sys.argv.index('--baseline') + 1]
    b = scan(root, rev)
    rep = {'row_scope': list(ROWS), 'baseline': b, 'verdict': b['result']}
    ok = b['result'] == 'PASS'
    if '--mutate' in sys.argv:
        rep['mutation_controls'] = [mutate(root, r, rev) for r in ROWS]
        ok = ok and all(m['non_vacuous'] for m in rep['mutation_controls'])
        rep['verdict'] = 'PASS' if ok else 'FAIL'
    rep['row_verdicts'] = {r: ('PASS' if b['checks'][r] and b['scope_ok'] else 'FAIL') for r in ROWS}
    print(json.dumps(rep, indent=2))
    return 0 if rep['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
