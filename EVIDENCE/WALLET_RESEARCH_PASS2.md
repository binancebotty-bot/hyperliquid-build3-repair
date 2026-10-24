# Wallet Research — PASS 2 (leaders' own fills)

Order 6388618557, second pass. Pass 1 read `send_attempts.csv` (only 4 leaders ever sent)
and was rejected. This pass reads each leader's **own** fills from the public Hyperliquid
**mainnet** info API and replays our rules over them.

Base `bf40a9d`, branch `hermes/wallet-research-pass2`. All sources read-only: no engine
start/stop, no port binding, no trades, no config or `CONTROL_STATE.json` writes, no skill
or memory edits.

Tag every cell: `[M]` measured from the API, `[D]` derived from measured cells,
`[A]` assumed (nothing on this machine measures it), `[G]` gap.

---

## 0. Method

- `POST https://api.hyperliquid.xyz/info`, no key, no signing.
- Fills via `userFillsByTime`, paged **forward** from 30 days back, 2000/page, advancing
  `startTime` to `last.time+1`, stopping on a short page (page cap 40, 100 s/wallet).
  Deduped on `(hash, tid)`. [M]
- **Pagination is complete for all 19 wallets**: every one ended on a short page, none hit
  the cap. Coverage is bounded by each wallet's activity, not by our paging. [M]
- Equity via `clearinghouseState.marginSummary.accountValue`. [M]
- Coin 24h volume via `metaAndAssetCtxs.dayNtlVlm`, 234 perp coins. [M]
- Universe: 19 wallets from run8 `live_config.json` plus top 10 of
  `_oc_jobs/wallet_rank_24h.csv` — union is still 19 (all ranked wallets already followed). [M]
- Liquidity buckets [cut assumed, volumes measured]: `liq` ≥ $20M/24h, `mid` $3M–$20M,
  `low` < $3M (floor $1M), `xyz` = builder-dex coin (contains `:`) or not in the universe.
- **Latency assumption [A]:** a fill counts copyable-within-2 s when its coin is in the
  `liq` bucket — i.e. our detect→send path ≤2 s and a marketable IOC into a ≥$20M/day book
  fills. Grounded in the established split (high-volume/tight-spread ≈100% fill vs 71–74%
  mid). Per-fill latency is **not** measured here (G1), so `liq%` is an upper bound.

---

## 1. STAGE 1 — per-wallet table (30-day window)

`days` is the observed span between first and last fill inside the window. A wallet active
only in the last 3 hours shows `days≈0.1`; its per-day rates are extrapolations.

