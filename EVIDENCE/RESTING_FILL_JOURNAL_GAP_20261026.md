# Resting-fill journal gap — the 10 cloids, with the exchange's own outcome

**Date:** 2026-10-26 · **Run:** `run13/state_20261026` (build `2c630b6`) · **Network:** testnet
**Recorded by:** Hermes, from the exchange. Not inferred, not from our logs.

## Why this file exists

The all-coin join (comment `6410992345`) found **10 orders that filled on the exchange while our
`send_attempts.csv` still showed them as `ORDER_RESTING` (8) or only `pending_send` (2)**. The position
ledger was nonetheless exact — 0 drift across 243 coins against `clearinghouseState` — because the ledger is
fed by the WS/reconciler path, not by these journal rows. This file records the exchange's own verdict for
each of the 10 so the audit trail has it now, without waiting for the sweep.

Source for every row: the exchange's `orderStatus` by cloid, plus `userFillsByTime` for the fills. Both
queries are read-only and were made after the fact; nothing was placed, cancelled or modified.

## The 10, verbatim from the exchange

| coin | side | origSz | exchange status | status at (UTC) | our journal's last row | journal row at (UTC) | oid |
|---|---|---|---|---|---|---|---|
| REZ | B | 2617.0 | **filled** | 05:51:52 | `ORDER_RESTING` | 05:51:28 | 63706149321 |
| COMP | B | 1.14 | **filled** | 05:54:04 | `ORDER_RESTING` | 05:50:21 | 63706087499 |
| GRIFFAIN | B | 858.0 | **filled** | 05:54:26 | `ORDER_RESTING` | 05:50:19 | 63706084732 |
| HYPE | B | 0.16 | **filled** | 06:00:15 | `ORDER_RESTING` | 05:51:59 | 63706175741 |
| HYPE | B | 0.18 | **filled** | 06:04:28 | `ORDER_RESTING` | 06:04:28 | 63706869163 |
| NIL | A | 124.0 | **filled** | 06:31:22 | `ORDER_RESTING` | 06:26:47 | 63708162451 |
| NIL | A | 132.0 | **filled** | 06:40:13 | `ORDER_RESTING` | 06:37:39 | 63708800066 |
| **USUAL** | **B** | **1094.0** | **filled** | **07:07:35** | **`pending_send` only** | 07:07:34 | 63710546331 |
| **ZK** | **B** | **973.0** | **filled** | **07:37:37** | **`pending_send` only** | 07:37:21 | 63712315667 |
| REZ | B | 2475.0 | **filled** | 07:47:44 | `ORDER_RESTING` | 07:46:36 | 63712886697 |

**All 10 are `filled`.** None was cancelled, none was rejected, none partially filled and abandoned.

## What the two closes tell us about the mechanism

The two that never got past `pending_send` are the informative ones:

* **USUAL** — journal row written **07:07:34**, the exchange reports the order filled at **07:07:35**: one
  second later. The engine wrote the write-ahead row, the order went out and filled, and the result row
  never landed.
* **ZK** — journal row **07:37:21**, exchange fill at **07:37:37**: sixteen seconds later, consistent with a
  resting limit that filled shortly after placement.

So this is **not** "the order was never sent". It is "the order was sent and filled, and the journal never
recorded the outcome". That distinction is exactly why a sweep may only write journal rows from the
exchange's data and must never place, cancel or infer: the trades are already done.

## What this file does NOT claim

* It does not claim the engine lost money or a position — the ledger is exact (0 drift, 243 coins).
* It does not name the write path that should have advanced the row; that is the root-cause step, and it
  goes in the comment that follows with file:line.
* No key material, no secrets, no account credentials appear in this file. The account address is public
  chain data and the cloids/oids are exchange identifiers.

## Reproduce

    # order status by cloid (read-only)
    POST /info {"type":"orderStatus","user":"0x7AE3…9205","oid":"<cloid>"}
    # -> orderStatus.order.status == "filled" | "canceled" | "open"
    # fills for the window (read-only)
    POST /info {"type":"userFillsByTime","user":"0x7AE3…9205","startTime":1792993800000,"aggregateByTime":false}
