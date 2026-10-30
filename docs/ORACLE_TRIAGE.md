# ORACLE TRIAGE v2 — the 58 LOST_OBLIGATION candidates

Source run: `tools/oracle/runs/after/m3_oracle_20261030T005055Z.json` (run_at 2026-10-30T00:50:55Z, build3 live commit `a1acc28`).
Cross-run comparator: `tools/oracle/runs/prefix_before/m3_oracle_20261030T004231Z.json` (55 LOST_OBLIGATION).
Previous document: `docs/ORACLE_TRIAGE.md` at `976bf18`, which triaged the throttled 22:43 run (24 rows).

Read-only review. The oracle, the tests and the Core were not modified; every artifact was opened read-only.

Run shape (58-run): 411 pair-rows — **58 LOST_OBLIGATION**, 335 UNRESOLVED, 18 OK.
Thresholds in force: `MATERIAL_USD = 5.00`, `EPS = 1e-6`, `PENDING_DELAY_MS = 120000`.

## Why v1 was invalidated

The 22:43 run was throttled — one leader (`0x7717a7a2`) failed with HTTP 429 and 261 pairs fell to UNRESOLVED, so
only 24 rows could reach LOST_OBLIGATION. Two later runs of the same oracle over the same audit inputs produce
55 and 58 rows. v1's classifications are sound **for the rows it saw**; its completeness claim ("24 rows = 19
distinct exposures") understates the real set by roughly half. This document replaces it.

## Method

1. Union of LOST_OBLIGATION rows from the 58-run and the 55-run, keyed `(wallet, coin)`: **63 pairs**.
2. **STABLE** = present in both runs (**50**). **VOLATILE** = present in only one (**8** only in the 58-run, **5**
   only in the 55-run).
3. Classification is a fixed rule ladder applied to the 58-run row, in this order (first match wins):
   - `target == 0` and `actual != 0` → ORPHAN_POSITION (UNDECIDED for `NEAR @ 0x21ca98`, see below)
   - `target_units IS NULL` → UNDECIDED
   - `actual` and `target_units` non-zero with opposite signs → SIGN_INVERSION
   - `leader_fill_count == 0` and `leader_postbaseline_net == 0` → BASELINE_ARTEFACT (nothing was ever copied; the row is a baseline/ledger artefact, not a lost fill)
   - `|actual| > |target_units|` → STALE_LEDGER (follower holds more than one copy unit, so its ledger disagrees with the account)
   - otherwise → PARTIAL_COPY
4. Remedy: RECONCILE (ledger/position disagreement the engine can settle), OPERATOR_DECISION (direction or
   ownership question a human must answer), NO_ACTION (artefact, nothing owed). **CLOSE_REMAINDER is not assigned
   in v2** — see §WHAT CHANGED.
5. Exposure is recomputed per coin, not per row (see §Distinct exposure).

**STABLE vs VOLATILE meaning.** A STABLE row is reproduced by two independent unthrottled passes of the same
oracle over the same inputs: it is a property of the account, not of the run. A VOLATILE row exists in one run
and not the other, which is the signature of a live position that opened, closed or resized between the two
snapshots — an in-flight copy, not a lost obligation. Volatile rows are listed and classified for completeness but
**must not be counted as obligations** until a third pass reproduces them.

## Counts

| | n |
|---|---|
| LOST_OBLIGATION in the 58-run | 58 |
| LOST_OBLIGATION in the 55-run | 55 |
| union of the two | 63 |
| STABLE (both runs) | **50** |
| VOLATILE (58-run only) | **8** |
| VOLATILE (55-run only) | **5** |

Per class, STABLE set (50):

