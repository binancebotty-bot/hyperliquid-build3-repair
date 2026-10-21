#!/usr/bin/env python3
"""A failed refresh read must show UNKNOWN / STALE, not the misleading OFF state."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "HL_Copy_App_SSOT.py"


def function_line(source: str, name: str) -> str | None:
    start = source.find(f"async function {name}(")
    if start < 0:
        start = source.find(f"function {name}(")
    if start < 0:
        return None
    end = source.find("\n", start)
    return source[start:] if end < 0 else source[start:end]


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    get = function_line(source, "jget")
    status = function_line(source, "setSendModeStatus")
    refresh = function_line(source, "refresh")
    if not get or not status or not refresh:
        print("RESULT::failed_get_shows_unknown_amber_FAIL | missing refresh helper")
        return 1

    js = "\n".join((get, status, refresh))
    driver = f"""
const vm = require('node:vm');
const label = {{ textContent: 'OFF' }};
const pill = {{ className: 'lc-pill' }};
const root = {{ querySelector: (selector) => selector === '#lcSendModeLabel' ? label : selector === '#lcSendModePill' ? pill : null }};
const requested = [];
let failedStatus = 503;
let sendMode = 'ON';
const fetch = async (path) => {{
  requested.push(path);
  return path === '/api/live-ws-health' && failedStatus
    ? {{ ok: false, status: failedStatus, json: async () => ({{}}) }}
    : {{ ok: true, status: 200, json: async () => ({{ global_controls: {{ send_mode: sendMode }} }}) }};
}};
const msg = () => {{}};
const context = {{ root, fetch, msg, normalizedSendMode: (mode) => mode || 'OFF', lcSendModePending: null, render: () => {{}}, loadGcForm: () => {{}} }};
vm.runInNewContext({json.dumps(js)}, context);
async function checkFailedRead(status) {{
  failedStatus = status;
  requested.length = 0;
  await context.refresh(true);
  if (requested.length !== 4 || label.textContent !== 'UNKNOWN / STALE' || pill.className !== 'lc-pill lc-amber') {{
    throw new Error(JSON.stringify({{ status, requested, text: label.textContent, className: pill.className }}));
  }}
}}
async function main() {{
  await checkFailedRead(503);
  await checkFailedRead(401);
  failedStatus = null;
  for (const [mode, text, className] of [['ON', 'ON · LIVE', 'lc-pill lc-green'], ['CLOSE', 'CLOSE · CLOSE ONLY', 'lc-pill lc-amber'], ['OFF', 'OFF', 'lc-pill']]) {{
    sendMode = mode;
    requested.length = 0;
    await context.refresh(true);
    if (requested.length !== 4 || label.textContent !== text || pill.className !== className) throw new Error('wrong refresh rendering for ' + mode);
  }}
  console.log('RESULT::failed_get_shows_unknown_amber_PASS');
}}
main().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    result = subprocess.run(["node", "-e", driver], capture_output=True, text=True, timeout=10, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
