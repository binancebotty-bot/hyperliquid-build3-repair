# Lane i08: PROGRAMDATA scope correction

## Root cause and change

The lock path trusted the process `PROGRAMDATA` environment variable. A user process can override that value, so separate sessions could resolve different lock paths despite the variable's usual machine-wide default. On Windows, `_global_instance_lock_path()` now asks the OS for Common AppData (`CSIDL_COMMON_APPDATA`) and stores the lock under `HL_Live_Copy_Service_Core/engine-global.lock`; non-Windows behavior remains under the system temporary directory. The regression now supplies different `PROGRAMDATA`, `LOCALAPPDATA`, and `HL_LIVE_GLOBAL_LOCK_FILE` values for two simulated users and checks that both resolve to the same application-scoped machine path. The separate-process test still uses an isolated temporary lock.

## Commands and results

| Command | Result |
|---|---|
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv run --offline --python 3.12 python 'C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py' query 'I08 PROGRAMDATA scope source violation'` | No matches. The local `graphify-out` has no `.graphify_analysis.json`; the query CLI fell back to the unrelated bridge graph. |
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv run --offline --python 3.14 python 'C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py' query PROGRAMDATA` | Returned bridge-project results, confirming the fallback is not this clone's graph. |
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv run --offline --python 3.14 python 'C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py' explain PROGRAMDATA` | No matches in the fallback graph. |
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv run --offline --python 3.14 python _archive/hl_stage2/test_core_network_and_global_controls.py` (before) | 13 checks passed, 4 failed. The two N6 checks lacked `requests`; the two N8 checks lacked `fastapi`. The script then exited on the FastAPI import error. |
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv run --offline --python 3.14 python _archive/hl_stage2/test_core_network_and_global_controls.py` (after) | 13 checks passed, 4 failed for the same missing dependencies. The new `N7_GLOBAL_LOCK_PATH_MACHINE_PROGRAMDATA_SCOPE` check passed. |
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv pip install --python 'C:/Users/wigmore/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' --target .test-deps requests fastapi` | Blocked: package index connection denied by the environment. |
| `$env:UV_CACHE_DIR='C:/Users/wigmore/fresh-lanes/i08-programdata/.uv-cache'; uv run --offline --python 3.14 python -m py_compile _archive/hl_stage2/HL_Live_Copy_Service_Core.py _archive/hl_stage2/test_core_network_and_global_controls.py` | Passed. |
| `git diff --check` | Passed. |

## Blockers

- The requested script does not reach zero failures in this environment: `requests` and `fastapi` are not installed, and package-index access is denied. The I08 scope regression itself passes.
- The clone's `graphify-out` is stale/mismatched and lacks the analysis file needed for a local query, so graphify could not guide source navigation.

## Lane i08: I08 DEX-scope recovery

### Root cause and change

The full-scope sweep discarded cached readings for DEXes no longer returned by `perpDexs`. If a cached reading showed a held position, dropping that DEX removed the only startup/recovery evidence of the position and let the sweep report clean. The sweep now keeps stale cache records that show positions and returns `SCOPE_UNAVAILABLE` when such a held DEX is absent from the current enumeration. This invalidates a prior clean sweep and keeps entries blocked; empty cached scopes can still be discarded.

Added `certification/test_i08_dex_scope.py`, a standalone offline regression that simulates restart recovery from an old held-position cache while `perpDexs` omits that DEX. It checks both fail-closed gating and cache retention.

### Commands and results

| Command | Result |
|---|---|
| `$env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache'); uv run --offline --python 3.12 python certification/test_i08_dex_scope.py` (before source fix) | 0 passed, 2 failed: the sweep returned `ok=True`, dropped `xyz`, and left the previous clean gate open. |
| `$env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache'); uv run --offline --python 3.12 python certification/test_i08_dex_scope.py` (after source fix) | 2 passed, 0 failed. |
| `$env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache'); uv run --offline --python 3.12 python _archive/hl_stage2/test_core_dex_scope_and_ui_truth.py` | Blocked before checks: `ModuleNotFoundError: No module named 'requests'`. |
| `$env:UV_CACHE_DIR=(Join-Path (Get-Location) '.uv-cache'); uv run --offline --python 3.12 python -m py_compile _archive/hl_stage2/HL_Live_Copy_Service_Core.py certification/test_i08_dex_scope.py` | Passed. |
| `git diff --check` | Passed. |

### Blockers

- The existing combined DEX/UI script cannot start because `requests` is not installed; the offline package cache has no dependency available and package-index access is denied. The new I08 regression has no third-party dependencies and passes.
