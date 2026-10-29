#!/usr/bin/env python3
"""The hot-swap seam: allowlisted sibling modules swap in one atomic step, everything else refuses.

Each case runs in its own temp audit dir with a FAKE module registered in sys.modules under the
allowlisted name, and a fake importer that does what the engine does: hold a guard proxy and
register a one-assignment rebind. The real exchange_truth.py is never imported, read or written.

The guard is shared for calls and exclusive for the swap, with a fail-closed timeout. Every
ordering assertion uses threading.Event plus a bounded join - no sleeps.
"""
import hashlib
import json
import sys
import tempfile
import threading
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
    tmp = Path(tempfile.mkdtemp(prefix='hotswap_src_'))
    src = tmp / ('%s.py' % name)
    src.write_text(body, encoding='utf-8')
    mod = type(sys)(name)
    mod.__file__ = str(src)
    exec(compile(body, str(src), 'exec'), mod.__dict__)
    sys.modules[name] = mod
    return mod, src


def fake_importer(name='exchange_truth', body='def marker():\n    return "old"\n'):
    mod, src = fake_module(name, body)
    box = {'X': hotswap.guarded(mod)}
    hotswap.register_setter(name, lambda new: box.__setitem__('X', hotswap.guarded(new)))
    return box, src


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


def state_bytes(audit_dir):
    p = Path(audit_dir) / hotswap.STATE_FILE
    return p.read_bytes() if p.is_file() else b''


def wait(event, timeout=5.0):
    return event.wait(timeout)


# --- NO_REQUEST_IS_A_NOOP ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
try:
    out = hotswap.tick(audit)
    check('NO_REQUEST_IS_A_NOOP',
          out is False and log_text(audit) == '' and not (Path(audit) / hotswap.STATE_FILE).exists(),
          'returned %r, log=%r' % (out, log_text(audit)))
except Exception as exc:
    check('NO_REQUEST_IS_A_NOOP', False, '%s: %s' % (type(exc).__name__, exc))

# --- NOT_ALLOWLISTED_IS_REFUSED ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
fake_importer()
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

# --- PROTECTED_NAMES_ARE_ALWAYS_REFUSED ---
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

# --- BAD_SHA_IS_REFUSED_AND_OLD_CODE_STAYS ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer()
art, _art_sha = write_artifact('def marker():\n    return "new"\n')
try:
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256='0' * 64)
    ok = hotswap.tick(audit)
    check('BAD_SHA_IS_REFUSED_AND_OLD_CODE_STAYS',
          ok is False and 'REFUSED_SHA_MISMATCH' in log_text(audit) and box['X'].marker() == 'old',
          'ok=%r marker=%r log=%r' % (ok, box['X'].marker(), log_text(audit)))
except Exception as exc:
    check('BAD_SHA_IS_REFUSED_AND_OLD_CODE_STAYS', False, '%s: %s' % (type(exc).__name__, exc))

# --- GOOD_ARTIFACT_SWAPS_IN_ONE_STEP ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer(body='def marker():\n    return "old"\n\nVALUE = 1\n')
art, art_sha = write_artifact('def marker():\n    return "new"\n')
try:
    old_obj = box['X']._fallback
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    ok = hotswap.tick(audit)
    new_obj = sys.modules['exchange_truth']
    check('GOOD_ARTIFACT_SWAPS_IN_ONE_STEP',
          ok is True and new_obj is not old_obj and box['X'].marker() == 'new'
          and hotswap.loaded_sha('exchange_truth') == art_sha
          and new_obj.__file__ == str(art) and 'APPLIED' in log_text(audit),
          'ok=%r rebound=%r marker=%r sha=%r' % (ok, new_obj is not old_obj, box['X'].marker(),
                                                 hotswap.loaded_sha('exchange_truth')))
except Exception as exc:
    check('GOOD_ARTIFACT_SWAPS_IN_ONE_STEP', False, '%s: %s' % (type(exc).__name__, exc))

# --- FOLLOWER_VOLUME_MODULE_IS_ALLOWLISTED_BUT_CORE_STAYS_PROTECTED ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer(name='follower_volume', body='def read_24h_volumes():\n    return "old"\n')
art, art_sha = write_artifact('def read_24h_volumes():\n    return "new"\n')
try:
    request(audit, module='follower_volume', action='apply', artifact=str(art), sha256=art_sha)
    ok = hotswap.tick(audit)
    check('FOLLOWER_VOLUME_MODULE_IS_ALLOWLISTED',
          ok is True and box['X'].read_24h_volumes() == 'new'
          and hotswap.loaded_sha('follower_volume') == art_sha,
          'ok=%r value=%r' % (ok, box['X'].read_24h_volumes()))
