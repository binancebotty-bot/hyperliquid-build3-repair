# ORACLE TRIAGE — the 24 LOST_OBLIGATION candidates

Source run: `tools/oracle/runs/m3_oracle_20261029T224357Z.json` (run_at 2026-10-29T22:48:15Z, engine commit `a1acc28`).
Read-only review. Nothing in the oracle, the tests or the Core was modified.

Run shape: 411 pair-rows — **24 LOST_OBLIGATION**, 371 UNRESOLVED, 15 OK, 1 PENDING.
Thresholds in force (`m3_oracle.py`): `MATERIAL_USD = 5.00`, `EPS = 1e-6`, `PENDING_DELAY_MS = 120000`.

## What the oracle actually compares

For each (leader wallet, coin) pair it takes the **live mainnet leader position** as the target, sizes one
copy unit from the follower's **last own fill size on that pair** (`u = |fill_size|` of the most recent
`live_fills` row), and asserts `target_units = sign(target) * u` against `actual + in_flight` on the testnet
follower account. `delta = target_units - actual - in_flight`, `delta_usd = |delta| * price`.

Two consequences that shape this triage:

1. **`delta` is a single-copy-unit residual, not the leader/follower quantity gap.** Fixed-notional copying
   asserts direction and open/closed only, so a follower holding 1 unit where the leader holds 1,000,000 is
   not a quantity failure. It is `quantity_short_of_one_unit` only when it holds materially less than its own
   last copy size.
2. **A `leader flat on live mainnet position` target of 0 makes `target_units` NULL** (no unit can be sized
   for a flat leader), so `delta`/`delta_usd` are NULL too. Those rows carry no dollar figure from the
   oracle; §5 computes `actual * price` for them and says so.

**The `contradictory leader direction` rows are all UNRESOLVED, not LOST_OBLIGATION.**
`meta.unresolved_causes` holds 40 such entries (40 rows), every one labelled UNRESOLVED by construction:
`m3_oracle.py:183-185` appends the cause to `miss` before any labelling, and `miss` forces UNRESOLVED at
line 222. So **none of the 24 is a BASELINE_ARTEFACT**; the class appears below with a count of 0 rather
than being papered over. They are excluded correctly and must be triaged separately after a baseline re-take.

## Per-class counts (24)

| class | n | rows |
|---|---|---|
| SIGN_INVERSION | 2 | PUMP @ 0xbee0, CASHCAT @ 0xfe7c |
| ORPHAN_POSITION | 2 | FARTCOIN, PUMP @ 0x92bb |
| PARTIAL_COPY | 9 | VVV, XMR, APT, BNB, BTC@0xd4c1, WLD@0xd4c1, BTC@0xfe7c, KPEPE, MON |
| BASELINE_ARTEFACT | 0 | (40 such rows exist, all UNRESOLVED — see above) |
| STALE_LEDGER | 9 | XPL@0x92bb, JUP, NEAR@0xbee0, AVAX, PONS, SOL, WLFI, HYPE, XPL@0xfe7c |
| UNDECIDED | 2 | NEAR@0x21ca, WLD@0xbee0 |
| **total** | **24** | |

Remedy counts: **RECONCILE 17, CLOSE_REMAINDER 1, OPERATOR_DECISION 6, NO_ACTION 0.**

## The 24 rows

Wallet truncated to 8 hex chars; full addresses in the source JSON. Values in coin units, unchanged from the
run. `Δ$` is the oracle's `delta_usd`, rounded to cents for display (exact values in the JSON).

