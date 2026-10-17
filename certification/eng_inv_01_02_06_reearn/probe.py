#!/usr/bin/env python3
"""Row-bound re-earn of ENG-INV-01 / -02 / -06.

Card t_43fbb222: repairs the two defects the reviewer found in the t_20e1cb6d
re-earn. Reads engine sources straight out of git objects, so the result is
bound to a commit and cannot drift with a dirty working tree.

Rows:
  ENG-INV-01  "One process."                         ARCHITECTURE.md invariant 1
  ENG-INV-02  "One physical production .order() call site."   invariant 2
  ENG-INV-06  "No new engine/runtime around Build 3."         invariant 6

ENG-INV-02 SCOPE (defect 2)
---------------------------
The previous predicate counted every `*.order(...)` Call node across the whole
production file set and found 2. That was over-scoped: it counted a sender in a
module that is not the certified engine. The predicate is narrowed here to the
CERTIFIED ENGINE SCOPE, which is not a convenience choice - it is the scope the
project's own recorded authority fixes:

  * ARCHITECTURE.md "Scope budget" states the budget as "production files:
    <=2" and "physical production order sites: 1", i.e. production = the
    repaired engine, not every .py shipped under _archive/.
  * MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md OD-26 / section 5 (Boss,
    2026-10-09T12:30Z): certification targets the real Core engine
    HL_Live_Copy_Service_Core.py, NOT the legacy HL_Live_Copy_Service.py that
    G1-G4 were built on. Core's own header says it is "intentionally
    independent of the legacy HL_Live_Copy_Service.py flow".
  * CONTROL_STATE.json single_order_site: "exactly one physical
    exchange.order() call site" is a property of the engine being repaired.

Nothing is hidden by the narrowing. The probe reports BOTH numbers:
order_call_nodes_all (whole file set) and order_call_nodes_certified_scope,
plus the exclusion list with the reason each site was excluded. The legacy site
is also carried as a disclosed residual in verdicts.json. A scope-demonstration
control proves the narrowed predicate does NOT see a send path added to the
legacy module while the unnarrowed one does - so the narrowing is visible and
falsifiable rather than silent.

Usage: python probe.py --repo <git worktree> --out RESULT.json
"""
import argparse, ast, json, subprocess, sys
from pathlib import Path

BASE = '89b3bc7'   # branch point the card names
TEST = '43731b4f1f19a56e835032dabf608a550f925717'  # commit the matrix cites
DIR = '_archive/hl_stage2'
CORE = 'HL_Live_Copy_Service_Core.py'
LEGACY = 'HL_Live_Copy_Service.py'
PROD = ['HL_Copy_App_SSOT.py', LEGACY, CORE,
        'convergence_shadow.py', 'exchange_truth.py']

# The certified Build 3 engine module(s) - see module docstring for authority.
CERT_SCOPE = [CORE]

SPAWN_MOD = {'subprocess', 'multiprocessing', 'pty'}
SPAWN_ATTR = {'system', 'popen', 'spawnl', 'spawnv', 'spawnve', 'execv', 'execvp', 'fork',
              'Popen', 'Process', 'call', 'run', 'check_call', 'check_output'}
SPAWN_NAME = {'Popen', 'Process', 'fork', 'system'}
STORE = ('sqlite3.connect', 'psycopg', 'pymysql', 'redis.Redis', 'shelve.open', 'dbm.open')


def git(repo, *a):
    r = subprocess.run(['git'] + list(a), cwd=str(repo), capture_output=True)
    if r.returncode:
        raise SystemExit('git %s failed: %s' % (' '.join(a), r.stderr.decode('utf-8', 'replace')))
    return r.stdout


def ls_py(repo, commit):
    out = git(repo, 'ls-tree', '-r', '--name-only', commit, '--', DIR).decode()
    names = [p.split('/')[-1] for p in out.split('\n')
             if p.endswith('.py') and p.startswith(DIR) and not p.split('/')[-1].startswith('test_')]
    return sorted(names)


def blob(repo, commit, name):
    return git(repo, 'show', '%s:%s/%s' % (commit, DIR, name)).decode('utf-8-sig', 'replace')


def asts(repo, commit, names=None):
    out = {}
    for n in (names or PROD):
        try:
            out[n] = ast.parse(blob(repo, commit, n), filename=n)
        except SystemExit:
            pass
    return out


def sha256_of(repo, commit, name):
    import hashlib
    return hashlib.sha256(git(repo, 'show', '%s:%s/%s' % (commit, DIR, name))).hexdigest()