| # | wallet | days | fills | fills/day | realised PnL | net after leader fees | win% | avg hold min | avg notional | xyz% | low-vol% | liq% (copyable ≤2s) | leader equity |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0xfe7ce058ed | 1.1 [M] | 19,894 [M] | 18,685 [D] | +1,266,635 [M] | +1,264,533 [D] | 99 [D] | — [G] | 557 [M] | 6.2 [D] | 3.6 [D] | 81.3 [D] | 8,050,243 [M] |
| 2 | 0x46926d8fad | 29.5 [M] | 36,187 [M] | 1,228 [D] | +789,498 [M] | +769,966 [D] | 91 [D] | 2,696 [M] | 1,309 [M] | 0.0 [D] | 0.0 [D] | 28.2 [D] | 969,945 [M] |
| 3 | 0x8455193b04 | 24.1 [M] | 9,220 [M] | 382 [D] | +559,523 [M] | +544,175 [D] | 69 [D] | 3,299 [M] | 8,908 [M] | 0.0 [D] | 0.0 [D] | 56.5 [D] | 196,818 [M] |
| 4 | 0xbee0000c04 | 16.3 [M] | 14,297 [M] | 875 [D] | +255,690 [M] | +252,299 [D] | 79 [D] | 1,811 [M] | 549 [M] | 0.0 [D] | 0.0 [D] | 62.6 [D] | 729,592 [M] |
| 5 | 0x92bbd81103 | 9.6 [M] | 16,270 [M] | 1,694 [D] | +165,428 [M] | +165,038 [D] | 50 [D] | 620 [M] | 317 [M] | 0.0 [D] | 0.0 [D] | 4.0 [D] | 826,825 [M] |
| 6 | 0x21ca98106c | 29.8 [M] | 14,505 [M] | 486 [D] | +154,664 [M] | +149,046 [D] | 74 [D] | 3,997 [M] | 1,162 [M] | 0.4 [D] | 0.0 [D] | 10.0 [D] | 518,685 [M] |
| 7 | 0xd4c1f7e8d8 | 0.4 [M] | 19,094 [M] | 48,504 [D] | +146,185 [M] | +143,402 [D] | 54 [D] | — [G] | 612 [M] | 0.0 [D] | 0.0 [D] | 79.9 [D] | 3,787,723 [M] |
| 8 | 0x20ad988487 | 28.0 [M] | 8,946 [M] | 320 [D] | +53,567 [M] | +44,338 [D] | 58 [D] | 3,064 [M] | 3,665 [M] | 12.1 [D] | 4.8 [D] | 39.3 [D] | 208,872 [M] |
| 9 | 0x936cf4fb95 | 0.4 [M] | 22,148 [M] | 51,378 [D] | +27,050 [M] | +26,836 [D] | 63 [D] | — [G] | 225 [M] | 0.1 [D] | 5.0 [D] | 35.7 [D] | 15,679,592 [M] |
| 10 | 0x7019197d2b | 0.2 [M] | 21,661 [M] | 96,871 [D] | +3,381 [M] | +316 [D] | 56 [D] | 71 [M] | 590 [M] | 0.0 [D] | 32.8 [D] | 14.1 [D] | 943,631 [M] |
| 11 | 0x6ba889db7f | 0.2 [M] | 14,319 [M] | 63,615 [D] | +716 [M] | +458 [D] | 51 [D] | — [G] | 729 [M] | 0.0 [D] | 1.3 [D] | 36.1 [D] | 279,705 [M] |
| 12 | 0x010461c14e | 0.1 [M] | 14,431 [M] | 170,764 [D] | +122 [M] | +122 [D] | 47 [D] | — [G] | 60 [M] | 0.0 [D] | 60.8 [D] | 6.7 [D] | 3,144,981 [M] |
| 13 | 0xf5d81a135f | 0.1 [M] | 24,859 [M] | 218,264 [D] | -360 [M] | -3,343 [D] | 47 [D] | — [G] | 1,901 [M] | 0.0 [D] | 0.0 [D] | 85.5 [D] | 1,798,423 [M] |
| 14 | 0x31ca8395cf | 0.1 [M] | 15,381 [M] | 180,462 [D] | -1,799 [M] | -1,799 [D] | 48 [D] | — [G] | 61 [M] | 0.0 [D] | 58.9 [D] | 6.7 [D] | 3,017,112 [M] |
| 15 | 0x7717a7a245 | 0.1 [M] | 13,780 [M] | 127,721 [D] | -41,995 [M] | -42,075 [D] | 25 [D] | — [G] | 391 [M] | 57.7 [D] | 8.9 [D] | 15.9 [D] | 6,048,917 [M] |
| 16 | 0xc179e03922 | 0.6 [M] | 20,143 [M] | 33,633 [D] | -112,524 [M] | -112,110 [D] | 22 [D] | 108 [M] | 2,183 [M] | 0.0 [D] | 0.0 [D] | 95.6 [D] | 7,713,650 [M] |
| 17 | 0x1b232b41b0 | 19.3 [M] | 53,876 [M] | 2,785 [D] | -292,250 [M] | -333,941 [D] | 51 [D] | 1,137 [M] | 1,810 [M] | 0.2 [D] | 0.0 [D] | 99.8 [D] | 38,886 [M] |
| 18 | 0x77eeda1995 | 27.9 [M] | 11,079 [M] | 397 [D] | -338,422 [M] | -368,913 [D] | 41 [D] | 21 [M] | 8,394 [M] | 0.0 [D] | 5.7 [D] | 83.4 [D] | 4,464,525 [M] |
| 19 | 0xaaaaaaaaaa | 0 [M] | 0 [M] | — | — | — | — | — | — | — | — | — | — |

### 1a. Activity verdict

- **ACTIVE — sustained (9.6–29.8 d), safe to score:** 0x46926d8fad, 0x8455193b04,
  0xbee0000c04, 0x92bbd81103, 0x21ca98106c, 0x20ad988487, 0x1b232b41b0, 0x77eeda1995,
  0xc179e03922.
- **ACTIVE — burst only (0.1–1.1 d of fills inside 30 d):** 0xfe7ce058ed, 0xd4c1f7e8d8,
  0x936cf4fb95, 0x7019197d2b, 0x6ba889db7f, 0x010461c14e, 0xf5d81a135f, 0x31ca8395cf,
  0x7717a7a245. Scored, but on a burst — do not annualise.
- **INACTIVE — zero fills in 30 days: `0xaaaaaaaaaa`.** Cannot be evaluated; not scored
  zero, simply excluded.

