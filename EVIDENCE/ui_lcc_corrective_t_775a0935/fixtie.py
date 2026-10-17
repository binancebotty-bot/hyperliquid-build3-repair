import hashlib
from pathlib import Path
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
F=WS/'evidence'/'live_dom_capture.html'
b=F.read_bytes()
print('on_disk_before',hashlib.sha256(b).hexdigest())
lfb=b.replace(b'\r\n',b'\n')
h=hashlib.sha256(lfb).hexdigest()
print('lf_normalized',h)
if h=='809be3fb0f9a05ae2e1691504a3934218915177c085c8394c6ffbbada1500858':
    F.write_bytes(lfb)
    print('REWRITTEN_LF_OK')
else:
    print('MISMATCH_no_write')
print('on_disk_after',hashlib.sha256(F.read_bytes()).hexdigest())
