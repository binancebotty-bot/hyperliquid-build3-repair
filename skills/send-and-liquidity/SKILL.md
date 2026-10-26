---
name: send-and-liquidity
description: Change the global send switch only under order and identify unsupported liquidity-filter controls.
---

# Sending and liquidity filter

Require a fresh signed order naming the intended mode and run. `OFF` means no sends; `CLOSE` is not the same as `OFF`; `ON` enables normal sending. The live-copy dashboard's global-controls form does not submit `send_mode`.

The runbook requires editing a staged copy of `live_config.json`, keeping a timestamped backup and before/after hashes, then applying the change as part of a graceful pair restart. Do not edit the file watched by a running engine. After a signed order, use this sequence from the approved checkout (set `$Mode` to the ordered value, `ON` or `OFF`):

```powershell
if ($Mode -notin @('ON', 'OFF')) { throw 'Only an explicitly ordered ON or OFF is allowed' }
$Original = Join-Path $State 'live_config.json'
$Backup = "$Original.bak-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))-send-mode"
$Stage = Join-Path $State 'live_config.operator-staged.json'
$Before = (Get-FileHash -Algorithm SHA256 -LiteralPath $Original).Hash
Copy-Item -LiteralPath $Original -Destination $Backup
Copy-Item -LiteralPath $Original -Destination $Stage
python -c "import json,pathlib; p=pathlib.Path(r'$Stage'); d=json.loads(p.read_text(encoding='utf-8')); d.setdefault('global_controls', {})['send_mode']='$Mode'; p.write_text(json.dumps(d,indent=2)+chr(10),encoding='utf-8')"
$Staged = (Get-FileHash -Algorithm SHA256 -LiteralPath $Stage).Hash
if ($Before -eq $Staged) { throw 'Staged config did not change' }
ops/stop_pair.py --all
if ($LASTEXITCODE -ne 0) { throw 'Pair stop failed; do not apply the staged config' }
Copy-Item -LiteralPath $Stage -Destination $Original -Force
$After = (Get-FileHash -Algorithm SHA256 -LiteralPath $Original).Hash
"$(Get-Date -Format o) send_mode=$Mode before=$Before after=$After backup=$Backup" | Add-Content -LiteralPath (Join-Path $HOME '.hermes/state/pair_launch.log') -Encoding Ascii
ops/start_pair.py --checkout $Checkout --state $State --expect-sha $ApprovedSha
```

Use these commands only when the signed order explicitly authorizes the restart. Verify the effective mode from the new identity/health evidence before declaring completion.

No `liquidity_filter` setting or command is implemented in this checkout. Do not substitute `liq_parity`: that is a separate liquidation-parity gate. Leave it unchanged and report the missing control as a blocker.
