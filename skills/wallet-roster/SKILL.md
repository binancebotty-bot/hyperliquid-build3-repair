---
name: wallet-roster
description: Safely add or archive a follower wallet in the live-copy roster.
---

# Wallet roster changes

Use only for an explicit, current controller order. Confirm the signed run identity first. Never enter or copy a private key, API secret, or seed phrase.

## Add

1. Use the dashboard's **Add wallet** form at `http://127.0.0.1:8031/live-copy`, or its existing loopback API with a public address and mode `OFF`:

   ```powershell
   $Wallet = '<public-wallet-address>'
   $Body = @{ wallet = $Wallet; mode = 'OFF' } | ConvertTo-Json -Compress
   $null = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8031/api/live-config/add-wallet' -ContentType 'application/json' -Body $Body
   ```

2. Expect an HTTP success response with `ok: true`. Verify one row appears with the intended address and `OFF` mode. Do not enable it in the same change.

## Remove from the active roster

1. Use **Archive**, not **Purge**, or the existing loopback API:

   ```powershell
   $Body = @{ wallet = $Wallet; archive = $true } | ConvertTo-Json -Compress
   $null = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8031/api/live-config/remove-wallet' -ContentType 'application/json' -Body $Body
   ```

2. Expect an HTTP success response with `ok: true` and mode `OFF`. Verify the wallet is no longer active and appears in the archived roster.

Archiving removes the wallet from config only; it does not cancel exchange orders or flatten exposure. Stop and escalate if the request assumes otherwise. Keep audit/history evidence.
