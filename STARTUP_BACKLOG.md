# STARTUP_BACKLOG_FINDINGS_2026-10-12.md - why the hot backlog stays 40-280 after a restart (read-only)

**Job**: `STARTUP_BACKLOG_SPEC.md`. **Model**: deepseek-flash (Hermes session, all parts; no worker - the only
reachable delegation route is the excluded config model). Read-only: the running engine (a live soak test, Q13's
process) was never restarted, written to, or stopped; no orders; no WebSocket subscriptions; no keys/.env opened.

**Graphify**: fresh clone `hl-build3-hermes-SBL`, `graphify update .` then `graphify query "hot backlog send queue
leader fill dispatch proc_start proc_end intent_build"` and `"copy_poll_stats slowest_sections send_lock intent_build"`
- these located `_hot_send_loop`/`hot_backlog()` and `send_lock:intent_build` as the engine's own instrumented hot
path (same names that appear in `copy_poll_stats[*].slowest_sections` and `fill_trace.jsonl`, confirming the data
sources named in the spec are the engine's real instrumentation, not ad-hoc logging).

**Data coverage, stated plainly**: `fill_trace.jsonl` + `.old` only go back to **1791781493084** (12 Oct 03:58Z);
Q9's restart (03:38:24Z) is **before that - "not found"** for every fill_trace-based item below for Q9. `Q9` is
reported from `QUEUE_LOG.md` + its own engine log only. `copy_poll_stats` in `copy_poll_state.json` is a **rolling
60-entry buffer covering only the last ~4.5 minutes of wall time** (1791797608541-1791797880711) - it does **not**
reach back to ANY restart's first-25-min or minute-40+ window; item 3 is **"not found"** for all three restarts, the
current (live) slowest-section pattern is reported instead as the only available data point.

## Table

| restart | ready after | backlog at ready | 25-min poll_dispatched | 25-min proc_end | dominant proc duration (p50/p90/max ms, ENTRY/INTENT_NOT_SEND_ALLOWED) | REPLAY_DEFERRED (proc_end) | released_unaccepted | repeat-processed ids | error lines (/info, SCOPE_UNAVAILABLE, non-JSON, timeout) |
|---|---|---|---|---|---|---|---|---|---|
| Q9 (03:38:24Z, main 1da27e4) | 1086 s | 38 | not found (fill_trace rotated out) | not found | not found | not found | not found | not found | 0 (grepped engine_1da27e4_Q9-info-retry.log) |
| Q12 (08:36:44Z, main 2f25e09) | FAILED (20 min, backlog 282) | - | **6,244** | 2,770 | n=2,389, p50=9,618, p90=31,336, max=79,203 | 183 | 43 | 124 ids re-started (152 extra starts) | 0 |
| Q13 (09:01:30Z, main 2f25e09, **live soak**) | FAILED test item (20 min, backlog 202), engine kept running as the soak | - | **2,822** | 3,846 | n=3,279, p50=8,818, p90=21,944, max=93,228 | 245 | 54 | 115 ids re-started (216 extra starts) | 0 |

## Five sentences, dominant cause named

1. **Arrival is a burst, not a steady stream**: Q12's 6,244 poll_dispatched events land almost entirely in minutes
   1-5 (1,078/1,811/1,268/1,124/830 per minute), Q13's 2,822 land almost entirely in **minute 1 alone (2,618)** -
   the restart's leader-poll catch-up dumps the whole missed window in one or two polls, then goes quiet.
2. **Per-fill processing is itself slow, not just outpaced**: the dominant bucket (`ENTRY`/`INTENT_NOT_SEND_ALLOWED`,
   2,389-3,279 fills) has **p50 = 8.8-9.6 seconds** per fill (p90 21-31 s, max 79-93 s) measured proc_start-to-proc_end
   - at that rate even 12 hot-send workers clear only a few hundred fills per minute, so a burst of 1,000+/minute
   cannot drain in the same minute it arrives.
3. **The backlog is real deferral cycling, not just a queue depth number**: 183-245 fills end a cycle with
   `REPLAY_DEFERRED_TRUTH_UNREADABLE` in 25 minutes, 43-54 more are `released_unaccepted`, and **115-124 distinct
   leader-fill ids are started more than once** (152-216 extra starts) inside the same 25-minute window - the same
   fills are genuinely re-entering the queue via the deferred retry, not merely waiting once.
4. **The dominant cause is the combination, named precisely**: a burst arrival (minute 1-2) that is several times
   larger than what the measured per-fill latency can clear, which then produces deferral-retry cycling for the
   fills still unresolved when the backlog threshold logic revisits them - "slow per-fill reads" (sentence 2) is
   the mechanism, "arrival burst" (sentence 1) is why it matters, and "deferral cycling" (sentence 3) is the
   secondary amplifier once the backlog is already large.
5. **It is not an error-driven slowdown**: zero lines across `Q9`/`Q12`/`Q13` engine logs match `/info`,
   `SCOPE_UNAVAILABLE`, non-JSON/`JSONDecodeError`, or `timeout`/`timed out` - nothing here is retrying because of a
   network or parse failure; the cost is intrinsic to building an intent per fill (`send_lock:intent_build` is also
   the single largest `slowest_sections` entry in the only copy_poll_stats data available, the current live tail).

## Honest limits
- Q9's per-fill/per-minute numbers are **not found** (fill_trace.jsonl had already rotated past that restart by the
  time this job ran) - only its QUEUE_LOG summary (ready 1086 s, backlog 38) is available.
- `copy_poll_stats`'s rolling 60-entry buffer could not be read historically for Q9/Q12/Q13's first-25-min or
  post-minute-40 windows - **not found** for item 3 as specified; only the CURRENT slowest-section snapshot is
  reported (and it agrees with `fill_trace`'s finding: `send_lock:intent_build` dominates `total_ms`).
- The negative-looking p50 values seen for `REPLAY_DEFERRED_TRUTH_UNREADABLE`/`STALE_WS_SNAPSHOT_IGNORED` in a first
  pass were a measurement artifact of pairing `proc_start`/`proc_end` by id when an id has MULTIPLE pairs (exactly
  the cycling in sentence 3) - excluded from the reported duration stats, which use only the dominant, unambiguous
  `ENTRY`/`INTENT_NOT_SEND_ALLOWED` bucket.
