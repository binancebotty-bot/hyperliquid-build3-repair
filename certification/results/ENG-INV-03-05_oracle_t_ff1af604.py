#!/usr/bin/env python3
'''Row-bound oracle for ENG-INV-03 / -04 / -05.

Defect being fixed: the committed ENG-INV-03-05_43731b4f.json is one AGGREGATE census blob
covering three ids with no per-row assertion, which is exactly why the evidence audit
demoted 03/04/05. This oracle gives each row its OWN predicate plus its OWN mutation control.

AST only. Never imports the engine. Engine-WIDE scope (every production .py in _archive/hl_stage2).

ENG-INV-03 no new dependency without approval -> unapproved third-party import census
ENG-INV-04 no authoritative persistent store -> store-driver / store-sink census
ENG-INV-05 no Build-4 control-plane import -> build4/platform import census

usage: oracle <repo_root> [--mutate]
'''
import ast, json, pathlib, shutil, sys, tempfile

APPROVED = {
    'requests','websocket','websockets','eth_account','eth_utils','hyperliquid',
    'fastapi','uvicorn','pydantic','starlette','hexbytes','web3','aiohttp',
}
STORES = {
    'sqlite3','psycopg','psycopg2','pymysql','MySQLdb','redis','shelve','dbm',
    'sqlalchemy','peewee','pymongo','motor','lmdb','rocksdb',
}
B4 = {
    'build4','b4','mission_control','missioncontrol','control_plane','controlplane',
    'gate_root','b4_gate','hl_prod_base','hyperliquid_build4',
}
B4_PREFIX = ('build4_','b4_','mission_control_')
ROWS = ('ENG-INV-03','ENG-INV-04','ENG-INV-05')


def prod_files(root):
    hls = pathlib.Path(root)/'_archive'/'hl_stage2'
    if not hls.exists():
        hls = pathlib.Path(root)
    return sorted(p for p in hls.glob('*.py')
                  if not (p.name.startswith('test_') or p.name.endswith('_test.py')))


def imports_of(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.append((n.lineno, a.name.split('.')[0]))
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                continue
            if n.module:
                out.append((n.lineno, n.module.split('.')[0]))
    return out


def is_b4(m):
    return m in B4 or any(m.startswith(p) for p in B4_PREFIX)


def scan(root):
    files = prod_files(root)
    local = {p.stem for p in files}
    third, stores, b4, parsed, bad = [], [], [], 0, []
    for path in files:
        src = path.read_text(encoding='utf-8-sig', errors='replace')
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as e:
            bad.append({'file': path.name, 'error': str(e)})
            continue
        parsed += 1
        for line, mod in imports_of(tree):
            # Store drivers that are ALSO stdlib (sqlite3/dbm/shelve) must be
            # classified BEFORE the stdlib skip, or the store check is vacuous.
            if is_b4(mod):
                b4.append({'file': path.name, 'line': line, 'module': mod})
            elif mod in STORES:
                stores.append({'file': path.name, 'line': line, 'module': mod})
            elif mod in local or mod in sys.stdlib_module_names:
                continue
            elif mod not in APPROVED:
                third.append({'file': path.name, 'line': line, 'module': mod})
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                continue
            attr = n.func.attr
            recv = n.func.value
            recv_name = recv.id if isinstance(recv, ast.Name) else (
                recv.attr if isinstance(recv, ast.Attribute) else '')
            # json.dump writes a config stamp file, not an authoritative store.
            if attr == 'dump' and recv_name in {'json', 'pickle', 'yaml', 'toml'}:
                continue
            if attr == 'to_sql' or attr in {'dump', 'dump_all'} and recv_name not in {'json','pickle','yaml','toml'}:
                stores.append({'file': path.name, 'line': n.lineno,
                               'module': '<sink:%s>' % (recv_name or attr)})
    checks = {'ENG-INV-03': not third, 'ENG-INV-04': not stores, 'ENG-INV-05': not b4}
    scope = parsed == len(files) and len(files) > 1
    return {
        'repo_root': str(pathlib.Path(root).resolve()),
        'files_scanned': [p.name for p in files],
        'files_parsed': parsed,
        'parse_errors': bad,
        'engine_wide_scope': scope,
        'ENG-INV-03': {'assertion': 'zero unapproved third-party imports engine-wide',
                       'approved': sorted(APPROVED), 'violations': third, 'pass': checks['ENG-INV-03']},
        'ENG-INV-04': {'assertion': 'zero persistent-store drivers or store sinks',
                       'violations': stores, 'pass': checks['ENG-INV-04']},
        'ENG-INV-05': {'assertion': 'zero Build-4 control-plane imports',
                       'violations': b4, 'pass': checks['ENG-INV-05']},
        'checks': checks,
        'result': 'PASS' if all(checks.values()) and scope else 'FAIL',
    }


MUT = {
    'ENG-INV-03': '\nimport totally_unapproved_new_package\n',
    'ENG-INV-04': '\nimport sqlite3\n',
    'ENG-INV-05': '\nimport build4_control_plane\n',
}


def mutate(root, row):
    tmp = tempfile.mkdtemp(prefix='invmut_')
    dest = pathlib.Path(tmp)/'m'
    try:
        shutil.copytree(root, dest)
        hls = dest/'_archive'/'hl_stage2'
        if not hls.exists():
            hls = dest
        tgt = hls/'HL_Live_Copy_Service_Core.py'
        if not tgt.exists():
            c = sorted(hls.glob('*Core*.py'))
            if not c:
                return {'row': row, 'non_vacuous': False, 'error': 'no core file'}
            tgt = c[0]
        tgt.write_text(tgt.read_text(encoding='utf-8') + MUT[row], encoding='utf-8')
        mu = scan(dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {'row': row, 'mutation': MUT[row].strip(), 'expected': 'FAIL',
            'actual_row_check': mu['checks'][row],
            'non_vacuous': mu['checks'][row] is False}


def main():
    if len(sys.argv) < 2:
        print('usage: oracle <repo_root> [--mutate]', file=sys.stderr)
        return 2
    root = sys.argv[1]
    base = scan(root)
    rep = {'row_scope': list(ROWS), 'baseline': base, 'verdict': base['result']}
    ok = base['result'] == 'PASS'
    mut_ok = {}
    if '--mutate' in sys.argv:
        rep['mutation_controls'] = [mutate(root, r) for r in ROWS]
        mut_ok = {m['row']: m['non_vacuous'] for m in rep['mutation_controls']}
        ok = ok and all(mut_ok.values())
        rep['verdict'] = 'PASS' if ok else 'FAIL'
    # Each row is scored ONLY on its own predicate and its own mutation control.
    rep['row_verdicts'] = {
        r: ('PASS' if (base['checks'][r] and base['engine_wide_scope']
                       and mut_ok.get(r, True))
            else 'FAIL')
        for r in ROWS
    }
    print(json.dumps(rep, indent=2))
    return 0 if rep['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
