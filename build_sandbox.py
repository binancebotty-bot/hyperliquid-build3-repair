import hashlib, pathlib, shutil, subprocess
ROOT = pathlib.Path('C:/Users/wigmore/.hermes/kanban/workspaces/t_99472e6c')
SB = ROOT / 'sandbox_repo'
ENG = pathlib.Path('_archive/hl_stage2/HL_Live_Copy_Service_Core.py')
SHA = '2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405'
C = 'fa9d9f55fffa74cb6888c471d97d1655267999b6'
if SB.exists():
    shutil.rmtree(SB)
(SB / ENG).parent.mkdir(parents=True, exist_ok=True)
(SB / 'certification' / 'results').mkdir(parents=True, exist_ok=True)
blob = subprocess.run(['git', '-C', str(ROOT / 'reearn_repo'), 'cat-file', '-p', C + ':' + ENG.as_posix()], capture_output=True, check=True).stdout
(SB / ENG).write_bytes(blob)
sha = hashlib.sha256(blob).hexdigest()
print('engine_sha256', sha, 'matches', sha == SHA)
src = (ROOT / 'reearn_repo' / '_reearn' / 'art' / 'RISK_harness_fa9d9f55ff.py').read_text()
old = 'REPO = Path("C:/Users/wigmore/hyperliquid-build3-repair")'
new = 'REPO = Path(r"' + SB.as_posix() + '")'
assert old in src
patched = src.replace(old, new)
out = SB / 'certification' / 'results' / 'RISK_harness.py'
out.write_text(patched)
print('sandbox', SB)
