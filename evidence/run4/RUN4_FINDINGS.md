# Testnet run 4 — findings (2026-10-09)

Code: main @ 3c03099 (PR #10 missed-entry rule + sender-key stop; PR #11 run-3 fixes + mainnet guards).
10 most active mainnet leaders → testnet follower 0x7AE3…9205. Limits: fixed $12, max order $50, per-wallet $300,
per-asset $300, total $1,200, daily loss $1,000, slippage 0.2 %. Start balance 1,449.21 USDC (testnet flat on all 269 DEXes).
Slippage/price quality: **not meaningful on testnet** (illiquid books) — to be proven on mainnet. Testnet judges latency and accounting.

## Timeline (UTC)
- 17:59:16 fresh state folder; 18:01:30 sending armed. 18:04–18:05 brief disarm to inspect (ORDI close, settle lag).
- 18:05:40–18:19:22 15-min watchdog run; auto-disarmed on a GRASS netting exit misread by my checker (not an engine fault).
- 18:59:16 engine + screen restarted on Boss's request (same code, same state folder, sending on) and left running.
- 22:13:20 DISARMED by the agreed watchdog rule (below). Engine + screen still running for data; no new orders after 22:13:55.

## Proven (good)
- First 18 min: 659 sends, 414 filled; every exchange order id traced to the engine; ledger matched exchange within 2–10 s
  (watchdog max mismatch streak 3 × 20 s, all cleared). First pass after start 30 s (run 3: 6 min); 7,683 pre-start fills skipped.
- Netting across leaders works and is shown per coin ("which leader holds what"). Sender key valid; network separation held.
- Exchange call itself ~1.0 s p50 / 1.7 s p99; send path 1.9 s p50.

## Failures (stop conditions)
R1 **Latency runs away.** Leader→send p50: first 5 min 21 s → 10–18 min 57 s → overnight hourly 58 → 65 → 93 → 99 min
   (p90 113 min); send_backlog 99,906 at 22:11. Whole delay is queue wait. Copies of 1–2 h-old trades are not copies.
R2 **Caps breached.** Exchange gross notional $3,161 vs $1,200 total cap; one position $548 vs $300 per-asset cap;
   plus 186 resting orders worth $2,256 not counted in exposure. Missed-entry GTC limits fill later outside the cap check.
R3 **Missed-entry limits flood the book.** 3,885 of 5,476 sends since 18:59 were GTC missed-entry limits; 160–186 open.
   (Boss: illiquid testnet makes many sit; but they also bypass caps and age.)
R4 **Exit-recovery fills are not ledgered.** Recovery reduce-only standing limits (EXIT_RECOVERY_QUEUED, 172) are not
   written to send_attempts; their fills come back COPY_FILL_UNMATCHED / NO_INTENT (e.g. NEAR oid 62286327364,
   AR oid 62290648144), so the ledger keeps positions the exchange has closed → ~24 persistent mismatches. Also
   EXIT_RECOVERY_QUEUE_FAILED 190, CLOSE_REJECTED_REDUCE_ONLY 258, PENDING_EXIT_GUARD/BLOCKED_SEND_UNCLASSIFIED 1,661
   — matches Boss's "positions don't fully close / dust".
R5 **Disarm is not immediate.** 33 orders were still sent 22:13:21–22:13:55 (already queued). On 3c03099 resting
   entry limits stay after disarm (fixed in f7ec737, not yet tested).
R6 **P&L doesn't tally (Boss).** Screen: portfolio $1,353.58, realized −$17.92, unrealized −$3.04, but start was
   $1,449.21 (−$95.6). Realized uses only "recent fetched fills" (250 of 5,314) and excludes fees/funding.
   Exchange day PnL −$97.

## UI review (screenshots in run4/ui_capture/)
Shown while the engine was healthy (18:20Z) — label, and whether it is a real fault:
- Header badge "REAL ORDERS: ON" and status card "MASTER REAL ORDERS: ON" while header also says "Real order sending: OFF"
  and live_config auto_send=false (22:15Z) — **conflicting/untrue**.
- "LIVE INTEGRITY: RED" with a run-on list of 10 internal codes (filled send awaiting copy poll within grace;
  missed entry/add terminal states present; send latency warnings present; ownership gate terminal blocks present;
  sends safely suppressed; exchange/manual mismatch…; service_created_unledgered_stale_resolved; hard_copy_active_red)
  — mostly normal transient states shown as RED; only the persistent mismatch was real.
- "restart required for WS subscription changes" always shown — informational, looks like a fault.
- Every wallet: "DD/MaxDD: UNKNOWN/NOT_PROVEN" (amber) and "R/U/Net: n/a" — **per-wallet P&L is not visible**; the
  only per-wallet money figure is "LEAD↔COPY DIFF Total $x" (slippage vs leader), which reads like P&L but is not.
- "Shared coin" red pill on 8/10 wallets — normal under netting, shown as a warning.
- "N recent rejects" (red) / "N recent blocks" (amber) per wallet — mostly cap blocks and illiquid IOC no-match; normal.
- Last reject card: "IOC_NO_IMMEDIATE_MATCH / EXIT_RECOVERY_REQUIRED" red — illiquid testnet; recovery is real.
- Account-level/orphan table lists every netted coin as "USER_MANAGED NOT ENGINE OWNED / NO OWNED SLEEVE" — wrong for
  shared sleeves the engine does own; alarming.
- Default open: status cards, Real Account, Live Account/Wallet PnL chart (Account), Live Copy Wallets table, and the
  "Real Copy Positions" tab (NET BY COIN + OWNED COPY POSITIONS + ACCOUNT-LEVEL/ORPHAN). Other tabs: Execution Quality,
  Order Intents / Audit, Reconciliation, WS Health.
- Boss: white border around the screen looks poor.
Per-wallet P&L today: not shown. Only account-level portfolio value, realized (partial) and unrealized.

## Evidence
run4/snapshot_20261009T2211Z (state + logs), run4/evidence_2215Z/exchange (openOrders, frontendOpenOrders,
clearinghouseState, spotClearinghouseState, userFunding, portfolio, 5,314 fills since run 4 start), watch_log.txt.
Engine start: `python HL_Live_Copy_Service_Core.py --ws --loop --interval 10 --poll-live --poll-copy` (env run_env.sh),
first start 17:59:16Z, restarted 18:59:16Z (PID 16176). GitHub evidence branch NOT pushed: the PC's safety check
blocked uploading state files (needs Boss's own approval).
