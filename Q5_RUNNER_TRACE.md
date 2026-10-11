# Q5_RUNNER_TRACE.md - runner patch (proposed) + Q4 catch-up timing (read-only)

**Job**: `Q5_RUNNER_TRACE_SPEC.md`. **Model**: deepseek-flash (Hermes session, all parts; no worker - the only
reachable delegation route is the excluded config model). **Nothing on the PC was touched**: the running runner
(`run5/test_queue_runner.py`, currently mid-Q5-block-reasons), the engine, and `hl-build3-testnet-cert` were never
edited or restarted; everything below is a proposed patch file plus a read-only reading of existing evidence.

## Part 1 - proposed runner patch (NOT applied; `Q5_RUNNER_PATCH.diff`)
`run5/test_queue_runner.py` lives in the local evidence tree (`hl-build3-testnet-cert-evidence`), which **is not a
git repository** (`git status` there: "fatal: not a git repository") - it cannot be committed here. The patch is
included as a plain unified diff, `Q5_RUNNER_PATCH.diff`, for whoever next edits the live file to apply by hand.
Two changes, both inside `window_ids()` and the `outage` step of `run_item()`:
1. `window_ids(t0, t1, item_id=None)` now also builds `{hash: {wallet, coin, time, side}}` and, when an
   `item_id` is passed, writes it to `run5/results/<id>.window.json` - exactly what Q4_IDS had to reconstruct itself
   by re-querying mainnet after the fact.
2. The `outage` step writes the classifier's FULL stdout to `run5/results/<id>.classifier.txt` (never truncated),
   and the issue-#3 body gets a `MISSING=N` header plus the first 40 lines instead of the last-6000-chars slice
   that cut the posted comment to "... 45 more" - which is exactly the gap Q4_IDS had to work around.

## Part 2 - leader_poll_trace.jsonl (main 08a7875)
**Absent**, and explained, not guessed: the Q4 outage's restarted engine process (`started_at 2026-10-11T17:17:52Z`,
read from `clean_core_runtime_state.json`) predates `9987e40`/`08a7875` ("leader_poll_trace.jsonl records every
leader poll"), so that build was never running when Q4 happened. The trace file will only start existing after the
**next** `pull`+`restart` queue step, which is the runner's own job, not mine. `find` confirms
`hl_live_copy_audit_testnet/leader_poll_trace.jsonl` does not exist on the PC today.

## Part 3 - what the PC's EXISTING evidence says about the Q4 catch-up (numbers, no guesses)
No per-poll trace survives from that commit, so the exact `startTime`/`endTime` the first leader poll asked for
after restart cannot be read directly. What IS measurable from `order_intents.csv` (append-only, never rewritten):

- Engine restarted **17:17:52.388Z**. The first POLL-sourced `order_intents` row for either LIVE leader lands at
  **17:18:13.927Z** (+21.5 s) - but that row is a **re-ingestion of a pre-outage fill already captured by WS at
  17:02:29Z** (same `leader_fill_id` twice, sources `WS_CAPTURED` then `POLL`) - not new catch-up.
- The first POLL row for a fill whose own timestamp is genuinely **inside** the outage window (17:12:21-17:17:51Z)
  lands at **17:18:21.8Z (+29.8 s after restart)**, for wallet `0xd4c1f7e8..` coin LINK. By 17:23:23Z, **11 of the
  428 window-id fills** (not 85 - this is window-wide, any wallet) got a POLL-sourced `order_intents` row at all.
- **None of the 85 never-ingested ids (`Q4_IDS.md`) are among those 11** - their coins (USELESS/AAVE/EIGEN/ONDO for
  `0x936cf4..`, BTC/XPL/ONDO/DOGE for `0xd4c1f7e8..`) never appear in a POLL-sourced row at any point up to now.
- **Did the first poll return the missing fills? No - not then, and not since.** Re-checking the full
  `send_attempts`/`reconciliation`/`order_intents` CSVs **now** (hours later) still shows zero rows for all 85 - the
  catch-up never recovered them, it is not merely delayed.
- `errors.csv`: **0 rows** in 17:17:52-17:44:00Z - no exception was logged for this window; the loss is silent, not
  a crash.

## Bottom line
The runner's own classifier output is too thin to answer "what did the first poll ask for" (hence the Part-1 patch);
what the audit CSVs DO show is that catch-up partially worked for a small, unrelated subset of window fills and
never touched the 85 that `Q4_IDS.md` already identified as LIVE-leader losses - consistent with (not contradicting)
that finding's root cause.
