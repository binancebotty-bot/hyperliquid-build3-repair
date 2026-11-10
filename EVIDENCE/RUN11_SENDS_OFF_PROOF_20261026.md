# Run 11 — sends OFF on ec6bb4a: the gate's production proof (2026-10-26)

The first production run of the master gate. Engine and UI both from `ec6bb4a`, one checkout
(`C:/tmp/v37_ec6bb4a`), audit dir `run11/state_20261026`, `send_mode` OFF, T0 = 1792978362617.

## Result in one line

**1814 order attempts were refused at the physical call. Zero orders, zero fills, zero open
orders, and the balance did not move.**

## The gate's own journal

| gate reason | rows |
|---|---|
| `MASTER_REAL_ORDERS_OFF` | 976 |

Every one of those rows is a BLOCKED_AT_PLACE_ORDER written by `_gate_refusal_row`, i.e. an order that
reached `_place_order` and was stopped before the exchange client. Under the pre-ec6bb4a code the same
intents were placed as GTC limits (1,549 of them on 2026-10-25).

## The anchor held for the whole run

leader polls: **112**
earliest poll start: **T0 +0 ms**
polls that asked for fills before T0: **0**

On the 25th the equivalent measurement reached T0 − 1,196 s and walked backwards 150 s per poll. Here
every poll started at T0 or later, because `leader_poll_start_ms` floors the read at the anchor.

## Exchange truth (read directly, not from our counters)

fills since T0 **0** · historical orders since T0 **0** · open orders **0** · spot USDC **986.95**
The counters that lied on the 25th (`leader_sends_attempted` = 0 while 1,549 orders went out) read
`0` here too - which is exactly why the run's abort condition was the
exchange, not the counter.

## The stop

Graceful sentinel: engine PID 21644 exited 4.5 s after the request, shutdown record
`clean=True reason=stop_sentinel`, UI PID 12392 stopped by verified pid, zero engines and zero listeners
afterwards. No forced stop, no row loss.

## What this run does not prove

It does not prove the gate is correct for sends ON - it proves the gate refuses when told to. The
sends-ON path is what the sends-ON run will test, with the caps and ENG-017 behaviour live.
It also does not make sending OFF cheap: ~140 refusals a minute cost reads and pushed the shared info
budget over 100% three times, which is why the pair was stopped. Skipping the missed-entry rest attempt
when `send_mode` is OFF would remove that churn at source; not implemented, pending an order.