finally:
    saved_allow = hotswap.ALLOWLIST
    hotswap.ALLOWLIST = frozenset({'follower_volume', 'HL_Live_Copy_Service_Core'})
    audit = tempfile.mkdtemp(prefix='hotswap_audit_')
    art, art_sha = write_artifact('def unexpected():\n    return True\n')
    request(audit, module='HL_Live_Copy_Service_Core', action='apply', artifact=str(art), sha256=art_sha)
    refused = hotswap.tick(audit) is False and 'REFUSED_PROTECTED_MODULE' in log_text(audit)
    hotswap.ALLOWLIST = saved_allow
    check('CORE_REMAINS_PROTECTED_WITH_VOLUME_ALLOWLIST', refused
          and 'HL_Live_Copy_Service_Core' not in sys.modules)
check('VOLUME_SWAP_GUARD_ISOLATED_FROM_EXCHANGE_TRUTH',
      hotswap.guard('follower_volume') is not hotswap.guard())

# --- STAGED_MODULE_IDENTITY ---
try:
    staged = hotswap._build(Path(str(art)), art.read_bytes(), 'exchange_truth')
    spec_name = getattr(getattr(staged, '__spec__', None), 'name', None)
    spec_origin = getattr(getattr(staged, '__spec__', None), 'origin', None)
    check('STAGED_MODULE_IDENTITY',
          staged.__name__ == 'exchange_truth' and spec_name == 'exchange_truth'
          and str(spec_origin) == str(art) and staged.__file__ == str(art)
          and staged.__loader__ is not None,
          '__name__=%r spec=%r origin=%r file=%r' % (staged.__name__, spec_name, spec_origin,
                                                     staged.__file__))
except Exception as exc:
    check('STAGED_MODULE_IDENTITY', False, '%s: %s' % (type(exc).__name__, exc))

# --- LOOKUP_TO_CALL_GAP_IS_CLOSED ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer(body='def marker():\n    return "old"\n')
art2, art2_sha = write_artifact('def marker():\n    return "new"\n')
try:
    stale_callable = box['X'].marker          # lookup BEFORE the swap
    request(audit, module='exchange_truth', action='apply', artifact=str(art2), sha256=art2_sha)
    swapped = hotswap.tick(audit)
    ran = stale_callable()                    # call AFTER the swap
    check('LOOKUP_TO_CALL_GAP_IS_CLOSED',
          swapped is True and ran == 'new',
          'swapped=%r call_after_swap_returned=%r (must be new)' % (swapped, ran))
except Exception as exc:
    check('LOOKUP_TO_CALL_GAP_IS_CLOSED', False, '%s: %s' % (type(exc).__name__, exc))

# --- LOADED_SHA_IS_THE_INSTALLED_DIGEST_NOT_THE_FILE_HASH ---
try:
    art2.write_bytes(b'def marker():\n    return "tampered"\n')
    mutated = hotswap.loaded_sha('exchange_truth')
    art2.unlink()
    deleted = hotswap.loaded_sha('exchange_truth')
    check('LOADED_SHA_IS_THE_INSTALLED_DIGEST_NOT_THE_FILE_HASH',
          mutated == art2_sha and deleted == art2_sha and box['X'].marker() == 'new',
          'installed=%r mutated=%r deleted=%r' % (art2_sha, mutated, deleted))
except Exception as exc:
    check('LOADED_SHA_IS_THE_INSTALLED_DIGEST_NOT_THE_FILE_HASH', False, '%s: %s' % (type(exc).__name__, exc))

# --- NEW_CALL_AFTER_SWAP_IS_ENTIRELY_NEW ---
try:
    check('NEW_CALL_AFTER_SWAP_IS_ENTIRELY_NEW',
          box['X'].marker() == 'new' and not hasattr(box['X']._fallback, 'VALUE'),
          'marker=%r stale_VALUE=%r' % (box['X'].marker(), getattr(box['X']._fallback, 'VALUE', None)))
except Exception as exc:
    check('NEW_CALL_AFTER_SWAP_IS_ENTIRELY_NEW', False, '%s: %s' % (type(exc).__name__, exc))

