#!/usr/bin/env python3
"""The hot-swap seam: allowlisted sibling modules swap in one atomic step, everything else refuses.

Each case runs in its own temp audit dir with a FAKE module registered in sys.modules under the
allowlisted name. The real exchange_truth.py is never imported, read or written here.

FAILING FIRST: before hotswap.py existed this file could not import it at all (ImportError), so
every case failed. After the seam, each refusal must leave the OLD callable working.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hotswap  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:180]) if not ok else ''))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fake_module(name, body):
    """Register a throwaway module under `name`, sourced from a real file so __file__ is honest."""
    tmp = Path(tempfile.mkdtemp(prefix='hotswap_src_'))
    src = tmp / ('%s.py' % name)
    src.write_text(body, encoding='utf-8')
    mod = type(sys)(name)
    mod.__file__ = str(src)
    exec(compile(body, str(src), 'exec'), mod.__dict__)
    sys.modules[name] = mod
    return mod, src


def write_artifact(body):
    tmp = Path(tempfile.mkdtemp(prefix='hotswap_art_'))
    art = tmp / 'artifact.py'
    raw = body.encode('utf-8')
    art.write_bytes(raw)
    return art, sha(raw)


def request(audit_dir, **fields):
    p = Path(audit_dir) / hotswap.REQUEST_FILE
    p.write_text(json.dumps(fields), encoding='utf-8')
    return p


def log_text(audit_dir):
    p = Path(audit_dir) / hotswap.LOG_FILE
    return p.read_text(encoding='utf-8') if p.is_file() else ''


# --- NO_REQUEST_IS_A_NOOP -------------------------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
try:
    out = hotswap.tick(audit)
    check('NO_REQUEST_IS_A_NOOP',
          out is False and log_text(audit) == '' and not (Path(audit) / hotswap.STATE_FILE).exists(),
          'returned %r, log=%r' % (out, log_text(audit)))
except Exception as exc:
    check('NO_REQUEST_IS_A_NOOP', False, '%s: %s' % (type(exc).__name__, exc))

# --- NOT_ALLOWLISTED_IS_REFUSED -------------------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
fake_module('exchange_truth', 'def marker():\n    return "old"\n')
art, art_sha = write_artifact('def marker():\n    return "hijack"\n')
try:
    request(audit, module='exchange_truth2', action='apply', artifact=str(art), sha256=art_sha)
    ok = hotswap.tick(audit)
    check('NOT_ALLOWLISTED_IS_REFUSED',
          ok is False and 'REFUSED_NOT_ALLOWLISTED' in log_text(audit)
          and 'exchange_truth2' not in sys.modules,
          'ok=%r log=%r imported=%r' % (ok, log_text(audit), 'exchange_truth2' in sys.modules))
except Exception as exc:
    check('NOT_ALLOWLISTED_IS_REFUSED', False, '%s: %s' % (type(exc).__name__, exc))

# --- PROTECTED_NAMES_ARE_ALWAYS_REFUSED (allowlist widened on purpose) ----------------------
saved_allow = hotswap.ALLOWLIST
refused, leaked = [], []
try:
    for variant in ('order_gate', 'send_queue', 'wallet_sync', 'secret_box', 'api_key_reader',
                    'HL_Live_Copy_Service_Core', 'HL_Copy_App_SSOT'):
        audit = tempfile.mkdtemp(prefix='hotswap_audit_')
        hotswap.ALLOWLIST = frozenset({variant})
        art, art_sha = write_artifact('SENTINEL = "should never load"\n')
        try:
            request(audit, module=variant, action='apply', artifact=str(art), sha256=art_sha)
            hotswap.tick(audit)
        except Exception as exc:
            leaked.append('%s raised %s' % (variant, type(exc).__name__))
            continue
        if 'REFUSED_PROTECTED_MODULE' in log_text(audit) and variant not in sys.modules:
            refused.append(variant)
        else:
            leaked.append('%s not refused: %r' % (variant, log_text(audit)))
finally:
    hotswap.ALLOWLIST = saved_allow
check('PROTECTED_NAMES_ARE_ALWAYS_REFUSED', len(refused) == 7 and not leaked,
      'refused=%r leaked=%r' % (refused, leaked))

# --- BAD_SHA_IS_REFUSED_AND_OLD_CODE_STAYS --------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
fake_module('exchange_truth', 'def marker():\n    return "old"\n')
art, _art_sha = write_artifact('def marker():\n    return "new"\n')
try:
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256='0' * 64)
    ok = hotswap.tick(audit)
    check('BAD_SHA_IS_REFUSED_AND_OLD_CODE_STAYS',
          ok is False and 'REFUSED_SHA_MISMATCH' in log_text(audit)
          and sys.modules['exchange_truth'].marker() == 'old',
          'ok=%r marker=%r log=%r' % (ok, sys.modules['exchange_truth'].marker(), log_text(audit)))
except Exception as exc:
    check('BAD_SHA_IS_REFUSED_AND_OLD_CODE_STAYS', False, '%s: %s' % (type(exc).__name__, exc))

# --- GOOD_ARTIFACT_SWAPS_IN_ONE_STEP --------------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
fake_module('exchange_truth', 'def marker():\n    return "old"\n\nVALUE = 1\n')
art, art_sha = write_artifact('def marker():\n    return "new"\n')
try:
    before = sys.modules['exchange_truth']
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    ok = hotswap.tick(audit)
    after = sys.modules['exchange_truth']
    check('GOOD_ARTIFACT_SWAPS_IN_ONE_STEP',
          ok is True and before is after and after.marker() == 'new'
          and hotswap.loaded_sha('exchange_truth') == art_sha
          and after.__file__ == str(art) and 'APPLIED' in log_text(audit),
          'ok=%r same=%r marker=%r sha=%r' % (ok, before is after, after.marker(),
                                              hotswap.loaded_sha('exchange_truth')))
except Exception as exc:
    check('GOOD_ARTIFACT_SWAPS_IN_ONE_STEP', False, '%s: %s' % (type(exc).__name__, exc))

# --- MID_CYCLE_SWAP -------------------------------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
fake_module('exchange_truth', 'def marker():\n    return "old"\n')
art, art_sha = write_artifact('def marker():\n    return "new"\n')
try:
    in_flight = sys.modules['exchange_truth'].marker   # held by a call already running
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    hotswap.tick(audit)
    next_call = sys.modules['exchange_truth'].marker
    check('MID_CYCLE_SWAP', in_flight() == 'old' and next_call() == 'new',
          'in_flight=%r next=%r' % (in_flight(), next_call()))
except Exception as exc:
    check('MID_CYCLE_SWAP', False, '%s: %s' % (type(exc).__name__, exc))

# --- ROLLBACK_RESTORES_THE_PREVIOUS_ARTIFACT ------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
_mod, src = fake_module('exchange_truth', 'def marker():\n    return "old"\n')
original_sha = sha(Path(src).read_bytes())
try:
    art, art_sha = write_artifact('def marker():\n    return "new"\n')
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    hotswap.tick(audit)
    swapped = sys.modules['exchange_truth'].marker()
    request(audit, module='exchange_truth', action='rollback')
    rb = hotswap.tick(audit)
    restored = sys.modules['exchange_truth'].marker()
    check('ROLLBACK_RESTORES_THE_PREVIOUS_ARTIFACT',
          swapped == 'new' and rb is True and restored == 'old'
          and hotswap.loaded_sha('exchange_truth') == original_sha
          and 'ROLLED_BACK' in log_text(audit),
          'swapped=%r rb=%r restored=%r sha=%r' % (swapped, rb, restored,
                                                    hotswap.loaded_sha('exchange_truth')))
except Exception as exc:
    check('ROLLBACK_RESTORES_THE_PREVIOUS_ARTIFACT', False, '%s: %s' % (type(exc).__name__, exc))

# --- MALFORMED_REQUEST_IS_REFUSED -----------------------------------------------------------
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
fake_module('exchange_truth', 'def marker():\n    return "old"\n')
try:
    (Path(audit) / hotswap.REQUEST_FILE).write_text('{not json', encoding='utf-8')
    ok1 = hotswap.tick(audit)
    log1 = log_text(audit)
    request(audit, module='exchange_truth', action='apply')   # no artifact, no sha
    ok2 = hotswap.tick(audit)
    log2 = log_text(audit)
    check('MALFORMED_REQUEST_IS_REFUSED',
          ok1 is False and ok2 is False and 'REFUSED_MALFORMED_REQUEST' in log1
          and 'REFUSED_MALFORMED_REQUEST' in log2
          and sys.modules['exchange_truth'].marker() == 'old',
          'ok1=%r ok2=%r marker=%r log=%r' % (ok1, ok2, sys.modules['exchange_truth'].marker(), log2))
except Exception as exc:
    check('MALFORMED_REQUEST_IS_REFUSED', False, '%s: %s' % (type(exc).__name__, exc))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
