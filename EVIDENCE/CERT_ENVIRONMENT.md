
## :8031 serving-process binding (2026-10-19)

UI certification requires binding a capture to what the process actually serves. For the live Command Centre:

| field | value |
|---|---|
| PID | 41124 (`pythonw.exe`) |
| process start | 2026-10-18T23:15:14+01:00 |
| command line | `...\Python311\pythonw.exe HL_Copy_App_SSOT.py` (relative path — cwd matters) |
| working dir | `C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2` |
| launch source | `C:/Users/wigmore/trading_stack/_tools/launch_8031_live.txt` |
| audit dir | `...\_archive\hl_stage2\hl_live_copy_audit_testnet` |
| **source commit** | **none — that directory is NOT a git repository** |
| script sha256 | `b45ff9af2182944a1fabd98b6369d0ad7dd7d215062abec3bdc20dfd75e9e7c2` |
| script mtime | 2026-10-18 21:19:57 +0100 (predates process start — consistent) |

**Because there is no git repo, bind by content hash, not commit.** Record:

```
serving_binding_type  = content_sha256
serving_script_sha256 = <sha256 of the served HL_Copy_App_SSOT.py>
serving_pid           = 41124
serving_process_start = 2026-10-18T23:15:14+01:00
source_commit         = null
```

Re-verify the hash at test time — if it has changed, the process was restarted and the capture must be re-taken.
Do not ask for a commit that cannot exist, and do not invent one.

## The matrix's UI source EXISTS — located 2026-10-19

The matrix declares `source_sha256["hyperliquid-build3-repair/HL_Copy_App_SSOT_20260513.py"] =
fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0`, referenced by 254 rows. No file in the git repo
matched it, which blocked UI certification.

**It was not missing — it is on disk, outside version control:**

| field | value |
|---|---|
| path | `C:\Users\wigmore\trading_stack\build3-live-screen-0513-view\hl_stage2\HL_Copy_App_SSOT.py` |
| sha256 | `fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0` — **exact match to the matrix** |
| mtime | 2026-05-13 08:18:03 (matches the "13 May" label) |
| git | **not a repository** |
| sibling | `ui_8023.log` — this tree was served on port 8023 |

## Three distinct files, do not conflate them

```
fad19d22…  build3-live-screen-0513-view/hl_stage2/            <- what the REGISTER certifies
4574ca72…  hyperliquid-build3-repair/_archive/hl_stage2/      <- what the REPO holds
b45ff9af…  hl-build3-testnet-cert/_archive/hl_stage2/         <- what :8031 ACTUALLY SERVES
```

**Consequence:** a capture of the live `:8031` page certifies the app that is running (`b45ff9af`), not the source the
register names (`fad19d22`). To certify UI rows against the register, the app must be started from
`build3-live-screen-0513-view` — or the register's `source_sha256` must be corrected to the file actually served.

Until one of those happens, no UI row can be bound to its declared source. Do not certify against `:8031` as-is and
call it a register row.

## :8032 isolated instance (found running 2026-10-19)

A second, isolated Command Centre instance exists. It is the fixture the control-write cards required.

| field | value |
|---|---|
| endpoint | `http://127.0.0.1:8032` |
| PID | 30580 |
| command | `python -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8032` |
| started | 2026-10-18T19:43:11+01:00 |
| workspace | `C:\Users\wigmore\trading_stack\hl-build3-testnet-cert-8032\_archive\hl_stage2` |
| served source sha256 | `658ec8e31eb96d70…` — **different** from live `:8031`'s `b45ff9af2182944a…` |
| controls | `/api/global-controls` returns `{"ok":true,...}` with all limits `0.0` (fresh state) |

**Isolation evidence:** separate workspace tree, different served source hash, zeroed controls. Control-write tests
run against this instance, never against `:8031`.

**Every control test must record the live config's sha256 before and after.** If it changes, the test mutated live
configuration and that is a defect, not a pass.