# --- ROLLBACK_RESTORES_THE_PREVIOUS_ARTIFACT ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, src = fake_importer()
original_sha = sha(Path(src).read_bytes())
try:
    art, art_sha = write_artifact('def marker():\n    return "new"\n')
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    hotswap.tick(audit)
    swapped = box['X'].marker()
    request(audit, module='exchange_truth', action='rollback')
    rb = hotswap.tick(audit)
    restored = box['X'].marker()
    check('ROLLBACK_RESTORES_THE_PREVIOUS_ARTIFACT',
          swapped == 'new' and rb is True and restored == 'old'
          and hotswap.loaded_sha('exchange_truth') == original_sha
          and 'ROLLED_BACK' in log_text(audit),
          'swapped=%r rb=%r restored=%r sha=%r' % (swapped, rb, restored, hotswap.loaded_sha('exchange_truth')))
except Exception as exc:
    check('ROLLBACK_RESTORES_THE_PREVIOUS_ARTIFACT', False, '%s: %s' % (type(exc).__name__, exc))

# --- STATE_WRITE_FAILED_IS_REFUSED_AND_NOTHING_IS_INSTALLED ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer()
art, art_sha = write_artifact('def marker():\n    return "new"\n')
saved_writer = hotswap._write_state
try:
    hotswap._write_state = lambda *a, **k: None
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    ok = hotswap.tick(audit)
    check('STATE_WRITE_FAILED_IS_REFUSED_AND_NOTHING_IS_INSTALLED',
          ok is False and 'REFUSED_STATE_WRITE_FAILED' in log_text(audit) and box['X'].marker() == 'old'
          and not (Path(audit) / hotswap.STATE_FILE).exists(),
          'ok=%r marker=%r log=%r' % (ok, box['X'].marker(), log_text(audit)))
finally:
    hotswap._write_state = saved_writer

# --- TWO_CONCURRENT_CALLS_DO_NOT_BLOCK_EACH_OTHER ---
inside = [threading.Event(), threading.Event()]
release = threading.Event()
error = []


def concurrent_call(slot):
    try:
        with hotswap.guard():
            inside[slot].set()
            if not wait(release):
                error.append('call %d timed out waiting for its peer' % slot)
    except Exception as exc:
        error.append('%s: %s' % (type(exc).__name__, exc))


threads = [threading.Thread(target=concurrent_call, args=(i,), daemon=True) for i in (0, 1)]
for t in threads:
    t.start()
both = wait(inside[0]) and wait(inside[1])
release.set()
for t in threads:
    t.join(5)
check('TWO_CONCURRENT_CALLS_DO_NOT_BLOCK_EACH_OTHER',
      both and not error and not any(t.is_alive() for t in threads),
      'both_inside=%r errors=%r' % (both, error))

# --- PAUSED_CALL_BLOCKS_THE_SWAP ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer(body=(
    'import threading\n'
    'ENTERED = threading.Event()\n'
    'RELEASE = threading.Event()\n'
    'def slow():\n'
    '    ENTERED.set()\n'
    '    RELEASE.wait(10)\n'
    '    return "old"\n'
    'def marker():\n'
    '    return "old"\n'))
art, art_sha = write_artifact('def marker():\n    return "new"\n\ndef slow():\n    return "new"\n')
try:
    paused_result = []
    slow_mod = sys.modules['exchange_truth']
    slow_thread = threading.Thread(target=lambda: paused_result.append(box['X'].slow()), daemon=True)
    slow_thread.start()
    entered = wait(slow_mod.ENTERED)
    request(audit, module='exchange_truth', action='apply', artifact=str(art), sha256=art_sha)
    swap_result = []
    swap_thread = threading.Thread(target=lambda: swap_result.append(hotswap.tick(audit)), daemon=True)
    swap_thread.start()
    wait(hotswap.guard().swap_entered)
    # NO guarded call here: while the swap holds the exclusive turn any entry would park, which is the
    # very race this test exists to avoid. The swap being unfinished IS the assertion.
    swap_thread.join(0.2)
    blocked = swap_thread.is_alive() and not swap_result and 'APPLIED' not in log_text(audit)
    slow_mod.RELEASE.set()
    slow_thread.join(5)
    swap_thread.join(5)
    check('PAUSED_CALL_BLOCKS_THE_SWAP',
          entered and blocked and paused_result == ['old'] and swap_result == [True]
          and box['X'].marker() == 'new' and hotswap.loaded_sha('exchange_truth') == art_sha,
          'entered=%r blocked=%r paused=%r swap=%r marker=%r'
          % (entered, blocked, paused_result, swap_result, box['X'].marker()))
