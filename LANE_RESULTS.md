# Lane i08: source violation fix

## Finding and fix

I08 requires one canonical sender. The engine's global sender lock claimed to be machine-wide, but `_global_instance_lock_path()` used `LOCALAPPDATA` first, which is different for each Windows user, and accepted a user-scoped `HL_LIVE_GLOBAL_LOCK_FILE` override. Two user sessions could therefore acquire different lock files and run separate senders. The source now uses shared `PROGRAMDATA` on Windows (with `C:\ProgramData` as the fallback) and the shared system temp directory elsewhere. The per-user override was removed.

Added a regression to `test_core_network_and_global_controls.py` that checks the resolved lock path is identical across distinct user-local directories and override values, and verifies the global lock refuses a second process. The process test uses an isolated temporary lock path and makes no exchange calls.

## Commands and evidence

| Command | Result | Counts |
|---|---|---|
| `graphify query I08` | Blocked: `graphify.cmd` invokes `python`, which is not available to the shell. Read `graphify-out/GRAPH_REPORT.md` and `graphify-out/graph.json` before source inspection. | 0 tests; 0 passed; 0 failed |
| `graphify explain I08` | Blocked for the same missing Python runtime. | 0 tests; 0 passed; 0 failed |
| `python _archive/hl_stage2/test_core_network_and_global_controls.py` | Blocked: PowerShell reported `Program 'python' failed to run: Access is denied`. The Python test suite did not start. | 0 tests collected; 0 passed; 0 failed; 1 blocked command |
| Baseline PowerShell source-contract probe using `git show HEAD:_archive/hl_stage2/HL_Live_Copy_Service_Core.py` | Expected failure: `FAIL: baseline global sender lock is per-user or overridable`. | 1 failed probe (red) |
| PowerShell source-contract probe against the fixed file | Passed: `PASS: global lock path is shared and non-overridable`. | 1 passed probe (green) |
| `git diff --check` | Passed. | 0 tests; 0 passed; 0 failed |
| `git add ...` in the requested clone | Blocked: could not create `.git/index.lock` because the clone's `.git` directory is read-only. Created a writable local clone inside the workspace and committed there. | Commit `5ceeb654789af535c646e73624d3ef05e9086e6a` |
| `git push -u origin lane-i08/source-violation-fix` | Failed: could not connect to `github.com` port 443. | Not pushed |
| GitHub connector `create_blob` fallback | Rejected: `MCP tool call requires approval, but approval policy is never`. | Not pushed |

## Blockers

- Python tests and Graphify query/explain could not run because the configured Python launcher is inaccessible or absent. The integration regression is included in the local commit but remains unexecuted in this environment.
- The requested clone's Git metadata is read-only, direct GitHub access is unavailable, and the connector rejected the write fallback under the `never` approval policy. The commit exists locally in `.lane-commit`; the branch was not pushed.
