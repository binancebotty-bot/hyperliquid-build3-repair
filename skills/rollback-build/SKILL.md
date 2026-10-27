---
name: rollback-build
description: Return to an approved last-good build without resetting run state.
---

# Roll back the build, retain run state

Require a fresh signed order naming the last-good full SHA and authorizing the restart. Do not reset, reseed, or delete the current run directory.

1. Verify the target commit exists and make a clean rollback checkout:

   ```powershell
   git -C $SourceCheckout rev-parse --verify "$GoodSha^{commit}"
   git -C $SourceCheckout worktree add --detach $RollbackCheckout $GoodSha
   git -C $RollbackCheckout rev-parse HEAD
   git -C $RollbackCheckout status --porcelain
   ```

   Expect the exact approved SHA and an empty status. Stop if not.
2. Gracefully stop the pair and restart it from the rollback checkout against the same run state:

   ```powershell
   ops/stop_pair.py --all
   ops/start_pair.py --checkout $RollbackCheckout --state $State --expect-sha $GoodSha
   ops/pair_identity.py --port 8031
   ```

   Expect a clean stop and `pair UP and consistent`; engine/UI must report the approved SHA and the original state path. Do not seed a new directory for a build rollback.
3. If the stop is unclean, start fails, identity disagrees, or any state evidence is stale, stop and report. Never force-kill or silently retry another build.
