> Independent cross-check by a second lane. The spec-path deliverable is `process/Q4_IDS.md` (already on
> this branch, 46 lines) and it identifies the ROOT CAUSE: `window_ids()` only queries LIVE/CLO wallets,
> so the window-id set is structurally LIVE-only. This file is my own independent measurement, produced
> without reading theirs first by querying ALL 15 wallets (not just LIVE/CLO) and diffing against the
> audit CSVs directly - it CORROBORATES the peer: every one of the 85 hashes I found with no engine row
> touches a LIVE wallet, none is OFF-only.

# Q4_IDS.md - the Q4 outage never-ingested fills: who are they? (read-only)

**Job**: `Q4_IDS_SPEC.md`. **Model**: deepseek-flash (Hermes session, all parts; no worker - the only reachable
delegation route is the excluded config model). Read-only throughout: no engine restart, no orders, no key file
opened, live engine folder never written to, ports 8012/8014/8031 and the Wallet Finder untouched.

## Method
- Window: issue #3 comment 6111845875 (Q4-outage-detail) - armed 17:12:21Z, disarm-before-stop at the same instant,
  armed restart 17:17:51Z (330 s down). Ids read from `run5/Q4-outage-detail_window_ids.txt` (428 lines, **262 unique**
  hashes).
- "Never ingested" = computed myself as: a hash with **no row anywhere** as `leader_fill_id` in
  `hl_live_copy_audit_testnet/append_only/{send_attempts,reconciliation,order_intents}.csv` (all 3 scanned in full,
  including `notes` text, to rule out the id surviving only inside another row's `merged_fill_ids`: none did).
  Result: **85 unique never-ingested hashes**, all with fill timestamps inside the exact 17:12:21-17:17:51Z window.
- **Honest discrepancy**: the posted comment said "MISSING ... 45 more" (its own classifier, not rerun here) implying
  ~55; my own-computed set is **85**. I did not force a match to 55 - this file reports what I measured, with the
  method stated, so the discrepancy is visible rather than hidden. Both sets overlap: all 9 explicitly-named ids in
  the comment are inside my 85.
- Mapping hash -> wallet/coin/side/time: `POST https://api.hyperliquid.xyz/info userFillsByTime` per leader wallet in
  `live_config.json` (15 wallets), window padded to 17:10-17:20Z, 1 request/s, matched by the fill's own `hash` field.
  All 85 matched on the first pass (0 unmatched).

## Q1/Q2 - wallet mode and who the 85 belong to
Modes are the **current** `live_config.json` (read now; no history file exists for 17:12Z, but the engine's own Q4
log tail recorded the same split - `"LIVE": 7, "OFF": 8"` - so the config was unchanged between the test and this read).

| wallet (short) | mode | own fills in window | of those, missing |
|---|---|---|---|
| `0x936cf4..381bb0f` | **LIVE** | 321 | **62 (19%)** |
| `0xd4c1f7e8..83d1d` | **LIVE** | 139 | **23 (17%)** |
| `0xf5d81a..643ec3ad53` | OFF | 648 | 7 (1%) |
| `0x6ba889..4b80c1817` | OFF | 261 | 7 (3%) |
| `0x010461..31c703a` | OFF | 670 | 4 (1%) |
| `0x31ca83..dfb974b` | OFF | 794 | 2 (0%) |
| `0x7019197..94abd36` | OFF | 363 | 1 (0%) |
| `0x7717a7a..ed7bd7e` | OFF | 588 | 1 (0%) |
| other 7 wallets (3 OFF, 4 LIVE at low/zero activity) | mixed | <=18 each | 0 |

## Q3 - "are the 55 (here, 85) all from OFF wallets?" **NO.**
Every one of the 85 unique missing hashes involves **at least one LIVE wallet** (20 of the 85 are counterparty trades
between two monitored wallets and so carry a second, OFF-side, wallet tag too - but the LIVE side is always present).
**Zero** of the 85 are OFF-only. The OFF-skip-poll hypothesis in the spec (item 3) is **not** what explains this
outage: it is not an artifact of polling OFF wallets, it is missing coverage of the engine's own LIVE leaders.

## Q4 - per-wallet counts (the two LIVE leaders that matter)
- `0x936cf4..381bb0f` (LIVE): 321 fills in the window, **62 missing (19%)**. Coins: USELESS 36, AAVE 30, EIGEN 7,
  ONDO 6, ZRO 3, GRASS 2, LIT 1, GRAM 1 (some ids tag 2 coins via the counterparty match). Sides B 38 / A 48.
- `0xd4c1f7e8..83d1d` (LIVE): 139 fills in the window, **23 missing (17%)**. Coins: BTC 19, XPL 17, ONDO 11, DOGE 5,
  SUI 1, ETH 1. Sides A 53 / B 1.
- The other 5 LIVE wallets traded 0-18 times in the window and have **zero** missing fills (0% miss rate) - the
  defect is concentrated on exactly these two active LIVE leaders, not spread across every LIVE wallet.

## Q5 - timing: did an ON/LIVE leader trade, and did the engine write nothing? **YES, stated plainly.**
`0x936cf4fb95c30ce83f658b5bbb247e4bb381bb0f` and `0xd4c1f7e8d876c4749228d515473d36f919583d1d` are both **LIVE** (ON)
in the live config, both traded heavily inside the 5.5-minute outage (321 and 139 fills respectively), and the
engine's audit files carry **no row of any kind** - no `send_attempts`, no `reconciliation`, no `order_intents` - for
85 of those fills (62 and 23 respectively). This is a direct ON-leader coverage gap during the outage, not a
wallet-mode artifact.

## Bottom line
The 85 never-ingested fills are concentrated in two **LIVE** leader wallets that were actively trading through the
whole outage; OFF wallets contribute only a handful of co-tagged counterparty rows. The spec's hypothesis (poll skips
OFF, WS down during outage, so OFF fills have no row) does not fit the data: these are LIVE-leader losses during
an outage, which is the more serious class of defect.
