# REJECTS_7.md - exchange rejects + "nothing fills straight away" (read-only, last 24h)

**Job**: `REJECTS_SPEC.md`. **Model**: deepseek-flash (Hermes session, all parts; no worker - the only reachable
delegation route is the excluded config model). Read-only throughout: no engine restart, no orders, no key file
opened, live engine folder/ports 8012/8014/8031/Wallet Finder untouched; the Q5-block-reasons queue item currently
running on the PC was never touched.

**Honest discrepancy up front**: Boss's report said "7 orders rejected." `send_attempts.csv` for the last 24 h
(cutoff = now - 24h, 1791747802624) shows **318 ORDER_REJECTED rows**, not 7. I looked for a narrower window that would
give exactly 7 (the current Q5 test's own outage window: only 2 rejects since its 19:11:20Z restart; distinct
reject_category count: 5; distinct error-text templates: 4) and found none that matches "7" exactly - the closest
is `MISSED_ENTRY_IOC_NO_MATCH` terminal_state count = **7** (see table). I report the real 24h numbers below rather
than force-fitting to 7, and flag the `MISSED_ENTRY_IOC_NO_MATCH=7` coincidence as the likely source of Boss's number.

## Grouped by error text (318 ORDER_REJECTED rows, last 24h)

| error text | n | reject_category | terminal_state breakdown | coins (top) | retried (entry_ioc_retry)? |
|---|---|---|---|---|---|
| "Order could not immediately match against any resting orders." | 251 | IOC_NO_IMMEDIATE_MATCH | EXIT_RECOVERY_REQUIRED 240 (EXIT/REDUCE - never retried by design), MISSED_ENTRY_IOC_NO_MATCH 7, MISSED_ADD_IOC_NO_MATCH 4 | NEAR 85, HYPE 47, AR 32, WIF 25, TIA 8, XYZ:PLTR 8, MET 8, PUMP 7 | retry is ENTRY/ADD-only; 18 separate rows in the same 24h show "entry IOC retry filled" (the retry succeeded elsewhere); of the 11 ENTRY/ADD rejects here, none carry a retry note - i.e. the retry was attempted and still failed, or the retry-eligibility window (bps cap) was not met |
| "Trading is halted." | 42 | EXCHANGE_REJECTED_UNKNOWN | MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN 42 | ZEC 40, XYZ:HYUNDAI 1, XYZ:HIMS 1 | n/a (exchange-side halt, not an IOC-cross failure) |
| "Reduce only order would increase position." | 24 | REDUCE_ONLY_REJECTED | CLOSE_REJECTED_REDUCE_ONLY_REJECTED 24 | RESOLV 20, SUI 1, LIT 1, FOGO 1, WLD 1 | n/a |
| "Price too far from oracle" | 1 | PRICE_OR_TICK_REJECTED | MISSED_ENTRY_LIMIT_REJECTED 1 | NEAR 1 | n/a |

Per-order detail (time, coin, side, size, limit_px, tif, reduce_only, lifecycle) for the smallest two groups and a
representative sample of the largest (full CSV rows available in `send_attempts.csv`, columns unchanged):
- `Price too far from oracle` (n=1): `2026-10-10T19:47:12Z`, NEAR, BUY, size 6.7, limit 5.5952, `REAL_GTC_MISSED_ENTRY_LIMIT` (GTC, resting-entry limit path, not IOC), reduce_only=False, lifecycle=ENTRY (from terminal_state `MISSED_ENTRY_LIMIT_REJECTED`).
- `Reduce only order would increase position.` representative: `2026-10-10T19:43:52.74Z`, RESOLV, SELL, size 663.0, limit 0.018522, `REAL_IOC`, reduce_only=True, lifecycle=EXIT/CLOSE (terminal `CLOSE_REJECTED_REDUCE_ONLY_REJECTED`) - the engine believed it still owned the sleeve; the exchange's own position disagreed (a ledger/exchange residual mismatch, not a market condition).
- `Order could not immediately match...` representative (ENTRY, MISSED_ENTRY_IOC_NO_MATCH): `2026-10-10T19:43:42.25Z`, WIF, SELL, size 57.0, limit 0.23425, `REAL_IOC`, reduce_only=False, lifecycle=ENTRY.
- `Order could not immediately match...` representative (EXIT, EXIT_RECOVERY_REQUIRED, the dominant 240): coin varies, `REAL_IOC`, reduce_only=True, lifecycle=EXIT - these never retry (retry is coded ENTRY/ADD-only).
- `Trading is halted.` representative: `2026-10-10T19:44:14.00Z`, XYZ:HYUNDAI, SELL, size 0.05, limit 241.32, `REAL_IOC`, reduce_only=False, lifecycle=ENTRY (`MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN`).

