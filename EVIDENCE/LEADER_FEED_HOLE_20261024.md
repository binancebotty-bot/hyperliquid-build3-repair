# LEADER FEED HOLE TEST — 2026-10-24

Controller order 6389265751. Read-only: no engine start/stop, no port binding, no trades,
no config/roster/cap change, no source edit. No balances or keys recorded.

## Epoch window

- `startTime` = **1792859059000** = **2026-10-24T16:24:19Z** (as ordered)
- end = script run **2026-10-24T20:40Z** -> window ~**4h16m**
- Ground truth: `POST https://api.hyperliquid.xyz/info {"type":"userFillsByTime",...}` keyless, read-only,
  paged 2000/page until a short page (max 20 pages).
- Engine data: `run8/state_20261024/{leader_poll_trace.jsonl, fill_trace.jsonl, live_ws_health.json}`,
  `append_only/{order_intents.csv, send_attempts.csv}`.

## PART B — per-wallet table

`poll_new` = sum of `new` in `leader_poll_trace.jsonl` where `kind=="poll"` and `ts >= start`.
`fill_trace` = rows in `fill_trace.jsonl` with `t >= start`, keyed by 10-char `w`.

| wallet | exch fills (window) | exch notional USD | engine poll_new | fill_trace | intents | send attempts | verdict |
|---|---|---|---|---|---|---|---|
| 0x20ad9884 | 0 | 0.00 | 0 | 0 | 0 | 0 | IN_SYNC (quiet) |
| 0x21ca9810 | 16 | 971.79 | 2 | 0 | 2 | 2 | LOST_FILLS (poll 2 vs 16) |
| **0x46926d8f** | **0** | **0.00** | **0** | **0** | **0** | **0** | **IN_SYNC — no hole** |
| 0x7717a7a2 | 13,849 | 6,181,595.87 | 3,701 | 13,329 | 14,849 | 518 | OVER_COUNT (intents > exch) |
| **0x77eeda19** | **0** | **0.00** | **0** | **0** | **0** | **0** | **IN_SYNC — premise false** |
| 0x8455193b | 33 | 473,542.14 | 0 | 0 | 2 | 0 | LOST_FILLS (poll+fill_trace blind) |
| 0x92bbd811 | 11 | 1,600.10 | 0 | 0 | 6 | 0 | LOST_FILLS (poll+fill_trace blind) |
| 0xbee0000c | 34 | 24,275.35 | 0 | 28 | 20 | 4 | LOST_FILLS (poll 0) |
| 0xd4c1f7e8 | >=4,000 (429-capped) | >=3,678,361 | 2,107 | 6,118 | 5,601 | 144 | OVER_COUNT (fill_trace > exch) |
| 0xfe7ce058 | 119 | 17,869.42 | 4 | 5 | 74 | 0 | LOST_FILLS (poll 4 vs 119) |

24h context (`startTime`=1792772659000): 0x46926d8f **2,087** fills; 0x7717a7a2 13,851;
0x92bbd811 1,728; 0xbee0000c 1,026; 0x8455193b 1,015; 0x21ca9810 173; 0x20ad9884 171;
**0x77eeda19 0**.

### Finding on the two named wallets

- **0x46926d8f**: 2,087 fills in the last 24h, but **0 fills inside the 16:24:19Z->20:40Z window**.
  The engine saw 0 because the exchange had 0. Its ~1,228/day rate is carried by earlier hours.
  **No feed hole.**
- **0x77eeda19**: **0 fills in the entire last 24h**, so not "very active". Nothing to lose.
- Neither produced an intent because neither produced a fill in the window, not because the engine
  was deaf.

### Real defects found (different from the suspected cause)

1. `leader_poll_trace.new` **undercounts**: 0x8455193b/0x92bbd811/0xbee0000c/0xfe7ce058/0x21ca9810
   report 0–4 against 11–119 real fills. Not a usable fill counter.
2. `fill_trace` **over-records** on 0xd4c1f7e8: 6,118 rows against >=4,000 exchange fills ->
   replay/duplicate amplification.
3. `0x7717a7a2` intents 14,849 > exchange fills 13,849 -> one fill yields >1 intent in places
   (retry/supersede path).

## WS subscription list — suspected root cause REFUTED

Read from `live_ws_health.json`, field **`wallets`** (dict, key = address), corroborated by
`ws_summary` (written 2026-10-24T20:42:40.692661+00:00):
`ws_status=WS_OK, socket_open=True, thread_alive=True, subscribe_acked=10, subscribe_pending=False,
subscribe_refused=0, wallet_count=10, wallets_without_feed=0, total_reconnect_count=1,
resubscribe_attempts=0, last_subscribe_ms=1792869722210 (19:22:02Z), worst_health_grade=OK,
stale_count=0, message_errors=0, last_socket_error=fin=1 opcode=8 data=b'\x03\xe8Expired'`.