except Exception as exc:
    check('PAUSED_CALL_BLOCKS_THE_SWAP', False, '%s: %s' % (type(exc).__name__, exc))

# --- BUSY_APPLY_LEAVES_STATE_BYTE_IDENTICAL ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer(body='def marker():\n    return "old"\n')
art_a, sha_a = write_artifact('def marker():\n    return "A"\n')
art_b, sha_b = write_artifact('def marker():\n    return "B"\n')
saved_timeout = hotswap.GUARD_SWAP_TIMEOUT_SEC
holder_release = threading.Event()
held = threading.Event()
try:
    hotswap.GUARD_SWAP_TIMEOUT_SEC = 0.2
    request(audit, module='exchange_truth', action='apply', artifact=str(art_a), sha256=sha_a)
    first = hotswap.tick(audit)
    before = state_bytes(audit)

    def stuck_call():
        with hotswap.guard():
            held.set()
            holder_release.wait(10)

    holder = threading.Thread(target=stuck_call, daemon=True)
    holder.start()
    wait(held)
    request(audit, module='exchange_truth', action='apply', artifact=str(art_b), sha256=sha_b)
    second = hotswap.tick(audit)
    after = state_bytes(audit)
    live = box['X'].marker()
    holder_release.set()
    holder.join(5)
    check('BUSY_APPLY_LEAVES_STATE_BYTE_IDENTICAL',
          first is True and second is False and 'REFUSED_BUSY' in log_text(audit)
          and before == after and live == 'A'
          and hotswap.loaded_sha('exchange_truth') == sha_a,
          'first=%r second=%r state_changed=%r live=%r sha=%r'
          % (first, second, before != after, live, hotswap.loaded_sha('exchange_truth')))
finally:
    hotswap.GUARD_SWAP_TIMEOUT_SEC = saved_timeout

# --- BUSY_ROLLBACK_LEAVES_STATE_BYTE_IDENTICAL ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer(body='def marker():\n    return "old"\n')
art_c, sha_c = write_artifact('def marker():\n    return "C"\n')
saved_timeout = hotswap.GUARD_SWAP_TIMEOUT_SEC
holder_release2 = threading.Event()
held2 = threading.Event()
try:
    hotswap.GUARD_SWAP_TIMEOUT_SEC = 0.2
    request(audit, module='exchange_truth', action='apply', artifact=str(art_c), sha256=sha_c)
    applied = hotswap.tick(audit)
    before = state_bytes(audit)

    def stuck_call2():
        with hotswap.guard():
            held2.set()
            holder_release2.wait(10)

    holder2 = threading.Thread(target=stuck_call2, daemon=True)
    holder2.start()
    wait(held2)
    request(audit, module='exchange_truth', action='rollback')
    rb = hotswap.tick(audit)
    after = state_bytes(audit)
    live = box['X'].marker()
    holder_release2.set()
    holder2.join(5)
    check('BUSY_ROLLBACK_LEAVES_STATE_BYTE_IDENTICAL',
          applied is True and rb is False and 'REFUSED_BUSY' in log_text(audit)
          and before == after and live == 'C' and hotswap.loaded_sha('exchange_truth') == sha_c,
          'applied=%r rb=%r state_changed=%r live=%r sha=%r'
          % (applied, rb, before != after, live, hotswap.loaded_sha('exchange_truth')))
finally:
    hotswap.GUARD_SWAP_TIMEOUT_SEC = saved_timeout

# --- MALFORMED_REQUEST_IS_REFUSED ---
audit = tempfile.mkdtemp(prefix='hotswap_audit_')
box, _src = fake_importer()
try:
    (Path(audit) / hotswap.REQUEST_FILE).write_text('{not json', encoding='utf-8')
    ok1 = hotswap.tick(audit)
    log1 = log_text(audit)
    request(audit, module='exchange_truth', action='apply')
    ok2 = hotswap.tick(audit)
    log2 = log_text(audit)
    check('MALFORMED_REQUEST_IS_REFUSED',
          ok1 is False and ok2 is False and 'REFUSED_MALFORMED_REQUEST' in log1
          and 'REFUSED_MALFORMED_REQUEST' in log2 and box['X'].marker() == 'old',
          'ok1=%r ok2=%r marker=%r log=%r' % (ok1, ok2, box['X'].marker(), log2))
