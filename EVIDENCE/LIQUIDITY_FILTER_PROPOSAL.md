# LIQUIDITY FILTER PROPOSAL (RW16)

Scope: a pre-trade gate that skips copy orders the book cannot absorb, so the engine stops burning
send attempts on IOC rejects. Read-only analysis: the only inputs were the append-only send-attempt
CSV (snapshot `_snap/send_attempts_snapshot.csv`) and two public `info` captures (`meta`, `l2Book`)
made by `_fetch.py` / `_book.py` in the analysis worktree. No engine, port, or database was touched.

## 1. SEPARATION TEST

Question: do pre-trade observables (24h notional volume, quoted spread, 10bps ask depth) separate
attempts that fill from attempts that reject?

Method: latest row per `attempt_id`, joined to captured `meta` volume and `l2Book` spread/depth, then
split into equal thirds per dimension.

Measured (n=200 attempts):

```
vol low     att 66 fill 56 rej  7 fillpct  84.8
vol mid     att 66 fill 47 rej 11 fillpct  71.2
vol high    att 68 fill 68 rej  0 fillpct 100.0
spread tight att 66 fill 66 rej  0 fillpct 100.0
spread mid   att 66 fill 49 rej 11 fillpct  74.2
spread wide  att 68 fill 56 rej  7 fillpct  82.4
depth thin  att 66 fill 51 rej  9 fillpct  77.3
depth mid   att 66 fill 52      fillpct  78.8
depth high  -- not captured (line truncated when the worker died)
```

**Verdict: this is not a null result. Pre-trade observables do separate.** The tightest-spread third
and the highest-volume third filled 100% of the time (0 rejects of 68), while the mid buckets sat at
71-74%. Rejects are concentrated in an identifiable, pre-send knowable region of the observable space
rather than spread evenly across coins.

The depth-high bucket was never captured. It is left blank rather than estimated. A later
re-derivation over a slightly larger joined set (n=209, `_sep.out`) did reach a deep bucket and
reported 100% fill, consistent with the other two 100% buckets - but that is a separate run and is not
part of the n=200 measurement above.

### Candidate threshold

The data supports a **spread cap** first, and a **volume floor** second:

- `spread_bps <= ~10` - every attempt in that region filled; the mid bucket (~10-20 bps) holds the
  11-reject population.
- `dayNtlVlm >= ~3000` (the vol-high third boundary) - again 0 rejects.

Both are defensible. Prefer the spread cap: spread is measured at send time and reflects the book the
order will actually hit, while 24h volume is a lagging aggregate that will not notice a book that has
just thinned.

**Caveat, stated plainly: n=200 over 35 coins is thin.** Two of the three dimensions have ~68
observations in the top bucket - enough to say "this region is quiet", not enough to say "no reject
can happen here". Set the threshold **conservatively** - a cap that skips only the clearly illiquid
tail, not one tuned to maximise the fill rate - and revisit it once the attempt count is in the many
hundreds across a much wider coin set and a full market cycle.

## 2. SEND OUTCOMES

Basis of this document: `_stats.py` over `_snap/send_attempts_snapshot.csv` (465 lines), collapsing
each `attempt_id` to its latest row - the same read that produced the per-coin table.

```
TOTALS n=233 coins=47 F=182 R=38 T=12 I=1
```

182 filled, 38 rejected, 12 resting, 1 still pending send.

Rejects by cause (38):

| cause | n |
|---|---|
| `Order could not immediately match against any` (`IOC_NO_IMMEDIATE_MATCH`) | 31 |
| `Trading is halted.` (`MARKET_HALTED`) | 7 |

The no-match population is dominated by asset `750035` (`XYZ:PLATINUM`, 11 of 31 on its own), the rest
over CHIP 5, USELESS 4, ANIME 2, NXPC 2, BIGTIME 2, HYPE 2, TIA 1, GRASS 1, ATOM 1. `Trading is
halted.` accounts for ZEC 4 and one each of `XYZ:EWY`, `XYZ:LITE`, `XYZ:MRVL`. Exactly one reject is
on a reduce-only send (`ro_reject 1`) - which is why the policy below forbids blocking closes.

