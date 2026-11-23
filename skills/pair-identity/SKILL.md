---
name: pair-identity
description: Read the pair identity block and verify the engine/UI refer to one build and run.
---

# Verify pair identity

1. Run the read-only identity reporter only when the active operating rules permit its process checks:

   ```powershell
   python ops/pair_identity.py --port 8031
   ```

2. Expect exit `0` and `pair UP and consistent`. Confirm the engine and UI PIDs are present, both report the same approved checkout/SHA and state directory, and the UI listener is on the requested port.
3. Stop and report on `DEGRADED`, `UNKNOWN`, mismatched build/state, missing PID, or extra process. Never infer identity from old files.

`pair_identity.py` inspects process command lines to count engine instances. If the current policy forbids command-line inspection, do not run it; use the latest signed identity block and PID-only presence checks, and mark any unverified fields UNKNOWN.
