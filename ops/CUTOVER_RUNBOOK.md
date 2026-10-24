# Build 3 TESTNET Cutover Runbook

**Branch:** `hermes/fallback-startup-231023` @ `bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847`
**Controller Order:** `CUTOVER ORDER bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847`
**Controller Order ID:** `<to be filled at cutover>`

---

## Overview

This runbook executes the sequential cutover from the current live engine (PID 10156, build `bf40a9d`) to a supervised fresh start on the same pinned spec. The runbook is **sequential** — each step must PASS before the next begins. **No second engine ever.**

**Current State:**
- Live engine: PID 10156, build `bf40a9d`, state `run7/state_20261023`
- Legacy watchdog: PID 38604 (expected start `1792755782375`)
- Both proportional wallets: fixed $12 (copy_mode=fixed, norm_base=100)

---

## Prerequisites

- [ ] Controller issues cutover order comment with exact line: `CUTOVER ORDER bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847`
- [ ] Comment ID recorded as `AUTHORIZATION_ORDER_ID`
- [ ] All 18 tests PASS (`pytest ops/test_testnet_startup.py -v`)
- [ ] `py_compile ops/testnet_startup.py` PASS
- [ ] `ops/testnet_startup.py self-check` PASS
- [ ] `ops/testnet_startup.py plan` PASS

---

## Step 1: Stop Core (Hermes)

**Command:**
```bash
python ops/testnet_startup.py stop --dry-run
# If dry-run shows expected PID, then:
python ops/testnet_startup.py stop
```

**File:** `ops/testnet_startup.py` — `stop_core_process()` function (lines ~600-650)
**Line:** `stop_core_process()` called with `dry_run=False`

**Pass Criterion:**
- Output: `STOP_OK: Core process 10156 stopped successfully`
- Shutdown record written: `core_shutdown_record.json` with `clean: true`
- Exit code: 0

**Failure:** If exit code ≠ 0 or shutdown record not written → **ABORT**. Do not proceed. Report to controller.

---

## Step 2: Retire Legacy Watchdog (Hermes)

**Command:**
```bash
python ops/testnet_startup.py retire-legacy --dry-run
# If dry-run shows expected PID, then:
python ops/testnet_startup.py retire-legacy
```

**File:** `ops/testnet_startup.py` — `retire_legacy_watchdog()` function (lines ~693-760)
**Line:** `retire_legacy_watchdog()` called with `dry_run=False`

**Pass Criterion:**
- Output: `RETIRE_LEGACY_OK: Legacy watchdog retired; startup entry disabled (...)` 
- Startup entry `Hermes_PL_Controller_Link.vbs` renamed to `.vbs.disabled_by_hermes`
- Exit code: 0

**Failure:** If exit code ≠ 0 or startup entry not disabled → **ABORT**. Report to controller.

---

## Step 3: Cancel-All + Flatten (Hermes)

**Command:**
```bash
python ops/testnet_flatten.py --dry-run
# If dry-run passes:
python ops/testnet_flatten.py --execute
```

**File:** `ops/testnet_flatten.py`
- Cancels all open orders on testnet follower account `0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205`
- Reduce-only IOC closes for all non-flat positions
- Re-reads and verifies zero open orders + flat positions
- `--dry-run` cancels and closes nothing and skips the live assertion (it cannot pass without acting)

**Pass Criterion:**
- `--dry-run` exit 0, ends `=== DRY RUN COMPLETE: Would flatten successfully ===`
- `--execute` exit 0 and prints `VERIFIED: Zero open orders, all positions flat`

**Note:** the script treats any non-flat position as failure. Documented residuals are accepted by `prepare` (Step 4); if a residual must stay, `--execute` reports it and you stop for a controller ruling.

**Failure:** If exit code ≠ 0 or output contains `FAIL` → **ABORT**. Report to controller. Do not proceed.

---

## Step 4: Prepare Verification (Hermes)

**Command:**
```bash
python ops/testnet_startup.py prepare
```

