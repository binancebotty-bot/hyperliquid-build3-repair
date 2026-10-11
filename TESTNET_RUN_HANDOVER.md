# Testnet run handover — 2026-10-09

Written by Claude (Projects session) for Hermes, the Controller and the Architect.
This note reports work done outside the gated loop. It does not set or change any gate.
`CONTROL_STATE.json` (`current_gate`, `next_action`) was deliberately left untouched; reconciling it is the Controller/Architect's call.

## 1. What was merged to `main` (human authority: Boss / Richard, "Merge" decision 2026-10-09T14:04Z)

| PR | Merge commit | What it changed |
|----|--------------|-----------------|
| #4 Network switch + Global Controls | `2b549f81636608aa2f7a3626d1684b17df179d6e` | Engine base moved to the real Core engine `_archive/hl_stage2/HL_Live_Copy_Service_Core.py` (2 June backup, imported unchanged first: sha256 `5bda57be…1f848`, Boss's choice). Leader and follower networks are set separately (`HL_LEADER_NETWORK` default mainnet, `HL_FOLLOWER_NETWORK` default testnet). Each network has its own state folder (`hl_live_copy_audit_testnet/` for testnet) with a `network.json` stamp and an `instance.lock`, so mainnet and testnet can run in parallel. `HL_APP_PORT` sets the UI port. Global Controls from the UI are now enforced by the engine (0 or blank = off): total and per-asset caps use follower exchange truth across all DEXes and fail closed when unreadable; every entry limit is checked at the worst-case follower price; final wire notional re-checked against max order. ENG-016: entries are blocked in a coin whose exchange net differs from the engine's ledger (unowned inventory is never adopted). Exits fall back to the position mark when no fresh mid exists; with no price at all the exit goes to `MANUAL_EXIT_RECOVERY_REQUIRED` (RED). |
| #6 Core engine gaps | `07c29ae47a501718869de2e289a868585d3b4397` | Exactly one physical order site (`SenderGateway._place_order`). Daily loss limit as a UI control `max_daily_loss_usd` (0 = off), read from the follower's portfolio "day" PnL; unreadable PnL blocks entries. Proportional sizing uses the leader's real account value (portfolio whole-account, max with sum of perp accountValue across DEXes); the silent 10,000 `leader_equity_base` is ignored, and no equity means no order. More than 10 active wallets refuses startup / blocks entries instead of silently dropping wallets. Boss rulings implemented: **OD-01** entries priced from a fresh follower-market mid (≤5 s old, all DEXes), no fresh mid = no order; **OD-10 (part)** default slippage 0.2 % (20 bps) when unset. Independent review findings folded in. |
| #5 Certification contract | `9eb2d40f69fdfb3b667af54ba626cc2029a0d3b1` (last merge, current `main`) | `certification/`: master product invariants, ~790-requirement certification matrix (all `NOT_TESTED`), open-decision register (`open_decisions.json`), generator. Records the OD-01 and OD-10 rulings. |

Tests on merged `main` (`9eb2d40`), run offline in the cloud session:
Core `--self-test` 144 PASS / 0 FAIL; `test_core_network_and_global_controls.py` 60/60; `test_core_engine_gaps.py` 22/22; G3 48/48; G4 fixed slices 16/16, intake sleeves 14/14, order cap 16/16, UI controls 7/7.
`test_g2_copy_correctness.py` 40/41: the FLATTEN SELL check fails, and it fails identically on `main` before these PRs (pre-existing, not introduced here, still open).

## 2. Testnet run status: IN PROGRESS, no trade placed yet

Running on Boss's PC through a Remote Control session ("First testnet run" thread), from a fresh checkout of `main`.
- Done: waited for the merges; fresh copy set up; its offline checks all pass.
- In progress at the time of writing (2026-10-09 ~14:11Z): locating the still-running Build 4 (close-only mode) and stopping it cleanly. Instructions: record its network, account, open positions, orders and state folder; place or cancel nothing; no flatten; copy its state and logs to a dated preserved folder; confirm it no longer runs.
- Not yet done: confirm the testnet follower (0x7AE3…9205, ~$1,450 USDC, cleared by Boss) has no open orders or positions; set conservative limits (small per-order and total caps, a daily loss limit, slippage 0.2 %); start the Build 3 engine and UI on a different port and state folder from Build 4; copy real active mainnet leaders onto the testnet follower; compare every trade and UI number with the testnet exchange; map results to `certification/`.
- Reason no trade yet: Build 4 shutdown and account checks must finish first.

## 3. Build 4 and the mainnet leftovers — must be handled before ANY mainnet launch

Build 4 is being stopped and preserved (not deleted). Per Boss, the open trades on the mainnet account are leftovers from the failed earlier attempt that had to be shut down; Build 4 is not managing anything useful.
**Those leftover mainnet orders and positions must be dealt with deliberately (by a human decision) before Build 3 goes live on mainnet.** Build 3 never adopts or closes positions it did not open, and its ENG-016 gate will block entries in any coin where these leftovers sit. Nothing in this session cancelled, closed or adopted them.

## 4. Things the Controller/Architect should reconcile

1. **Gate state vs reality.** `CONTROL_STATE.json` still shows G4 open, `production_logic_changes_authorised: false`, and physical testnet trading deferred to G5. The work above was done on Boss's direct instruction outside that loop, on the Core engine instead of `HL_Live_Copy_Service.py`. The gate record needs a ruling on how to absorb it.
2. **Mark-price authority conflict.** The Architect's F3 ruling (B3-A2C-G4-F3-MARK-AUTHORITY-RULING-1) points at a `metaAndAssetCtxs` markPx adapter. Boss separately ruled OD-01 as a fresh follower **mid** (`allMids` per DEX, ≤5 s), and that is what `main` now implements. These need to be reconciled into one rule.
3. Pre-existing G2 FLATTEN SELL failure (above).

## 5. What's left next

1. Finish the first testnet run (section 2) and record results against the certification matrix. Watch specifically: whether a partial IOC fill wrongly blocks further entries in that coin (ENG-016 tolerance), whether the testnet portfolio endpoint gives daily PnL and covers HIP-3, and the per-DEX `allMids` key format (both unverified offline).
2. Known engine follow-ups: blocking on foreign open orders (needs order-id tracking); automatic exit retry after `MANUAL_EXIT_RECOVERY_REQUIRED`; units-vs-USD sizing across networks (product decision).
3. ~38 smaller open decisions in `certification/open_decisions.json`, including the rest of OD-10 (entry price bound, close adverse diff).
4. Human decision on the mainnet leftovers (section 3) before any mainnet launch. Mainnet should then need only a credential and network change.
