import os, subprocess, sys
from pathlib import Path

WS = Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_f8fa9bf6')
APP = WS / 'src89' / '_archive' / 'hl_stage2'
PYW = r'C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe'
CREATE_NO_WINDOW = 0x08000000


def launch(audit_dir, port, logname):
    env = dict(os.environ)
    env['HL_LIVE_ENV_FILE'] = r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-j28-89b3bc7/hl_stage2.env'
    env['HL_LIVE_AUDIT_DIR'] = str(WS / audit_dir)
    env['HL_APP_PORT'] = str(port)
    env['HL_LIVE_WS_ENABLED'] = '0'
    log = open(WS / logname, 'wb')
    p = subprocess.Popen([PYW, 'HL_Copy_App_SSOT.py'], cwd=str(APP), env=env,
                         stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=CREATE_NO_WINDOW)
    return p


if __name__ == '__main__':
    audit, port, logname = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    p = launch(audit, port, logname)
    (WS / (logname + '.pid')).write_text(str(p.pid))
    print('pid', p.pid, 'port', port, 'audit', audit)