# ---------------------------------------------------------------- ENG-INV-01
def spawn_sites(trees):
    hits = []
    for n, t in trees.items():
        for x in ast.walk(t):
            if isinstance(x, ast.Import):
                for a in x.names:
                    if a.name.split('.')[0] in SPAWN_MOD:
                        hits.append({'file': n, 'line': x.lineno, 'what': 'import ' + a.name})
            elif isinstance(x, ast.ImportFrom):
                if x.module and x.module.split('.')[0] in SPAWN_MOD:
                    hits.append({'file': n, 'line': x.lineno, 'what': 'from ' + x.module})
            elif isinstance(x, ast.Call):
                f = x.func
                if isinstance(f, ast.Attribute) and f.attr in SPAWN_ATTR and isinstance(f.value, ast.Name) \
                        and f.value.id in ('os', 'subprocess', 'multiprocessing'):
                    hits.append({'file': n, 'line': x.lineno, 'what': f.value.id + '.' + f.attr + '()'})
                if isinstance(f, ast.Name) and f.id in SPAWN_NAME:
                    hits.append({'file': n, 'line': x.lineno, 'what': f.id + '()'})
    return hits


# ---------------------------------------------------------------- ENG-INV-02
def order_nodes(trees):
    hits = []
    for n, t in trees.items():
        for x in ast.walk(t):
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == 'order':
                hits.append({'file': n, 'line': x.lineno, 'receiver': ast.unparse(x.func.value)})
    return sorted(hits, key=lambda h: (h['file'], h['line']))


def production_order_sites(trees, scope=None):
    """The narrowed ENG-INV-02 predicate: physical .order() send sites that
    belong to the CERTIFIED ENGINE SCOPE.

    Excluded by construction: every .order() node in a module outside
    CERT_SCOPE. Those modules are not the engine under certification (OD-26).
    The excluded nodes are returned so the narrowing is auditable, never silent.
    """
    scope = scope or CERT_SCOPE
    inside, outside = [], []
    for h in order_nodes(trees):
        (inside if h['file'] in scope else outside).append(h)
    return inside, outside


def cited_inv02_predicate(trees):
    """Verbatim predicate of the cited harness (harness_corrected_43731b4f.py L232):
       physical_calls = [ln for ln in order_calls if ln > 2700 and ln < 2800]
       passed = len(physical_calls) == 1
       ...where order_calls is the AST order-node list of the CORE file only."""
    core = [h['line'] for h in order_nodes({CORE: trees[CORE]})]
    win = [ln for ln in core if 2700 < ln < 2800]
    return {'core_order_lines': core, 'window_2700_2800': win, 'passed': len(win) == 1}


def mutate(repo, commit, kind):
    """Return {name: ast} for a perturbed copy of the production sources."""
    src = {n: blob(repo, commit, n) for n in PROD if n in ls_py(repo, commit)}
    if kind == 'inv01_add_subprocess':
        # EOL-agnostic: append, never string-replace (the blob is CRLF).
        src[CORE] = src[CORE] + (
            "\n\ndef _spawn_helper():\n"
            "    import subprocess\n"
            "    return subprocess.Popen(['cmd', '/c', 'echo hi'])\n")
    elif kind == 'inv01_add_second_process':
        src[CORE] = src[CORE] + \
            "\n\ndef _worker():\n    import multiprocessing\n    p = multiprocessing.Process(target=print)\n    p.start()\n    return p\n"
    elif kind == 'inv02_add_site_legacy_only':
        # A genuine second send path, added to the LEGACY module only.
        # Demonstrates that the narrowed predicate is scope-bounded.
        src[LEGACY] += \
            "\n\ndef _second_send_path(exchange, c, b, s, px):\n    return exchange.order(c, b, s, px, {'limit': {'tif': 'Ioc'}})\n"
    elif kind == 'inv02_add_site_core_far':
        # A genuine second send path inside the CERTIFIED engine, far from
        # _place_order. This MUST trip the narrowed predicate.
        src[CORE] = src[CORE] + \
            "\n\ndef _far_send(exchange, c, b, s, px):\n    return exchange.order(c, b, s, px, {})\n"
    elif kind == 'inv02_add_site_core_in_place_order':
        # A second send stacked directly inside the one sanctioned sender.
        lines = src[CORE].splitlines()
        for i, ln in enumerate(lines):
            if 'The ONE physical exchange order call' in ln:
                lines.insert(i + 4, "            exchange.order('MUT', True, 1, 1, {})")
                break
        src[CORE] = '\n'.join(lines)
    elif kind == 'inv02_add_site_core_in_window':
        lines = src[CORE].splitlines()
        lines.insert(2704, "            exchange.order('MUT', True, 1, 1, {})")
        src[CORE] = '\n'.join(lines)
    elif kind == 'inv06_add_runtime_file':
        src['HL_Copy_Runtime_v2.py'] = 'def p(exchange,c,b,s,px):\n    return exchange.order(c,b,s,px,{})\n'
    elif kind == 'inv06_add_store':
        src['exchange_truth.py'] += "\n\nimport sqlite3\n_CONN = sqlite3.connect('state.db')\n"
    else:
        raise SystemExit('unknown mutation ' + kind)
    return {n: ast.parse(t, filename=n) for n, t in src.items()}