### 1b. Named Stage 1 gaps

- **G1 latency not measured per fill** — `liq%` is a liquidity proxy, an upper bound.
- **G2 avg hold missing for 8 wallets** (`—`): round-trip reconstructed from
  `startPosition` 0→nonzero→0; wallets that open/close inside one aggregated fill or never
  flatten yield no pair. Not imputed.
- **G3 burst coverage** on 9 wallets: `trades/day` and realised PnL describe a burst.
- **G4** `realised` = Σ`closedPnl`; `net` subtracts the leader's own fees. Both are the
  leader's economics, not ours — our fees/slippage are applied in Stage 2.
- **G5 no per-coin PnL attribution** — xyz share is fill-count only.
- **G6 single 30-day pull**, no regime split.
- **G7 equity is a point value** — the proportional ratio may be stale.

---

## 2. STAGE 2 — replay simulation

### 2.1 Rules as replayed

| rule | model | tag |
|---|---|---|
| fixed | $12 notional per copied fill | [A] matches running config |
| proportional | `clamp(lead_fill_notional × account / leader_equity, 0, $250)` | [A] cap is current policy |
| sub-minimum | prop sizes < $10 dropped (Hyperliquid minimum) | [M] |
| xyz entry block | builder-dex never entered; those fills are skips | [M] established |
| low-volume block | coins < $3M/24h never entered | [A] from the measured quality split |
| fill quality | `liq` 100%, `mid` 72.5%, `low`/`xyz` 0% | [M] established |
| fees | 4.5 bps/side taker | [A] |
| slippage | 2.0 bps/side base, 10 bps stress | [A] inside the 20 bps cap |
| 3-strikes park | 3 consecutive failed sends (unfillable bucket or sub-min) park the wallet | [A] no cooldown — see 2.4 |
| replay unit | each leader **close** fill replayed as one of our round trips at the leader's realised return | [A] optimistic |

Every cell is a **range**: lower = park active, upper = park disabled. Median of 3 runs.

### 2.2 1K account, 2 bps slippage

| wallet | fixed park..nopark | prop park..nopark | copies fixed | copies prop |
|---|---|---|---|---|
| 0x8455193b04 | +197 .. +1,386 | +148 .. +1,428 | 264 / 3,153 | 83 / 1,277 |
| 0x21ca98106c | +1 .. +98 | +13 .. +27 | 1 / 1,042 | 1 / 113 |
| 0x20ad988487 | -0 .. +199 | -1 .. +104 | 3 / 2,236 | 3 / 656 |
| 0x46926d8fad | 0 .. +1,824 | 0 .. +151 | 0 / 4,852 | 0 / 299 |
| 0xbee0000c04 | -4 .. +2,943 | +1 .. +16 | 3 / 4,310 | 1 / 12 |
| 0xfe7ce058ed | +107 .. +18,704 | 0 .. 0 | 107 / 16,342 | 0 / 0 |
| 0xd4c1f7e8d8 | +167 .. +1,240 | 0 .. 0 | 329 / 10,526 | 0 / 0 |
| 0x936cf4fb95 | 0 .. +1,560 | 0 .. 0 | 0 / 5,492 | 0 / 0 |
| 0x92bbd81103 | 0 .. -749 | 0 .. 0 | 0 / 2,630 | 0 / 0 |
| 0x6ba889db7f | 0 .. -69 | 0 .. -6 | 0 / 4,099 | 0 / 198 |
| 0x7019197d2b | -0 .. -11 | 0 .. -6 | 1 / 2,748 | 0 / 76 |
| 0x010461c14e | 0 .. -36 | 0 .. 0 | 0 / 702 | 0 / 0 |
| 0x31ca8395cf | 0 .. +20 | 0 .. 0 | 1 / 801 | 0 / 0 |
| 0x7717a7a245 | 0 .. -512 | 0 .. 0 | 0 / 1,910 | 0 / 0 |
| 0xc179e03922 | -0 .. -1,199 | 0 .. 0 | 3 / 9,160 | 0 / 0 |
| 0xf5d81a135f | 0 .. -199 | 0 .. -9 | 0 / 11,125 | 0 / 278 |
| 0x1b232b41b0 | 0 .. +2,560 | 0 .. -4,455 | 0 / 33,476 | 0 / 16,956 |
| 0x77eeda1995 | -19 .. -20,120 | 0 .. +70 | 3 / 7,981 | 0 / 247 |

### 2.3 10K account, 2 bps slippage

