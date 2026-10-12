# WS_FEED_STALE_FINDINGS_2026-10-12.md - why did WS_FEED_STALE block 34 entries in Q17 (read-only)

**Job**: `WS_FEED_STALE_SPEC.md`. **Model**: deepseek-flash (Hermes session, all parts; no worker - the only
reachable delegation route is the excluded config model). Read-only: the live engine was never restarted/touched,
the Wallet Finder was never touched, no orders, no WebSocket subscriptions opened by me, no keys/.env.

**Graphify**: fresh clone `hl-build3-hermes-WSFS`, `graphify update .` then `graphify query "write_health
worst_health_grade DEGRADED subscribe refusal socket reconnect WS_FEED_STALE"` - located `WSManager.write_health`
(L7411) and the entry-safety Gate 1 check (L10287-10290), which I then read directly to get the exact gate
condition quoted below.

## Overlap check (the coordinator's explicit ask): NO temporal overlap
Mainnet WS-quota exhaustion by the Wallet Finder copy engines: **13:14Z-15:08Z**. All 34 WS_FEED_STALE blocks
happened at **16:07:08.153Z-16:07:14.316Z** (11 unique reconciliation rows, 6.2 seconds wide; the classifier's
"34" counts merged-fill duplicates of the same 11 terminal rows). That is **~59 minutes after** the stated
mainnet-quota window closed. **No temporal overlap with the 13:14-15:08Z incident.**

**However** (item 4, "is any other process holding WS users NOW, names only, nothing changed"): right now,
`netstat -ano` shows PID **30984, `pythonw.exe -u HL_Copy_Engine_SSOT.py`** (confirmed via `Get-CimInstance
Win32_Process`) holding **9 ESTABLISHED connections to 216.137.44.122:443** (a Hyperliquid/Cloudflare edge IP) - a
Wallet Finder copy engine is **still running now**, hours after the stated 13:14-15:08Z window. I did not touch it.
This is a live, present-tense fact, not evidence about the Q17 window itself (no historical connection snapshot for
15:58-16:36Z exists on the PC), but it means the quota-contention risk the context describes has not gone away.

## Item 1 - what caused DEGRADED, for how long, at what times
`write_health()` (L7411-7462) grades DEGRADED from exactly 4 sources: (a) `refused` (subscriptions refused + fewer
subscribed than wallets), (b) `subscribe_pending` (socket open, no ack/message within 30 s), (c) socket not
open/thread dead, (d) `stale_count>0` (a subscribed wallet silent > 4 h). Gate 1 (L10289) ONLY blocks when
**`HL_LIVE_WS_ENABLED` env is truthy AND `worst_health_grade == DEGRADED`**.
- `errors.csv` 15:58-16:36Z: **5 rows**, all `follower_dex_missing` ("DEX 'io'/'para' ... does not exist on the
  follower network; not read") at 16:00:37Z and 16:07:07Z - unrelated to WS health.
- The engine's printed `run_cycle` state (`engine_33f8811_Q17-dex-scope_post.log`, 348 dumps across the whole
  post-outage run) shows `"ws_status": "WS_DISABLED"` in **every single one of the 348 dumps**, and
  `"entry_sends_blocked_reason"` is `WS_FEED_STALE` in exactly **1 of 348** - the very first dump written after the
  post-outage restart (matching the 16:07:08-16:07:14Z reconciliation timestamps).
- **This is an apparent contradiction worth flagging to the engine thread, not resolved here**: if `ws_status` is
  `WS_DISABLED` (meaning `self.enabled` is False) in every printed cycle including that first one, Gate 1's own
  condition (`HL_LIVE_WS_ENABLED` env truthy) should never have been true either, since both read the same env
  var. I cannot determine from these files alone whether the two reads genuinely disagreed for one cycle (a
  startup race) or whether `ws_status` in the printed summary is a one-cycle-stale value relative to the gate's own
  fresh `write_health()` call that cycle - a source-level timing question, not something `grep` settles.
- **ws_partial_feed, subscribe refusal text, reconnect, socket close, ping/pong gap**: none found in the engine
  logs or `errors.csv` for this window - **not found**, i.e. whatever drove the one DEGRADED cycle left no textual
  trace outside the `entry_sends_blocked_reason`/`terminal_state` fields themselves.
- **Total DEGRADED duration**: bounded tightly by the data - 1 of 348 ten-second cycles, i.e. **~10 s**, during
  which 11 entries were evaluated and blocked (and classified as 34 after merge-expansion).

## Item 2 - per-entry detail (11 unique terminal rows; "34" = merge-expanded count)
| time | coin | side | block |
|---|---|---|---|
| 16:07:08.153Z | NEAR | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:09.197Z | NEAR | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:10.145Z | XPL | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:11.436Z | XPL | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:12.182Z | SOL | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:12.211Z | XPL | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:13.545Z | LIT | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:13.571Z | AERO | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:14.163Z | SOL | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:14.172Z | LIT | - | ENTRY_BLOCKED_WS_FEED_STALE |
| 16:07:14.315Z | AERO | - | ENTRY_BLOCKED_WS_FEED_STALE |
`side` not carried in `reconciliation.csv`'s own columns for this terminal type (only in the `notes` text, e.g.
"side=BUY"); leader fill time is not separately recorded in these rows - **not found** beyond the block timestamp
itself. "WS state at that moment (acked count, refusals, socket_open)" - **not found**: no historical
`live_ws_health.json` snapshot survives from 16:07Z (it is a single overwritten file, now at 17:04:53Z/now).

## Item 3 - acked wallets, resubscribe, time to full feed
**Not found.** `ws_status: WS_DISABLED` in every printed cycle means `self.enabled` was False for this entire run
(per `write_health`'s own branch `not self.enabled -> "WS_DISABLED"/"DISABLED"`) - there is no `subscribe_acked`
count, no refusal text, and no resubscribe event anywhere in this run's logs to measure against. If WS truly never
enabled, "time from first refusal to full feed" does not apply; the one blocked cycle is the open question in Item 1.

## Item 5 - did the grade flip during the restart itself?
**Yes, and precisely located**: the single DEGRADED/`WS_FEED_STALE` cycle is the FIRST post-outage-restart state
dump (outage ran 16:01:08Z-16:06:08Z per `QUEUE_LOG.md`; the blocked entries land at 16:07:08-16:07:14Z, i.e.
60-66 s after the outage's stated end) - consistent with "socket reopened, wait for acks" happening once, briefly,
right after the restart, then clearing for the remaining 347 cycles. "Time from process start to all 10 acked" -
**not found** (no acked-count field ever shows non-WS_DISABLED in this log).

## Bottom line
The 34 WS_FEED_STALE blocks are real but tiny in scope (11 unique entries, 6.2 s, right after the post-outage
restart) and have **no temporal overlap** with the 13:14-15:08Z mainnet WS-quota exhaustion - that incident had
ended nearly an hour before Q17's restart. What IS still true right now: a Wallet Finder copy engine
(`pythonw.exe -u HL_Copy_Engine_SSOT.py`, PID 30984) is holding 9 live mainnet WS connections at this moment,
untouched per the rules, so the underlying contention risk the context describes is not resolved, even though it
did not cause Q17's specific block.
