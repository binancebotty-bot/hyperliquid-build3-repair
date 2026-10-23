# Build 3 TESTNET startup

The committed launch spec pins the source base, Core/UI entrypoints, TESTNET follower, and one shared audit/state directory. The launcher passes that same directory to Core, UI, and its minute-by-minute alert-only check. It does not change wallet modes or config and never restarts a Core process. The spec currently names `run7/state_20261023`; that active run is verify-only until it has been cleanly stopped under a fresh direct order.

```powershell
python ops/testnet_startup.py plan
python ops/testnet_startup.py self-check
python ops/testnet_startup.py verify
python ops/testnet_startup.py watch
python ops/testnet_startup.py start --execute --confirm-testnet --authorization-order <fresh-direct-order-id>
```

`plan` is the default and starts nothing. `verify` checks once; `watch` checks every minute until Ctrl+C. `start` requires `--execute`, `--confirm-testnet`, a fresh direct authorization order ID, a clean pinned checkout, TESTNET follower selection, no tracked Core holder, and a free UI endpoint on 8031. It waits up to 30 seconds for fresh Core state before starting the loopback UI. The foreground launcher checks PID, start time, build SHA, follower network, shared state path, other run-state PIDs, and `/api/state` every minute. Changed failures go to issue #3; neither mode restarts Core. Ctrl+C in the launch console is the only supported stop path; do not use Task Manager force-stop. A restart requires a fresh direct order, a clean shutdown, and the same run state directory so dedupe history is preserved.

For rollback, stop only through the approved foreground path, check out the previously reviewed commit in a clean worktree, then run `plan` and `self-check` before any separately authorized start. Preserve every audit/state file and do not change send modes, config, network credentials, active PIDs, or the selected state folder. Old launchers and scheduled tasks are disabled only after their exact ownership is verified; keep them for audit rather than deleting them. Never start a second Core, reuse another run's audit directory, or use this testnet launcher for mainnet.