except Exception as exc:
    check('MALFORMED_REQUEST_IS_REFUSED', False, '%s: %s' % (type(exc).__name__, exc))

# --- STATE_WRITE_IS_ATOMIC: a crash mid-write must leave the OLD map whole ---
audit_atomic = tempfile.mkdtemp(prefix='hotswap_atomic_')
_state_file = hotswap._state_path(audit_atomic)
hotswap._write_state(audit_atomic, {'exchange_truth': {'installed_path': 'old', 'installed_sha': 'oldsha'}})
_before = _state_file.read_text(encoding='utf-8')
_real_replace = hotswap.os.replace


def _boom(src, dst):
    raise OSError('simulated crash during replace')


hotswap.os.replace = _boom
try:
    hotswap._write_state(audit_atomic, {'exchange_truth': {'installed_path': 'new', 'installed_sha': 'newsha'}})
finally:
    hotswap.os.replace = _real_replace
_after = _state_file.read_text(encoding='utf-8')
check('STATE_WRITE_IS_ATOMIC', _after == _before and 'oldsha' in _after,
      'prior state changed after a failed write: %r' % (_after[:120],))

# --- SETTER_RAISE_ROLLS_THE_STATE_BACK: a refused install must not leave a pointer to dead code ---
audit_setter = tempfile.mkdtemp(prefix='hotswap_setter_')
OLD_BODY = "def marker():" + chr(10) + '    return "old"' + chr(10)
NEW_BODY = "def marker():" + chr(10) + '    return "new"' + chr(10)
box2, _src2 = fake_importer(body=OLD_BODY)
art2, art2_sha = write_artifact(NEW_BODY)
hotswap._write_state(audit_setter, {'exchange_truth': {'installed_path': 'prior', 'installed_sha': 'priorsha'}})
_sf2 = hotswap._state_path(audit_setter)
_pre2 = _sf2.read_text(encoding='utf-8')


def _raising_setter(_new):
    raise RuntimeError('importer refused the rebind')


hotswap.register_setter('exchange_truth', _raising_setter)
request(audit_setter, module='exchange_truth', action='apply', artifact=str(art2), sha256=art2_sha)
_ok2 = hotswap.tick(audit_setter)
_post2 = _sf2.read_text(encoding='utf-8')
check('SETTER_RAISE_ROLLS_THE_STATE_BACK',
      _ok2 is False and _post2 == _pre2 and box2['X'].marker() == 'old',
      'tick=%r state_changed=%r old_code_still_live=%r'
      % (_ok2, _post2 != _pre2, box2['X'].marker() == 'old'))

# --- STALE_PREVIOUS_POINTER_IS_NOT_MASKED_BY_A_MATCHING_PATH_AND_SHA (Codex 6408591328) ---
audit_stale = tempfile.mkdtemp(prefix='hotswap_stale_')
OLD_BODY_FOR_STALE = "def marker():" + chr(10) + '    return "old"' + chr(10)
NEW_BODY_FOR_STALE = "def marker():" + chr(10) + '    return "new"' + chr(10)
box3, _src3 = fake_importer(body=OLD_BODY_FOR_STALE)
art3, art3_sha = write_artifact(NEW_BODY_FOR_STALE)
_state_file3 = hotswap._state_path(audit_stale)
hotswap._write_state(audit_stale, {'exchange_truth': {
    'installed_path': str(art3), 'installed_sha': art3_sha,
    'previous_path': 'C:/old/previous.py', 'previous_sha': 'olds'}})
_before3 = _state_file3.read_text(encoding='utf-8')
_saved_writer = hotswap._write_state
hotswap._write_state = lambda *a, **k: False
try:
    request(audit_stale, module='exchange_truth', action='apply', artifact=str(art3), sha256=art3_sha)
    _ok3 = hotswap.tick(audit_stale)
finally:
    hotswap._write_state = _saved_writer
_after3 = _state_file3.read_text(encoding='utf-8')
_refused3 = 'REFUSED_STATE_WRITE_FAILED' in log_text(audit_stale)
check('STALE_PREVIOUS_POINTER_IS_NOT_MASKED_BY_MATCHING_PATH_AND_SHA',
      _ok3 is False and _refused3 and box3['X'].marker() == 'old' and _after3 == _before3,
      'tick=%r refused=%r old_live=%r state_changed=%r'
      % (_ok3, _refused3, box3['X'].marker() == 'old', _after3 != _before3))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
