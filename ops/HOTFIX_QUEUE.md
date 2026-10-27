# Hot-fix queue

Every item here is a **live hot fix, route per `ops/HOTFIX.md`**. Nothing in this file waits for a restart.
The only restart is the final mainnet start itself, and it is not in this list.

Status legend: `OPEN` = not yet applied live; `APPLIED` = live, proof recorded; `BLOCKED` = route unavailable, reason noted.

| # | Item | What it fixes | Where | Status |
|---|---|---|---|---|
| 1 | `_recovery_finalised` duplicate-terminal hardening | a recovery pass could finalise the same terminal twice | engine: `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` | OPEN |
| 2 | 960f830 pending-send fix | pending-send state after an ambiguous timeout (PR #94) | branch `codex/hotfix-pending-send-terminal` | OPEN |
| 3 | `liq_parity` default `False` unless mainnet | liquidation parity asserted on a testnet run | controls / live_config | OPEN |
| 4 | UI `send_mode` drop | UI showed a send mode the engine was not in | `_archive/hl_stage2/HL_Copy_App_SSOT.py` | OPEN |
| 5 | D5 UI equity | equity tile read the wrong scope | `_archive/hl_stage2/HL_Copy_App_SSOT.py` | OPEN |
| 6 | e6844a8 UI scope | account tile did not read every dex in scope | branch `codex/ui-tile-scope-643118` | OPEN |
| 7 | CAP_REFUSED | a cap refusal was not surfaced as its own terminal state | engine + UI | OPEN |
| 8 | wallet-cap size-down | wallet cap refusal must size down, not stop the engine | engine cap path | OPEN |

## How an item leaves this file

1. Follow `ops/HOTFIX.md` (route, pre-checks, load, proof, rollback).
2. Proof is a measured before/after value plus open orders, ledger and USER-OWNED sleeves unchanged.
3. Change the row to `APPLIED` with the proof comment id. Do not delete rows.

## Not in this queue

The final mainnet start is a restart, not a hot fix. It is tracked separately.