**Reconciliation with the earlier 274/35 figure.** An earlier read of this same append-only CSV gave
274 attempts over 35 coins (104 filled / 26 rejected / 7 resting / 137 pending). It is a different
window of the same file, taken while a large batch was still `pending_send`; as those resolved, the
pending count collapsed and the settled counts grew. The two are not averaged, and 274/35 is not
quoted as current. The CSV has since moved on again - a re-read covering
`2026-10-24T16:24:55Z -> 2026-10-24T18:53:36Z` gives 238 attempts / 48 coins (186 filled / 39 rejected
/ 12 resting / 1 pending), i.e. +5 attempts past this snapshot, with the same two reject causes. The
snapshot-based n=233/47 above is this document's basis.

## 3. XYZ CASING

Allegation: `XYZ:PLATINUM` rejects are a symbol-naming fault, not a liquidity fault.

Measured: the main `meta` has **212 assets and zero `XYZ:*` names**. There is exactly **one** builder
dex, keyed lowercase `xyz`, holding **70 assets including `xyz:PLATINUM`**. The repo's symbol
resolution already normalises dex-key casing before constructing the exchange symbol, so the name it
sends is the name the dex expects.

**Conclusion: casing is not the cause.** A naming fault would surface as an unknown-asset or
symbol-resolve error; the exchange instead answers `Order could not immediately match against any`,
which is a book-level answer to a correctly addressed order. The `XYZ:PLATINUM` reject is a **book
condition** - no resting liquidity at the price the IOC was willing to cross.

Policy consequence: do **not** resurrect the `XYZ:` exclude-prefix. The controller has already ordered
it dropped; re-adding it would blackhole a whole dex for a book problem the liquidity gate handles
correctly and generally, and would also suppress `xyz` assets that do have books.

## 4. POLICY

The behaviour rule, as settled:

1. **Skip before send.** Evaluate the gate after symbol resolution and before the exchange call. A
   skipped attempt never touches the exchange.
2. **Record it as a decision, not an error.** `reject_category = ILLIQUID_SKIP`,
   `terminal_state = SKIPPED_ILLIQUID`. These must not increment reject counters, must not raise
   alerts, and must not be classified as failures in latency/health reporting - the gate working is a
   success. Every skip is still written to the append-only CSV with the observable values that caused
   it, so the threshold can be audited and re-tuned from the log alone.
3. **Park the coin, not the engine.** After **3 consecutive** qualifying rejects on the same coin,
   park that coin for **30 minutes**, then re-evaluate against a fresh book. Parking is per-coin and
   expires; it is never a global stop.
4. **Never block a close, reduction, or EXIT.** The gate applies to entries only. A held position's
   close/reduce/EXIT bypasses the gate unconditionally, even on a parked coin and even on a coin whose
   book is empty. One reduce-only reject already exists in the data; blocking exits to protect a fill
   metric would trade a cosmetic number for real position risk.

## 5. WHAT WOULD RAISE FILL QUALITY NEXT

**Testable from data already on disk** (no new capture):

- Exact threshold sweep - re-run the thirding at finer granularity over spread and volume and pick the
  boundary from the marginal reject curve rather than from the coarse bucket edges used here.
- Per-coin persistence - do the same coins reject repeatedly (CHIP, USELESS, `XYZ:PLATINUM`) or does
  the population churn? This decides whether parking keys on coin or on (coin, side, size).
- Size sensitivity - join `copy_notional` to outcome. The mid buckets may fail on size relative to
  book depth rather than on coin quality; if so the gate should scale with notional rather than be a
  flat coin blacklist.
- Latency vs outcome - filled median 2331 ms / p90 5656 ms versus rejected median 2005 ms / p90
  7173 ms over the n=233 set; the p90 gap is worth one look to see whether slow sends arrive into a
  book that has already moved.
- `MARKET_HALTED` separation - 7 rejects, 4 of them ZEC. Halt state is a distinct cause and belongs
  to a halt check, not to the liquidity threshold.

**Needing a new capture:**

- **Depth-high bucket** - never captured in the n=200 run, so depth is the one dimension currently
  unvalidated at the top end. One re-run fixes it.
- **Live book sampling at send time.** The present analysis joins attempts to a snapshot book. The
  gate is evaluated against the live book, so the honest measure of gate quality is book state in the
  tens of milliseconds before send. Requires capturing book state per attempt at send.
- **Book depth at the actual limit price**, not 10bps aggregate depth - an IOC crosses at a price, and
  aggregate depth can look fine while the specific level is empty.
- **Post-skip counterfactual** - what skipped attempts would have done. Only obtainable by running
  the gate in shadow (log the skip decision, still send) before enforcing it.
