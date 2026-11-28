# Lane i06-headroom results

## I06 headroom

- Changed `headroom.py` so a configured `/info` request is charged in a `finally` block, even when its transport raises. The transport exception still propagates; response row counting and immediate 429 refusal handling remain in place.
- Added `raised_info_request_counts_weight` to the runnable script test `_archive/hl_stage2/test_core_headroom.py`. It checks that a timed-out `userRole` request charges 60 weight units and that the timeout is not swallowed.
- Root cause: quota accounting happened only after `post()` returned. A request that raised after transmission was invisible to the monitor, overstating remaining headroom.

## Test runs

| Stage | Exact command | Script checks | Passed | Failed | Outcome |
|---|---|---:|---:|---:|---|
| Before runtime discovery | `python _archive/hl_stage2/test_core_headroom.py` | — | 0 executed | 0 executed | Blocked: Windows Python launcher returned `Access is denied`. |
| Before source fix (RED) | `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' _archive/hl_stage2/test_core_headroom.py` | 15 | 14 | 1 | The new `raised_info_request_counts_weight` check failed with measured weight `0`; all prior checks passed. |
| After source fix (GREEN) | `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' _archive/hl_stage2/test_core_headroom.py` | 15 | 15 | 0 | Exit 0. |
| Related foreign-WS check | `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' _archive/hl_stage2/test_core_headroom_foreign_ws.py` | 8 | 8 | 0 | Exit 0. |
| Related keepalive check | `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' _archive/hl_stage2/test_http_keepalive.py` | — | 0 executed | 0 executed | Blocked at import: `ModuleNotFoundError: No module named 'requests'`. |
| pytest availability | `pytest _archive/hl_stage2/test_core_headroom.py -q` | — | 0 executed | 0 executed | Blocked: `pytest` is not recognized. The headroom checks are script-style and were run directly with Python. |

## Blockers and Graphify

- `py --list-paths` reported `No installed Pythons found!`; Graphify's Python shim could not find `python` on `PATH`. A Python 3.12 runtime installed by `uv` was available and used directly for the script tests.
- The `graphify` shim depends on Python. `graphify query headroom` and `graphify explain _archive/hl_stage2/headroom.py` could not run because its Python launcher was unavailable. As a fallback, I queried the checked-in `graphify-out/graph.json`: it has no headroom or I06 nodes and only identifies archived stage-2 source; the graph appears stale for this lane.
- The keepalive check needs the unavailable `requests` package; the focused headroom and foreign-WebSocket scripts ran successfully. No secrets or wallet material were opened; `CONTROL_STATE.json`, walletproof engine (8014), and scout (8012) were not changed.
