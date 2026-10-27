---
name: hot-fix-build
description: Apply an approved code artifact while retaining the current process and run state.
---

# Hot fix with state retained

This is a live module swap, not a process restart. Require a fresh signed order naming the artifact, target module, run, and rollback plan. Never swap the engine, UI, launcher, wallet, send, key, or gate code. The current seam allowlists `exchange_truth` and `follower_volume`; Core remains protected.

A hot fix that needs Core goes into the mainnet restart queue. Do not apply it to the running pair or restart the pair to load it; wait for the separately authorized mainnet restart.

1. Confirm the artifact is the reviewed build and compute its full digest:

   ```powershell
   Get-FileHash -Algorithm SHA256 -LiteralPath $Artifact
   ```

   Record the full 64-hex SHA-256; do not shorten it.
2. After approval, write this exact request to the identified run's audit directory:

   ```json
   {"module":"exchange_truth","action":"apply","artifact":"<absolute-artifact-path>","sha256":"<64-hex-sha256>"}
   ```

   PowerShell form (set `$Artifact`, `$State`, and `$ApprovedSha` to the approved values):

   ```powershell
   $ActualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Artifact).Hash.ToLowerInvariant()
   if ($ActualSha -ne $ApprovedSha.ToLowerInvariant()) { throw 'Artifact SHA does not match approval' }
   $Request = @{ module = 'exchange_truth'; action = 'apply'; artifact = (Resolve-Path -LiteralPath $Artifact).Path; sha256 = $ActualSha } | ConvertTo-Json -Compress
   Set-Content -LiteralPath (Join-Path $State 'HOTSWAP_REQUEST.json') -Value $Request -Encoding Ascii
   ```

   The running loop consumes the request. Do not restart or reset state.
3. Verify the new `hotswap.log` entry has `event: APPLIED`, `module: exchange_truth`, and the same digest. The request file is consumed. Any `REFUSED_*`, missing result, or digest mismatch is a blocker; do not retry with changed bytes.

The hot-swap seam preserves the previous module for rollback. Do not use it as a general build deployer.