| class | n | remedy mix |
|---|---|---|
| PARTIAL_COPY | 34 | RECONCILE 34 |
| BASELINE_ARTEFACT | 6 | NO_ACTION 6 |
| STALE_LEDGER | 5 | RECONCILE 5 |
| SIGN_INVERSION | 3 | OPERATOR_DECISION 3 |
| ORPHAN_POSITION | 1 | OPERATOR_DECISION 1 |
| UNDECIDED | 1 | OPERATOR_DECISION 1 |
| **total** | **50** | RECONCILE 39, OPERATOR_DECISION 5, NO_ACTION 6 |

Per class, VOLATILE set (8, informational only):

| class | n | rows |
|---|---|---|
| ORPHAN_POSITION | 2 | FARTCOIN, PUMP @ 0x92bbd8 |
| STALE_LEDGER | 2 | XMR, XPL @ 0x92bbd8 |
| PARTIAL_COPY | 2 | COMP, STX @ 0x7717a7 |
| SIGN_INVERSION | 1 | ZRO @ 0x7717a7 |
| BASELINE_ARTEFACT | 1 | DOGE @ 0xd4c1f7 |

## The 58 rows

Wallet truncated to 8 hex chars; full addresses in the source JSON. Values in coin units, unchanged from the run.
`Δ$` is the oracle's `delta_usd`, null where the oracle could not size a unit. `v1` marks rows the previous
document also carried.

