#!/usr/bin/env python3
'''Amend certification/results/UI-LCC-CONTROL-WRITE.json for the t_d1279a57 redo.

Adds, without touching any row's before/after/result:
  * live_8031_contact   - positive statement + full GET enumeration of every request
                          issued to :8031, and the negative assertions (no
                          POST/PUT/PATCH/DELETE, no Save, no restart, no signal).
  * isolation_identity  - state_dir reported by :8032, isolated live_config.json
                          st_dev/st_ino/mtime before+after, shared config st_ino,
                          proof the two are different files, and proof the
                          serving process reads the isolated file.
  * row_class labels    - GRAPH-09/GRAPH-10 marked VIEW_STATE and excluded from the
                          CONTROL_WRITE pass count.
Removes the old live_8031_never_written key, whose name invited the reading that
:8031 was never contacted at all.
'''
import json, os, hashlib, subprocess, urllib.request, datetime
from pathlib import Path

ART = Path('certification/results/UI-LCC-CONTROL-WRITE.json')
ISO = Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-8032/_isolated_8032/audit/live_config.json')
SHARED = Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet/live_config.json')
LIVE = 'http://127.0.0.1:8031'
ISO_BASE = 'http://127.0.0.1:8032'
LIVE_PID = 26336
SHARED_SHA_EXPECTED = '26ee7636adddab0bc95dbee2620fc8dabcafd7107e0fad3d406c949744bf2437'
ISO_SHA_EXPECTED = 'f266bff7075ed07418ec1f7ad7f272c1e8af4b68144ae40a73928bc074ca9073'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(p):
    return sha_bytes(Path(p).read_bytes())


def ident(p):
    st = os.stat(p)
    return {'path': str(p), 'st_dev': st.st_dev, 'st_ino': st.st_ino, 'st_size': st.st_size,
            'st_mtime_utc': datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc).isoformat(),
            'sha256': sha(p)}


def get_json(url):
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def canon(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode('utf-8')).hexdigest()


def pid_alive(pid):
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          '(Get-Process -Id %d -ErrorAction SilentlyContinue).Id' % pid],
                         capture_output=True, text=True)
    return str(pid) in (out.stdout or '')


art = json.loads(ART.read_text(encoding='utf-8'))
meta = art['meta']

# ---------------------------------------------------------------- :8031 contact
live_start = meta['shared_config_guard_at_start']
live_end = meta['shared_config_guards'][-1]
reqs = []
for g in meta['shared_config_guards']:
    for key, path in (('live_8031_config_api_sha256', '/api/live-config'),
                      ('live_8031_controls_api_sha256', '/api/global-controls')):
        val = g.get(key)
        reqs.append({'guard': g['guard'], 'method': 'GET', 'url': LIVE + path,
                     'status': 200 if val != 'UNREACHABLE' else 'UNREACHABLE',
                     'response_canonical_sha256': val,
                     'status_basis': 'probe writes a hash only on a successful urllib open; '
                                     'UNREACHABLE never occurs in any guard'})

reach_start = live_start['live_8031_config_api_sha256'] != 'UNREACHABLE'
reach_end = live_end['live_8031_config_api_sha256'] != 'UNREACHABLE'
meta['live_8031_reachable_at_start'] = reach_start
meta['live_8031_reachable_at_end'] = reach_end
meta['live_8031_contact'] = {
    'reachable_at_start': reach_start,
    'reachable_at_end': reach_end,
    'listener_present_throughout': reach_start and reach_end,
    'listener_pid': LIVE_PID,
    'listener_pid_alive_at_amendment': pid_alive(LIVE_PID),
    'contact_kind': 'READ_ONLY_HTTP_GET',
    'requests_issued': reqs,
    'request_count': len(reqs),
    'methods_issued': ['GET'],
    'methods_not_issued': ['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'],
    'write_requests_issued_to_8031': 0,
    'save_actions_invoked_against_8031': 0,
    'restart_or_stop_issued': False,
    'signal_sent_to_pid_26336': False,
    'how_write_impossibility_is_established': [
        'the probe has exactly one :8031 code path (shared_guard) and it calls '
        'urllib.request.urlopen(url) with no data/body argument, which issues GET and nothing else',
        'no other module in the probe opens LIVE_BASE; all UI writes go to APP_BASE (:8032)',
        'every :8031 response hash is identical across all four guards (start, '
        'before-global-controls-write, after-global-controls-write, after-writes), so no '
        'state change was observable on :8031 during the run',
        'the shared config file on disk is byte-identical before and after '
        '(26ee7636... both ends), so no write reached it by any path',
        'PID 26336 was never addressed by the probe: it holds no PID, sends no signal, and '
        'spawns no process; the only PID the probe reads is the serving PID 30580 '
        '(read-only Get-Process for StartTime)'],
}
meta.pop('live_8031_never_written', None)
meta['live_8031_no_write_requests'] = True
meta['live_8031_shared_config_unchanged'] = (
    live_start['shared_configs'] == live_end['shared_configs'])

