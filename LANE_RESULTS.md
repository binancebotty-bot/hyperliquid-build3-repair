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