| # | stability | wallet | coin | target | target_units | actual | in_flight | Δ$ | class | remedy | v1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | STABLE | 0x20ad98 | ETH | -438.1736 | -0.0051 | 0.0103 | 0 | 34.0894 | SIGN_INVERSION | OPERATOR_DECISION | - |
| 2 | STABLE | 0x21ca98 | NEAR | 0 | null | -0.5 | 0 | null | UNDECIDED | OPERATOR_DECISION | Y |
| 3 | STABLE | 0x21ca98 | VVV | 43586.88 | 8.49 | 0 | 0 | 189.3567 | PARTIAL_COPY | RECONCILE | Y |
| 4 | STABLE | 0x7717a7 | 2Z | -1333780.0 | -1162.0 | 0 | 0 | 29.4567 | PARTIAL_COPY | RECONCILE | - |
| 5 | STABLE | 0x7717a7 | AAVE | 3573.18 | 0.16 | 0.5 | 0 | 40.2390 | STALE_LEDGER | RECONCILE | - |
| 6 | STABLE | 0x7717a7 | ALT | -1159156.0 | -15038.0 | 0 | 0 | 87.2956 | PARTIAL_COPY | RECONCILE | - |
| 7 | STABLE | 0x7717a7 | ANIME | 5645098.0 | 56.0 | 0 | 0 | 0.1513 | PARTIAL_COPY | RECONCILE | - |
| 8 | STABLE | 0x7717a7 | APE | 184528.8 | 101.0 | 0 | 0 | 11.1383 | PARTIAL_COPY | RECONCILE | - |
| 9 | STABLE | 0x7717a7 | CHIP | -641956.0 | -207.0 | 0 | 0 | 8.5561 | PARTIAL_COPY | RECONCILE | - |
| 10 | VOLATILE | 0x7717a7 | COMP | 4362.32 | 0.56 | 0 | 0 | 11.6262 | PARTIAL_COPY | RECONCILE | - |
| 11 | STABLE | 0x7717a7 | DASH | -303.73 | -0.26 | 0 | 0 | 12.1642 | PARTIAL_COPY | RECONCILE | - |
| 12 | STABLE | 0x7717a7 | EIGEN | -530384.55 | -61.91 | 0 | 0 | 10.5061 | PARTIAL_COPY | RECONCILE | - |
| 13 | STABLE | 0x7717a7 | ETH | 839.629 | 0.0324 | 0.0103 | 0 | 48.9206 | PARTIAL_COPY | RECONCILE | - |
| 14 | STABLE | 0x7717a7 | FARTCOIN | 2754668.0 | 1.9 | 316.5 | 0 | 35.5813 | STALE_LEDGER | RECONCILE | - |
| 15 | STABLE | 0x7717a7 | FET | 127716.0 | 8.0 | 0 | 0 | 1.2668 | PARTIAL_COPY | RECONCILE | - |
| 16 | STABLE | 0x7717a7 | HBAR | 582688.0 | 997.0 | 0 | 0 | 68.4480 | PARTIAL_COPY | RECONCILE | - |
| 17 | STABLE | 0x7717a7 | INJ | 12409.1 | 11.5 | 0 | 0 | 81.6103 | PARTIAL_COPY | RECONCILE | - |
| 18 | STABLE | 0x7717a7 | IOTA | -378943.0 | -288.0 | 0 | 0 | 10.6589 | PARTIAL_COPY | RECONCILE | - |
| 19 | STABLE | 0x7717a7 | KLUNC | -495838.0 | -561.0 | 0 | 0 | 23.1659 | BASELINE_ARTEFACT | NO_ACTION | - |
| 20 | STABLE | 0x7717a7 | KPEPE | 59938625.0 | 3899.0 | 0 | 0 | 17.8418 | BASELINE_ARTEFACT | NO_ACTION | - |
| 21 | STABLE | 0x7717a7 | NEAR | 68500.9 | 0.1 | -0.5 | 0 | 2.4105 | SIGN_INVERSION | OPERATOR_DECISION | - |
| 22 | STABLE | 0x7717a7 | NIL | -621984.0 | -256.0 | 0 | 0 | 17.6622 | PARTIAL_COPY | RECONCILE | - |
| 23 | STABLE | 0x7717a7 | ONDO | 996024.0 | 453.0 | 0 | 0 | 167.7731 | PARTIAL_COPY | RECONCILE | - |
| 24 | STABLE | 0x7717a7 | PUMP | 31150709.0 | 20833.0 | 2904.0 | 0 | 69.9052 | PARTIAL_COPY | RECONCILE | - |
| 25 | STABLE | 0x7717a7 | PYTH | 1027066.0 | 95.0 | 0 | 0 | 5.6958 | PARTIAL_COPY | RECONCILE | - |
| 26 | STABLE | 0x7717a7 | RENDER | -102109.9 | -28.0 | 0 | 0 | 41.7998 | PARTIAL_COPY | RECONCILE | - |
| 27 | STABLE | 0x7717a7 | RUNE | -799842.9 | -134.9 | 0 | 0 | 83.5611 | PARTIAL_COPY | RECONCILE | - |
| 28 | STABLE | 0x7717a7 | SPX | 323830.0 | 6.0 | 0 | 0 | 2.2928 | PARTIAL_COPY | RECONCILE | - |
| 29 | STABLE | 0x7717a7 | STABLE | 5994995.0 | 446.0 | 0 | 0 | 11.1246 | PARTIAL_COPY | RECONCILE | - |
| 30 | VOLATILE | 0x7717a7 | STX | 662982.3 | 1.4 | 0 | 0 | 0.3819 | PARTIAL_COPY | RECONCILE | - |
| 31 | STABLE | 0x7717a7 | TAO | -201.282 | -0.051 | 0.047 | 0 | 22.4175 | SIGN_INVERSION | OPERATOR_DECISION | - |
| 32 | STABLE | 0x7717a7 | TRUMP | 47495.5 | 14.0 | 0 | 0 | 21.0693 | PARTIAL_COPY | RECONCILE | - |
| 33 | STABLE | 0x7717a7 | USELESS | 469204.0 | 74.0 | 0 | 0 | 9.2193 | PARTIAL_COPY | RECONCILE | - |
| 34 | STABLE | 0x7717a7 | VVV | 12015.46 | 1.95 | 0 | 0 | 43.4918 | PARTIAL_COPY | RECONCILE | - |
| 35 | STABLE | 0x7717a7 | XYZ:COPPER | 2766.43 | 7.0 | 0 | 0 | 45.9606 | BASELINE_ARTEFACT | NO_ACTION | - |
| 36 | STABLE | 0x7717a7 | XYZ:TSLA | 165.719 | 0.06 | 0 | 0 | 24.2160 | BASELINE_ARTEFACT | NO_ACTION | - |
| 37 | VOLATILE | 0x7717a7 | ZRO | -266601.4 | -0.3 | 7.5 | 0 | 11.3794 | SIGN_INVERSION | OPERATOR_DECISION | - |
| 38 | VOLATILE | 0x92bbd8 | FARTCOIN | 0 | null | 316.5 | 0 | null | ORPHAN_POSITION | OPERATOR_DECISION | Y |
| 39 | VOLATILE | 0x92bbd8 | PUMP | 0 | null | 2904.0 | 0 | null | ORPHAN_POSITION | OPERATOR_DECISION | Y |
| 40 | VOLATILE | 0x92bbd8 | XMR | -148.845 | -0.13 | -1.42 | -0.02 | 814.4074 | STALE_LEDGER | RECONCILE | Y |
| 41 | VOLATILE | 0x92bbd8 | XPL | -12093752.0 | -637.0 | -12245.0 | -162.0 | 869.3087 | STALE_LEDGER | RECONCILE | Y |
| 42 | STABLE | 0xbee000 | APT | 0 | null | -18.95 | 0 | null | ORPHAN_POSITION | OPERATOR_DECISION | Y |
| 43 | STABLE | 0xbee000 | JUP | -16370.0 | -45.0 | 0 | 0 | 11.0673 | PARTIAL_COPY | RECONCILE | Y |
| 44 | STABLE | 0xbee000 | NEAR | -31286.3 | -2.5 | -0.5 | 0 | 8.0351 | PARTIAL_COPY | RECONCILE | Y |
| 45 | STABLE | 0xd4c1f7 | BNB | 1361.078 | 0.122 | 1.217 | 0 | 760.4063 | STALE_LEDGER | RECONCILE | Y |
| 46 | VOLATILE | 0xd4c1f7 | DOGE | -2929956.0 | -45.0 | 0 | 0 | 3.3286 | BASELINE_ARTEFACT | NO_ACTION | - |
| 47 | STABLE | 0xd4c1f7 | ETH | 429.7891 | 0.0324 | 0.0103 | 0 | 48.9206 | PARTIAL_COPY | RECONCILE | - |
| 48 | STABLE | 0xd4c1f7 | MON | -4944924.0 | -6143.0 | -662.0 | 0 | 101.8151 | PARTIAL_COPY | RECONCILE | - |
| 49 | STABLE | 0xd4c1f7 | ONDO | 1286268.0 | 174.0 | 0 | 0 | 64.4426 | PARTIAL_COPY | RECONCILE | - |
| 50 | STABLE | 0xd4c1f7 | PONS | -1035798.0 | -64.0 | 0 | -41.0 | 5.1825 | PARTIAL_COPY | RECONCILE | Y |
| 51 | STABLE | 0xd4c1f7 | SOL | -7005.29 | -0.63 | -0.12 | 0 | 52.9916 | PARTIAL_COPY | RECONCILE | Y |
| 52 | STABLE | 0xd4c1f7 | SUI | -465276.1 | -156.9 | 0 | 0 | 133.7494 | PARTIAL_COPY | RECONCILE | - |
| 53 | STABLE | 0xd4c1f7 | WLFI | -960417.0 | -2237.0 | 0 | 0 | 114.0042 | PARTIAL_COPY | RECONCILE | Y |
| 54 | STABLE | 0xfe7ce0 | BTC | -8.93396 | -0.00014 | -0.00028 | 0 | 10.8153 | BASELINE_ARTEFACT | NO_ACTION | Y |
| 55 | STABLE | 0xfe7ce0 | CASHCAT | -2498968.0 | -113.0 | -237.0 | 0 | 10.9333 | STALE_LEDGER | RECONCILE | Y |
| 56 | STABLE | 0xfe7ce0 | HYPE | -77171.0 | -0.15 | 0 | 0 | 8.4616 | PARTIAL_COPY | RECONCILE | Y |
| 57 | STABLE | 0xfe7ce0 | KPEPE | 441493253.0 | 2457.0 | 0 | 0 | 11.2432 | BASELINE_ARTEFACT | NO_ACTION | Y |
| 58 | STABLE | 0xfe7ce0 | XPL | -11176419.0 | -1418.0 | -12245.0 | -162.0 | 811.6256 | STALE_LEDGER | RECONCILE | Y |

