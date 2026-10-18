import json, os, subprocess, hashlib
from datetime import datetime, timezone
from pathlib import Path
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = 'C:/Users/wigmore/AppData/Local/ms-playwright'
from playwright.sync_api import sync_playwright
EV = Path('C:/Users/wigmore/.hermes/cache/scratch/b3_clean/EVIDENCE'); EV.mkdir(parents=True, exist_ok=True)
SERVE = Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/_archive/hl_stage2')
URL = 'http://127.0.0.1:8031/live-copy'
PH = {'', '-', '\u2014', 'n/a', 'none yet', 'loading...', 'loading', 'no data'}

SPEC = json.load(open('C:/Users/wigmore/.hermes/cache/scratch/b3_clean/spec.json', encoding='utf-8'))

def N(s):
    s = (s or '').replace('\u2194', '<->').replace('\u2192', '->').replace('\u2014', '-')
    s = ' '.join(s.split()).strip().lower()
    return s.replace('p&l', 'pnl').replace('p n l', 'pnl')

def run(a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()

commit = run(['git', '-C', str(SERVE), 'rev-parse', 'HEAD'])
cdate = run(['git', '-C', str(SERVE), 'log', '-1', '--format=%cI', 'HEAD'])
sha = hashlib.sha256((SERVE / 'HL_Copy_App_SSOT.py').read_bytes()).hexdigest()
pid = ''
for ln in run(['netstat', '-ano']).splitlines():
    if ':8031' in ln and 'LISTENING' in ln:
        pid = ln.split()[-1]
start = run(['powershell', '-NoProfile', '-Command', "(Get-CimInstance Win32_Process -Filter 'ProcessId=%s').CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss')" % pid]) if pid else ''
dts = datetime.strptime(start, '%Y-%m-%dT%H:%M:%S') if start else None
dtc = datetime.fromisoformat(cdate.replace('Z', '+00:00')).replace(tzinfo=None)
bound = bool(dts and dtc < dts)
print('BUILD', commit, cdate, pid, start, 'BOUND', bound)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1920, 'height': 1080})
    pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(35000)
    tabs = []
    for t in pg.locator('table').all():
        hdr = [h.strip() for h in t.locator('thead th').all_inner_texts()]
        rows = [[c.strip() for c in r.locator('td').all_inner_texts()] for r in t.locator('tbody tr').all()]
        tabs.append(dict(headers=hdr, rows=rows))
    mod = dict(opened=False, labels=[], inputs=0, cancel=False, closed=False, err='')
    try:
        btn = pg.get_by_role('button', name='Add wallet')
        if btn.count() == 0:
            btn = pg.get_by_role('button', name='Add Wallet')
        btn.first.click()
        pg.wait_for_timeout(1500)
        dlg = pg.locator('#lcWalletModal').first
        mod['opened'] = bool(dlg.count() and dlg.is_visible())
        if mod['opened']:
            mod['labels'] = [x.strip() for x in dlg.locator('label, .lc-field, legend, h4').all_inner_texts() if x.strip()][:30]
            mod['inputs'] = dlg.locator('input, select').count()
            cb = pg.get_by_role('button', name='Cancel')
            mod['cancel'] = cb.count() > 0
            if mod['cancel']:
                cb.first.click()
                pg.wait_for_timeout(1200)
                mod['closed'] = not dlg.is_visible()
    except Exception as e:
        mod['err'] = type(e).__name__ + ':' + str(e)[:150]
    pg.screenshot(path=str(EV / 'ui_lcc_live_copy.png'))
    b.close()

(EV / 'ui_lcc_dom_capture.json').write_text(json.dumps(dict(tables=tabs, modal=mod, url=URL), indent=1), encoding='utf-8')

area_idx = {}
for name, sig in SPEC['areas'].items():
    for ti, t in enumerate(tabs):
        hs = [N(h) for h in t['headers']]
        if all(N(s) in hs for s in sig):
            area_idx[name] = ti
            break
print('AREAS', area_idx)

how = ('git -C %s rev-parse HEAD -> %s (commit date %s); sha256(HL_Copy_App_SSOT.py) -> %s; :8031 PID %s process start %s UTC; commit predates process start = %s' % (SERVE, commit, cdate, sha, pid, start, bound))
out = []

def add(rid, v, probe, obs, pred):
    out.append(dict(row_id=rid, verdict=v, serving_commit=commit, serving_ssot_sha256=sha, serving_pid=pid, serving_pid_start_utc=start, executed_probe=probe, independent_oracle='headless Chromium (Playwright py3.11) reading the rendered DOM of live :8031 /live-copy; no engine import, nothing written', observed=obs, failing_predicate=pred, reproduces='py311 _v3.py (re-runs this exact probe)'))

