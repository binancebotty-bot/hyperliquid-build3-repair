# STARTUP_PHASES_FINDINGS_2026-10-12.md - where do the ~9s per fill go (read-only, numbers only)

**Job**: `STARTUP_PHASES_SPEC.md`. **Model**: deepseek-flash (Hermes session, all parts; no worker - the only
reachable delegation route is the excluded config model). Read-only: the live Q14 soak engine was never restarted
or written to; no orders; no WebSocket subscriptions; no keys/.env opened.

**Graphify**: fresh clone `hl-build3-hermes-SPH`, `graphify update .` then `graphify query "STAGE_STAMP_KEYS
enqueued_ms picked_up_ms process_started_ms prewarm_done_ms lock_acquired_ms intent_written_ms"`, confirmed by
`search_files` for `STAGE_STAMP_KEYS`/`stamp_fill(`. This is how the structural finding below was reached, not a
guess: `stamp_fill()` is called from the general fill-processing path (`_process_leader_fill`/dispatch, L8624-9352)
on EVERY fill, but those stamps only get COPIED into a `send_attempts.csv` row inside `SenderGateway._base_timing`
(L5029-5043) - which is only reached if `send_if_allowed` passes its FIRST check, `intent.send_allowed`. For a fill
whose status is `INTENT_NOT_SEND_ALLOWED` (round 1's dominant ~9s bucket, 2,389-3,279 of them per window), that
check fails immediately and `_base_timing` - hence `_begin_pending_send`, hence any `send_attempts.csv` row at
all - is **never reached**. The spec also names the wrong file (`order_intents.csv`); the six stamp columns are
on `send_attempts.csv` - confirmed by header inspection, noted so the next job doesn't repeat the lookup.

## Items 1-3: structurally "not found" for Q12/Q13 - and why, with evidence
`send_attempts.csv`'s **last row is 2026-10-12T01:50:13Z** - hours before BOTH restarts (Q12 08:36:44Z, Q13
09:01:30Z). Zero rows of ANY kind exist in either 25-minute window, not just zero with all 6 stamps. This is not a
data-collection gap, it is a structural consequence of the file's own write condition plus the fact (confirmed in
`QUEUE_LOG.md`) that **both Q12 and Q13 FAILED and the runner called `set_arm(False, ...)` immediately** -
`master_real_orders_enabled` was OFF for the whole of both windows, so every fill in them hit `INTENT_NOT_SEND_ALLOWED`
and never reached the code path that writes a `send_attempts.csv` row. Items 1 (stage-interval p50/p90/max), 2
(intents-per-minute written) and 3 (distinct coins/wallets, shared-read share) are therefore **not found** - there
is no populated row to compute them from, for either restart, by design of the engine's own instrumentation.

| restart | send_attempts rows in window | rows with all 6 stamps | p50/p90/max per stage | intents/min written | distinct coins/wallets |
|---|---|---|---|---|---|
| Q12 (08:36:44Z) | 0 | 0 | not found | not found | not found |
| Q13 (09:01:30Z) | 0 | 0 | not found | not found | not found |

## Item 4 - 429 / rate-limit / throttle mentions
Zero genuine hits in either window, in BOTH engine logs (`engine_2f25e09_Q12-newmain.log`,
`engine_2f25e09_Q13-soak.log`) and in `errors.csv`/`reconciliation.csv` notes. **Correction worth recording**: a
first-pass regex (`429|rate.?limit|throttl|too many`) matched 103 (Q12) / 112 (Q13) reconciliation rows - every one
was the literal digits "429" occurring INSIDE a leader-fill hex hash (e.g. `...429f742c0446...`), not an HTTP 429.
Re-run with word-anchored terms (`rate.?limit`, `throttl`, `too many requests`, `HTTP 429\b`): **0 hits** in both
windows. The engine was not being rate-limited during either restart.

## Item 5 - REPLAY_DEFERRED_TRUTH_UNREADABLE notes, grouped (reconciliation.csv, first 80 chars)
This instrumentation IS populated (reconciliation rows are written regardless of send permission). Counts differ
from round 1's `fill_trace.jsonl` figures (183/245) because `reconciliation.csv` logs a row per STATE TRANSITION,
not once per fill - a single fill can appear in `FILL_PENDING_QUEUED` repeatedly across polls before its terminal
row; the two files measure different units and are not expected to match.

| restart | REPLAY_DEFERRED_TRUTH_UNREADABLE rows (25 min) | dominant note (first 80 chars) | count |
|---|---|---|---|
| Q12 | 2,449 | "entry held, not lost: follower exposure unavailable (SCOPE_UNAVAILABLE); entries" | 153 |
| Q12 | (same) | "merged_into=<hash>; held with its head fill..." (38 distinct head hashes, ~38 each) | ~38 x many |
| Q13 | 1,931 | "entry held, not lost: follower exposure unavailable (SCOPE_UNAVAILABLE); entries" | 138 |
| Q13 | (same) | "merged_into=<hash>; held with its head fill..." (38 distinct head hashes, ~38 each) | ~38 x many |

**New signal vs round 1**: `SCOPE_UNAVAILABLE` (follower exposure unavailable) appears **153/138 times** in these
notes, in BOTH windows - round 1's engine-log grep for this term found 0 because it only appears in the audit CSV
`notes` field, never printed to stdout. It is not the dominant reason (the `merged_into` family of notes, i.e. fills
absorbed into an already-queued merged order, is larger in aggregate across the many distinct hashes), but it is a
real, previously-invisible contributor worth the engine thread's attention.

## Bottom line
The spec's premise (stage-stamp breakdown of the ~9s delay) cannot be answered for Q12/Q13 because those 9-second
fills are, by the engine's own code, exactly the ones that NEVER get a `send_attempts.csv` row - `fill_trace.jsonl`'s
coarser `proc_start`/`proc_end` pair (round 1) is the only instrumentation that covers them. What IS newly visible
here: no rate-limiting anywhere (after correcting a hash-substring false positive), and a real, previously-missed
`SCOPE_UNAVAILABLE` contributor inside the deferred-retry population.
