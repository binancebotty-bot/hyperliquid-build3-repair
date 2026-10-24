# Build 3 TESTNET startup

The committed spec pins one Core revision, one TESTNET Info endpoint, the follower address, the shared run state/audit folder, and the global Core lock. Core, UI, verification, and the relauncher use that same folder. The spec must contain a public `follower_account_address` and exact signed residual sizes in `documented_residuals_by_coin`; neither field accepts private credentials.

```powershell
python ops/testnet_startup.py stop --dry-run
python ops/testnet_startup.py stop
python ops/testnet_startup.py retire-legacy --dry-run
python ops/testnet_startup.py retire-legacy
python ops/testnet_flatten.py --dry-run
python ops/testnet_flatten.py --execute
python ops/testnet_startup.py prepare
python ops/testnet_startup.py start --execute --confirm-testnet --authorization-order <fresh-order-id>
python ops/testnet_startup.py verify
```

`start` is the single start command for the cutover (see `ops/CUTOVER_RUNBOOK.md`, Step 5). `supervise` exists in the script but is NOT used by this cutover.

`stop` and `retire-legacy` are supported orderly routes (via `stop_core_process()` and `retire_legacy_watchdog()`). `plan` starts nothing. `verify` checks the pinned Core/UI identity once; `watch` repeats the read-only check and reports changes. `preflight` and start query TESTNET positions and resting orders for every perpetual DEX. They print positions by coin and PASS/FAIL for flatness, no remaining resting orders, no running Core immediately before launch, and retirement of legacy watchdog PID 38604. Exact documented residual positions may remain; any open order or undocumented/mismatched position fails closed. The script verifies cancel-all outcome but does not send cancellation requests. If orders need cancellation, use only the separately authorized supported route (`ops/testnet_flatten.py`), then rerun preflight.

**Prepare design (accepted):** the script does NOT cancel or flatten. Hermes does cancel-all and flatten with `ops/testnet_flatten.py` (`--dry-run`, then `--execute`), and that step runs AFTER Core is stopped so the live engine cannot re-open positions mid-flatten. `prepare` then verifies zero open orders and flat, apart from the documented residuals, and fails closed.

`start` launches once. `supervise` holds one Windows lock and relaunches only the pinned spec after Core exits; it also checks stale state every minute. It refuses to run until the legacy watchdog retirement is confirmed in the spec and the old PID is absent. Ctrl+C exits this launcher/supervisor only; Core is left running. Supported orderly Core-stop route exists: `stop_core_process()` in `ops/testnet_startup.py`. Do not use Task Manager or force-kill.

Every launch requires a fresh direct authorization order, TESTNET confirmation, a passing preflight, exact source pin, and the configured state folder. The running engine remains untouched while building. Preserve all state/audit files and wallet modes. Never point the spec at mainnet or another run.

## Env-injecting start: `ops/hermes_core_start.py`

`ops/testnet_startup.py start` calls `prepare_account`, which cancels all orders and flattens the account. When the residual positions and reduce-only orders must survive — or when `launch_once` refuses on a missing clean-shutdown record — use the small launcher below instead. It lives OUTSIDE the Core folder and NEVER prints, logs or commits an env value.

```powershell
python ops/hermes_core_start.py --dry-run   # prints CMD + cwd + wallet length only
python ops/hermes_core_start.py             # starts ONE Core, detached, no console
```

What it does: reads the pinned `ops/testnet_launch_spec.json`, builds the child environment from the spec's own fields exactly as `launch_once` does (`HL_LIVE_AUDIT_DIR`, `HL_FOLLOWER_NETWORK`, `HL_LIVE_WS_ENABLED`, `HL_BUILD_SHA`, `HL_APP_PORT`, `HL_USER_WALLET`, `HL_LIVE_GLOBAL_LOCK_FILE`), then Popens the Core with `creationflags=CREATE_NO_WINDOW` from `core_script`'s directory. It does not run `prepare_account`, does not call `launch_once`, and does not touch the spec.

Interpreter: the Core needs the Python that has the `hyperliquid` SDK — `C:/Users/wigmore/AppData/Local/Python/bin/pythonw.exe` at the time of writing. Hermes' own venv does not have it, so the script pins the interpreter and accepts `HERMES_CORE_PYTHON` as an override. A wrong interpreter starts a Core that answers `SDK_UNAVAILABLE`, not a credential error.

**The wallet value must keep its `0x` prefix.** The script hard-fails if the spec's `follower_account_address` is not a 42-character `0x` string, because `is_valid_wallet()` in the Core (`HL_Live_Copy_Service_Core.py:3481`) requires `startswith("0x") and len == 42`. A hand-built environment once carried a 40-character address with the prefix stripped; the Core then reported `copy_account_status = COPY_ACCOUNT_NOT_CONFIGURED` and polled no copy fills while looking otherwise healthy. A correct launch reports `COPY_ACCOUNT_POLLED` within seconds.

Verify from engine state, not from the process: `live_service_state.json` must show `copy_account_status=COPY_ACCOUNT_POLLED`, `last_copy_poll_age_ms` under 5000, `ws_status=WS_OK`, `ws_wallet_count` equal to the configured wallet count, and `send_backlog=0`.