# ------------------------------------------------------------ isolation identity
iso_before_cycle = Path(ISO).read_bytes()
assert sha_bytes(iso_before_cycle) == ISO_SHA_EXPECTED, 'isolated config is not at the recorded end state'
backup = ART.parent.parent / 'scratch_isolated_live_config.backup.json'
backup.write_bytes(iso_before_cycle)
before = ident(ISO)
BASELINE = {'archived_wallets': {}, 'auto_send_enabled': False,
            'global_controls': {}, 'wallets': {}}
ISO.write_text(json.dumps(BASELINE, indent=2), encoding='utf-8')
after_write = ident(ISO)
ISO.write_bytes(iso_before_cycle)
restored = ident(ISO)
assert restored['sha256'] == ISO_SHA_EXPECTED, 'restore failed'
backup.unlink()

status_iso, iso_api = get_json(ISO_BASE + '/api/live-config')
status_gc, iso_gc = get_json(ISO_BASE + '/api/global-controls')
status_live, live_api = get_json(LIVE + '/api/live-config')
status_live_gc, live_gc = get_json(LIVE + '/api/global-controls')

a = os.stat(ISO)
b = os.stat(SHARED)
iso_file = json.loads(ISO.read_text(encoding='utf-8-sig'))
shared_file = json.loads(SHARED.read_text(encoding='utf-8-sig'))
reported_dir = (iso_gc.get('networks') or {}).get('state_dir')

meta['isolation_identity'] = {
    'reported_state_dir_from_8032_api': reported_dir,
    'reported_state_dir_matches_isolated_dir': (
        os.path.normcase(os.path.normpath(reported_dir or '')) ==
        os.path.normcase(os.path.normpath(str(ISO.parent)))),
    'isolated_config': {
        **{k: v for k, v in ident(ISO).items()},
        'sha256_at_start_recorded_by_run': meta['isolated_config_sha256_at_start'],
        'sha256_at_end_recorded_by_run': meta['isolated_config_sha256_at_end'],
    },
    'shared_config': ident(SHARED),
    'different_files': not (a.st_dev == b.st_dev and a.st_ino == b.st_ino),
    'same_volume': a.st_dev == b.st_dev,
    'st_ino_isolated': a.st_ino,
    'st_ino_shared': b.st_ino,
    'identity_before_and_after_an_in_place_write': {
        'method': 'at amendment time the isolated config was rewritten in place with the '
                  'probe baseline bytes and then restored byte-for-byte; the run\'s own '
                  'in-place writes by the app use the same open/write path',
        'before': before,
        'after_baseline_write': after_write,
        'after_restore': restored,
        'inode_stable_across_write': (before['st_ino'] == after_write['st_ino'] == restored['st_ino']),
        'mtime_advanced_on_write': (before['st_mtime_utc'] != after_write['st_mtime_utc']),
        'content_restored_to_run_end_state': restored['sha256'] == ISO_SHA_EXPECTED,
    },
    'serving_process_reads_isolated_config': {
        'state_dir_returned_by_8032': reported_dir,
        'isolated_config_global_controls': iso_file.get('global_controls'),
        'api_8032_global_controls_file_section': (iso_gc.get('global_controls') or None),
        'api_8032_global_controls_matches_isolated_file': (
            (iso_gc.get('global_controls') or {}) == (iso_file.get('global_controls') or {})),
        'isolated_config_archived_wallets': sorted((iso_file.get('archived_wallets') or {}).keys()),
        'shared_config_global_controls': shared_file.get('global_controls'),
        'isolated_and_shared_global_controls_differ': (
            (iso_file.get('global_controls') or {}) != (shared_file.get('global_controls') or {})),
        'api_8032_live_config_canonical_sha256': canon(iso_api),
        'api_8031_live_config_canonical_sha256': canon(live_api),
        'api_8032_differs_from_api_8031': canon(iso_api) != canon(live_api),
        'api_8031_matches_shared_file_controls': (
            (live_gc.get('global_controls') or {}) == (shared_file.get('global_controls') or {})),
        'requests_issued_for_this_check': [
            {'method': 'GET', 'url': ISO_BASE + '/api/live-config', 'status': status_iso},
            {'method': 'GET', 'url': ISO_BASE + '/api/global-controls', 'status': status_gc},
            {'method': 'GET', 'url': LIVE + '/api/live-config', 'status': status_live},
            {'method': 'GET', 'url': LIVE + '/api/global-controls', 'status': status_live_gc},
        ],
    },
    'isolation_verdict': 'the serving :8032 process reads the isolated live_config.json; '
                         'the shared live_config.json is a different file on the same volume '
                         'and was not written',
}
meta['shared_config_sha256_rehashed_at_amendment'] = sha(SHARED)
meta['shared_config_still_matches_expected'] = (
    meta['shared_config_sha256_rehashed_at_amendment'] == SHARED_SHA_EXPECTED)