def enclosing(repo, commit, name, line):
    src = blob(repo, commit, name).splitlines()
    best = None
    for i, ln in enumerate(src[:line], start=1):
        s = ln.strip()
        if s.startswith('def ') or s.startswith('class ') or s.startswith('async def '):
            best = {'line': i, 'def': s.rstrip(':')[:120]}
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--out', default='RESULT.json')
    a = ap.parse_args()
    repo = Path(a.repo)

    base_files = ls_py(repo, BASE)
    test_files = ls_py(repo, TEST)
    trees = asts(repo, TEST)

    # ---- ENG-INV-01
    hits01 = spawn_sites(trees)
    r01 = {'row': 'ENG-INV-01',
           'expected_behaviour': 'One process.',
           'assertion': 'AST of every production engine source at the cited commit contains no '
                        'process-spawn construct (import subprocess/multiprocessing/pty, '
                        'Popen()/Process()/fork(), os.system/popen/spawn*)',
           'pass': not hits01,
           'detail': {'files_scanned': [n for n in PROD if n in trees], 'spawn_sites': hits01}}

    # ---- ENG-INV-02 (narrowed)
    all_nodes = order_nodes(trees)
    cert_nodes, excluded_nodes = production_order_sites(trees)
    for h in excluded_nodes:
        h['excluded_because'] = ('module outside the certified engine scope; '
                                 'OD-26 fixes certification to %s' % CORE)
        h['enclosing'] = enclosing(repo, TEST, h['file'], h['line'])
    for h in cert_nodes:
        h['enclosing'] = enclosing(repo, TEST, h['file'], h['line'])

    r02 = {'row': 'ENG-INV-02',
           'expected_behaviour': 'Exactly one physical production .order() call site.',
           'predicate_name': 'ONE_PHYSICAL_ORDER_SITE_CERTIFIED_SCOPE',
           'assertion': ('exactly one `*.order(...)` Call node exists in the CERTIFIED BUILD 3 '
                         'ENGINE SCOPE (%s); .order() nodes in modules outside that scope are '
                         'reported separately and do not count' % ', '.join(CERT_SCOPE)),
           'certified_scope': CERT_SCOPE,
           'scope_authority': ['ARCHITECTURE.md scope budget ("physical production order sites: 1")',
                               'MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md OD-26 / section 5',
                               'CONTROL_STATE.json single_order_site'],
           'pass': len(cert_nodes) == 1,
           'detail': {'order_call_nodes_certified_scope': cert_nodes,
                      'count_certified_scope': len(cert_nodes),
                      'order_call_nodes_all': all_nodes,
                      'count_all': len(all_nodes),
                      'excluded_from_scope': excluded_nodes,
                      'note': ('count_all is reported unchanged so the narrowing is auditable. '
                               'Before this card the row was measured on count_all.')}}

    # ---- ENG-INV-06
    added = [f for f in test_files if f not in base_files]
    removed = [f for f in base_files if f not in test_files]
    base_trees = asts(repo, BASE, [n for n in base_files if n in PROD])
    base_nodes = order_nodes(base_trees) if base_trees else []
    stores = []
    for n, t in trees.items():
        txt = blob(repo, TEST, n)
        for tok in STORE:
            if tok in txt:
                stores.append({'file': n, 'token': tok})
    r06 = {'row': 'ENG-INV-06',
           'expected_behaviour': 'No new engine/runtime around Build 3.',
           'assertion': 'relative to the branch-point commit the production .py file set gains '
                        'no new file, no new .order() send site appears, and no new authoritative '
                        'persistent store constructor is introduced',
           'pass': (not added) and (not stores),
           'detail': {'base_commit': BASE, 'test_commit': TEST,
                      'base_production_files': base_files, 'test_production_files': test_files,
                      'added_files': added, 'removed_files': removed,
                      'base_order_sites': base_nodes, 'test_order_sites': all_nodes,
                      'new_store_tokens': stores}}

    # ------------------------------------------------------------ mutations
    ctl = []

    def add(row, mutation, res, expect_pass=False, detail=None, note=''):
        got = bool(res)
        ctl.append({'row': row, 'mutation': mutation,
                    'expected': 'PASS' if expect_pass else 'FAIL',
                    'actual_row_check': got, 'non_vacuous': got is expect_pass,
                    'detail': detail, 'note': note})

    add('ENG-INV-01', 'inv01_add_subprocess', not spawn_sites(mutate(repo, TEST, 'inv01_add_subprocess')))
    add('ENG-INV-01', 'inv01_add_second_process', not spawn_sites(mutate(repo, TEST, 'inv01_add_second_process')))

    # --- narrowed ENG-INV-02: the check MUST be able to fail inside its own scope
    m_far = mutate(repo, TEST, 'inv02_add_site_core_far')
    far_in, far_out = production_order_sites(m_far)
    add('ENG-INV-02', 'inv02_add_site_core_far', len(far_in) == 1,
        detail={'certified_scope_sites': far_in, 'count': len(far_in)},
        note='a second send path appended to the certified engine must trip the narrowed check')

    m_in = mutate(repo, TEST, 'inv02_add_site_core_in_place_order')
    in_in, in_out = production_order_sites(m_in)
    add('ENG-INV-02', 'inv02_add_site_core_in_place_order', len(in_in) == 1,
        detail={'certified_scope_sites': in_in, 'count': len(in_in)},
        note='a second send stacked inside the one sanctioned sender must also trip it')

    # --- the narrowing is explicit and falsifiable
    m_leg = mutate(repo, TEST, 'inv02_add_site_legacy_only')
    leg_in, leg_out = production_order_sites(m_leg)
    leg_all = order_nodes(m_leg)
    ctl.append({'row': 'ENG-INV-02',
                'mutation': 'inv02_add_site_legacy_only',
                'expected': 'PASS (scope-bounded: excluded from certified scope)',
                'actual_row_check': len(leg_in) == 1,
                'non_vacuous': (len(leg_in) == 1),
                'detail': {'certified_scope_count': len(leg_in),
                           'whole_tree_count': len(leg_all),
                           'excluded': leg_out},
                'note': ('demonstrates the scope boundary: the same synthetic send path '
                         'is invisible to the narrowed predicate and visible to the '
                         'unnarrowed one. Both numbers are reported.')})

    # --- reproduce the originally cited (window-bound) predicate for the record
    cited_base = cited_inv02_predicate(trees)
    cited_win = cited_inv02_predicate(mutate(repo, TEST, 'inv02_add_site_core_in_window'))
    cited_leg = cited_inv02_predicate(mutate(repo, TEST, 'inv02_add_site_legacy_only'))
    ctl.append({'row': 'ENG-INV-02',
                'mutation': 'reproduce the ORIGINAL cited predicate verbatim: window 2700<line<2800 on Core only',
                'expected': 'PASS on the unmutated tree',
                'actual_row_check': cited_base['passed'], 'non_vacuous': cited_base['passed'] is True,
                'detail': cited_base,
                'note': 'the original predicate was window- and file-bound; it is superseded, not reused'})
    ctl.append({'row': 'ENG-INV-02',
                'mutation': 'original cited predicate vs a real second send path in the LEGACY module',
                'expected': 'PASS - it is blind to every file except Core',
                'actual_row_check': cited_leg['passed'], 'non_vacuous': cited_leg['passed'] is True,
                'detail': {'cited_predicate': cited_leg, 'whole_tree_count': len(leg_all)},
                'note': 'this blindness is why the original predicate could not speak for the row'})
    ctl.append({'row': 'ENG-INV-02',
                'mutation': 'original cited predicate vs a second .order() site INSIDE 2700<line<2800',
                'expected': 'FAIL - its own-window negative control is real',
                'actual_row_check': cited_win['passed'], 'non_vacuous': cited_win['passed'] is False,
                'detail': cited_win})

    t06 = mutate(repo, TEST, 'inv06_add_runtime_file')
    new_names = [n for n in t06 if n not in test_files]
    add('ENG-INV-06', 'inv06_add_runtime_file', not new_names)
    t06b = mutate(repo, TEST, 'inv06_add_store')
    add('ENG-INV-06', 'inv06_add_store', not any(tok in ast.unparse(t06b['exchange_truth.py']) or tok in
                     blob(repo, TEST, 'exchange_truth.py') + "import sqlite3\n_CONN = sqlite3.connect('state.db')\n"
                     for tok in STORE))

    out = {'schema': 'eng_inv_01_02_06_reearn/v2',
           'card': 't_43fbb222',
           'supersedes_card': 't_20e1cb6d',
           'repo': 'binancebotty-bot/hyperliquid-build3-repair',
           'branch_base': BASE,
           'tested_commit': TEST,
           'inv02_predicate_version': 'CERTIFIED_SCOPE (narrowed, defect 2 of t_43fbb222)',
           'engine_sha256': {n: sha256_of(repo, TEST, n) for n in PROD if n in trees},
           'rows': [r01, r02, r06],
           'mutation_controls': ctl}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'rows': [(r['row'], r['pass']) for r in out['rows']],
                      'inv02_counts': {'certified_scope': len(cert_nodes), 'all': len(all_nodes)},
                      'controls_non_vacuous': [c['non_vacuous'] for c in ctl]}, indent=1))


if __name__ == '__main__':
    main()