**File:** `ops/testnet_startup.py` — `prepare_account()` function (lines ~535-565)
**Line:** `prepare_account()` calls `follower_account_state()` → `evaluate_flatness()`

**Pass Criterion:** 
- Output: `PREPARE_OK: Account is flat and cancel-all verified`
- Exit code: 0

**Failure:** If exit code ≠ 0 or output contains `PREPARE_FAILED` → **ABORT**. Report to controller. Do not proceed.

---

## Step 5: Start (Hermes)

**Command:**
```bash
python ops/testnet_startup.py start --execute --confirm-testnet --authorization-order <COMMENT_ID>
```

**File:** `ops/testnet_startup.py` — `main()` → `run_startup(supervised=False)` (lines ~1135-1180)
**Line:** `run_startup(spec, state_dir, sha, supervised=False)` called

**Arguments:**
- `--execute`: Allow actual TESTNET launch
- `--confirm-testnet`: Explicit TESTNET confirmation
- `--authorization-order <COMMENT_ID>`: Controller's cutover order comment ID

**Pass Criterion:**
- Output shows: `CORE_STARTED pid=<PID> build_sha=bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847 follower=testnet state_dir=...`
- UI starts: `UI_STARTED pid=<PID> url=http://127.0.0.1:8031`
- Core identity verified: `SELF_CHECK_PASS` equivalent checks pass
- Exit code: 0 (runs indefinitely)

**Failure:** If core fails to start or identity mismatches → **ABORT**. Core left running. Report to controller. **No second engine ever.**

---

## Step 6: Post-Start Verification (Hermes)

**Command:**
```bash
python ops/testnet_startup.py verify
```

**File:** `ops/testnet_startup.py` — `verify` action in `main()` (line ~1145)
**Line:** `collect(spec, state_dir, sha)` called

**Pass Criterion:** 
- Output: JSON with `"status": "PASS"`
- PID matches started process
- SHA matches `bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847`
- State advancing (timestamp increasing)
- UI shows PID, SHA, audit dir
- UI sends `ON`

**Failure:** If status ≠ PASS → **ABORT**. Report to controller.

---

## Step 7: 30-Minute Post-Start Sample (Hermes)

**Command:** (Wait 30 minutes from Step 5 start, then run)
```bash
python ops/testnet_startup.py verify
# Also check audit log for durability timeouts
```

**Pass Criterion:**
- Output: `"status": "PASS"`
- Count of durability timeouts (audit_write_failures.log lines with "NOT on disk before exchange call" or "intent audit writer did not drain") reported to controller
- Sizing stable at fixed $12

**Failure:** Report any anomalies to controller. Continue monitoring.

---

## Failure Handling (All Steps)

| Step | Failure Action |
|------|----------------|
| 1 (Stop Core) | **ABORT** — Report to controller. Do not proceed. |
| 2 (Retire Legacy) | **ABORT** — Legacy watchdog may still be active. Report to controller. |
| 3 (Cancel-All + Flatten) | **ABORT** — Report to controller. Do not proceed. |
| 4 (Prepare) | **ABORT** — Report to controller. Do not proceed. |
| 5 (Start) | **ABORT** — Core may be in unknown state. **No second engine ever.** Report to controller. |
| 6 (Verify) | **ABORT** — Core may be unhealthy. Report to controller. |
| 7 (30-min Sample) | Report anomalies. Continue monitoring. |

---

## Critical Rules

1. **No second engine ever** — Only one Core process at any time.
2. **Fail closed** — Any verification failure stops the cutover.
3. **Controller authorization required** — Step 5 requires a fresh Controller comment ID.
4. **Shutdown record mandatory** — Core stop must write `core_shutdown_record.json`.
5. **Legacy watchdog retired** — Startup entry disabled before Step 5 starts. `supervise` is NOT used by this cutover; `start` is the single start command.
6. **Exact SHA in cutover order** — `CUTOVER ORDER bf40a9d8bbb91348ebebf1b7d8d53ec15cbc7847`

---

## GRAPHIFY/PONYTAIL
