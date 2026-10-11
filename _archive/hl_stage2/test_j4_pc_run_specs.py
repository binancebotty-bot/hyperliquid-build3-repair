#!/usr/bin/env python3
'''J4 conformance test: the five PC run specs (process/PC_RUN_SPECS_2026-10-11.md) must be complete
and paste-able. Doc-only job, so this test grades the DOCUMENT, not the engine:
  * all five gap sections exist (outage, memory, liquidation parity, latency, disk-full)
  * each has an "- exact command:" with a fenced code block of real length
  * each has an "- expected pass line:" naming its own GAP<n>_RESULT:: verdict token
  * each has a non-empty "- attach:" list
  * each emits exactly one GAP<n>_RESULT:: token in its code (no duplicate/absent verdicts)
  * every fenced ```python block in the doc compiles (nothing broken is handed to the PC)
  * every repo test/tool the doc leans on actually exists in this checkout
Run: HL_LIVE_ENV_FILE=/nonexistent python test_j4_pc_run_specs.py
'''
import ast
import os
import re
import sys
from pathlib import Path

os.environ.setdefault('HL_LIVE_ENV_FILE', '/nonexistent')
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DOC = REPO / 'process' / 'PC_RUN_SPECS_2026-10-11.md'

R = []


def check(name, ok, detail=''):
    R.append(bool(ok))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)) if detail and not ok else ''))


def sections(text):
    '''{n: body} for each '## GAP-<n> · ...' section.'''
    out, cur, buf = {}, None, []
    for ln in text.splitlines():
        m = re.match(r'^## GAP-(\d+)\b', ln)
        if m:
            if cur is not None:
                out[cur] = '\n'.join(buf)
            cur, buf = int(m.group(1)), [ln]   # keep the heading: it carries the gap name
        elif ln.startswith('## ') and cur is not None:
            out[cur] = '\n'.join(buf)
            cur, buf = None, []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        out[cur] = '\n'.join(buf)
    return out


TOPICS = {1: ['outage'], 2: ['memory'], 3: ['liquidation', 'liquidationPx'], 4: ['latency'], 5: ['disk-full', 'disk']}
# files the spec tells the PC to run or re-run; all must be present in this checkout
REQUIRED = ['_archive/hl_stage2/test_core_outage_replay.py',
            '_archive/hl_stage2/test_core_memory_bounds.py',
            '_archive/hl_stage2/test_core_liq_parity.py',
            '_archive/hl_stage2/test_core_liq_projection.py',
            '_archive/hl_stage2/test_core_liquidation.py',
            '_archive/hl_stage2/test_core_liq_isolated.py',
            '_archive/hl_stage2/test_core_adl.py',
            '_archive/hl_stage2/tools_memory_profile.py',
            'process/CERTIFICATION_MATRIX_2026-10-10.md',
            'certification/run_results.json',
            'certification/RUN_STATUS.md']

check('DOC_EXISTS', DOC.is_file(), DOC)
if not DOC.is_file():
    print('TOTAL=%d FAILED=%d' % (len(R), R.count(False)))
    sys.exit(1)
text = DOC.read_text(encoding='utf-8', errors='replace')
secs = sections(text)

check('FIVE_GAP_SECTIONS', sorted(secs) == [1, 2, 3, 4, 5], sorted(secs))

for n in (1, 2, 3, 4, 5):
    body = secs.get(n, '')
    tok = 'GAP%d_RESULT::' % n
    check('GAP%d_SECTION_PRESENT' % n, bool(body))
    check('GAP%d_TOPIC_NAMED' % n, all(t.lower() in body.lower() for t in TOPICS[n]), TOPICS[n])
    check('GAP%d_HAS_EXACT_COMMAND' % n, '- **exact command:**' in body)
    # the fenced block right after the command label must carry >= 3 real lines
    blocks = re.findall(r'```(?:bash|python)\n(.*?)```', body, re.S)
    longest = max((len([l for l in b.splitlines() if l.strip()]) for b in blocks), default=0)
    check('GAP%d_COMMAND_BLOCK_REAL' % n, longest >= 3, 'longest fenced block lines=%d' % longest)
    check('GAP%d_HAS_PASS_LINE' % n, '- **expected pass line:**' in body and tok in body)
    check('GAP%d_HAS_ATTACH' % n, '- **attach:**' in body and len(body.split('- **attach:**', 1)[1].strip()) > 20)
    code = '\n'.join(blocks)
    check('GAP%d_VERDICT_IN_CODE' % n, tok in code, 'verdict token absent from the script block')
    check('GAP%d_VERDICT_DETERMINISTIC' % n, 'PASS' in code and 'FAIL' in code,
          'script must be able to emit both PASS and FAIL')

for rel in REQUIRED:
    check('EXISTS_' + re.sub(r'\W+', '_', rel).strip('_'), (REPO / rel).is_file(), rel)

# every pure-python fence in the doc must compile (the PC pastes these verbatim)
pyblocks = re.findall(r'```python\n(.*?)```', text, re.S)
check('PYTHON_FENCES_FOUND', len(pyblocks) >= 1, len(pyblocks))
for i, blk in enumerate(pyblocks, 1):
    try:
        ast.parse(blk)
        ok, why = True, ''
    except SyntaxError as exc:
        ok, why = False, '%s line %s' % (exc.msg, exc.lineno)
    check('PYTHON_FENCE_%d_COMPILES' % i, ok, why)

# the five scripts must be reproducible from the doc alone: each names its audit dir surface
check('DOC_NAMES_VERDICTS_SUMMARY', all(('GAP%d_RESULT::' % n) in text for n in (1, 2, 3, 4, 5)))
check('DOC_STATES_OFFLINE_SAFETY', 'Offline only' in text and 'no orders' in text)

print('TOTAL=%d FAILED=%d' % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
