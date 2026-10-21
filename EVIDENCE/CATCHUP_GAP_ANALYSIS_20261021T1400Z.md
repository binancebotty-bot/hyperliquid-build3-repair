# Catch-up gap analysis - window 2026-10-21 12:56:00Z to 13:15:00Z

Read-only measurement (kanban t_5e019832, answers audit question 3 of directive 6316983782).
No product code edited, engine not started/stopped, no orders, no keys, no exchange writes.
Only public POST https://api.hyperliquid.xyz/info reads.

Window: W0=1792587360000 (12:56:00Z), W1=1792588500000 (13:15:00Z)
State dir: C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run6/state_572517_20261020
Probe: C:/Users/wigmore/.hermes/cache/scratch/catchup_gap_probe.py
Matcher: C:/Users/wigmore/.hermes/cache/scratch/gap_match.py
Follower: 0x7AE3B08bb4E7B085C6db5D635b96Bec9715e9205
LIVE set: 10 wallets in live_config.json with enabled=true AND mode=LIVE

## 1. Was the window polled?

leader_poll_trace.jsonl rows overlapping the window (end_ms>=W0, start_ms<=W1):

    0x20ad9884 POLL_OK 0 0
    0x21ca9810 POLL_OK 0 0
    0x46926d8f POLL_OK 122 58
    0x7717a7a2 POLL_OK 14029 3659
    0x77eeda19 POLL_OK 0 0
    0x8455193b POLL_OK 0 0
    0x92bbd811 POLL_OK 111 59
    0xbee0000c POLL_OK 161 78
    0xd4c1f7e8 POLL_OK 19201 3050
    0xfe7ce058 POLL_OK 4119 1822
    (second wave, all 10 again POLL_OK ending 1792591140189)

All 10 LIVE wallets polled POLL_OK. The gap is NOT 'not polled'.

fill_trace.jsonl rows with t inside the window: 180 - poll_dispatched 93, batch_drained 34,
proc_start/proc_end/lane_finished 10 each, batch_joined 9, released_unaccepted 2.
ZERO catchup_net_zero rows inside the window (first such row is ts=1792591519001, ~50 min later).

## 2. Leader fills in window vs rows produced

Public userFillsByTime, per LIVE wallet, 843 leader fills total:

    wallet      coin        leader   intent   attempt   copyfill   NO ROW
    0x46926d8f  NIL              2        1         1          0        1
    0x92bbd811  ZEC             18        2         0          0       16
    0x92bbd811  NEAR             6        0         0          0        6
    0x92bbd811  CRV             11        1         0          0       10
    0x92bbd811  HBAR             5        0         0          0        5
    0xbee0000c  WLD             11        4         4          1        7
    0xbee0000c  ONDO            11        0         0          0       11
    0xbee0000c  PUMP             3        0         0          0        3
    0xbee0000c  JUP              1        0         0          0        1
    0xd4c1f7e8  XPL            134        1         1          0      133
    0xd4c1f7e8  NEAR           133        0         0          0      133
    0xd4c1f7e8  ETH             49        1         0          0       48
    0xd4c1f7e8  LTC             12        0         0          0       12
    0xd4c1f7e8  SOL             21        0         0          0       21
    0xd4c1f7e8  BNB             21        0         0          0       21
    0xd4c1f7e8  MON              4        0         0          0        4
    0xd4c1f7e8  ZEC              4        1         0          0        3
    0xd4c1f7e8  ONDO             5        1         0          0        4
    0xd4c1f7e8  LIT              1        0         0          0        1
    0xfe7ce058  NEAR           335        1         1          0      334
    0xfe7ce058  ETH             55        2         2          1       53
    0xfe7ce058  xyz:DELL         1        1         0          0        0
    TOTAL                      843       16         9          2      827

Decisions on the 16 that got a row: ENTRY_ALLOWED 12, SEND_BLOCKED_RISK 1 (0x92bbd811 CRV),
SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION 3 (0xd4c1f7e8 ZEC, 0xd4c1f7e8 xyz:DELL, 0xfe7ce058 xyz:DELL).
Of the 9 attempts: ORDER_FILLED 2, ORDER_REJECTED 5, pending_send 2 (never terminalized).

ANSWER: 827 of 843 leader fills (98.1%) left NO ROW AT ALL - not blocked, not rejected,
no intent, no attempt, no fill, no trace row naming them.

## 3. Net position missing per wallet/coin

