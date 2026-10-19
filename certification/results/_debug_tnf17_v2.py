#!/usr/bin/env python3
import sys, os, re
from pathlib import Path

core_path = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/HL_Live_Copy_Service_Core.py'
text = Path(core_path).read_text(encoding='utf-8', errors='replace')

marker = 'def direction_from_size(self, size: float) -> str:'
idx = text.find(marker)
if idx < 0:
    print('METHOD NOT FOUND')
    sys.exit(1)

rest = text[idx:]
lines = rest.split('\n')
method_lines = [lines[0]]
for line in lines[1:]:
    if line.startswith('    def ') or line.startswith('    @'):
        break
    method_lines.append(line)

method_body = '\n'.join(method_lines)
print('Extracted method:')
print(method_body)
print('---')

checks = []
ok_long = 'size > POSITION_EPSILON' in method_body and 'return "LONG"' in method_body
checks.append(('size>eps->LONG', ok_long))

ok_short = 'size < -POSITION_EPSILON' in method_body and 'return "SHORT"' in method_body
checks.append(('size<-eps->SHORT', ok_short))

ok_flat = 'return "FLAT"' in method_body
checks.append(('zero->FLAT', ok_flat))

no_snapshot = 'snapshot' not in method_body.lower() and 'position_direction' not in method_body.lower()
checks.append(('no_snapshot_dependency', no_snapshot))

for name, ok in checks:
    print(f'  {name}: {ok}')

all_ok = all(ok for _, ok in checks)
if all_ok:
    print('RESULT::TNF17_POSITIVE_PASS')
    sys.exit(0)
else:
    print('RESULT::TNF17_POSITIVE_FAIL')
    sys.exit(1)