## Distinct exposure — method and number

Raw row count is not exposure count. Two mechanisms inflate it:

1. **The same account position is reported under several leaders.** `actual` is the whole follower account
   position for the coin, not a per-leader slice. ETH appears on 3 rows (0x20ad98, 0x7717a7, 0xd4c1f7) all
   showing `actual = 0.0103`; NEAR on 3 rows all showing `-0.5`; XPL on 2 rows both showing `-12245.0`; FARTCOIN,
   PUMP, KPEPE, ONDO, VVV on 2 rows each. Summing rows would multiply one position by the number of leaders that
   touch it.
2. **Rows with `actual = in_flight = 0`** represent nothing held; they are absent obligations, not exposures, and
   contribute $0 to an exposure figure however large `target` is.

**Method.** Group the 58 rows by `coin`; per coin take the account-level net `(actual + in_flight)` **once**, and
value it at that coin's run mark price. No row-summing, no per-leader multiplication. Verified: no coin carries
conflicting `(actual, in_flight)` across its rows in the 58-run, so the single-position assumption holds
(conflicts = 0).

| set | rows | distinct coins | coins with non-zero net position | gross |net| | signed net |
|---|---|---|---|---|
| all 58 | 58 | **48** | **16** | **$2,897.40** | **-$905.57** |
| STABLE 50 | 50 | 43 | 14 | $1,991.23 | -$21.28 |
| 55-run | 55 | 46 | 15 | $1,995.66 | -$9.32 |

