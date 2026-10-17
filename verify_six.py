import json, subprocess, sys, os, pathlib

BRREF = os.environ.get('BRREF', 'HEAD')
MATRIX = 'certification/certification_matrix.json'
SIX = ['ENG-INV-0%d' % i for i in range(1, 7)]

def matrix_at(ref):
    raw = subprocess.run(['git', 'show', '%s:%s' % (ref, MATRIX)], capture_output=True)
    return {r['id']: r for r in json.loads(raw.stdout.decode('utf-8-sig'))['records']}

# full path list of the ref's tree
tree = subprocess.run(['git', 'ls-tree', '-r', '--name-only', BRREF], capture_output=True)
if tree.returncode != 0:
    sys.exit('FATAL: ls-tree %s failed' % BRREF)
paths = set(tree.stdout.decode('utf-8').split())

before = matrix_at('origin/main')
after = matrix_at(BRREF)

print('ref =', BRREF, '| tree files =', len(paths))
fails = []
for k in SIX:
    a, b = before.get(k), after.get(k)
    ref = b.get('evidence_ref') or ''
    files = []
    for part in ref.split(' + '):
        p = part.split('#')[0].strip()
        if p:
            files.append(p)
    checks = [(p, p in paths, os.path.exists(p)) for p in files]
    ok = bool(ref) and bool(b.get('tested_commit')) and bool(b.get('tested_at_utc')) and all(c[1] for c in checks)
    print('')
    print('%s  %-11s -> %-11s tested_commit=%s tested_at=%s' % (k, a['result'], b['result'], b.get('tested_commit','')[:8], b.get('tested_at_utc','')))
    print('  evidence_ref: %s' % ref)
    for p, in_tree, on_disk in checks:
        print('    %-6s tree=%-5s disk=%-5s  %s' % ('OK' if in_tree else 'FAIL', in_tree, on_disk, p))
    if not ok:
        fails.append(k)

print('')
print('VERDICT: six rows resolvable =', not fails, '| failures =', fails)
print('register: PASS=%d NOT_TESTED=%d total=%d' % (
    sum(1 for r in after.values() if r['result'] == 'PASS'),
    sum(1 for r in after.values() if r['result'] == 'NOT_TESTED'),
    len(after)))
sys.exit(1 if fails else 0)
