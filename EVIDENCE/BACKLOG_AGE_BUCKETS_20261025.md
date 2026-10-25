# Backlog age at the 2026-10-25 replay

Answers the backlog-age half of the 6404562872 ask. Method: for every send attempt in run9's
`append_only/send_attempts.csv`, age = `created_at_ms - leader_fill_timestamp_ms`, i.e. how old the
leader fill already was when the engine tried to act on it. Read-only; no engine was running.

## The buckets (221 attempts)

| leader-fill age at attempt | attempts | what happened |
|---|---|---|
| < 1 s | 0 | — |
| 1–5 s | 9 | 6 still queued, 1 rejected, 1 resting |
| 5–30 s | 31 | 13 FILLED, 3 rejected, 15 still queued |
| 30 s – 2 min | 17 | 1 FILLED, 16 still queued |
| 2–10 min | 164 | all still queued (pending_send) |
| 10–60 min | 0 | — |
| > 60 min | 0 | — |

Quantiles: **p50 262 s, p90 425 s, p99 472 s, max 486 s** (about 8 minutes).

## Attempts that actually reached the exchange

| age band | reached the exchange |
|---|---|
| 1–5 s | 3 |
| 5–30 s | 16 |
| 30 s – 2 min | 1 |
| 2–10 min | 0 |

20 attempts reached the exchange. Every one was less than two minutes old at the moment it was sent.

## What this says

1. The replay did not send hundred-minute-old orders. It QUEUED them: 164 of 221 attempts were
   2–10 minutes stale and were still `pending_send` when the engine was stopped. The 58 positions
   came from 20 executions, 16 of them on fills 5–30 s old.
2. The queue was still growing when it was stopped (send_backlog 406 → 824), so the loss was capped
   by the stop, not by the design. Left alone, older buckets would have drained into the exchange.
3. Age was never the guard. The 30 s boundary is only the routing threshold into the missed-entry
   rule (Core:8050-8051); above it a fill gets a price test, not a refusal. That is ENG-017 by Boss's
   decision - "a trade at the same price, better, or within tolerance executes at once however late
   it is" (Core:8063-8064).
4. A queue-age cap would therefore be a genuinely independent backstop: refuse to act on a fill that
   has been sitting in the queue longer than N seconds, whatever its price. Nothing on the current
   path does that, and it is the one guard that would have bounded this incident by construction
   rather than by my hand on the stop.

## Caveat on the measurement

`order_intents.csv` carries no leader-fill timestamp column, so the age of a DECISION cannot be
bucketed from that file; only send attempts can. The intent-side counts in this report are therefore
absent rather than zero.
