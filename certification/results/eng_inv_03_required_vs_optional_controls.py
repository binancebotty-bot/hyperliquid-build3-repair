#!/usr/bin/env python3
'''ENG-INV-03 control harness: REQUIRED vs OPTIONAL imports (non-vacuity gate).

The row predicate must score an import as a NEW DEPENDENCY only when the module is
required at import time. An import inside the body of a ``try`` whose handlers catch
ImportError / ModuleNotFoundError / Exception is OPTIONAL: the engine runs without it
(it has a fallback), so it must be reported as an optional fact, never as a violation.

Controls (all three must hold, otherwise the row is not non-vacuous):

  C1 NEGATIVE  bare required unapproved import injected into an engine-closure module
               -> ENG-INV-03 RED, naming file:line:module
  C2 POSITIVE  the same import guarded by try/except ImportError
               -> ENG-INV-03 GREEN, no violation for that module
  C3 SIBLINGS  ENG-INV-04 / ENG-INV-05 verdicts identical between the pre-change oracle
               and the current oracle on the same tree

Defect this harness pins: the pre-change predicate (imports_of() walks every Import node)
scores headroom.py:79 `import psutil` -- guarded by `except ImportError:` falling back to
`netstat -ano` -- as a required new dependency, so row 03 is a FALSE RED.

usage: python eng_inv_03_required_vs_optional_controls.py [repo_root]
'''
import json, pathlib, shutil, subprocess, sys, tempfile

BASE_REV = 'b3c090b0f53d2b6989a4850914d711271ffbe209'   # branch base: source of the PRE-change oracle
ORACLE_REL = 'certification/results/rowbound_oracle.py'
TARGET_REL = '_archive/hl_stage2/HL_Live_Copy_Service_Core.py'
MUT_MODULE = 'yaml'

BARE = 'import %s\n' % MUT_MODULE
GUARDED = 'try:\n    import %s\nexcept ImportError:\n    %s = None\n' % (MUT_MODULE, MUT_MODULE)


def run_oracle(oracle_path, root):
    # No --baseline override: the oracle's pinned DEPENDENCY_BASELINE_REF (43731b4f) is the
    # authority for "new". Passing the evaluated commit as the baseline would make the row
    # vacuous by construction -- the exact defect this harness exists to prevent.
    proc = subprocess.run([sys.executable, str(oracle_path), str(root)],
                          capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        report = None
    return {'exit_code': proc.returncode, 'report': report,
            'stdout_tail': (proc.stdout or '')[-400:], 'stderr_tail': (proc.stderr or '')[-400:]}


def scratch_copy(root):
    tmp = tempfile.mkdtemp(prefix='inv03_ctl_')
    dest = pathlib.Path(tmp) / 'tree'
    shutil.copytree(str(root), str(dest))
    return tmp, dest


def inject(dest, snippet, offset):
    '''Append snippet to the engine-closure target; return the injected import line number.'''
    p = pathlib.Path(dest) / TARGET_REL
    text = p.read_text(encoding='utf-8')
    if not text.endswith('\n'):
        text += '\n'
    before = text.count('\n')
    p.write_text(text + snippet, encoding='utf-8')
    return before + offset


def row03(report):
    return (report or {}).get('baseline', {}).get('ENG-INV-03', {})


def checks(report):
    return (report or {}).get('baseline', {}).get('checks', {})


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    oracle = root / ORACLE_REL
    results = {}

    # ---- C1 NEGATIVE: bare required unapproved import must go RED ----
    tmp, dest = scratch_copy(root)
    try:
        line = inject(dest, BARE, 1)
        got = run_oracle(oracle, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    r3 = row03(got['report'])
    viol = [v for v in r3.get('violations', []) if v.get('module') == MUT_MODULE]
    named = [v for v in viol
             if v.get('file') == pathlib.Path(TARGET_REL).name
             and v.get('line') == line and v.get('module') == MUT_MODULE]
    results['C1'] = {
        'injection': 'bare `%s` appended to %s' % (BARE.strip(), TARGET_REL),
        'expected_import_line': line,
        'ENG-INV-03': checks(got['report']).get('ENG-INV-03'),
        'new_unapproved': r3.get('new_unapproved'),
        'violations': r3.get('violations'),
        'exit_code': got['exit_code'],
        'names_file_line_module': bool(named),
        'PASS': checks(got['report']).get('ENG-INV-03') is False and bool(named),
    }

    # ---- C2 POSITIVE: the same import, guarded, must stay GREEN ----
    tmp, dest = scratch_copy(root)
    try:
        line = inject(dest, GUARDED, 2)
        got = run_oracle(oracle, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    r3 = row03(got['report'])
    flagged = [v for v in r3.get('violations', []) if v.get('module') == MUT_MODULE]
    results['C2'] = {
        'injection': 'try/except ImportError guarded `%s` appended to %s' % (BARE.strip(), TARGET_REL),
        'expected_import_line': line,
        'ENG-INV-03': checks(got['report']).get('ENG-INV-03'),
        'new_unapproved': r3.get('new_unapproved'),
        'yaml_flagged': bool(flagged),
        'violations': r3.get('violations'),
        'exit_code': got['exit_code'],
        'PASS': checks(got['report']).get('ENG-INV-03') is True and not flagged,
    }

    # ---- C3 SIBLINGS: pre-change oracle vs current oracle on the same tree ----
    pre_src = subprocess.run(['git', '-C', str(root), 'show', '%s:%s' % (BASE_REV, ORACLE_REL)],
                             capture_output=True, text=True)
    tmp = tempfile.mkdtemp(prefix='inv03_pre_')
    try:
        pre_oracle = pathlib.Path(tmp) / 'pre_oracle.py'
        pre_oracle.write_text(pre_src.stdout, encoding='utf-8')
        pre = run_oracle(pre_oracle, root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    post = run_oracle(oracle, root)
    sib = {}
    for row in ('ENG-INV-04', 'ENG-INV-05'):
        sib[row] = {'pre': checks(pre['report']).get(row), 'post': checks(post['report']).get(row)}
    results['C3'] = {
        'pre_oracle_source': 'git show %s:%s (sha256 %s)' % (
            BASE_REV, ORACLE_REL, sha256_of(pre_src.stdout.encode())),
        'siblings': sib,
        'differs': sorted(r for r in sib if sib[r]['pre'] != sib[r]['post']),
        'PASS': all(sib[r]['pre'] == sib[r]['post'] for r in sib),
    }
    results['row03_on_tree_unchanged'] = {
        'ENG-INV-03': checks(post['report']).get('ENG-INV-03'),
        'new_unapproved': row03(post['report']).get('new_unapproved'),
        'violations': row03(post['report']).get('violations'),
        'optional': row03(post['report']).get('optional', 'KEY_ABSENT'),
    }
    results['verdict'] = 'PASS' if all(results[c]['PASS'] for c in ('C1', 'C2', 'C3')) else 'FAIL'
    print(json.dumps(results, indent=2, default=str))
    print('CONTROLS %s' % results['verdict'])
    return 0 if results['verdict'] == 'PASS' else 1


def sha256_of(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    sys.exit(main())