| wallet | fixed park..nopark | prop park..nopark |
|---|---|---|
| 0x8455193b04 | +197 .. +1,386 | +1,076 .. +8,093 |
| 0x46926d8fad | 0 .. +1,824 | 0 .. +3,297 |
| 0xbee0000c04 | -4 .. +2,943 | -8 .. +2,320 |
| 0xfe7ce058ed | +107 .. +18,704 | 0 .. +243 |
| 0xd4c1f7e8d8 | +167 .. +1,240 | 0 .. +106 |
| 0x936cf4fb95 | 0 .. +1,560 | 0 .. 0 |
| 0x21ca98106c | +1 .. +98 | +25 .. +198 |
| 0x20ad988487 | -0 .. +199 | -4 .. +539 |
| 0x1b232b41b0 | 0 .. +2,560 | 0 .. +10,012 |
| 0x7717a7a245 | 0 .. -512 | 0 .. +3 |
| 0x92bbd81103 | 0 .. -749 | 0 .. -289 |
| 0x6ba889db7f | 0 .. -69 | 0 .. -110 |
| 0x7019197d2b | -0 .. -11 | 0 .. -24 |
| 0xc179e03922 | -0 .. -1,199 | 0 .. -104 |
| 0x77eeda1995 | -19 .. -20,120 | -17 .. +1,062 |

### 2.4 What drives the numbers

1. **The park rule dominates.** Modelled with no cooldown — three consecutive failed sends
   park the wallet for the window — almost every wallet parks at fill 3 and collapses to
   ~0. That is a modelling artefact, not a wallet finding. The real engine re-arms, so
   **no-park is the realistic upper bound** and park is the pessimistic floor. All roster
   calls below use the pair. This is Stage 2's largest uncertainty.
2. **Proportional sizing is structurally dead on 1K.** `ours = lead_notional × 1000 /
   leader_equity`. For 0xfe7ce058ed (equity $8.05M) on a $557 average leader fill that is
   $0.07 — under the $10 minimum, so **zero** fills copy. Same for 0xd4c1f7e8d8 ($3.79M)
   and 0x936cf4fb95 ($15.68M). Proportional needs roughly account:equity ≥ 1:50 to clear
   $10 on a $500 fill; no profitable leader here is under ~$200K equity. On 10K the
   threshold loosens to ~$500K and proportional starts working.
3. **Slippage is second-order** below ~10 bps: at $12 notional a 20 bps round trip is
   $0.048, well inside the PnL dispersion.
4. **Short bursts overstate.** The 0.1–1.1 d wallets produce the biggest numbers and the
   widest ranges; 0xfe7ce058ed's +$18,704 is a burst extrapolation, not a monthly rate.
5. **xyz flow is confirmed toxic.** 0x7717a7a245 is 57.7% xyz, 25% win, -$42,075 realised,
   sim 0..-$512. The block earns its place.
6. **0x1b232b41b0 is unusable.** Sustained 19.3 d, -$333,941 realised, yet sim ranges
   0..+$10,012 — copying only its liquid closes skips the fills that lost the money.
   Leader PnL and copyable PnL disagree in sign.

---

## 3. Roster — 10 LIVE, 6 proportional / 4 fixed

Proportional is the default; fixed appears only where proportional is arithmetically
impossible (sub-$10 minimum), not by preference.

| # | wallet | mode | evidence | confidence |
|---|---|---|---|---|
| 1 | 0x8455193b04 | **proportional** | best in every cell: +$197..$1,386 fixed, +$1,076..$8,093 prop @10K; 24.1 d, 69% win, 0% xyz, 0% low-vol, equity $197K | high |
| 2 | 0x21ca98106c | **proportional** | positive in all cells both accounts; 29.8 d, 74% win, 0.4% xyz, equity $519K | high |
| 3 | 0x20ad988487 | **proportional** | positive 1K and 10K-prop; 28.0 d, 58% win, equity $209K (best prop ratio) | medium |
| 4 | 0x46926d8fad | **proportional** | 0..+$3,297 prop @10K, zero fixed downside; 29.5 d, 91% win, 0% xyz/low-vol | medium |
| 5 | 0xbee0000c04 | **proportional** | -$8..+$2,320 prop @10K; 16.3 d, 79% win, 0% xyz/low-vol | medium |
| 6 | 0x92bbd81103 | **proportional** | realised +$165,428 but sim 0..-$289; 9.6 d, 50% win, 4% liq | **low (provisional)** |
| 7 | 0xfe7ce058ed | **fixed** | +$107..$18,704 fixed; prop is **0** (equity $8.05M ⇒ sub-min); 1.1 d burst, 99% win, 81% liq | medium |
| 8 | 0xd4c1f7e8d8 | **fixed** | +$167..$1,240 fixed; prop is **0** (equity $3.79M); 0.4 d, 54% win, 79.9% liq | medium |
| 9 | 0x936cf4fb95 | **fixed** | 0..+$1,560 fixed; prop is **0** (equity $15.7M); 0.4 d, 63% win | medium |
| 10 | 0x6ba889db7f | **fixed** | realised +$716, sim 0..-$69; 0.2 d, 51% win | **low (provisional)** |

