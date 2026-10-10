# Testnet run 5 — findings (interim, 2026-10-10 06:20Z)

Same 10 leaders, limits and follower as run 4 (fixed $12, max order $50, per-wallet/per-asset $300, total $1,200,
daily loss $1,000, 0.2 %). Same state folder as run 4 (ledger stamped testnet). Slippage not meaningful on testnet.

## Timeline (UTC)
- 22:47 restart on e51e047 (run-4 fixes). With sending off it withdrew 185 resting entry limits, kept 1 reduce-only exit.
- 03:39 ledger repair on 7894343 (records only, no orders): dry run → 22 coins to repair, 1 refused (RESOLV: "an unowned
  fill is not from an order this engine placed"), all 80 exchange positions explained; applied 22/22 verified.
  After restart ledger = exchange on every coin except RESOLV (stale +1, known refusal). Files: repair_dryrun.json,
  repair_applied.json.
- 03:40:49 armed. Watchdog stops: 03:42:13 (my checker raced the send-row write — rule now needs 2 checks);
  04:17:07 VVV ledger lag ~90 s (settled with sending off; rule widened to ~150 s).
- Restarts onto fixes (sending off for each, re-armed after first pass, ledger MATCH each time):
  8946636 copy-poll lag fix (04:35–04:40), 5c6bf0c send-lock fix (04:59–05:06), cff92fa file-lock fix (05:28–06:14;
  first pass + backlog drain took ~40 min with sending off).

## Measurements (run5/metrics.jsonl, watch_log.txt)
Leader→send latency (all sends; every one is over 0.5 s):
| hour | sends | lead p50 | lead p90 | queue p50 | exchange call p50 |
|---|---|---|---|---|---|
| 03h | 668 | 36 s | 134 s | 34 s | 0.97 s |
| 04h | 1,849 | 126 s | 502 s | 124 s | 0.97 s |
| 05h | 385 | 775 s | 1,159 s | 773 s | 0.97 s |
Queue wait is almost the whole delay; the exchange call itself is ~1 s. **Latency is still far from the 0.5 s target.**

Copy-poll (fill → ledger): before 8946636 ~90 s; on 8946636 median 1.9–15 s, max 26 s, lock_wait up to 8.4 s;
on 5c6bf0c median 0.7–15.6 s, send_lock_hold_ms_max up to 7.5 s (file work under the shared lock — fixed in cff92fa,
being measured now). http_ms ~0.6–1.3 s, no failed reads.

Exposure vs caps (exchange): gross notional $2,434–$3,127 vs $1,200 total cap (positions carried from run 4; new entries
are blocked by the cap, which is correct, but exits have not brought it under). Largest position $550 (ETH) at start,
now CASHCAT $308 vs $300 per-asset cap. Resting entry orders: 0–14 (run 4: 160–186) — fixed.
Dust (positions under $10): 4–10 at each sample.
Accounting: every exchange order traced to an engine send or an audited recovery order; ledger = exchange apart from
RESOLV and transient settle lag.

## Open
L1 Leader→send latency (queue wait) still minutes; target 0.5 s.
L2 Total exposure stays ~2.3× the cap from inherited positions; per-asset cap slightly exceeded (CASHCAT).
L3 Dust persists (4–10 positions under $10).
L4 RESOLV ledger +1 stale (repair refused it; needs a manual ruling).
L5 Restart-to-ready took ~40 min on cff92fa (backlog drained slowly with sending off).
