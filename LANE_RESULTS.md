# Lane Results: per-leader ledger tests

## FLAT coverage follow-up (lane-ledger/flat-coverage)

- Added an open-then-close regression check to `_archive/hl_stage2/test_core_per_leader_ledger.py`. It verifies a zero-sized `FLAT` sleeve has empty `opened_by_intent_id`, `position_id`, and `opened_at_ms == 0`.
- Commands: `& 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' '_archive/hl_stage2/test_core_per_leader_ledger.py'` before and after.
- Counts: before **5 passed, 0 failed**; after **6 passed, 0 failed**.
- Root cause: this state transition had no assertion. `ManualLedger.apply_copy_fill` already clears all three metadata fields on FLAT, so the new regression passes without a Core change.
- Graphify commands, attempted before source inspection: `uv --cache-dir '.uv-cache' run --python 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' -- 'C:\Users\wigmore\WINAGENT-HERMES BRIDGE\graphify_query.py' query ledger flat position`; `uv --cache-dir '.uv-cache' run --python 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe' -- 'C:\Users\wigmore\WINAGENT-HERMES BRIDGE\graphify_query.py' explain test_core_per_leader_ledger.py`. Query had no matches; explain returned no entries because `graphify-out/.graphify_analysis.json` is absent. `GRAPH_REPORT.md` was read for navigation.
- Blockers: graphify query data is unavailable in this checkout. No implementation blocker found.

Branch: `lane-ledger/per-leader-tests`
Base: `origin/main` (`eff73dfac67c8557d7f7b8482e7872eddf43d1f3`)

## Changes

- Added five checks in `_archive/hl_stage2/test_core_per_leader_ledger.py` for leader sleeve isolation, both directions of zero crossing, merged fill identity, and one `$12` fixed amount per merged intent.
- Fixed `ManualLedger.apply_copy_fill` so a position that crosses zero starts a new position with the fill price, new intent identity, and new open timestamp; flat positions clear their open metadata.
- Fixed fixed-mode sizing to apply the configured amount once per intent, including a merged fill.

## Commands and results

- `graphify.cmd query --help` — blocked: the wrapper could not find `python`.
- `graphify.cmd query "per-leader ledger zero-crossing merged fills"` — blocked: the wrapper could not find `python`.
- `graphify.cmd explain "ManualLedger.apply_copy_fill"` — blocked: the wrapper could not find `python`. Read `graphify-out/GRAPH_REPORT.md`, `graphify-out/manifest.json`, and the graph JSON for navigation before opening project source.
- `python _archive/hl_stage2/test_core_per_leader_ledger.py` — blocked: Windows denied execution of the `python` command.
- `py -3 _archive/hl_stage2/test_core_per_leader_ledger.py` — blocked: `No installed Python found!`
- Test counts: **0 passed, 0 failed, 5 checks not executed**. The runner failed before importing or executing the test script, so no code-level test result is available.
- `git -c core.whitespace=cr-at-eol diff --check` — passed with no output.
- `git add _archive/hl_stage2/HL_Live_Copy_Service_Core.py _archive/hl_stage2/test_core_per_leader_ledger.py LANE_RESULTS.md` — blocked: Git could not create `.git/index.lock` (`Permission denied`). The workspace grants read-only access to `.git`, so the changes could not be staged or committed and `git push -u origin lane-ledger/per-leader-tests` could not be run.

## Root causes and blockers

- On a sign crossing, `apply_copy_fill` kept the old average entry price and position identifiers for the newly opened opposite position.
- Fixed-mode `_copy_notional` multiplied `$12` by `merged_fill_count`, making one merged intent exceed its configured fixed amount.
- Blocker: this environment has no runnable Python installation, so the focused regression test and broader Python suite could not execute.
- Blocker: the installed Graphify wrapper also requires the unavailable `python` command. The checked-in graph artifacts were used to navigate before source inspection.
- Blocker: `.git` is read-only in this workspace. Git could not stage the changes, preventing the required commit and push.

## Whitespace normalization

- Commands: `uv run --cache-dir .uv-temp-cache --no-project --offline python _archive/hl_stage2/test_core_per_leader_ledger.py` (before and after); `git diff --check`; `uv run --cache-dir .uv-temp-cache --no-project --offline python "C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py" test_core_per_leader_ledger`; `uv run --cache-dir .uv-temp-cache --no-project --offline python "C:/Users/wigmore/WINAGENT-HERMES BRIDGE/graphify_query.py" explain test_core_per_leader_ledger`.
- Test counts: before **5 passed, 0 failed**; after **5 passed, 0 failed**. `git diff --check` passed with no output. Graphify query/explain reported no matches.
- Root cause: `HL_Live_Copy_Service_Core.py` mixed CRLF and LF endings; `LANE_RESULTS.md` had trailing Markdown spaces. Normalized line endings and removed trailing whitespace without changing logic or assertions.
- Blockers: none. The shell `python` command is unavailable; `uv` supplied an offline Python interpreter.
