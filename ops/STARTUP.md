# Build 3 TESTNET startup

The committed spec pins one Core revision, one TESTNET Info endpoint, the follower address, the shared run state/audit folder, and the global Core lock. Core, UI, verification, and the relauncher use that same folder. The spec must contain a public `follower_account_address` and exact signed residual sizes in `documented_residuals_by_coin`; neither field accepts private credentials.

```powershell
python ops/testnet_startup.py plan
python ops/testnet_startup.py self-check
python ops/testnet_startup.py verify
python ops/testnet_startup.py watch
python ops/testnet_startup.py preflight
python ops/testnet_startup.py start --execute --confirm-testnet --authorization-order <fresh-order-id>
python ops/testnet_startup.py supervise --execute --confirm-testnet --authorization-order <fresh-order-id>
python ops/testnet_startup.py prepare
python ops/testnet_startup.py stop
python ops/testnet_startup.py retire-legacy
```

`plan` starts nothing. `verify` checks the pinned Core/UI identity once; `watch` repeats the read-only check and reports changes. `preflight` and both start modes query TESTNET positions and resting orders for every perpetual DEX. They print positions by coin and PASS/FAIL for flatness, no remaining resting orders, no running Core immediately before launch, and retirement of legacy watchdog PID 38604. Exact documented residual positions may remain; any open order or undocumented/mismatched position fails closed. The script verifies cancel-all outcome but does not send cancellation requests. If orders need cancellation, use only the separately authorized supported route, then rerun preflight.

**Prepare design (accepted):** the script does NOT cancel or flatten. Codex does cancel-all and flatten as step 1 of the cutover window, sequentially. `prepare` then verifies zero open orders and flat, apart from the documented residuals, and fails closed.

`start` launches once. `supervise` holds one Windows lock and relaunches only the pinned spec after Core exits; it also checks stale state every minute. It refuses to run until the legacy watchdog retirement is confirmed in the spec and the old PID is absent. This branch does not stop Core or disable that external watchdog. Ctrl+C exits this launcher/supervisor only; Core is left running. No supported orderly Core-stop route was found in the checked-in code, so stop/restart/rollback require a separate fresh direct order and a verified shutdown method. Do not use Task Manager or force-kill.

Every launch requires a fresh direct authorization order, TESTNET confirmation, a passing preflight, exact source pin, and the configured state folder. The running engine remains untouched while building. Preserve all state/audit files and wallet modes. Never point the spec at mainnet or another run.