for rid, area, names in SPEC['rows']:
    probe = "locate the '%s' table by signature headers %s, require a header equal to one of %s, verify row/cell alignment, then read that column" % (area, SPEC['areas'][area], names)
    ti = area_idx.get(area)
    if ti is None:
        add(rid, 'FAIL', probe, 'no rendered table carries the %s signature %s; headers on page: %s' % (area, SPEC['areas'][area], ' | '.join('/'.join(t['headers'][:8]) for t in tabs)[:380]), 'the %s surface renders with its expected headers' % area)
        continue
    t = tabs[ti]
    hs = [N(h) for h in t['headers']]
    ci = next((i for i, h in enumerate(hs) if h in [N(n) for n in names]), None)
    if ci is None:
        add(rid, 'FAIL', probe, 'table %d (%s) headers are %s; none equals %s' % (ti, area, t['headers'], names), 'a column header for this row exists in the %s table' % area)
        continue
    mis = [i for i, r in enumerate(t['rows']) if len(r) != len(t['headers'])]
    if mis:
        add(rid, 'FAIL', probe, 'table %d (%s) header %r col %d: %d/%d rows render %d cells against %d headers (first offender row %d), so index %d is not this column' % (ti, area, t['headers'][ci], ci, len(mis), len(t['rows']), len(t['rows'][mis[0]]), len(t['headers']), mis[0], ci), 'each tbody row renders exactly one cell per header so a column can be addressed by index')
        continue
    if len(t['rows']) == 1 and len(t['rows'][0]) == 1:
        add(rid, 'FAIL', probe, 'table %d (%s) header %r col %d; tbody is one placeholder cell %r' % (ti, area, t['headers'][ci], ci, t['rows'][0][0][:100]), 'at least one data row renders under %r' % t['headers'][ci])
        continue
    vals = [(i, r[ci]) for i, r in enumerate(t['rows']) if N(r[ci]) not in PH]
    if rid in SPEC['write_rows']:
        add(rid, 'NOT_TESTED', probe, 'column %r present in the %s table (table %d); %d/%d rows populated' % (t['headers'][ci], area, ti, len(vals), len(t['rows'])), 'expected behaviour requires writing through the live app (mode change / archive) and observing the engine apply it; schema hard requirement 8 forbids POSTing to live :8031 and no authorised isolated instance was provisioned')
        continue
    if not vals:
        add(rid, 'FAIL', probe, 'table %d (%s) header %r col %d: %d rows, 0 non-placeholder (first %r)' % (ti, area, t['headers'][ci], ci, len(t['rows']), (t['rows'][0][ci][:60] if t['rows'] else '')), 'at least one row carries a non-placeholder value under %r' % t['headers'][ci])
        continue
    add(rid, 'PASS', probe, 'table %d (%s) header %r col %d: %d/%d rows non-placeholder; %s' % (ti, area, t['headers'][ci], ci, len(vals), len(t['rows']), '; '.join('r%d=%r' % (i, v[:55]) for i, v in vals[:3])), 'at least one row carries a non-placeholder value under %r (fails if the header is absent, indices are shifted, or every cell is a placeholder)' % t['headers'][ci])

blob = N(' | '.join(mod['labels']))
for rid in SPEC['add_rows']:
    probe = 'click Add wallet, read #lcWalletModal labels/inputs, click Cancel'
    if rid == 'UI-LCC-ADD-09':
        ok = mod['opened'] and mod['cancel'] and mod['closed']
        add(rid, 'PASS' if ok else 'FAIL', probe, 'modal_opened=%s cancel_present=%s closed_after_cancel=%s inputs=%d labels=%s' % (mod['opened'], mod['cancel'], mod['closed'], mod['inputs'], mod['labels'][:8]), 'the modal opens, offers a Cancel control, and Cancel closes it without saving')
        continue
    lab = SPEC['add_labels'][rid]
    add(rid, 'NOT_TESTED', probe, 'modal_opened=%s label_%r_present=%s inputs=%d labels=%s' % (mod['opened'], lab, N(lab) in blob, mod['inputs'], mod['labels'][:8]), 'expected behaviour is persistence to live_config.json via POST /api/live-config/add-wallet; forbidden on the live app by schema hard requirement 8 and no authorised isolated instance was provisioned. Label presence is recorded but is not the certified predicate')

art = dict(card_id='t_5cc9db76', serving_commit=commit, serving_ssot_sha256=sha, serving_pid=pid, serving_pid_start_utc=start, how_serving_build_was_established=how, process_rule_satisfied=bound, oracle='headless Chromium (Playwright py3.11) against live :8031 /live-copy; each area located by signature headers; read-only, no engine import', rows_total=len(out), rows=sorted(out, key=lambda r: r['row_id']))
(EV / 'ui_lcc_reearn_artifact.json').write_text(json.dumps(art, indent=1), encoding='utf-8')
from collections import Counter
print('TOTAL', len(out), dict(Counter(r['verdict'] for r in out)))
for r in out:
    print('%-17s %-10s %s' % (r['row_id'], r['verdict'], r['observed'][:110]))