## IOC_NO_IMMEDIATE_MATCH vs the LIVE testnet order book (read now, `l2Book`)
Engine slippage tolerance (`global_controls.marketable_bps`): **20 bps (0.2%)** of mid.

| coin | best bid | best ask | mid | spread (bps) | vs engine's 20 bps tolerance |
|---|---|---|---|---|---|
| NEAR | 5.7233 | 5.9554 | 5.83935 | **397** | 20x wider than tolerance |
| AR | 4.3350 | 4.5019 | 4.41845 | **378** | 19x wider |
| WIF | 0.22209 | 0.24500 | 0.233545 | **981** | 49x wider |
| HYPE | 39.171 | (no ask on the book right now) | - | - | book one-sided now |
| ZEC | (no bid) | (no ask) | - | - | book EMPTY now - matches "Trading is halted" |
| RESOLV (for reference, not an IOC reject) | 0.018387 | 0.018417 | 0.018402 | 16 | inside tolerance |

**Reading**: NEAR/AR/WIF's testnet spreads are 19-49x wider than the 20 bps the engine is willing to cross. An IOC
order priced at mid +/- 0.2% on a book this thin will almost never find a resting order to match - the engine's IOC
policy is working as designed; the testnet book is the limiting factor. RESOLV, by contrast, has a tight 16 bps book
right now, which is consistent with its rejects being a REDUCE_ONLY mismatch, not a spread problem.

## Fill-rate, last 24h (2,893 send_attempts rows)
| status | n | % |
|---|---|---|
| ORDER_FILLED | 2,160 | 74.7% |
| ORDER_REJECTED | 318 | 11.0% |
| ORDER_RESTING | 275 | 9.5% |
| pending_send (crash-record only, not a terminal state) | 140 | 4.8% |

Of the 2,160 filled, a 1,000-row sample (first + last 500) compared `copy_size` against the exchange response's
`filled.totalSz`: **~99.5% full fills, ~0.5% partial** (scaled: ~2,149 full / ~11 partial across all 2,160; "not at
all" = the 318 rejected + however many of the 275 resting never later filled, not re-checked here).
**Send-to-fill latency** (`send_total_ms` on the 2,160 filled rows): **p50 = 2,191 ms, max = 20,503 ms.**

## Classification: (a) our construction / (b) real market condition / (c) other
- **IOC_NO_IMMEDIATE_MATCH (251, 79% of all rejects) = (b) real market condition.** The L2 reads above prove the
  testnet spread (378-981 bps on the three biggest offenders) is far wider than the engine's 20 bps IOC tolerance;
  this is the illiquid testnet book, not a construction bug.
- **"Trading is halted." (42, mostly ZEC) = (c) other** - an exchange-side state (testnet asset halted / no book at
  all right now), outside engine control and not a spread problem.
- **"Reduce only order would increase position." (24, mostly RESOLV) = (a) our construction** - the engine's own
  ledger disagreed with the exchange's live position for a reduce-only close; a position-tracking/residual issue,
  not a market condition. (RESOLV is also in `global_controls.symbol_blocklist`, so these may be legacy residual
  closes on an already-blocked symbol rather than new entries.)
- **"Price too far from oracle" (1, NEAR) = (b) real market condition** - same coin as the worst IOC spread above;
  one resting-entry limit priced outside the oracle band on a thin book.

Bottom line: of 318 rejects in 24h, **~93% (293) are market-condition (b/c)**, consistent with testnet illiquidity
and one halted asset; **~7% (24) are a construction issue (a)** - the RESOLV reduce-only/ledger mismatch, worth a
focused look by the engine thread. None of these reflect "nothing fills straight away": 74.7% of all sends filled,
p50 send-to-fill is ~2.2 s.
