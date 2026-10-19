
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
