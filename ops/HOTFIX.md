# Same-state Build 3 hotfix swap

`apply_hotfix.py` changes the Core and UI together to a clean, reviewed checkout while keeping the current state directory. It does not seed, clear, re-claim, or rename the state. Keep the engine attached to the process until its polling cursor has crossed the outage window and the proof table passes.

```powershell
python ops/apply_hotfix.py <build_sha_or_worktree> --dry-run
python ops/apply_hotfix.py <build_sha_or_worktree>
python ops/apply_hotfix.py --rollback
```

The target must be a source-clean pair checkout with an existing worktree if a SHA is supplied; generated `graphify-out/` files do not affect the build check. Before the stop, the helper verifies one engine for the selected state, the Core identity block and running checkout SHA, the tracked UI identity and same build, `CURRENT_AUDIT_DIR`, the preserved state and pair anchor, launch-environment key names, the local raw leader-fill source, and Python compilation for the Core, UI, and reused pair scripts. Environment contents are forwarded in memory and are never printed or included in the proof.

After staging a timestamped state backup, it rechecks the identity and invariants, calls `stop_pair.py --all`, changes only the non-secret build metadata in `core_launch_env.json`, rewrites `CURRENT_AUDIT_DIR` to the same state path, then calls the target build's `start_pair.py` and records the UI identity with `stop_pair.py --track-ui`. The scripts remain the existing pair launch/stop implementation.

The proof compares `PAIR_START_ANCHOR.json` byte-for-byte and its `t0_ms`; `live_config.json` by parsed JSON equality (key order, whitespace and BOM ignored; no timestamp fields ignored in live_config); the sleeve ledgers `manual_live_positions.json` and `xyz_position_state.json`; and USER-OWNED wallet entries. The only ignored timestamp fields are `manual_live_positions.last_updated_at` and `xyz_position_state.updated_at` / `updated_at_ms`. All other content must match. A changed state invariant fails closed. Raw config bytes are still recorded for diagnostics, but do not gate the post-start proof: a harmless JSON formatting rewrite is accepted, while changed values fail. `PAIR_START_ANCHOR.json` remains byte-for-byte immutable.

The helper timestamps the moment the old pair is fully down and the first post-start healthy Core cycle. The gap must be **under 20 seconds**. It then remains attached until every local raw leader fill in that gap has an `order_intents.csv` row, every LIVE/CLO wallet poll cursor has crossed the gap, no previously-sent fill receives another send attempt, and the unresolved counters are zero. A missing local fill source, identity ambiguity, unclean stop, timeout, state change, missing replay row, duplicate send, or gap of 20 seconds or more is a failure. A measured gap of 20 seconds or more prints `FAIL`, exits non-zero, and leaves the new pair running; it does not automatically roll back. In contrast, **any exception after requesting the old pair stop**, including launch-metadata writes, new-pair start, and replay proof failures, attempts to restore the original checkout and pair, then exits non-zero. Failure to restore is reported as a separate hard failure. An explicit `--rollback` remains a second operator-authorised swap.

`--dry-run` runs the target and state prechecks without writing a backup, changing launch metadata, or controlling processes. Do not use the helper against a different run or state path from the one in the latest controller identity.