| # | wallet | coin | target | target_units | actual | in_flight | delta | Δ$ | target_source | class | remedy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0x21ca98 | NEAR | 0 | null | -0.5 | 0 | null | null | leader flat on live mainnet position | UNDECIDED | OPERATOR_DECISION |
| 2 | 0x21ca98 | VVV | 43586.88 | 8.49 | 0 | 0 | -8.49 | 194.30 | live mainnet leader position; post-baseline net 624.92 same sign (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 3 | 0x92bbd8 | FARTCOIN | 0 | null | 100.7 | 0 | null | null | leader flat on live mainnet position | ORPHAN_POSITION | OPERATOR_DECISION |
| 4 | 0x92bbd8 | PUMP | 0 | null | 2904.0 | 0 | null | null | leader flat on live mainnet position | ORPHAN_POSITION | OPERATOR_DECISION |
| 5 | 0x92bbd8 | XMR | -147.521 | -0.13 | -1.4 | -0.02 | -1.29 | 791.23 | live mainnet leader position == post-baseline leader net | PARTIAL_COPY | RECONCILE |
| 6 | 0x92bbd8 | XPL | -2349367 | -637.0 | -9448.0 | -162.0 | -8973.0 | 656.66 | live mainnet leader position; post-baseline net -910505.0 same sign (pre-baseline inventory) | STALE_LEDGER | RECONCILE |
| 7 | 0xbee000 | APT | -1322.08 | -18.21 | -167.22 | 0 | -149.01 | 93.07 | live mainnet leader position == post-baseline leader net | PARTIAL_COPY | RECONCILE |
| 8 | 0xbee000 | JUP | -20856 | -45.0 | 0 | 0 | 45.0 | 11.42 | live mainnet leader position == post-baseline leader net | STALE_LEDGER | RECONCILE |
| 9 | 0xbee000 | NEAR | -47934.2 | -2.5 | -0.5 | 0 | 2.0 | 8.26 | live mainnet leader position == post-baseline leader net | STALE_LEDGER | RECONCILE |
| 10 | 0xbee000 | PUMP | -5617946 | -2618.0 | +2904.0 | 0 | 5522.0 | 22.80 | live mainnet leader position; post-baseline net -1135155.0 same sign (pre-baseline inventory) | SIGN_INVERSION | OPERATOR_DECISION |
| 11 | 0xbee000 | WLD | 6896.5 | 28.2 | 30.9 | 31.2 | 33.9 | 13.21 | live mainnet leader position == post-baseline leader net | UNDECIDED | OPERATOR_DECISION |
| 12 | 0xd4c1f7 | AVAX | -2816.99 | -13.11 | 0 | 0 | 13.11 | 109.51 | live mainnet leader position; post-baseline net -603.43 same sign (pre-baseline inventory) | STALE_LEDGER | RECONCILE |
| 13 | 0xd4c1f7 | BNB | 1537.048 | 0.122 | 1.182 | 0.035 | 1.095 | 771.16 | live mainnet leader position; post-baseline net 2368.466 same sign (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 14 | 0xd4c1f7 | BTC | -114.09146 | -0.00254 | -0.00028 | 0 | 0.00226 | 177.69 | live mainnet leader position; post-baseline net -0.92110 same sign (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 15 | 0xd4c1f7 | PONS | -880705 | -64.0 | 0 | -41.0 | 23.0 | 5.46 | live mainnet leader position; post-baseline net -96918.0 same sign (pre-baseline inventory) | STALE_LEDGER | RECONCILE |
| 16 | 0xd4c1f7 | SOL | -6447.2 | -0.63 | -0.12 | 0 | 0.51 | 52.89 | live mainnet leader position; post-baseline net -921.95 same sign (pre-baseline inventory) | STALE_LEDGER | CLOSE_REMAINDER |
| 17 | 0xd4c1f7 | WLD | 17876.4 | 210.3 | 30.9 | 31.2 | -148.2 | 57.74 | live mainnet leader position; post-baseline net 56026.5 same sign (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 18 | 0xd4c1f7 | WLFI | -960417 | -2237.0 | 0 | 0 | 2237.0 | 113.82 | live mainnet leader position; post-baseline net -223499.0 same sign (pre-baseline inventory) | STALE_LEDGER | RECONCILE |
| 19 | 0xfe7ce0 | BTC | -8.93396 | -0.00014 | -0.00028 | 0 | -0.00014 | 11.01 | live mainnet leader position, no post-baseline fill (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 20 | 0xfe7ce0 | CASHCAT | -2498968 | -113.0 | -237.0 | 0 | -124.0 | 11.51 | live mainnet leader position; post-baseline net -35763.0 same sign (pre-baseline inventory) | SIGN_INVERSION | OPERATOR_DECISION |
| 21 | 0xfe7ce0 | HYPE | -68573.63 | -0.15 | 0 | 0 | 0.15 | 8.01 | live mainnet leader position; post-baseline net -57226.45 same sign (pre-baseline inventory) | STALE_LEDGER | RECONCILE |
| 22 | 0xfe7ce0 | KPEPE | 542271283 | 2457.0 | 10641.0 | 0 | 8184.0 | 36.85 | live mainnet leader position, no post-baseline fill (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 23 | 0xfe7ce0 | MON | -1190364 | -542.0 | -7460.0 | 0 | -6918.0 | 134.65 | live mainnet leader position, no post-baseline fill (pre-baseline inventory) | PARTIAL_COPY | RECONCILE |
| 24 | 0xfe7ce0 | XPL | -3375548 | -1418.0 | -9448.0 | -162.0 | -8192.0 | 599.51 | live mainnet leader position; post-baseline net -3159871.0 same sign (pre-baseline inventory) | STALE_LEDGER | RECONCILE |

Five coins appear twice (NEAR, PUMP, XPL, WLD, BTC) from two leaders each; `actual` is the whole follower
account position and is identical on both rows. The 24 rows are therefore **19 distinct coin exposures**, and
any money figure must be de-duplicated by coin (§5).

## Classification rationale

**SIGN_INVERSION (2) — PUMP @ 0xbee000 and CASHCAT @ 0xfe7ce0.** CASHCAT is the inversion oracle v1 documented end to end: leader `0x010461c1` went **long +144,387 from flat** while the follower's sleeve is **-113** — a SELL 113 at 2026-10-29T15:17:57Z opened a short against a long signal, then the wallet was set OFF and nothing closed it (5.28 h stale at the v1 capture). In this run the target for CASHCAT comes from a different, legitimately short leader (`0xfe7c`, live -2,498,968), so the exchange view alone cannot see the error; the class is still SIGN_INVERSION because the originating fill went the wrong way. Remedy **OPERATOR_DECISION**.

**PUMP @ 0xbee000.** Leader live `-5,617,946` short; follower holds `+2,904` long, while
the ledger's PUMP sleeve for that wallet is `-81,945` (short). A long 2,904 cannot come from that leader's
direction; it is the exact size another sleeve (0x46926d) holds. Window dressing / mis-mapped fill, not a
partially-completed copy. Remedy **OPERATOR_DECISION**: only a human can say whether that lot was manual or a
mapping error, and closing it is a bet either way while the same size sits in a non-participating wallet.

**ORPHAN_POSITION (2) — FARTCOIN 100.7 and PUMP 2,904 @ 0x92bbd8.** On both, the leader's live position is
absent from all 87 enumerated DEXes, so the target is a hard 0; the follower nevertheless holds a material lot
(12.06 USD / 11.99 USD at the oracle's price) and the ledger records the sleeves at 0.0. There is no leader
fill origin inside the capture — these are positions the engine never opened. Remedy
**OPERATOR_DECISION**: the engine cannot close what it does not own, and attributing them to a stray manual
trade versus a lost ledger row needs a human.

**PARTIAL_COPY (9) — VVV, XMR, APT, BNB, BTC@0xd4c1, WLD@0xd4c1, BTC@0xfe7c, KPEPE, MON.** In each, the
follower holds a materially different amount from its own one-copy unit (VVV 0 of 8.49; XMR -1.4 vs -0.13;
APT -167.22 vs -18.21; BNB 1.182 vs 0.122; BTC -0.00028 vs -0.00254; WLD 30.9 vs 210.3; BTC@0xfe7c -0.00028
vs -0.00014; KPEPE 10,641 vs 2,457; MON -7,460 vs -542) while the leader's live position corroborates the
direction. That is the signature of a partial fill or a skipped copy unit, not a sign error. Remedy
**RECONCILE** — only a fill-level pass over `live_fills`/`send_attempts` per intent can separate a partial
fill from a refused copy.

**STALE_LEDGER (10).** The ledger's account net disagrees with the exchange's live position while the leader
is active in the same direction. Three of the four oracle-v1 candidates land here — **JUP**, **SOL**,
**CASHCAT** — and are the useful cross-check; the fourth, **APT**, is PARTIAL_COPY above. Ledger figures are
from v1's capture and exchange figures from this run, so these are cross-time comparisons, not a simultaneous
reconciliation: **JUP** ledger -88 vs exchange **0** (gap 88, 22.34 USD), **SOL** ledger **0** vs exchange
**-0.12** (12.44 USD), **CASHCAT** ledger -113 vs exchange **-237** (gap -124, 11.51 USD), **APT** ledger
-72.74 vs exchange **-167.22** (gap -94.48, 59.01 USD). Same shape at larger size: **XPL** (ledger -1,735 vs exchange
-9,448, 564.45 USD), **MON** (ledger -662 vs exchange -7,460, 132.32 USD), **KPEPE** (-17,191 vs 10,641,
125.33 USD), plus smaller gaps on NEAR, WLD, BNB, HYPE, XMR. On 11 of the 19 coins **the ledger is not a
record of follower reality**, which is exactly why oracle v1 (ledger-based) found 4 and this run (exchange-based)
found 24. Remedy **RECONCILE** for nine of them, including **JUP**: the ledger's -88 is gone from the exchange and a fill-level account is what is needed to say where those 88 units went — closing a remainder is not the right action when the remainder no longer exists. The exception is **SOL**, the cleanest **CLOSE_REMAINDER**: exchange short 0.12
while the ledger says flat, no sleeve owns it, `engine_can_close=false` — the size and owner are known and a
close is the right action once the engine is permitted to. If that permission is not on the table, treat SOL
as OPERATOR_DECISION.

**UNDECIDED (2).** *NEAR @ 0x21ca98*: leader flat, follower -0.5, but the same -0.5 is claimed by 0xbee000's
NEAR row, and the ledger splits the -10.5 account lot as -10.0 to 0xbee000 and -0.4 to 0xd4c1 — the capture
cannot attribute it per sleeve. *WLD @ 0xbee000*: the oracle's own copy unit (28.2) is smaller than both the
position (30.9) and the in-flight order (31.2) while the ledger says 0.0 — the size arithmetic is internally
inconsistent, so the class cannot be read off the numbers. Missing input for both: **per-sleeve position
attribution from `reconciliation.csv`**, which the oracle deliberately does not use. Remedy
**OPERATOR_DECISION**.

## THE 429 PROBLEM

**Quantified.** Of 371 UNRESOLVED rows, **261 (70.4%)** carry the single cause
`leader fills unreadable for 0x7717a7a2: HTTP 429` — **63.5% of all 411 rows**. Fourteen leader wallets were queried: twelve returned
fills over 1–17 pages, one (`0x0000000000000000000000000000000000000001`) returned zero fills with no error, and
exactly one returned `pages: 0, fills: 0` on the 429 — so seven in ten of the undecided rows trace to a single
unread wallet — `meta.leader_fill_wallets` records a non-null error on that one
wallet only (`0x7717a7a245d9f950e586822b8c9b46863ed7bd7e`), so the limit is not diffuse: one endpoint-heavy
leader is fetched page by page inside the loop (`m3_oracle.py:100-106`) with no pacing, then positions are read
per leader. The failure is total for that wallet — `lf` falls back to `[]` at line 106, so its post-baseline net
is silently 0 on every pair and the `miss` gate pushes the row to UNRESOLVED before any target forms. The
oracle does the right thing with a bad read (it refuses to label), but 261 rows end with no verdict.

**Confidence in the 24 — a floor, not a ceiling, and not a clean one.**

1. The 24 are drawn from **five of the fourteen** queried leaders; `0x7717a7a2` contributes **no** verified
   LOST_OBLIGATION row because none
   of its rows got far enough to be labelled. Its pairs are the largest block of unknown outcome in the run,
   and `live_fills.csv` shows that wallet carrying real sleeves, so there is no reason to believe its share of
   lost obligations is zero. **24 is a lower bound on the true count.**
2. It is not a clean lower bound either: the money in §5 is computed from the follower account's `actual`, which
   is wallet-agnostic, so exposure from a pair that would have been flagged under `0x7717a7a2` may already be
   inside the 19-coin totals. The exposure number is closer to complete than the count is. Read "24" as "24
   proven, at least N more unproven, with at least some of those N already visible in the exposure totals".

**The two remedies (described, not implemented).**

- **Paced retry with backoff.** `leader_fills()` is called once per leader and any exception is swallowed into
  `lmeta[w]['error']`. Wrap the per-page request in a retry that honours `Retry-After` when present, otherwise
  exponential backoff from ~0.5 s to a cap (say 30 s) with jitter, bounded to a few attempts, and slow the loop
  *between* leaders instead of firing five leaders' page sequences back to back. A retry-exhausted leader must
  keep its UNRESOLVED label (already correct), but `error` should also record attempt count and last status code
  so the report distinguishes "rate limited hard" from "gone". Only a run with a zero 429 count should have its
  LOST_OBLIGATION count quoted without a floor qualifier.
- **Cached / persisted fill history.** The oracle re-fetches each leader's whole post-baseline fill history on
  every run. Persist per-leader pages to a dated file keyed by `(wallet, since_ms, cursor)` and read from disk
  when the same window is requested again; appending only the new tail turns O(pages) rate-limit exposure into
  O(1). It also makes the run reproducible — the fills this artifact used are already gone.

Neither is in scope here; both are what a v2 must do before its numbers can be quoted as a count.

## WHAT THE 24 MEAN IN MONEY

Mark-to-last-trade on the testnet follower account, using the oracle's `price` column — which is
`price_map(testnet,'xyz')` falling back to the follower's last fill price, so for HYPE, MON, KPEPE and others it
is a fill price, not a live mark. These are **not** realised losses; they are notional currently in the wrong
place.

- **Sum of the oracle's `delta_usd` across all 24 rows: 3,880.75 USD.** Distrust this first: it double-counts
  the five duplicated coins and measures each row against one copy unit, so XMR alone contributes 791.23 USD
  for a 0.13-unit copy-unit miss.
- **De-duplicated by coin (19 exposures), the follower's actual notional is 2,774.73 USD** (3,514.26 USD raw,
  with duplicate rows). That is the size of the book sitting where it should not be.
- **Exchange-vs-ledger gap — cannot be stated as one number from these artifacts, and the earlier draft's
  3,022.28 USD should not be quoted.** The ledger side of that comparison is *not* in the oracle run; the only
  ledger snapshot on disk is oracle v1's `oracle_v1_account_vs_ledger.json`, captured **before** this run. Joined
  across time it gives a spread of roughly 1,384 USD where the exchange holds more than the ledger records and
  1,660 USD where the ledger overstates (XMR and BNB alone account for most of the second figure through price
  movement between the two captures). Those two numbers are **not** a reconciliation and neither is a loss: the
  capture times differ, so coin quantity and mark price both moved. What is safe to say is directional and
  qualitative — on the v1 snapshot the exchange held more than any sleeve accounted for on **XPL, MON, APT,
  CASHCAT, BNB, SOL, KPEPE and both PUMP entries**, and the ledger overstated only on **NEAR** (41.30 USD) and
  **JUP** (22.34 USD, a ledger-only short the exchange no longer holds at all). Treat the material risk as
  undisclosed exposure, not phantom exposure, and get a same-timestamp ledger read before quoting a dollar gap.
- **Shortfall-only subset** — rows where the follower holds the *same sign* as the leader (or zero) but less
  than one copy unit: **739.09 USD** of `delta_usd` across **10 rows** — VVV 194.30, BTC@0xd4c1 177.69, WLFI
  113.82, AVAX 109.51, WLD@0xd4c1 57.74, SOL 52.89, JUP 11.42, NEAR@0xbee0 8.26, HYPE 8.01, PONS 5.46. This is
  the "copies that should exist and don't" number. Its complement is **3,118.86 USD across 10 rows holding
  *more* than one copy unit** (XMR, XPL@0x92bb, BNB, APT, WLD@0xbee0, BTC@0xfe7c, CASHCAT, KPEPE, MON,
  XPL@0xfe7c) — over-exposure, not shortfall, and not the same set as PARTIAL_COPY. One row disagrees in sign
  (PUMP @ 0xbee0, +2,904 long against a short target, 22.80 USD). The three groups reconcile to the full
  `delta_usd` total: 739.09 + 3,118.86 + 22.80 = **3,880.75 USD**.
- **Three rows carry no oracle dollar figure** (target 0 → `target_units` NULL → `delta_usd` NULL): NEAR@0x21ca
  2.07 USD, FARTCOIN 12.06 USD, PUMP@0x92bb 11.99 USD, computed here from `actual * price`.

**Stated plainly, the data cannot tell you:**

- The value of the 261 unread `0x7717a7a2` rows — outside every total above.
- Realised PnL versus open exposure: there is no entry price per sleeve, so "3,022 USD of gap" is not
  "3,022 USD lost".
- The largest `delta_usd` rows are not the largest exposures: BNB's 771.16 USD is mostly price effect on 1.182
  coins at 704 USD, with a follower book of 832 USD. Use the coin-level gap column, not the ranked `delta_usd`.
- HYPE, PONS, WLFI, AVAX and both PUMP rows have account-level ledger 0 and the exposure sits in-flight or in a
  sleeve the ledger no longer tracks; no number here recovers it without the per-sleeve attribution named under
  UNDECIDED.
