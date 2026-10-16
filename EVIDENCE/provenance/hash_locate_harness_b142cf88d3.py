#!/usr/bin/env python3
'''HASH_LOCATE harness for kanban task t_c24c9a36.

Determines, READ-ONLY, whether 4 hash-prefixes cited by PASS rows on the
register of record (main @ b142cf88d389e791160f691aac3d936852b99975) resolve as
  (a) a git commit anywhere on this PC, or
  (b) a sha256 file-content digest of an engine core on disk.

KEY INSIGHT
  A sha256 file digest is 64 hex chars and can NEVER be resolved by
  `git cat-file`. Testing these prefixes as git objects is a category error.
  Prefixes are matched as PREFIXES in both tests.

SCOPE / SAFETY
  Read-only over every search target: no write, gc, prune, fetch or push into
  any other repo, worktree or object store. This script writes exactly one
  file, its own JSON result in THIS repo.

INPUTS
  repos_scanned.txt  newline-separated repo roots discovered by a bounded
                     `find ~ -maxdepth 5 -name HEAD -path *.git*` sweep.
  ENGINE_ROOT        bounded file scan root for the engine core.

RUN
  python3 hash_locate_harness_b142cf88d3.py
'''
import hashlib
import json
import os
import subprocess

PREFIXES = ['2dfbd57', '5de53fa', '5bda57be', '2dfbd571']
REGISTER = 'main @ b142cf88d389e791160f691aac3d936852b99975'
HOME = 'C:/Users/wigmore'
ENGINE_ROOT = HOME + '/trading_stack'
ENGINE_NAME = 'HL_Live_Copy_Service_Core.py'
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_LIST = os.path.join(HERE, 'repos_scanned.txt')
OUT = os.path.join(HERE, 'HASH_LOCATE_b142cf88d3.json')


def sha256_file(path):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1048576), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def commit_matches(repo):
    try:
        out = subprocess.run(['git', '-C', repo, 'rev-list', '--all'],
                             capture_output=True, text=True, timeout=180).stdout
    except Exception:
        return []
    hits = []
    for line in out.splitlines():
        line = line.strip()
        for p in PREFIXES:
            if line.startswith(p):
                hits.append(line)
                break
    return hits


def engine_files():
    found = {}
    for dirpath, _dirnames, filenames in os.walk(ENGINE_ROOT):
        if ENGINE_NAME in filenames:
            p = os.path.join(dirpath, ENGINE_NAME).replace('\\', '/')
            d = sha256_file(p)
            if d:
                found[p] = d
    return found


def repo_list():
    if not os.path.exists(REPO_LIST):
        return []
    seen = []
    with open(REPO_LIST, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            r = line.strip()
            if r and os.path.isdir(os.path.join(r, '.git')) and r not in seen:
                seen.append(r)
    return seen


def register_digests():
    '''Every 64-hex sha256-shaped token in the register of record, keyed by the
    prefixes we care about. READ-ONLY: git show only, no working tree.'''
    import re
    txt = subprocess.run(
        ['git', '-C', os.path.join(HOME, 'hyperliquid-build3-repair'),
         'grep', '-h', '-I', '-E', '-o', '[0-9a-f]{64}', 'main'],
        capture_output=True, text=True, timeout=300).stdout
    found = {}
    for m in re.finditer(r'[0-9a-f]{64}', txt):
        tok = m.group(0)
        for p in PREFIXES:
            if tok.startswith(p):
                found.setdefault(p, set()).add(tok)
    return {p: sorted(v) for p, v in found.items()}


def main():
    repos = repo_list()
    commits = {}
    for r in repos:
        for sha in commit_matches(r):
            commits.setdefault(sha, r)

    reg = register_digests()
    files = engine_files()
    digest_index = {}
    for p, d in files.items():
        digest_index.setdefault(d, []).append(p)

    result = {
        'task': 't_c24c9a36',
        'register_of_record': REGISTER,
        'method': {
            'commit_scan': 'git -C <repo> rev-list --all, prefix match, over %d repos' % len(repos),
            'file_scan': 'sha256 of every %s under %s (%d files)' % (
                ENGINE_NAME, ENGINE_ROOT, len(files)),
            'note': 'a 64-hex sha256 file digest can NEVER resolve via git cat-file',
        },
        'repos_scanned': len(repos),
        'engine_files_scanned': len(files),
        'hashes': {},
    }

    for p in PREFIXES:
        entry = {'prefix': p, 'as_git_commit': None, 'as_sha256_digest': None,
                 'full_digests_cited_by_register': reg.get(p, []),
                 'digest_present_on_disk': []}
        for sha in sorted(commits):
            if sha.startswith(p):
                entry['as_git_commit'] = {'sha': sha, 'repo': commits[sha]}
                break
        for d in sorted(digest_index):
            if d.startswith(p):
                entry['as_sha256_digest'] = {'sha256': d, 'paths': sorted(digest_index[d])}
                break
        for d in entry['full_digests_cited_by_register']:
            if d in digest_index:
                entry['digest_present_on_disk'].append(
                    {'sha256': d, 'paths': sorted(digest_index[d])})
        result['hashes'][p] = entry

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
