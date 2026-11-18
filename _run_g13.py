import os, subprocess, sys
from pathlib import Path
root = Path(r'C:/Users/wigmore/oc-runs/w1-g13')
python = r'C:/Users/wigmore/.hermes/hermes-agent/.venv/Scripts/python.exe'
env = os.environ.copy()
env.update(HL_LIVE_ENV_FILE='/nonexistent', TMPDIR=r'C:/Users/wigmore/.hermes/cache/scratch/g13')
for label, rel in [('DUPLICATE_GATE', '_archive/hl_stage2/test_duplicate_send_first_attempt_gate.py'), ('C1_G13_BASELINE', '_archive/hl_stage2/test_c1_g13_sequences.py')]:
    print(f'=== {label} ===', flush=True)
    result = subprocess.run([python, rel], cwd=root, env=env, capture_output=True, text=True, timeout=300)
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    print(f'EXIT={result.returncode}', flush=True)