So: **58 rows → 48 distinct coin exposures → 16 coins actually carrying a non-zero position**. The material
concentration is 6 coins (|exposure| ≥ $100): XPL $916.36, XMR $895.23, BNB $845.13, SUI $133.75, WLFI $114.00,
MON $101.82 — 5 of those 6 are STABLE (XPL, BNB, SUI, WLFI, MON); only XMR is volatile.

The STABLE-only gross ($1,991.23) is the defensible figure for a money statement: it excludes the two volatile
carriers — XMR (+$895.23 long) and ZRO (-$10.94 short) — whose appearance in only one run makes them
unverifiable. Signed net over STABLE is -$21.28, i.e. the stable set is near directionally balanced; the
-$905.57 on all 58 is almost entirely the volatile XMR position.

## WHAT CHANGED FROM V1

**Completeness.** v1 triaged 24 rows and claimed 19 distinct exposures. The unthrottled set is 58 rows, 50 of them
reproducible, 48 distinct coins, 16 with non-zero positions. v1 missed the entire `0x7717a7a2` leader — the one
that 429'd — which alone accounts for 34 of the 58 rows (31 stable, 3 volatile). Rows v1 never saw (40 pairs):

- `0x7717a7a2` (34): 2Z, AAVE, ALT, ANIME, APE, CHIP, COMP, DASH, EIGEN, ETH, FARTCOIN, FET, HBAR, INJ, IOTA,
  KLUNC, KPEPE, NEAR, NIL, ONDO, PUMP, PYTH, RENDER, RUNE, SPX, STABLE, STX, TAO, TRUMP, USELESS, VVV,
  XYZ:COPPER, XYZ:TSLA, ZRO
- `0x20ad98` ETH; `0xd4c1f7` DOGE, ETH, MON, ONDO, SUI.