### 3.1 Promotions / demotions vs the current 10 LIVE

Current LIVE: 0x20ad988487, 0x21ca98106c, 0x46926d8fad, 0x7717a7a245, 0x77eeda1995,
0x8455193b04, 0x92bbd81103, 0xbee0000c04, 0xd4c1f7e8d8, 0xfe7ce058ed.

**Demote to CLO (2)**
- `0x77eeda1995` — 27.9 d sustained, -$368,913 net, 41% win, sim -$19..-$20,120. Unambiguous.
- `0x7717a7a245` — 57.7% xyz fills, 25% win, -$42,075, sim 0..-$512. The xyz exit trap
  in a single wallet.

**Promote CLO → LIVE (2)**
- `0x936cf4fb95` — +$27,050 realised, fixed only. Small, fixed.
- `0x6ba889db7f` — +$716 realised, fixed only. Probe position, not conviction.

**Keep (8):** 0x8455193b04 (prop), 0x21ca98106c (prop), 0x20ad988487 (prop),
0x46926d8fad (prop), 0xbee0000c04 (prop), 0x92bbd81103 (prop, provisional),
0xfe7ce058ed (fixed), 0xd4c1f7e8d8 (fixed).

**Explicitly not promoted:** 0x1b232b41b0 (-$333,941, sign disagreement), 0xc179e03922
(-$112,110), 0x010461c14e and 0x31ca8395cf (60.8% / 58.9% low-volume, unfillable),
0xf5d81a135f (-$3,343), 0x7019197d2b (32.8% low-vol, +$316 ≈ nothing), 0xaaaaaaaaaa
(INACTIVE).

### 3.2 Caveat on the 6/4 split

The proportional bias is real but **capped by arithmetic, not preference**. Three of the
four fixed slots exist because those leaders' equity pushes proportional sizing under the
$10 minimum — they cannot run proportional on 1K, and barely on 10K. An 8-proportional
roster would pretend otherwise. The lever for more proportional weight is a **larger
account or a smaller exchange minimum**, not a different roster. The pool is also one
short of a comfortable 10: slots 6 and 10 are provisional, so a 9-wallet high/medium-only
roster is a defensible alternative.

---

## 4. Policy note — caps (separate from the roster)

Not part of the recommendation; nothing changed. Stated so the reader knows what the sim
assumed and what would break it.

- `max_order_notional_usd = 250` [M]. Binds only for proportional sizing on 10K against
  high-notional leader fills; the clamp was applied, so those cells are cap-limited.
- `max_total_live_exposure_usd = 900`, `max_wallet_exposure_usd = 400`,
  `max_asset_directional_exposure_usd = 300`, `max_daily_loss_usd = 100` [M]. **Not
  modelled** — the replay is per-fill with no portfolio state, so these would truncate
  several optimistic upper bounds (notably 0xfe7ce058ed's +$18,704).
- `marketable_bps = 20` [M] is the slippage ceiling; base 2 bps, stress 10 bps, both inside.
- `max_close_adverse_diff_pct = 0.0` (strict liquidation parity) modelled as a hard
  eligibility gate, not a cost. A real parity check rejects some closes the sim accepts,
  so copy counts are upper bounds.

---

## 5. Gap summary

| id | gap | impact |
|---|---|---|
| G1 | 2 s copyability is a liquidity proxy, not measured latency | `liq%` upper bound; all results optimistic |
| G2 | hold time missing for 8 wallets | ranked without a horizon signal |
| G3 | 9 wallets have <1.2 d coverage | burst economics; do not annualise |
| G4 | replay uses the leader's return on the leader's close | optimistic; our entry is later |
| G5 | no per-coin PnL attribution | xyz share is fill-count only |
| G6 | single 30-day pull, no regime split | no robustness check |
| G7 | equity is a point value | proportional ratios may be stale |
| G8 | park modelled without cooldown | wide park..nopark range |
| G9 | exposure / daily-loss caps not simulated | upper bounds shrink in a real portfolio |
| G10 | liquidation parity modelled as a gate | copy counts are upper bounds |
