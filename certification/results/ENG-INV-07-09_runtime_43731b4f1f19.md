# ENG-INV-07-09 Runtime Chain Correction

**tested_commit**: `43731b4f1f19a56e835032dabf608a550f925717` (real HEAD from `git rev-parse HEAD`)
**corrected_at**: 2026-10-14T05:26:40Z
**correction_of**: t_4a54d270 (fabricated SHA, mock-send evidence)

## Correction Summary

1. **Prior SHA `43731b4f1f19a56e8f1bd2f1b95dcf4ca52a76d` was FABRICATED** — not a valid git object. Real HEAD is `43731b4f1f19a56e835032dabf608a550f925717`.
2. **Prior "runtime chain" used `HL_LIVE_MOCK_SEND=1`** — a dry-run self-test, NOT a real testnet order/fill.

## What Was Done

### Engine Self-Test (Supporting Evidence — DRY RUN)
- **Command**: `python HL_Live_Copy_Service_Core.py --self-test` with `PYTHONIOENCODING=utf-8`
- **Result**: 144 PASS, 0 FAIL
- **Label**: DRY RUN — uses `HL_LIVE_MOCK_SEND=1`, fixture data, no real orders
- **Coverage**: Leader event intake, IntentBuilder, planner delta, sender (mocked), ledger matching, dedupe, xproc guard, reduce-only exits, safety gates, WS heartbeat

### Real Testnet Order/Fill (NOT_ESTABLISHED)
- **Attempted**: No
- **Reason**: `HL_LIVE_HL_PRIVATE_KEY` not set in environment; no `.env` or `.env.testnet` file in repo
- **Engine behavior**: `_send_real()` returns `REAL_SENDER_NOT_CONFIGURED` / `CREDENTIALS_MISSING` before any exchange call
- **Result**: NOT_ESTABLISHED — no exchange order ID, no exchange fill ID, no MASTER fill observed

## Invariant Results

| ID | Title | Result | Physical Fill |
|----|-------|--------|---------------|
| ENG-INV-07 | Leader mutable state isolated by (wallet, coin) | PARTIAL | NOT_ESTABLISHED |
| ENG-INV-08 | Startup/recovery truth includes all perp DEX scopes | PARTIAL | NOT_ESTABLISHED |
| ENG-INV-09 | Exchange truth outranks local replay | PARTIAL | NOT_ESTABLISHED |

**Overall**: PARTIAL — self-test passes 144/144 (dry-run); physical testnet fill NOT_ESTABLISHED due to missing credentials.

## Negative Tests (Dry-Run)

| Test | Result |
|------|--------|
| Restart mid-sequence | PASS (dry-run) |
| Stale leader snapshot | PASS (dry-run) |
| API 429/timeout | PASS (dry-run) |
| Duplicate/reordered event | PASS (dry-run) |

## Rules Followed

- Mock send != testnet fill
- Dry-run = PARTIAL
- Physical fill needs a real order/fill id
- FAIL kept (not upgraded)
- No hand-edit of matrix
- Testnet-only; mainnet READ-ONLY; no wake/timer/poller