**Rows v1 carried that are gone from the unthrottled run** (6 pairs, none of which is an outstanding obligation):
`0xbee000` PUMP and WLD, `0xd4c1f7` AVAX, BTC and WLD, `0xfe7ce0` MON. These were either throttling artefacts or
positions that closed between runs.

**Classifications v1 got wrong** (rows present in both documents):

| row | v1 said | v2 says | why v2 disagrees |
|---|---|---|---|
| 0xd4c1f7 BNB | PARTIAL_COPY | STALE_LEDGER | follower holds 1.217 against a copy unit of 0.122 — ~10 units, not short of one |
| 0xbee000 APT | PARTIAL_COPY | ORPHAN_POSITION | leader target is 0 (flat); the -18.95 held has no leader position to mirror |
| 0xbee000 JUP | STALE_LEDGER | PARTIAL_COPY | follower holds 0 against a -45 unit; nothing stale to reconcile, a copy is simply missing |
| 0xbee000 NEAR | STALE_LEDGER | PARTIAL_COPY | -0.5 held against a -2.5 unit: short of one unit, not over-held |
| 0xd4c1f7 SOL | STALE_LEDGER / CLOSE_REMAINDER | PARTIAL_COPY / RECONCILE | same reasoning as NEAR; the CLOSE_REMAINDER remedy is withdrawn |
| 0xd4c1f7 WLFI | STALE_LEDGER | PARTIAL_COPY | 0 held against a -2237 unit |
| 0xfe7ce0 HYPE | STALE_LEDGER | PARTIAL_COPY | 0 held against a -0.15 unit |
| 0xfe7ce0 CASHCAT | SIGN_INVERSION | STALE_LEDGER | both sides negative (-113 unit vs -237 held); no inversion, just over-held |
| 0xfe7ce0 BTC | PARTIAL_COPY | BASELINE_ARTEFACT | no leader fill and no post-baseline leader net — nothing was ever copied |
| 0xfe7ce0 KPEPE | PARTIAL_COPY | BASELINE_ARTEFACT | same: pre-baseline inventory, zero fill activity |

v1's own caveat that "none of the 24 is a BASELINE_ARTEFACT" was true only because the throttled run could not
reach the pre-baseline-inventory rows; the unthrottled run produces 7 of them (6 STABLE, 1 volatile).

**Structural correction.** v1 deduplicated to "19 distinct exposures" by counting distinct coins across 24 rows.
That number is right as far as it goes but stops at row-dedup; it does not separate coins with a position from
coins merely present in a row. v2 reports both: 48 distinct coins, of which only 16 carry a non-zero net position.

**The 5 pairs present only in the 55-run** (read from `prefix_before/m3_oracle_20261030T004231Z.json`, the only
artifact that carries them):

| wallet | coin | target | target_units | actual | in_flight | Δ$ |
|---|---|---|---|---|---|---|
| 0x7717a7 | FOGO | -4165171.0 | -3666.0 | 0 | 0 | 9.6746 |
| 0x7717a7 | GRAM | 830.0 | 9.0 | 0 | 0 | 10.2717 |
| 0x7717a7 | SOL | 1657.18 | 1.1 | -0.12 | 0 | 126.3859 |
| 0x7717a7 | SUI | 208001.1 | 12.9 | 0 | 0 | 10.9662 |
| 0xd4c1f7 | WLD | 17876.4 | 210.3 | 0 | 0 | 78.0844 |

All five cleared between 00:42 and 00:50 — consistent with in-flight copies that landed. 0x7717a7 SOL is the only
one carrying a position (-0.12) and the only non-trivial dollar figure. SOL and SUI are already triaged as STABLE
rows under 0xd4c1f7, so no coin is untriaged because of these five.

**Unresolved.** Whether the five are genuinely settled or will reappear cannot be established from two artifacts:
**UNRESOLVED, missing input = a third unthrottled run** after 00:50.
