# EVIDENCE / RISK_BLOCK_JOIN_20261024

Controller order 6389330991. Read-only join over run8 `state_20261024/append_only/`.
Window: `created_at_ms >= 1792859059000` (2026-10-24T16:24:19Z). Scope: LIVE wallets only
(`mode == "LIVE"` in `live_config.json`: 10 of 19 roster wallets LIVE, 6 CLO, rest OFF).

Append-only files were still being written during the read; totals are a point-in-time snapshot
and drifted <0.1% between successive reads. All counts below are from one snapshot.

## 1. Scope and decision counts

| quantity | value |
|---|---|
| order_intents.csv rows, full file | 133,102 |
| order_intents.csv rows in window | 21,250 |
| rows in window AND LIVE wallet | **20,839** |
| distinct LIVE wallets in window | 7 |
| window timestamps covered (ms) | 1792859070959 - 1792874915788 |

Decision counts, window + LIVE (`order_intents.csv` col `decision`):

| decision | window+LIVE | full file (all wallets) |
|---|---|---|
| SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION | 13,100 | 24,432 |
| **SEND_BLOCKED_RISK** | **5,872** | 6,715 |
| **ENTRY_ALLOWED** | **1,774** | 7,126 |
| EXIT_ALLOWED | 93 | 93 |
| BLOCKED_CLO_ENTRY | 0 | 94,666 |
| NOT_APPLICABLE_SPOT | 0 | 69 |

**The Part A ratio does NOT survive the window restriction in the same form.**
Full file: 6,715 blocked vs 7,126 entry-allowed (~0.94:1). Window+LIVE: 5,872 blocked vs 1,774
entry-allowed (**3.31:1**). Restricting to the window and to LIVE wallets *raises* the block rate,
because the 94,666-row CLO block population is excluded while the LIVE risk blocks are not.

Blocked copy notional (window+LIVE): 79,560.00 of 265,257.56 total = **30.0%** of window notional.

## 2. Distinct reason strings with per-cap attribution

Source: `order_intents.csv`, column `reason` (decision `SEND_BLOCKED_RISK` only). That file has no
`reject_category` column.

| reason string (order_intents.csv) | count | notional | cap |
|---|---|---|---|
| `max wallet exposure exceeded` | 4,051 | 54,600 | wallet 400 |
| `no fresh follower-network (testnet) price to value the order` | 1,685 | 23,328 | pricing/data, not a cap |
| `max total exposure exceeded` | 91 | 1,092 | total 900 |
| `max total exposure exceeded (positions + resting limits)` | 37 | 444 | total 900 |
| `UNOWNED_INVENTORY: XYZ:MSTR exchange net -0.378 != engine-owned net 0.0; entries blocked` | 7 | 84 | inventory reconciliation |
| `UNOWNED_INVENTORY: XYZ:LLY exchange net -0.024 != engine-owned net 0.0; entries blocked` | 1 | 12 | inventory reconciliation |
| **total** | **5,872** | **79,560** | |

Caps with **zero** blocks in this window, stated explicitly: order-notional cap (250) = **0**;
per-asset directional cap (300) = **0**; daily-loss cap (100) = **0**; margin-mode gate = **0**;
coin allowlist/blocklist = **0**; liquidation parity = **0** in `order_intents.csv` (parity lives in
`reconciliation.csv`, see §4). Total-exposure cap (900) = **128** (91 + 37).
`CAP_SIZED_DOWN` (partial sizing under remaining allowance) appears 3 times, all on ALLOWED rows.

Three example intent_ids per bucket:
- wallet cap (400): `d70bd76400d0f5935c895335f67ae5d6`, `cbe1b2df051e95b1b1caa871e1261bf0`, `7cbbcdb5cf55f0bc84922b5f1ce9e2f2`
- no fresh price: `29f032a263f8ca7f7bf35c18a77248f3`, `436dcb53e344786e1d2aee68a85c3433`, `88d8e8a6fddb84cad7b8ee2534a53825`
- total cap (900): `7a8362aa0c1237813f057c4d75b4a4ca`, `71d4c47a0d463682e2c1c05553740242`, `369fb7f19961642afaa02b357fa2d4c3`
- total cap + resting: `12fcb7961c6049f4e4904222d3811bef`, `b91e43e47e1ee48f80944ab64dd3f72b`, `28314fe17f83e03fa6e7b2137b5e336b`
- unowned inventory: `0552279f05e30701d38c7a5826094fbe`, `83b2ae823df2f282e1bf39dd4437d660`, `e8d51c32e6ab891a69fe0f0368a0680d`

Allowed-reason contrast (`order_intents.csv`): `no owned sleeve; leader close fill cannot open reverse
position` 13,100; `ADD` 926; `ENTRY` 845; `EXIT` 93; three `CAP_SIZED_DOWN` rows. Example ids:
ENTRY_ALLOWED `e571b8fe6d0dff322a737bc3f17ce5df`, `0f62ab024fe3a7eee12d77319f5c666b`, `27ad89904d4f05ca7c109bb62d03bce2`;
EXIT_ALLOWED `d71f51ddc3643e89c5d2a7085988f448`, `f970f8fd1b34a3597a9d33905d4d131e`, `4501a60ac14c6a34bc459891bb0bde03`.

## 3. Per wallet and top-10 coin splits

Per wallet, window + LIVE (`order_intents.csv`):

| wallet (prefix) | rows | blocked | allowed | dominant blocked reasons |
|---|---|---|---|---|
| 0x7717a7a2 | 15,099 | 5,641 | 9,458 | wallet cap 4,051; no fresh price 1,582; unowned MSTR 7 |
| 0xd4c1f7e8 | 5,636 | 231 | 5,405 | no fresh price 103; total cap 91; total+resting 37 |
| 0x21ca9810 | 2 | 0 | 2 | - |
| 0x8455193b | 2 | 0 | 2 | - |
| 0x92bbd811 | 6 | 0 | 6 | - |
| 0xbee0000c | 20 | 0 | 20 | - |
| 0xfe7ce058 | 74 | 0 | 74 | - |

