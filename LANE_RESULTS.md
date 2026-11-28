# Lane i03-psutil Results

Invariant: `ENG-INV-03` — no new third-party runtime dependency without Architect approval.

## Commands and results

Python 3.12.13 was run from the installed uv-managed interpreter directory:

```powershell
$env:Path = 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none;' + $env:Path
python '_archive/hl_stage2/test_core_headroom_foreign_ws.py'
```

- Before adding F9: **8 passed, 0 failed**.
- Test-first run with F9 added and the original source: **8 passed, 1 failed** (`F9_NO_UNAPPROVED_THIRD_PARTY_IMPORT`, found `psutil`).
- After the source fix: **9 passed, 0 failed**.

The pinned-baseline oracle and all row mutation controls were run with:

```powershell
$env:Path = 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none;' + $env:Path
$repo = (Get-Location).Path
python 'certification/results/rowbound_oracle.py' $repo --baseline 43731b4f1f19a56e835032dabf608a550f925717 --mutate
```

Result: **PASS**; 10 production files parsed, `ENG-INV-03` has no unapproved new dependencies, and all **3/3** invariant mutation controls turned only their target row red while sibling rows stayed green.

The Windows OS lookup path was also exercised without external network access:

```powershell
$env:Path = 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none;' + $env:Path
python -c "import sys; sys.path.insert(0, '_archive/hl_stage2'); import headroom; rows = list(headroom._established_tcp()); assert all(len(row) == 3 and row[0] > 0 and 0 <= row[2] <= 65535 for row in rows); assert headroom._process_name(__import__('os').getpid()); print(f'OS_LOOKUP_PASS rows={len(rows)}')"
```

Result: **PASS**, 157 established TCP rows enumerated and the current process name resolved.

## Root cause and fix

`_archive/hl_stage2/headroom.py` imported `psutil` to map established feed connections to process IDs and names. The dependency was absent from the pinned baseline and explicitly unapproved in `certification/approved_dependencies.json`; the engine import closure reaches `headroom.py`. The prior implementation therefore failed `ENG-INV-03` even though it only used `psutil` as an optional import.

The source now reads established TCP ownership from the Windows TCP table or Linux `/proc`, and gets process names through the OS interfaces. The F9 check in the runnable headroom test rejects third-party imports without weakening the invariant.

## Blockers

None for the offline invariant test. The oracle also found two `psutil` imports in standalone profiling utilities, outside the engine import closure used by this invariant; they do not affect the ENG-INV-03 verdict. No walletproof engine, scout, live trading, deployment, or mainnet operations were used.

## Reviewer follow-up: profiling utilities

### Commands and results

Python 3.12.13 was run from the installed uv-managed interpreter directory:

```powershell
$env:Path = 'C:\Users\wigmore\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none;' + $env:Path
python '_archive/hl_stage2/test_core_headroom.py'
python '_archive/hl_stage2/test_core_headroom_foreign_ws.py'
python 'certification/results/rowbound_oracle.py' (Get-Location).Path --baseline 43731b4f1f19a56e835032dabf608a550f925717 --mutate
python -c "import sys; sys.path.insert(0, '_archive/hl_stage2'); import tools_memory_profile as m; rss=m._rss_mb(); avail=m._avail_mb(); assert rss is None or rss > 0; assert avail is None or avail > 0; print('OS_MEMORY_PROBES_PASS rss_mb=%s avail_mb=%s' % (rss, avail))"
python -c "import sys; sys.path.insert(0, '_archive/hl_stage2'); import bench_memory_profile as b; rss=b.rss_mb(); assert rss > 0 or rss != rss; print('BENCH_RSS_PROBE rss_mb=%s' % rss)"
```

- Before: headroom **14 passed, 0 failed**; foreign-WebSocket **9 passed, 0 failed**.
- Regression check before the fix: **9 passed, 1 failed**, identifying both profiling utilities.
- After: headroom **14 passed, 0 failed**; foreign-WebSocket **10 passed, 0 failed**.
- Oracle: **PASS**, 10 production files parsed, no ENG-INV-03/04/05 violations; **3/3** mutation controls isolated their target row.
- OS telemetry smoke checks passed: RSS resolved in both profiling tools; available memory resolved in `tools_memory_profile.py`.

### Root cause and blocker

`bench_memory_profile.py` and `tools_memory_profile.py` imported optional `psutil` for RSS/available-memory measurements. The reviewer’s oracle includes these files in its dependency scan even though they are outside the engine import closure; `headroom.py` already used standard-library OS queries. Replaced the profiling imports with Windows process/memory APIs through `ctypes` and Linux `/proc` reads. The regression check now enforces no `psutil` imports in all three oracle-listed files. **Blockers: none.**
