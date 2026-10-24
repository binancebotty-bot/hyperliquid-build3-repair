# Wallet Selection and Sizing — Decision Document

Order 6388227025 (scope 6386170191). Base `bf40a9d`. Evidence read-only from
`trading_stack/hl-build3-testnet-cert-evidence/run8/state_20261024`.

**Data basis (one basis, stated):** `append_only/send_attempts.csv`, 562 rows, of which 281 are settled —
212 ORDER_FILLED / 51 ORDER_REJECTED / 18 ORDER_RESTING (75.4% fill of settled); the other 281 are
`pending_send` with no outcome written yet. **Caveat:** earlier reports in this lane used 274/35 and 233/47,
and the file is append-only and still moving (238/48 at last read). These are different snapshots of the same
file — not averaged here, not reconciled. `reconciliation.csv` cannot supply per-coin fills; every per-coin
figure below comes from `send_attempts.csv`.

## 1. Leader selection — copyable vs uncopyable

What separates a copyable leader from an uncopyable one is **whether our order can actually meet their flow
in the book**, not their PnL. Measured fill separation by bucket (~200 attempts, out-of-band probes):

| bucket | fill rate |
|---|---|
| volume-low / mid / high | 84.8% / 71.2% / 100.0% |
| spread-tight / mid / wide | 100.0% / 74.2% / 82.4% |
| depth-thin / mid | 77.3% / 78.8% (depth-high never captured) |

So: prefer leaders whose flow is **main-dex, tight-spread, high-volume** — that is where our IOC fills land.
The one hard exclusion is **builder-dex (xyz) flow**: those books are empty or one-sided (`xyz:ORCL` and
`xyz:PLTR` both `bids []`, and a reduce-only sell could not match), so a leader concentrated there is
uncopyable on **both** entry and exit — an exit trap, not merely an entry failure. Our own record agrees:
XYZ symbols produced 25 settled attempts, 21 rejects, 3 resting, 1 fill (`XYZ:CRCL`); `XYZ:PLATINUM` alone was
12 sends / 11 rejects / 0 fills. Note volume-low (84.8%) beat volume-mid (71.2%), so buckets are not monotonic
— treat tight-spread + high-volume as the preferred pair, not a single composite score.

**Filters a selection pass can apply from data we already capture:** settled fill rate per coin
(`status` / `terminal_state`); dex of each coin (prefix `XYZ:` = builder dex → exclude); per-leader attempt,
fill and reject counts (`leader_wallet`); `reject_category` distribution; median `copy_notional`.
**Criteria that need a new capture:** per-coin spread, volume and book-depth bucket *at intent time* — today
those exist only as out-of-band probe results, not in the state dir. Add spread/volume/depth bucket fields to
the send-attempt or intent record; until then a selection pass can exclude xyz and rank by realised fill rate,
but cannot classify a new leader's markets without a fresh probe.

## 2. Sizing — proportional vs fixed, 1K vs 10K

Measured order size on fills: **mean $16.46, median $11.98, p90 $23.82** (n=212; only 12 fills above $25 and
3 above $100 — outliers against the $12 configured `fixed_notional`).

**Recommendation: keep fixed notional; do not switch to proportional.** Every fill-quality number we have was
earned at roughly $12–20 notional. Proportional sizing scales order size with leader equity, which silently
exits the only size band we have evidence for; larger orders also sit further from the touch in wide/thin
books, which is where we already fail. Fixed keeps the $250 per-order cap a meaningful hard bound rather than
a value proportional sizing would approach.

Ordered caps today (`live_config.json` → `global_controls`): `max_order_notional_usd` 250,
`max_wallet_exposure_usd` 400, `max_asset_directional_exposure_usd` 300, `max_total_live_exposure_usd` 900,
`max_daily_loss_usd` 100.

At 10K only the *exposure* caps can move, and only as a policy choice — the fill data does not support a
scaling claim. The order cap should stay at 250: at 1K it is 25% of the account (an effective concentration
stop), at 10K it is 2.5% and still ~10x our measured order size, so the fill evidence stays valid. Wallet /
total / daily-loss caps are concentration limits on the account rather than on the order; scaling them keeps
the risk ratio constant while leaving order-level behaviour untouched.

## 3. Recommended roster — PROPOSAL ONLY

**A named 10-wallet roster is not supportable from this data.** All 281 settled attempts came from 4 leaders:
`0x7717a7a2…` 145 filled / 51 rejected (every reject in the file) / 18 resting; `0xd4c1f7e8…` 65 filled /
0 rejected; `0x21ca9810…` 1 fill; `0xbee0000c…` 1 fill. The other 6 of the 10 current LIVE wallets have no
settled attempt at all. Naming 10 would mean inventing performance for 8 wallets, so the rule is given
instead:

> **Selection rule (per candidate leader):** exclude if a material share of recent flow is in `XYZ:` builder-dex
> symbols (exit trap). Require a probe of ≥20 copy attempts on main-dex symbols before LIVE; require settled
> fill rate ≥80% and rejects ≤10%. On real data `0xd4c1f7e8…` clears (100% filled, 0 rejects) and
> `0x7717a7a2…` does not (74% filled, 26% rejected). Promote further candidates from CLO to LIVE only after
> their own probe, one at a time.

**CLO/OFF — unchanged, and proposed to stay unchanged.** CLO: `0x010461c1…`, `0x31ca8395…`, `0x6ba889db…`,
`0x7019197d…`, `0x936cf4fb…`, `0xf5d81a13…`. OFF: `0x1b232b41…`, `0xaaaa…aaaa`, `0xc179e039…`.

**Caps scaled for 10K (proposal):** order 250 (unchanged), wallet 400 → **800**, per-asset 300 → **600**,
total 900 → **1800**, daily loss 100 → **200**. These are ratio-preserving multiples; nothing in the fill data
validates them. Fixed notional per wallet stays $12.

## 4. Status of the running system

**The running roster and caps are NOT changed by this document.** Everything in section 3 is a proposal
requiring a separate, explicitly ordered change; no config, roster or cap was modified in producing this
document, and the engine was not started, stopped or otherwise touched.
