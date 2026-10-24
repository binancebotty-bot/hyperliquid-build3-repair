# Wallet-400 open exposure, exitability, and price-gate coin census — 2026-10-24

Order 6389386608. Read-only: public `https://api.hyperliquid-testnet.xyz/info` (no key, no signing, no orders),
state dir `run8/state_20261024` only. Follower account `0x7AE3B08bb4E7B085C6db5D635b96Bec9715e9205`.

## Correction accepted

The `LIQ_PARITY_BLOCKED` intents ARE blocking — they terminate as `NO_SEND_LIQ_PARITY` and never reach
`send_attempts`. My earlier non-blocking phrasing was wrong. Evidence: `append_only/reconciliation.csv`, column
`status` = `LIQ_PARITY_BLOCKED`: 7,080 rows today over 5,799 distinct intent_ids, and only 1 of those intent_ids
appears in `append_only/send_attempts.csv` (712 rows). Effectively zero leak-through.

## 1. Attribution of positions to leader — RECORDED, not inferred

- File/field: `append_only/live_fills.csv`, column `leader_wallet` (per fill), plus `coin_net_after` (running net
  for that coin after the fill) and `sleeve_id` = `<leader>::<COIN>`.
- 269 fills, 4 leader wallets; 177 belong to `0x7717a7a245d9f950e586822b8c9b46863ed7bd7e`.
- Per-coin net for that leader = last `coin_net_after` in file order.
- Caveat: the account is shared by 4 leaders, so `clearinghouseState` gives one position per coin, not per leader.
  Where another leader holds the same coin the position is co-owned and not separable from these files. Only
  `SOL` is co-owned in the current book (leader net -0.12 of account net -0.23).
- Consequence: only a subset of the book is provably this leader's.

## 2. Per-coin open exposure (live)

`attr` = leader's `coin_net_after` from live_fills.csv (0.0 = not attributable to 0x7717a7a2); `bids` = bid level
count from `l2Book` (xyz coins queried with `dex:xyz`).

| coin | dex | side | size | entry | mark | notional | uPnL | lev | attr | bids | exit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ETH | perp | SHORT | -0.1275 | 2332.58 | 2343.10 | 298.75 | -1.341 | 3 | 0.0 | 20 | EXITABLE |
| MERL | perp | LONG | 2301.0 | 0.026102 | 0.027007 | 62.12 | +2.055 | 3 | 2301.0 | 20 | EXITABLE |
| xyz:MSTR | xyz | SHORT | -0.378 | 157.62 | 157.62 | 59.58 | 0.000 | 10 | 0.0 | 5 | EXITABLE |
| MOODENG | perp | LONG | 1229.0 | 0.039043 | 0.039627 | 48.69 | +0.706 | 3 | 1229.0 | 16 | EXITABLE |
| DYM | perp | LONG | 2012.1 | 0.01792 | 0.01805 | 36.30 | +0.228 | 3 | 2012.1 | 12 | EXITABLE |
| xyz:PLTR | xyz | LONG | 0.186 | 193.18 | 193.15 | 35.93 | -0.006 | 3 | 0.0 | 0 | UNEXITABLE |
| BTC | perp | LONG | 0.00042 | 81050.0 | 80964.0 | 34.00 | -0.037 | 3 | 0.00042 | 20 | EXITABLE |
| xyz:LLY | xyz | SHORT | -0.024 | 1327.9 | 1291.3 | 30.99 | +0.878 | 3 | 0.0 | 2 | EXITABLE (thin) |
| LAYER | perp | LONG | 366.0 | 0.06536 | 0.066508 | 24.33 | +0.412 | 3 | 366.0 | 17 | EXITABLE |
| ORDI | perp | LONG | 6.73 | 3.5665 | 3.5935 | 24.17 | +0.172 | 3 | 6.73 | 11 | EXITABLE |
| XPL | perp | SHORT | -326.0 | 0.073466 | 0.073801 | 24.06 | -0.111 | 3 | 0.0 | 20 | EXITABLE |
| ZETA | perp | LONG | 600.1 | 0.04006 | 0.04004 | 24.02 | -0.030 | 3 | 600.1 | 11 | EXITABLE |
| SOL | perp | SHORT | -0.23 | 100.8609 | 101.165 | 23.26 | -0.064 | 3 | -0.12 co-owned | 20 | EXITABLE |
| xyz:CRCL | xyz | SHORT | -0.147 | 86.049 | 91.761 | 13.49 | -0.840 | 3 | 0.0 | 1 | EXITABLE (1 lvl) |
| ANIME | perp | LONG | 3465.0 | 0.003463 | 0.003595 | 12.47 | +0.475 | 3 | 3465.0 | 14 | EXITABLE |
| VVV | perp | LONG | 0.51 | 23.8184 | 24.2345 | 12.36 | +0.214 | 3 | 0.51 | 18 | EXITABLE |
| AIXBT | perp | LONG | 657.0 | 0.018264 | 0.018626 | 12.23 | +0.232 | 3 | 657.0 | 18 | EXITABLE |
| FIL | perp | LONG | 13.0 | 0.92319 | 0.93559 | 12.16 | +0.157 | 3 | 13.0 | 20 | EXITABLE |
| GAS | perp | LONG | 10.3 | 1.1651 | 1.179 | 12.13 | +0.133 | 3 | 10.3 | 11 | EXITABLE |
| TIA | perp | LONG | 22.6 | 0.53297 | 0.53476 | 12.08 | +0.034 | 3 | 22.6 | 14 | EXITABLE |
| AXS | perp | LONG | 12.7 | 0.94146 | 0.95069 | 12.07 | +0.114 | 3 | 12.7 | 17 | EXITABLE |
| HYPER | perp | LONG | 187.0 | 0.064112 | 0.064409 | 12.04 | +0.050 | 3 | 187.0 | 12 | EXITABLE |
| NXPC | perp | LONG | 70.0 | 0.17102 | 0.170765 | 11.95 | -0.019 | 3 | 70.0 | 12 | EXITABLE |
| TRUMP | perp | LONG | 7.1 | 1.6693 | 1.66365 | 11.82 | -0.034 | 3 | 7.1 | 15 | EXITABLE |
| SUI | perp | SHORT | -12.5 | 0.93878 | 0.93756 | 11.72 | +0.013 | 3 | 12.9 | 20 | EXITABLE |
| xyz:ORCL | xyz | LONG | 0.058 | 128.23 | 126.14 | 7.32 | -0.121 | 3 | 0.0 | 0 | UNEXITABLE |