Subscribed (10, exactly the enabled LIVE set in `live_config.json`):
0x20ad9884…8183, 0x21ca9810…811d, 0x46926d8f…ef87, 0x7717a7a2…bd7e, 0x77eeda19…2902,
0x8455193b…974b, 0x92bbd811…9b6f, 0xbee0000c…fbca, 0xd4c1f7e8…3d1d, 0xfe7ce058…b7ae.

**No LIVE wallet is missing from the subscription list.** CLO-mode wallets are correctly absent.
`subscribe_acked=10 == wallet_count == LIVE roster`. The one `Expired` close was recovered
(reconnect=1, resubscribe_attempts=0, wallets_without_feed=0).
Caveat: current snapshot only (last subscribe 19:22:02Z); earlier subscription state is not retained.

## PART A — corrected bucketing (data-derived)

`reject_category` and `terminal_state` exist **only in `append_only/send_attempts.csv`** (668 rows).
`order_intents.csv` (132,862 rows) carries `decision`/`reason`, not those columns.

### Distinct `reject_category` (all attempts)
| value | count |
|---|---|
| `''` (empty) | 625 |
| `IOC_NO_IMMEDIATE_MATCH` | 26 |
| `MARKET_HALTED` | 17 |

### Distinct `terminal_state` (all attempts)
| value | count |
|---|---|
| `PENDING_SEND` | 334 |
| `FILLED_AWAITING_COPY_POLL` | 228 |
| `SUPERSEDED_BY_RETRY` | 30 |
| `ENTRY_LIMIT_RESTING_PRICE_MOVED` | 18 |
| `MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN` | 17 |
| `EXIT_RECOVERY_ACTIVE` | 15 |
| `EXIT_RECOVERY_REQUIRED` | 15 |
| `MISSED_ENTRY_IOC_NO_MATCH` | 11 |

### Distinct `decision` (`order_intents.csv`, 132,862 rows; 21,010 since window start)
| decision | count |
|---|---|
| `BLOCKED_CLO_ENTRY` | 94,666 |
| `SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION` | 24,278 |
| `ENTRY_ALLOWED` | 7,125 |
| `SEND_BLOCKED_RISK` | 6,639 |
| `EXIT_ALLOWED` | 84 |
| `NOT_APPLICABLE_SPOT` | 69 |
| `BLOCKED_SPOT_NOT_SUPPORTED` | 1 |

Top reasons: `CLO blocks entries/adds` 94,666; `no owned sleeve; leader close fill cannot open
reverse position` 24,278; `ENTRY` 6,193; `max wallet exposure exceeded` 4,008;
`no fresh follower-network (testnet) price to value the order` 2,507; `ADD` 926;
`max total exposure exceeded` 96; `EXIT` 84; UNOWNED_INVENTORY 10.

### Parity figure WITHDRAWN

**"1,419 of 1,469 red intents were liquidation parity" is withdrawn as unsupported.**
`LIQ_PARITY`, `OWNERSHIP_CONTRACT_BLOCK` and `NO_MANUAL_POSITION_TO_CLOSE` do **not appear at all**
as `reject_category` values in this dataset, and 1,469 is not reproducible from the 668-row
`send_attempts.csv`. Nothing here supports that figure.

Attempt-level exchange rejects in the whole file: **43** (26 `IOC_NO_IMMEDIATE_MATCH` + 17
`MARKET_HALTED`), all on 0x7717a7a2 (39) and 0xd4c1f7e8 (4).

### Re-classified as CORRECT_BEHAVIOUR (not BLOCKED)

`SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION` / `no owned sleeve; leader close fill cannot open reverse
position` — **24,278 rows = CORRECT_BEHAVIOUR**. This is the NO_MANUAL_POSITION_TO_CLOSE family
(leader close when we hold nothing). Per wallet: 0x7717a7a2 16,651; 0xd4c1f7e8 6,527;
0xfe7ce058 829; 0xbee0000c 156; 0x92bbd811 108; 0x8455193b 7.

`BLOCKED_CLO_ENTRY` (94,666) is a **configuration state** (`mode=CLO`), not a failure.

Corrected totals: 132,862 = 94,666 CONFIG_CLO + 24,278 CORRECT_BEHAVIOUR + 7,209 ALLOWED +
6,639 RISK_SUPPRESSED + 70 SPOT_NOT_APPLICABLE.

## Reproduce

`C:/Users/wigmore/.hermes/cache/scratch/leaderfeed_probe_20261024.py` (first pass),
`leaderfeed_probe2_20261024.py` (paged exchange truth + intents bucketing).