Follower userFillsByTime for the same window: 0 fills (two independent reads).
live_fills.csv filtered to the window: exactly 1 row (0xbee0000c WLD SELL 8.0).

    wallet      coin      leader net szi    follower   MISSING net szi
    0x46926d8f  NIL        -347982.0              0      -347982.0
    0x92bbd811  ZEC             -6.79             0           -6.79
    0x92bbd811  NEAR            -456.0            0         -456.0
    0x92bbd811  CRV            -7443.6            0        -7443.6
    0x92bbd811  HBAR          +9341.0             0        +9341.0
    0xbee0000c  WLD          -12327.0             0       -12327.0
    0xbee0000c  ONDO         -13605.0             0       -13605.0
    0xbee0000c  PUMP        -184962.0             0      -184962.0
    0xbee0000c  JUP             -221.0            0         -221.0
    0xd4c1f7e8  XPL         -442610.0             0      -442610.0
    0xd4c1f7e8  NEAR         -10949.0             0       -10949.0
    0xd4c1f7e8  ETH           -27.6101           0        -27.6101
    0xd4c1f7e8  LTC           -63.5              0          -63.5
    0xd4c1f7e8  SOL          -121.9              0         -121.9
    0xd4c1f7e8  BNB           -20.02             0          -20.02
    0xd4c1f7e8  MON        -22070.0              0       -22070.0
    0xd4c1f7e8  ZEC            +0.56             0           +0.56
    0xd4c1f7e8  ONDO        -4500.0              0        -4500.0
    0xd4c1f7e8  LIT          -294.0              0         -294.0
    0xfe7ce058  NEAR       -67938.7              0       -67938.7
    0xfe7ce058  ETH         -316.3382           0       -316.3382
    0xfe7ce058  xyz:DELL     -10.0              0          -10.0

These are WINDOW DELTAS, not portfolio divergence. A before/after follower clearinghouseState
snapshot pair was not captured at window start and cannot be reconstructed: cumulative
divergence is UNPROVEN. Proven: follower traded zero, leaders netted the above.
The one copy fill (8.0 WLD) is 0.06% of that wallet's -12327 WLD move.

## 4. Where the rows are lost (named functions)

Path located via Graphify (graphify-out/graph.json, _archive/hl_stage2/HL_Live_Copy_Service_Core.py):

- Every leader fill id must pass DedupeStore.accept_leader. A fill seen by the poller but
  absent from order_intents.csv was consumed (or dropped) upstream of intent creation.
- The observed sink for consumed-but-not-traded ids in this build is catchup_net_zero
  (fill_trace.jsonl, card t_658c32d9): leader opened and closed between polls, net zero,
  persist a terminal state.
- In this window there were ZERO catchup_net_zero rows and 827 fills with no row of any kind.
  The t_658c32d9 sink was not yet covering this window: fills were consumed and silently
  dropped, not recorded.
- Secondary hole: 2 of 9 attempts remain pending_send (0x46926d8f NIL, 0xd4c1f7e8 XPL) -
  a send that never terminalizes is equally unauditable.

## 5. Not-polled vs polled-but-blocked

- 0x20ad9884, 0x21ca9810, 0x77eeda19, 0x8455193b: polled, zero fills. No gap.
- 0x46926d8f, 0x92bbd811, 0xbee0000c, 0xd4c1f7e8, 0xfe7ce058: polled, fills seen, rows missing.
- 0x7717a7a2: poller reports 13087-14029 fills, public endpoint returns 0 for the window.
  UNPROVEN which is wrong. Most likely the poller 'fills' counter is a cumulative/full-history
  count (earliest trace rows show cursor_in=0), i.e. a trace units mismatch, not 13k missed
  fills. Settling it needs the raw /info body the poller received, which is not persisted.
- The STARTUP_ORPHAN_CHECK_PENDING / INTENT_NOT_SEND_ALLOWED state (t_da0a30aa) explains refused
  sends, NOT missing intent rows: a refused send still writes a decision row. Only 3 fills here
  carry a refusal-style decision. The other 827 have no row, so the startup gate is not the
  explanation for this window's gap.

## 6. What would settle the remainder

1. Persist raw userFillsByTime responses (or per-poll fill ids) to reconcile poller vs public
   counts - closes the 0x7717a7a2 13k-vs-0 discrepancy.
2. A follower clearinghouseState snapshot pair (window start and end) to convert 'missing net szi'
   into 'missing vs leader-equity-normalised target'. Not reconstructable now.
3. A later window proving catchup_net_zero actually fires for this pattern - in this window it
   did not exist, so it cannot be credited here.

## Verdict

All 10 LIVE wallets polled cleanly; leaders produced 843 fills; the copy produced 1 fill; and
827 leader fills (98.1%) left no audit row of any kind. The gap sits downstream of polling and
upstream of intent creation - exactly where the catchup_net_zero terminal state was later added,
which had zero rows in this window.
