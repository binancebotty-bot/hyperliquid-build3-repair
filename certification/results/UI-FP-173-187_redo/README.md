# UI-FP-173 .. UI-FP-187 - redo evidence (task t_1c4509ec)

Replaces the rejected presence-only evidence at 8e92a43. Each row is bound to the value it must show.

## What was run

An isolated copy of the dashboard per commit: its own HL_LIVE_AUDIT_DIR (fresh, empty),
its own port (8042 = 89b3bc75, 8043 = HEAD), leader mainnet / follower testnet, no engine,
no exchange connection, no order.

| tag | commit | HL_Copy_App_SSOT.py sha256 |
|---|---|---|
| c89 | 89b3bc7586bf328df336fc9ea721cee212617762 | 658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2 |
| head | 819050c6018ab3264cfe911f927e1f97ff0f979b | 4574ca72b0da4dc4aec101e6fa87b485a0e80abb99426a773957c26b5c173692 |

## UI-FP-173..179 (WS health detail)

live_ws_health.json with two wallets carrying different sentinel values (710170..710179,
DS178_*, LC179 *) was written to the isolated audit dir. Per row: (1) GET /api/live-ws-health
returns the file value; (2) the cell under that row's own <th> in #lcHealthRows shows that
exact value as text; (3) the neighbour wallet's row shows a different value (row-bound, not a
constant column).

| row | header | source field | API | DOM cell |
|---|---|---|---|---|
| UI-FP-173 | Snap recovered | snapshot_fill_recovered_count | 710173 | 710173 |
| UI-FP-174 | Ignored | ignored_snapshot_count | 710174 | 710174 |
| UI-FP-175 | Recent errors | recent_error_count | 710175 | 710175 |
| UI-FP-176 | Lifetime errors | lifetime_error_count | 710176 | 710176 |
| UI-FP-177 | Stale ms | stale_ms | 710177 | 710177 |
| UI-FP-178 | Data status | data_status | DS178_LIVE_OK | DS178_LIVE_OK |
| UI-FP-179 | Last close/error | last_close_msg | LC179 close sentinel | LC179 close sentinel |

## UI-FP-180..187 (controls)

Raw values are POSTed requiring normalisation (strings, padded/lowercase symbols, percent vs
bps). Checked: POST response, following GET, bytes in live_config.json, and the value rendered
back into the input.

| row | input | posted | stored/API | rendered |
|---|---|---|---|---|
| UI-FP-180 | gcMaxTotal | 12500.5 | 12500.5 | 12500.5 |
| UI-FP-181 | gcMaxDir | 2500 | 2500.0 | 2500 |
| UI-FP-182 | gcMaxWallet | 750.25 | 750.25 | 750.25 |
| UI-FP-183 | gcMaxOrder | "50.5" | 50.5 | 50.5 |
| UI-FP-184 | gcMktPct | 0.35 | marketable_bps 35.0 | 0.35 |
| UI-FP-185 | gcCloseAdv | "0.1200" | 0.12 | 0.12 |
| UI-FP-186 | gcAllowlist | ["btc"," eth ","Sol"] | ["BTC","ETH","SOL"] | BTC,ETH,SOL |
| UI-FP-187 | gcBlocklist | ["doge"," xrp"] | ["DOGE","XRP"] | DOGE,XRP |

## Negative controls (all pass on both commits)

- max_order_notional_usd -5 clamped to 0.0.
- live_ws_health.json deleted -> "WS service not running or no wallet health file found.", not zeros.
- live_ws_health.json = '{not json' -> same unavailable state, no traceback, no fabricated zeros.
- current_status=STALE, thread_alive=true -> Current cell "STALE / current idle", Stale ms still real.

## Defect in HEAD, outside the 15 rows - for lane triage, not fixed here

89b3bc75 kept control keys the form does not own (send_mode, follower_leverage, liq_parity);
its comment says dropping them "silently switched sending to the legacy root flag (OFF)".
HEAD 819050c deletes that pass-through. Measured on the isolated instance, seeded
{send_mode: CLOSE, follower_leverage: 7, liq_parity: true} plus one UI control save:
89b3bc75 preserved all three, HEAD dropped all three from live_config.json.
UI-FP-173..187 still PASS on both (they read only their own eight controls).