Blocking is concentrated in one wallet: 0x7717a7a2 holds 96% of all LIVE risk blocks.

Top 10 coins by blocked count (window + LIVE):

| coin | blocked | notional | reason mix |
|---|---|---|---|
| XYZ:INTC | 316 | 4,308 | wallet cap 316 |
| XYZ:SNDK | 315 | 4,344 | wallet cap 315 |
| XYZ:DRAM | 284 | 3,912 | no fresh price 284 |
| ANIME | 249 | 3,312 | wallet cap 249 |
| XYZ:CRCL | 187 | 2,712 | wallet cap 187 |
| XYZ:AAOI | 186 | 3,012 | no fresh price 186 |
| BTC | 181 | 2,184 | wallet cap 181 |
| ETH | 180 | 2,208 | wallet cap 73; no fresh price 2; total cap 91; total+resting 14 |
| XYZ:SKHX | 174 | 2,112 | wallet cap 173; no fresh price 1 |
| TIA | 169 | 3,336 | wallet cap 169 |

## 4. Liquidation-parity blocks (reconciliation.csv)

Field the engine records: `reconciliation.csv` column `notes`, one free-text sentence carrying **both**
sides in one string - `follower liquidation <px> is <P>% from the mark (projected); the safest leader is <Q>% away`. The engine records the follower distance and the best leader distance in that one field;
it does not record a single signed delta.

Population: `terminal_state = LIQ_PARITY_BLOCKED` - 7,079 rows / 5,798 unique intent_ids (full file).
5,645 of 7,079 notes parse under that template; 1,434 use another wording and were excluded.

Follower % distance to mark: min 1.27, p25 5.26, **median 11.11**, p75 75.46, p90 978.5, max 1,744.8.
Safest-leader % distance: min 25.0, p25 25.0, **median 25.0**, p75 1,571.9, p90 9,484.0, max 48,306,777.
In 5,645 of 5,645 parsed rows the follower is strictly closer to liquidation than the safest leader -
the gate is one-sided by construction; the leader side sits on the 25% floor for the median case.

Notional: **0% of blocked notional.** Parity is disjoint from the risk-blocked population - overlap is
0 intent_ids. In the window, parity rows = 1,851 (1,543 unique); all 1,542 of those intents present in
`order_intents.csv` are `ENTRY_ALLOWED`, with combined copy notional 18,930.66 - they were sized and
allowed, then refused at the parity gate. Parity blocks are not a subset of `SEND_BLOCKED_RISK`; they
are a second, separate population.

`send_attempts.csv` for contrast: 682 rows / 293 intents; `reject_category` only `IOC_NO_IMMEDIATE_MATCH` 29,
`MARKET_HALTED` 18, blank 635; `terminal_state` only PENDING_SEND 341, SUPERSEDED_BY_RETRY 30,
FILLED_AWAITING_COPY_POLL 228, ENTRY_LIMIT_RESTING_PRICE_MOVED 18, MISSED_ENTRY_* 40, EXIT_RECOVERY_* 36.
Overlap with the 5,872 blocked intents: **0**. Three files, three non-overlapping populations:
`order_intents.csv` (decisions), `reconciliation.csv` (terminal states incl. parity), `send_attempts.csv` (exchange rejects).

## 5. Mapping of the earlier 1,419 figure

The 1,419 figure does not reproduce as any single bucket in the current files, so it is stated as a
mapping rather than confirmed.

| population | rows | unique intents | overlap with the 5,872 window risk-blocked intents |
|---|---|---|---|
| reconciliation `ENTRY_BLOCKED_RISK` (window) | 5,876 | 5,872 | **5,872 - identical set** (4 duplicate rows) |
| reconciliation `LIQ_PARITY_BLOCKED` (window) | 1,851 | 1,543 | **0 - disjoint** |
| reconciliation `LIQ_PARITY_BLOCKED` (full file) | 7,079 | 5,798 | 0 - disjoint |
| reconciliation rows in window, all terminal states | 32,344 | - | 5,876 |

Mapping, not verdict:
- `reconciliation.csv` `ENTRY_BLOCKED_RISK` rows are the **same intents** as `order_intents.csv`
  `SEND_BLOCKED_RISK` (1:1 on 5,872 of 5,872; the 4 extra rows are duplicate appends).
- `reconciliation.csv` parity rows are **disjoint** from them.
- The 1,419 therefore maps into the parity population's window slice (1,543 unique), not into the cap
  blocks; it cannot be counted against the risk-block join.

## 6. Bottom line

- The Part A ratio (blocked ~ allowed) holds only in the full file; inside the window and LIVE scope
  blocks outnumber entry-allowed 3.31:1, which strengthens the "risk gate, not hot path" reading.
- It is one cap on one wallet: 4,051 of 5,872 blocks are the 400-per-wallet exposure cap on 0x7717a7a2.
  The 250 / 300 / 100 caps produced zero blocks. Fixing "risk" here means fixing wallet sizing, not
  cap thresholds.
- 1,685 blocks are a data problem (no fresh follower-network price), not a risk decision.
- Parity is a separate 5,798-intent population with 0 overlap, shaped by a follower on a 5-11%
  liquidation cushion against a 25% leader floor.
- `send_attempts.csv` contains neither population: 0 overlap with blocks, only IOC_NO_IMMEDIATE_MATCH /
  MARKET_HALTED, so low copy volume is not explained by send rejects.
