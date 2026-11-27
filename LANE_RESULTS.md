# Lane F: G4 latency fix

## Revision

- Starting HEAD: `2f783e40410dc85969e44a80b2aef712cdeef124` (`lane-f/g4-latency-fix`).
- New commit SHA: none. `git` could not run in this sandbox (`Access is denied`); no commit was created.
- Changed files: `LANE_RESULTS.md` only. No scratch data or protected files were changed.

## Stage breakdown

The requested 43 archived rows and 8 bench rows are absent from this checkout. The only relevant CSV is the uncommitted read-only copy `_scratch_latency/r3c_state_send_attempts.csv` (939 rows, 2026-11-09 r3c run). The coordinator supplied these percentiles from that source:

| Stage | Timestamp interval | n | p50 | p95 | max |
|---|---|---:|---:|---:|---:|
| Websocket receive to intent creation (decision/sizing) | `ws_received_ms` -> `intent_created_at_ms` | 591 | 801 ms | 50,622 ms | 76,961 ms |
| Intent creation through pre-send work to real send start | `intent_created_at_ms` -> `send_real_started_ms` | 515 | 45 ms | 231 ms | unavailable |
| Websocket receive to real send start (overall engine path) | `ws_received_ms` -> `send_real_started_ms` | 465 | 740 ms | 1,810 ms | unavailable |
| Pre-send checks only | `send_decision_started_ms` -> `send_real_started_ms` | unavailable | unavailable | unavailable | unavailable |
| Exchange call through recorded finish/ack | `exchange_call_started_ms` -> `exchange_call_finished_ms` | unavailable | unavailable | unavailable | unavailable |

The available aggregate intervals are not a fully additive per-stage breakdown: they use different row counts, and the coordinator did not provide pre-send-only or exchange-call percentiles. I have not inferred those values. The largest observed tail is before intent creation: p95 50.622 s, versus 231 ms from intent creation to send start. The tail is therefore in the engine's pre-intent path, not the exchange round-trip.

## Investigation and change

The source path records queue and lock stamps separately. WS fills are dispatched to per-coin worker lanes, each worker plans up to 500 queued fills by default, and fill handling then acquires the shared `_send_lock` before building the intent. The supplied aggregate percentiles do not distinguish time spent queued, waiting for `_send_lock`, or in fill decision/sizing. The raw requested 43+8 rows that could provide that attribution were not present, and no stage-specific `enqueued_ms`, `picked_up_ms`, `process_started_ms`, `prewarm_done_ms`, or `lock_acquired_ms` percentile summary was supplied.

I did not change the engine or add a speculative tuning change: reducing the queue batch or changing worker concurrency would only help particular queue patterns and could affect same-coin ordering or throughput. The evidence available here identifies the pre-intent engine stage, but not the responsible substage needed to choose the smallest safe change. No safeguards, send modes, close handling, or sizing logic were changed.

## Tests

- No test was added because no code behavior was changed.
- Tests were not run; the instruction prohibited Python or other interpreter execution.
- No pass counts are claimed.

## Blockers

- **Requested measurement subset missing:** the 43 archived and 8 bench rows were not found in the checkout. Only the 2026-11-09 r3c aggregate figures above were available.
- **Root-cause split missing:** no supplied percentiles separate queue delay from shared-lock wait and sizing/decision time, so a targeted engine change could not be selected safely.
- **Commit unavailable:** the configured Git executable returned `Access is denied`. No new commit SHA exists.

No orders were sent. No restart, deploy, or push occurred. No keys, `.env`, `CONTROL_STATE.json`, WALLET FINDER 8014, scout 8012, or upstream walletproof engine were read or touched.

## Coordinator verification (2026-11-27)

HEAD: 2f783e40

Same commit as lane-e (2f783e40). Same results: latency unit 4/4 pass; bench 8/9, fill-to-send p95 2682ms vs 2000ms limit FAIL.
This branch was not on origin before this run; pushed on this run.