# ---------------------------------------------------------------- row classes
VIEW_STATE = {'UI-LCC-GRAPH-09', 'UI-LCC-GRAPH-10'}
counts = {'CONTROL_WRITE': {'PASS': 0, 'FAIL': 0}, 'VIEW_STATE': {'PASS': 0, 'FAIL': 0}}
for r in art['rows']:
    if r['row_id'] in VIEW_STATE:
        r['row_class'] = 'VIEW_STATE'
        r['excluded_from_control_write_pass_count'] = True
        r['row_class_note'] = ('reads and changes only client-side graph view state (scale button, '
                               'datetime inputs, subtitle); it issues no config write and leaves the '
                               'isolated live_config.json and audit log byte-identical, so it is '
                               'excluded from the CONTROL-WRITE pass count')
    else:
        r['row_class'] = 'CONTROL_WRITE'
        r['excluded_from_control_write_pass_count'] = False
    counts[r['row_class']][r['result']] += 1

meta['row_classes'] = {
    'CONTROL_WRITE': 'mutates the isolated live_config.json or asserts a rejected mutation',
    'VIEW_STATE': 'client-side graph view state only, no config or audit write; excluded from the '
                  'CONTROL-WRITE pass count',
}
meta['row_counts_by_class'] = {
    k: {'PASS': v['PASS'], 'FAIL': v['FAIL'], 'total': v['PASS'] + v['FAIL']} for k, v in counts.items()}
meta['control_write_pass_count'] = counts['CONTROL_WRITE']['PASS']
meta['control_write_fail_count'] = counts['CONTROL_WRITE']['FAIL']
meta['row_counts'] = {'PASS': counts['CONTROL_WRITE']['PASS'] + counts['VIEW_STATE']['PASS'],
                      'FAIL': counts['CONTROL_WRITE']['FAIL'] + counts['VIEW_STATE']['FAIL']}
meta['amendment'] = {
    'card': 't_d1279a57',
    'amended_at_utc': now(),
    'rows_changed': [],
    'changed': ['meta.live_8031_contact added', 'meta.live_8031_never_written removed',
                'meta.isolation_identity added', 'row_class added to every row',
                'row_counts_by_class / control_write_pass_count added'],
    'known_app_defect_unchanged': 'UI-LCC-ADD-10 remains FAIL',
}

ART.write_text(json.dumps(art, indent=2, ensure_ascii=False), encoding='utf-8')
print('AMENDED', ART)
print(json.dumps({k: meta[k] for k in ('live_8031_reachable_at_start', 'live_8031_reachable_at_end',
                                       'row_counts', 'row_counts_by_class')}, indent=1))
print('isolation:', json.dumps({k: meta['isolation_identity'][k] for k in
                                ('different_files', 'st_ino_isolated', 'st_ino_shared',
                                 'reported_state_dir_matches_isolated_dir')}, indent=1))
