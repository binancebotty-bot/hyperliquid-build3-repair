# Hot fix in 5 steps

This is a same-state Core/UI build swap, not a module hot-swap. Use only the reviewed
`ops/apply_hotfix.py` helper (currently under review on
`codex/build-swap-helper-6441575282` at `965851e`). If the helper is absent from the
checkout, stop; do not improvise the sequence with direct process commands.

1. **Match the signed identity.** Confirm the controller's Core PID, start time, current
   build, state path, and UI PID/port. If any value differs or the pair is ambiguous,
   stop and report it. Never infer a run from old files.
2. **Preflight the target.** Use a source-clean pair checkout pinned to its full SHA.
   Run `python ops/apply_hotfix.py <sha-or-worktree> --dry-run`. Continue only if its
   identity, same-state, backup, source-fill, and precompile checks pass.
3. **Swap only on a direct order.** After the required gate and explicit approval for
   that run, run `python ops/apply_hotfix.py <sha-or-worktree>`. It backs up the existing
   state and reuses `stop_pair.py` / `start_pair.py`; it must not seed, clear, or re-claim
   the state or pair-start anchor. Do not touch another run or start a second engine.
4. **Leave the replay watch attached.** Let the helper verify a healthy cycle, gap-fill
   intent rows, caught-up poll cursors, unchanged ledgers and USER-OWNED sleeves, zero
   duplicate attempts, and `UNRESOLVED 0`. If it blocks or times out, stop and report;
   do not rerun it against the same state to get a pass.
5. **Report the proof.** Give the old-down and first-healthy timestamps, measured gap,
   state/anchor checks, replay counts, duplicates, unresolved count, target SHA, and
   pushed commit. The gap must be under 20 seconds. At 20 seconds or more the helper
   prints `FAIL`, exits non-zero, and leaves the new pair running; there is no automatic
   rollback. Report the failure and wait for the next operator decision.