Totals: whole account 880.05 USD notional, 26 positions (21 perp + 5 xyz). Provably attributed to
0x7717a7a2: 409.94 USD. Unattributed: 470.11 USD.

### Cap usage

`live_config.json -> global_controls.max_wallet_exposure_usd = 400.0`.

| measure | notional | % of 400 | headroom |
|---|---|---|---|
| whole follower account | 880.05 | 220.0% | -480.05 |
| provably 0x7717a7a2 sleeve | 409.94 | 102.5% | -9.94 |

Both exceed the cap. Caveat: the engine's cap is presumably per-wallet on its own sleeve, not account-wide gross,
and `live_service_state.json` shows `budget_exceeded: false` with note cycle_timing_only. The 400 is therefore
not being enforced against the account-level 880 — a discrepancy for the controller, not resolvable read-only.

### Exitable / unexitable

UNEXITABLE (zero bid levels in `l2Book`, xyz dex): xyz:PLTR (35.93) and xyz:ORCL (7.32) — 43.25 USD, 4.9% of
account notional. Both are xyz/builder-dex. All 21 perps have 11-20 bid levels. Fragile: xyz:CRCL 1 bid level,
xyz:LLY 2 levels.

## 3. Coins behind the price-gate blocks

Source: `append_only/order_intents.csv`, `reason` = `no fresh follower-network (testnet) price to value the order`
(decision always `SEND_BLOCKED_RISK`).

Actual count in this state dir is 2,568 rows (2,568 distinct intent_ids/position_ids), not 1,685. 2,403 belong to
0x7717a7a2, 165 to 0xd4c1f7e8. 48 distinct coins; 1,855 of 2,568 rows are xyz-prefixed (72.2%; 29 of 48 coins xyz).

| # | coin | count | copy notional | xyz? |
|---|---|---|---|---|
| 1 | XYZ:DRAM | 284 | 3912.00 | YES |
| 2 | XYZ:SOXL | 254 | 3060.00 | YES |
| 3 | XYZ:AAOI | 186 | 3012.00 | YES |
| 4 | XYZ:SKHY | 180 | 2580.00 | YES |
| 5 | XYZ:BE | 163 | 2676.00 | YES |
| 6 | LINK | 153 | 1860.00 | no |
| 7 | ETHFI | 147 | 2304.00 | no |
| 8 | XYZ:BOT | 121 | 1848.00 | YES |
| 9 | XYZ:CBRS | 103 | 1260.00 | YES |
| 10 | XYZ:MRNA | 98 | 1248.00 | YES |
| 11 | GMX | 96 | 1440.00 | no |
| 12 | XYZ:EWZ | 85 | 1056.00 | YES |
| 13 | XYZ:UNITREE | 72 | 948.00 | YES |
| 14 | XYZ:SHAZ | 64 | 768.00 | YES |
| 15 | XYZ:EBAY | 59 | 744.00 | YES |

Top 15 = 2,065 rows (80.4%). 12 of 15 are xyz. xyz share of all price-gate blocks: 1,855 / 2,568 = 72.2%.
Controller's suspicion confirmed as dominant, not exclusive: 4 non-xyz coins account for ~28%.

## Reproduce

Read-only scratch scripts: `~/.hermes/cache/scratch/wallet400_probe_20261024.py`, `w400b.py`, `w400diag.py`.

## Limits

- `lev` = `leverage.value` from the exchange position object; ANIME, xyz:MSTR, xyz:PLTR, xyz:ORCL, xyz:CRCL,
  xyz:LLY are isolated, the rest cross; all 3x except xyz:MSTR at 10x.
- Cap arithmetic uses gross sum of positionValue; the engine may use net/directional per asset.
- xyz:MSTR mark equals entry in `allMids` at sample time (no mark move seen).
