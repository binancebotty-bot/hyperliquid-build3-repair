---
name: zeroed-restart
description: Archive prior run evidence, seed a new empty state directory explicitly, and start a fresh pair.
---

# Fresh zeroed restart

Use only after a fresh signed controller order explicitly authorizes stopping and starting the pair. This procedure creates a new run; never reuse, empty, or delete a prior state directory. Preserve prior run evidence in place. Do not copy raw state off-host.

1. Confirm the reviewed checkout is clean and its full commit SHA is approved:

   ```powershell
   git -C $Checkout rev-parse HEAD
   git -C $Checkout status --porcelain
   ```

   Expect the approved SHA and no status output. Stop if either differs.
2. Choose a brand-new empty `$State` path. Do not seed it or copy prior state into it.

3. Gracefully stop the pair, claim the network stamp before seeding, then seed with an explicit seed file and sends off:

   ```powershell
   ops/stop_pair.py --all
   if ($LASTEXITCODE -ne 0) { throw 'Pair stop failed; do not stamp or seed' }
   python -c "from _archive.hl_stage2 import exchange_truth as x; import sys; x.claim_network_stamp(sys.argv[1], x.NETWORKS)" $State
   if ($LASTEXITCODE -ne 0) { throw 'Network stamp failed; do not seed or start' }
   $T0 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
   python ops/seed_pair_state.py --state-dir $State --seed ops/live_config_seed.json --start-ms $T0 --send-mode off
   python ops/seed_pair_state.py --state-dir $State --seed ops/live_config_seed.json --verify-only
   ```

   Expect clean shutdown evidence, `send_mode OFF`, pre-start fills reachable `0`, then `VERIFIED`. Seed within 120 seconds of start; if stale, stop and reseed a new empty directory.
4. Start engine and UI from the same checkout and SHA:

   ```powershell
   ops/start_pair.py --checkout $Checkout --state $State --expect-sha $ApprovedSha
   ops/pair_identity.py --port 8031
   ```

   Expect one identity block and `pair UP and consistent`, with matching checkout/SHA and state path for engine and UI. A mismatch or degraded result is a stop-and-report blocker; do not enable sending.

Before any separately ordered send arm, use the existing sender-key preflight/status to confirm `HL_LIVE_HL_PRIVATE_KEY` is provisioned and its key is valid and approved for the follower account on the follower network. A `no signing key configured`, invalid, missing, or unreadable result is not a pass. Never read, echo, copy, or export the private-key value or dump the process environment.
